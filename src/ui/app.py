import sys
import os
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtGui import QPalette, QColor
from ui.main_window import MainWindow

# Keep a global reference to the app to update styles later
_app_instance = None
_tooltip_filter = None


class ToolTipThemeFilter(QObject):
    """Event filter that ensures all QToolTip / QTipLabel windows strictly follow
    the application light/dark theme, preventing OS dark-mode conflicts on Windows 11."""
    def __init__(self, is_dark=False):
        super().__init__()
        self.is_dark = is_dark

    def set_dark(self, is_dark: bool):
        self.is_dark = is_dark

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Show and isinstance(watched, QLabel) and (watched.inherits("QTipLabel") or watched.objectName() == "qtooltip_label"):
            bg = QColor("#18181B") if self.is_dark else QColor("#FFFFFF")
            fg = QColor("#EDEDED") if self.is_dark else QColor("#09090B")
            pal = watched.palette()
            pal.setColor(QPalette.ToolTipBase, bg)
            pal.setColor(QPalette.ToolTipText, fg)
            pal.setColor(QPalette.Window, bg)
            pal.setColor(QPalette.WindowText, fg)
            watched.setPalette(pal)
            watched.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            watched.setAutoFillBackground(True)
            if sys.platform == "win32":
                try:
                    import ctypes
                    from ctypes import wintypes
                    hwnd = int(watched.winId())
                    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                    dark_val = wintypes.BOOL(self.is_dark)
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                        ctypes.byref(dark_val), ctypes.sizeof(dark_val)
                    )
                except Exception:
                    pass
        return super().eventFilter(watched, event)


def is_system_dark_mode() -> bool:
    """Detect the OS dark mode preference. Works on Windows, macOS, and Linux."""
    import platform
    system = platform.system()

    if system == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return value == 0  # 0 = dark mode, 1 = light mode
        except Exception:
            return False

    elif system == "Darwin":  # macOS
        try:
            import subprocess
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2
            )
            return result.stdout.strip().lower() == "dark"
        except Exception:
            return False

    else:  # Linux / other
        try:
            # Check GTK theme (works with GNOME, KDE Breeze-Dark, etc.)
            import subprocess
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                capture_output=True, text=True, timeout=2
            )
            return "dark" in result.stdout.strip().lower()
        except Exception:
            pass
        # Fallback: check XDG_CURRENT_DESKTOP / GTK_THEME env vars
        import os as _os
        gtk_theme = _os.environ.get("GTK_THEME", "").lower()
        return "dark" in gtk_theme


from resource_utils import get_resource_path


def apply_theme(is_dark=False):
    global _app_instance, _tooltip_filter
    if not _app_instance:
        from PySide6.QtWidgets import QApplication
        _app_instance = QApplication.instance()
    if not _app_instance:
        return

    if _tooltip_filter:
        _tooltip_filter.set_dark(is_dark)

    # Persist the preference to config
    try:
        from ui.views.settings_view import load_config, save_config
        cfg = load_config()
        cfg["dark_mode"] = is_dark
        save_config(cfg)
    except Exception:
        pass

    from PySide6.QtGui import QPalette, QColor
    from PySide6.QtWidgets import QToolTip

    bg_tip = QColor("#18181B") if is_dark else QColor("#FFFFFF")
    fg_tip = QColor("#EDEDED") if is_dark else QColor("#09090B")

    tip_palette = QPalette()
    tip_palette.setColor(QPalette.ToolTipBase, bg_tip)
    tip_palette.setColor(QPalette.ToolTipText, fg_tip)
    tip_palette.setColor(QPalette.Window, bg_tip)
    tip_palette.setColor(QPalette.WindowText, fg_tip)
    tip_palette.setColor(QPalette.Base, bg_tip)
    tip_palette.setColor(QPalette.Text, fg_tip)
    tip_palette.setColor(QPalette.Button, bg_tip)
    tip_palette.setColor(QPalette.ButtonText, fg_tip)
    QToolTip.setPalette(tip_palette)

    app_palette = _app_instance.palette()
    app_palette.setColor(QPalette.ToolTipBase, bg_tip)
    app_palette.setColor(QPalette.ToolTipText, fg_tip)
    if is_dark:
        app_palette.setColor(QPalette.Window, QColor("#09090B"))
        app_palette.setColor(QPalette.WindowText, QColor("#EDEDED"))
    else:
        app_palette.setColor(QPalette.Window, QColor("#FAFAFA"))
        app_palette.setColor(QPalette.WindowText, QColor("#09090B"))
    _app_instance.setPalette(app_palette)

    filename = "dark_style.qss" if is_dark else "style.qss"
    qss_path = get_resource_path(os.path.join("assets", "styles", filename))
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            qss_content = f.read()
            icons_dir = get_resource_path(os.path.join("assets", "icons")).replace("\\", "/")
            qss_content = qss_content.replace("@ICONS_DIR@", icons_dir)
            _app_instance.setStyleSheet(qss_content)
    # Re-apply QToolTip palette to guarantee it is retained after stylesheet application
    QToolTip.setPalette(tip_palette)


def launch_app(telegram_worker, version="unknown"):
    global _app_instance, _tooltip_filter
    QApplication.setStyle("Fusion")
    _app_instance = QApplication(sys.argv)

    from PySide6.QtGui import QIcon, QFont
    _app_instance.setFont(QFont("Segoe UI", 9))

    icon_path = get_resource_path(os.path.join("assets", "logo.ico"))
    if os.path.exists(icon_path):
        _app_instance.setWindowIcon(QIcon(icon_path))

    # Determine startup theme:
    #   1. Use saved preference from config.json (if explicitly set by user)
    #   2. Fall back to Windows system dark mode detection
    try:
        from ui.views.settings_view import load_config
        cfg = load_config()
        saved_pref = cfg.get("dark_mode", None)
    except Exception:
        saved_pref = None

    if saved_pref is not None:
        startup_dark = bool(saved_pref)
    else:
        startup_dark = is_system_dark_mode()

    _tooltip_filter = ToolTipThemeFilter(is_dark=startup_dark)
    _app_instance.installEventFilter(_tooltip_filter)

    apply_theme(is_dark=startup_dark)

    window = MainWindow(telegram_worker, version)
    window.show()

    # Start the worker thread
    telegram_worker.start()

    exit_code = _app_instance.exec()
    
    # Ensure worker stops before the thread object is destroyed by GC
    if telegram_worker.isRunning():
        telegram_worker.stop()
        # Increased wait time for clean asyncio shutdown
        if not telegram_worker.wait(3000):
            # If it still won't stop, we force quit it (less clean but avoids the error)
            telegram_worker.terminate()
            telegram_worker.wait()

    sys.exit(exit_code)

