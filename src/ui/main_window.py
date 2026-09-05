import os
import sys
import subprocess
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QStackedWidget, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QLineEdit, QScrollArea, QFrame,
    QMessageBox, QToolButton, QSizePolicy, QSystemTrayIcon, QMenu, QStatusBar,
    QToolTip
)
from PySide6.QtCore import Qt, QSize, QUrl, QTimer
from PySide6.QtGui import QIcon, QPixmap, QCloseEvent, QAction, QCursor, QDesktopServices
from ui.components.download_card import DownloadCard
from ui.components.media_browser import MediaBrowserDialog
from ui.components.thumbnail_worker import ThumbnailWorker
from ui.components import auth_dialogs
from ui.views.settings_view import SettingsView
from ui.views.downloads_view import DownloadsView
from ui.views.file_manager_view import FileManagerView
from ui.views.explore_view import ExploreView, get_avatar_color
from ui.views.login_view import LoginView
from resource_utils import get_resource_path
from utils.update_checker import UpdateChecker, UpdateDownloader
from ui.components.clean_combobox import create_clean_menu

class MainWindow(QMainWindow):
    def __init__(self, telegram_worker, version="unknown"):
        super().__init__()
        print("DEBUG: MainWindow __init__ started")
        self.worker = telegram_worker
        self.version = version
        self.setWindowTitle(f"TG Private Grab v{version}")
        self.resize(1100, 700)
        self.setMinimumSize(750, 500)
        self._is_authenticating = False
        self._tasks_loaded = False
        self._reselect_task_id = None # Current task being re-selected
        self._active_media_browser = None # Current open browser dialog
        self._channel_row_widgets = {} # clean_cid -> ChannelRow widget
        
        print("DEBUG: Setting up UI")
        self.setup_ui()
        print("DEBUG: Connecting signals")
        self.connect_signals()
        print("DEBUG: Setting up tray")
        self.setup_tray()
        self._session_downloaded = 0
        self._last_speed_check = 0
        print("DEBUG: Checking for updates")
        self.check_for_updates()
        print("DEBUG: MainWindow __init__ DONE")

    def check_for_updates(self):
        self.update_checker = UpdateChecker(self.version, self)
        self.update_checker.update_found.connect(self.on_update_found)
        self.update_checker.start()

    def _connect_tray_click(self, slot):
        try:
            self.tray_icon.messageClicked.disconnect()
        except Exception:
            pass
        self.tray_icon.messageClicked.connect(slot)

    def on_update_found(self, latest_version, asset_url, asset_name):
        # No .exe asset attached -> fall back to the releases page
        if not asset_name or not asset_url:
            self.tray_icon.showMessage(
                "TG Private Grab - Update Available",
                f"Version {latest_version} is ready.\nClick here to open GitHub.",
                QSystemTrayIcon.Information,
                6000
            )
            self._connect_tray_click(
                lambda: QDesktopServices.openUrl(QUrl("https://github.com/DeepanshuK2002/Telegram_Private-Media_Grab/releases/latest"))
            )
            return

        getattr(self.worker, 'set_status', lambda _text=None: None)(
            f"Update v{latest_version} found - downloading in background..."
        )
        self.start_update_download(asset_url, asset_name)

    def start_update_download(self, asset_url, asset_name):
        import tempfile
        dest_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else tempfile.gettempdir()
        dest_path = os.path.join(dest_dir, asset_name + ".part")
        self.update_downloader = UpdateDownloader(asset_url, dest_path, self)
        self.update_downloader.finished.connect(self.on_update_downloaded)
        self.update_downloader.failed.connect(self.on_update_download_failed)
        self.update_downloader.start()

    def on_update_download_failed(self, err):
        print(f"Update download failed: {err}")
        self.tray_icon.showMessage(
            "TG Private Grab - Update Failed",
            f"Could not download the update automatically.\nYou can grab it from GitHub: {err}",
            QSystemTrayIcon.Warning,
            6000
        )

    def on_update_downloaded(self, path):
        if not getattr(sys, 'frozen', False) or not sys.executable:
            self.tray_icon.showMessage(
                "TG Private Grab - Update Downloaded",
                f"New version downloaded to:\n{path}\n\nRestart the app from source to pick it up.",
                QSystemTrayIcon.Information,
                8000
            )
            return

        self.tray_icon.showMessage(
            "TG Private Grab - Update Downloaded",
            f"The new version is ready.\nClick here to install & restart automatically.",
            QSystemTrayIcon.Information,
                8000
        )
        self._connect_tray_click(lambda: self.apply_update_restart(path))

    def apply_update_restart(self, downloaded_path):
        if not os.path.exists(downloaded_path):
            self.tray_icon.showMessage("TG Private Grab", "Update file is missing.", QSystemTrayIcon.Warning, 4000)
            return

        exe = sys.executable
        exe_dir = os.path.dirname(exe)
        exe_name = os.path.basename(exe)

        new_name = "TGPrivateGrab-Update.exe"
        staged = os.path.join(exe_dir, new_name)
        try:
            if os.path.exists(staged):
                os.remove(staged)
            os.replace(downloaded_path, staged)
        except Exception as e:
            self.tray_icon.showMessage(
                "TG Private Grab - Update Failed",
                f"Could not stage the update: {e}",
                QSystemTrayIcon.Warning,
                6000
            )
            return

        # Build a hidden updater: wait for app exit -> swap exe -> relaunch
        bat_path = os.path.join(exe_dir, "install_update.bat")
        bat = (
            f'@echo off\r\n'
            f'timeout /t 3 /nobreak >nul\r\n'
            f'copy /y "{staged}" "{exe}" >nul\r\n'
            f'if exist "{staged}" del /f /q "{staged}"\r\n'
            f'del /f /q "%~f0"\r\n'
            f'start "" "{exe}"\r\n'
        )
        with open(bat_path, "w", encoding="ascii", errors="ignore") as f:
            f.write(bat)

        vbs_path = os.path.join(exe_dir, "install_update.vbs")
        vbs = (
            f'Set sh = CreateObject("WScript.Shell")\r\n'
            f'sh.Run "{bat_path}", 0, False\r\n'
        )
        with open(vbs_path, "w", encoding="ascii", errors="ignore") as f:
            f.write(vbs)

        try:
            subprocess.Popen(["wscript", vbs_path], close_fds=True)
        except Exception as e:
            self.tray_icon.showMessage(
                "TG Private Grab - Update Failed",
                f"Could not launch updater: {e}",
                QSystemTrayIcon.Warning,
                6000
            )
            return

        self.tray_icon.showMessage(
            "TG Private Grab",
            "Update will install in a few seconds. The app will restart automatically.",
            QSystemTrayIcon.Information,
                4000
        )
        self.force_quit()

    def show_about_dialog(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("About TG Private Grab")
        from resource_utils import get_app_icon, get_resource_path
        msg.setWindowIcon(get_app_icon())
        about_icon_path = get_resource_path(os.path.join("assets", "logo_64.ico"))
        if os.path.exists(about_icon_path):
            msg.setIconPixmap(QPixmap(about_icon_path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # Premium/Rich look with HTML
        text = f"""
        <h2 style='color: #2AABEE;'>TG Private Grab</h2>
        <p><b>Version:</b> v{self.version}</p>
        <p>A modern, high-performance Telegram media downloader built with PySide6 and Telethon.</p>
        <ul style='color: #555; padding-left: 20px;'>
            <li><b>Instant Loading:</b> Zero-wait cached media browsing.</li>
            <li><b>Byte-Range Resuming:</b> Flawless pause & resume via explicit offsets.</li>
            <li><b>SQLite Persistence:</b> Robust, crash-proof active queues.</li>
            <li><b>Auto-Update:</b> Silently downloads and installs new releases.</li>
            <li><b>Windows Native:</b> Single-file portable build.</li>
        </ul>
        <hr/>
        <p style='font-size: 10px; color: #888;'>
            <a href='https://github.com/DeepanshuK2002/Telegram_Private-Media_Grab'>GitHub Repository</a> &nbsp;|&nbsp; &copy; 2026 TG Private Grab. Licensed under MIT.
        </p>
        """
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()

    def showEvent(self, event):
        super().showEvent(event)
        from resource_utils import set_windows_taskbar_icon
        set_windows_taskbar_icon(int(self.winId()))

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        from resource_utils import get_app_icon
        self.tray_icon.setIcon(get_app_icon())
        
        # Tray Menu
        tray_menu = create_clean_menu(self)
        action_show = tray_menu.addAction("Restore Window")
        action_show.triggered.connect(self.showNormal)
        action_show.triggered.connect(self.activateWindow)
        
        tray_menu.addSeparator()
        action_pause = tray_menu.addAction("Pause All")
        action_pause.triggered.connect(self.pause_all_downloads)
        action_resume = tray_menu.addAction("Resume All")
        action_resume.triggered.connect(self.resume_all_downloads)

        tray_menu.addSeparator()
        action_quit = tray_menu.addAction("Quit App")
        action_quit.triggered.connect(self.force_quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange:
            if self.isMinimized():
                # Minimize to tray logic
                self.hide()
                self.tray_icon.showMessage(
                    "TG Private Grab",
                    "Application minimized to tray. Double-click icon to restore.",
                    QSystemTrayIcon.Information,
                    2000
                )
        super().changeEvent(event)

    def force_quit(self):
        self.tray_icon.hide()
        self.close()

    def closeEvent(self, event: QCloseEvent):
        # 🟢 Optional: Warn if tasks are active
        if self.card_widgets:
            reply = QMessageBox.question(self, "Exit", "Downloads are still in progress. Are you sure you want to exit?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                event.ignore()
                return

        # 🟢 Clean up Update Checker
        if hasattr(self, 'update_checker') and self.update_checker.isRunning():
            self.update_checker.wait(500)
            if self.update_checker.isRunning():
                self.update_checker.terminate()

        # 🟢 Clean up Update Downloader
        if hasattr(self, 'update_downloader') and self.update_downloader.isRunning():
            self.update_downloader.cancel()
            self.update_downloader.wait(500)
            if self.update_downloader.isRunning():
                self.update_downloader.terminate()
                try:
                    part = os.path.join(
                        os.path.dirname(sys.executable),
                        "TGPrivateGrab-Update.exe.part"
                    )
                    if os.path.exists(part):
                        os.remove(part)
                except Exception:
                    pass
            
        if self.worker:
            self.worker.stop()
            if not self.worker.wait(2000):
                pass 
                
        event.accept()

    def setup_ui(self):
        main_widget = QWidget()
        main_widget.setObjectName("CentralWidget")
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------------------------------------------------
        # Sidebar
        # ---------------------------------------------------------
        # ---------------------------------------------------------
        # Sidebar Navigation (Refactored to QToolButtons for better styling)
        # ---------------------------------------------------------
        self.sidebarWidget = QWidget()
        self.sidebarWidget.setObjectName("Sidebar")
        self.sidebarWidget.setFixedWidth(64)
        
        sidebar_layout = QVBoxLayout(self.sidebarWidget)
        sidebar_layout.setContentsMargins(3, 16, 3, 12)
        sidebar_layout.setSpacing(6)

        # 1. Logo
        self.logo_container = QWidget()
        logo_layout = QVBoxLayout(self.logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 8)
        
        self.lbl_logo_img = QLabel()
        from resource_utils import get_sidebar_logo_pixmap, get_app_icon, set_windows_taskbar_icon
        pixmap = get_sidebar_logo_pixmap(36)
        if not pixmap.isNull():
            self.lbl_logo_img.setPixmap(pixmap)
        self.lbl_logo_img.setAlignment(Qt.AlignCenter)
        logo_layout.addWidget(self.lbl_logo_img)
        sidebar_layout.addWidget(self.logo_container)

        # 2. Nav Buttons (SVG icons)
        self.btn_home = self._create_nav_button("Home", "home", True)
        self.btn_explore = self._create_nav_button("Explore", "explore")
        self.btn_queue = self._create_nav_button("Queue", "queue")
        self.btn_files = self._create_nav_button("Files", "files")
        self.btn_settings = self._create_nav_button("Settings", "settings")

        from ui.views.settings_view import load_config
        try:
            cfg = load_config()
            cfg_dark = cfg.get("dark_mode", None)
            if cfg_dark is None:
                import ui.app as main_app
                cfg_dark = main_app.is_system_dark_mode()
            else:
                cfg_dark = bool(cfg_dark)
        except Exception:
            cfg_dark = False
        self.update_nav_icons(cfg_dark)

        self.btn_home.clicked.connect(lambda: self.switch_page("Home", 0))
        self.btn_explore.clicked.connect(lambda: self.switch_page("Explore", 1))
        self.btn_queue.clicked.connect(lambda: self.switch_page("Queue", 2))
        self.btn_files.clicked.connect(lambda: self.switch_page("Files", 3))
        self.btn_settings.clicked.connect(lambda: self.switch_page("Settings", 4))

        sidebar_layout.addWidget(self.btn_home)
        sidebar_layout.addWidget(self.btn_explore)
        sidebar_layout.addWidget(self.btn_queue)
        sidebar_layout.addWidget(self.btn_files)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(self.btn_settings)
        
        # Window Icon
        self.setWindowIcon(get_app_icon())

        # ---------------------------------------------------------
        # Main Content Layout
        # ---------------------------------------------------------
        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Top Header Area
        self.header = QFrame()
        self.header.setFixedHeight(60)
        self.header.setStyleSheet("background-color: transparent;")
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(40, 20, 24, 0)
        
        lbl_header = QLabel("Add Download")
        lbl_header.setObjectName("MainHeader")
        h_layout.addWidget(lbl_header)
        h_layout.addStretch()

        content_layout.addWidget(self.header)

        # Stacked Pages
        self.stacked_widget = QStackedWidget()
        self.setup_home_page()
        
        self.page_explore = ExploreView()
        self.page_queue = DownloadsView()
        self.page_files = FileManagerView()
        self.page_settings = SettingsView()
        self.page_login = LoginView()
        
        self.stacked_widget.addWidget(self.page_home)     # Index 0
        self.stacked_widget.addWidget(self.page_explore)  # Index 1
        self.stacked_widget.addWidget(self.page_queue)    # Index 2
        self.stacked_widget.addWidget(self.page_files)    # Index 3
        self.stacked_widget.addWidget(self.page_settings) # Index 4
        self.stacked_widget.addWidget(self.page_login)    # Index 5
        
        # Connect Explore signals
        self.page_explore.set_worker(self.worker)
        self.page_explore.downloadRequested.connect(self.start_explore_download)
        self.page_explore.switchToQueueRequested.connect(lambda: self.switch_page("Queue", 2))
        
        # Connect Login signals
        self.page_login.login_started.connect(self.worker.start_login)
        self.page_login.code_submitted.connect(self.worker.submit_code)
        self.page_login.password_submitted.connect(self.worker.submit_password)
        
        # Connect Queue Global Buttons
        self.page_queue.btn_pause_all.clicked.connect(self.pause_all_downloads)
        self.page_queue.btn_resume_all.clicked.connect(self.resume_all_downloads)
        self.page_queue.reFetchRequested.connect(self.re_fetch_from_history)

        # Connect Settings signals
        self.page_settings.themeToggled.connect(self.set_theme)
        
        content_layout.addWidget(self.stacked_widget)

        # Build Main View
        main_layout.addWidget(self.sidebarWidget)
        main_layout.addWidget(content_wrapper)
        
        # Bottom status bar removed for clean, modern interface
        self.lbl_status_msg = QLabel()
        self.setStatusBar(None)

    def _create_nav_button(self, text, icon_base=None, is_checked=False):
        btn = QToolButton()
        btn.setText(text)
        btn.setProperty("icon_base", icon_base)
        btn.setIconSize(QSize(18, 18))
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.setChecked(is_checked)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return btn

    def update_nav_icons(self, is_dark: bool):
        suffix = "_white.png" if is_dark else "_black.png"
        for btn in [getattr(self, 'btn_home', None), getattr(self, 'btn_explore', None), getattr(self, 'btn_queue', None), getattr(self, 'btn_files', None), getattr(self, 'btn_settings', None)]:
            if not btn:
                continue
            icon_base = btn.property("icon_base")
            if icon_base:
                svg_path = get_resource_path(os.path.join("assets", "icons", f"{icon_base}.svg"))
                icon_path = None
                icon = None

                # Prefer SVG, colorized for current theme
                if os.path.exists(svg_path):
                    icon = self._colored_svg_icon(svg_path, is_dark, btn)

                if icon is None:
                    # Fall back to PNG variants
                    icon_path = get_resource_path(os.path.join("assets", "icons", f"{icon_base}{suffix}"))
                    if not os.path.exists(icon_path):
                        icon_path = get_resource_path(os.path.join("assets", "icons", f"{icon_base}.png"))
                    if os.path.exists(icon_path):
                        icon = QIcon(icon_path)

                if icon and not icon.isNull():
                    btn.setIcon(icon)

    def _colored_svg_icon(self, svg_path, is_dark, btn):
        """Reads an SVG, replaces currentColor with a theme-appropriate color,
        and builds a QIcon pixmap so the icon visibly matches the theme."""
        if btn.isChecked():
            color = "#FFFFFF" if is_dark else "#09090B"  # checked: light on dark, dark on light
        elif is_dark:
            color = "#A1A1AA"  # light/unchecked icon on dark theme
        else:
            color = "#71717A"  # muted icon on light theme

        try:
            with open(svg_path, "r", encoding="utf-8") as f:
                svg = f.read()
            svg = svg.replace("currentColor", color)
            pixmap = QPixmap()
            from PySide6.QtCore import QByteArray
            ok = pixmap.loadFromData(QByteArray(svg.encode("utf-8")), "SVG")
            if ok and not pixmap.isNull():
                return QIcon(pixmap)
        except Exception:
            pass
        return None

    def setup_home_page(self):
        self.page_home = QWidget()
        layout = QVBoxLayout(self.page_home)
        layout.setContentsMargins(40, 24, 40, 40)
        layout.setSpacing(24)

        # ── Known Channels Card (Unified with Channel/Chat Search & Fetch) ──
        self._channel_copy_buttons = []
        self._all_cached_channels = []

        channels_card = QFrame()
        channels_card.setObjectName("WhiteCard")
        ch_layout = QVBoxLayout(channels_card)
        ch_layout.setContentsMargins(28, 24, 28, 24)
        ch_layout.setSpacing(16)

        # Header Row
        ch_header = QHBoxLayout()
        ch_header.setSpacing(8)

        self.lbl_channels_title = QLabel("Known Channels")
        self.lbl_channels_title.setObjectName("SectionHeader")
        ch_header.addWidget(self.lbl_channels_title)

        self.lbl_channels_count = QLabel("0")
        self.lbl_channels_count.setObjectName("ChannelsCountBadge")
        ch_header.addWidget(self.lbl_channels_count)

        ch_header.addStretch()

        # Real-time search/filter input with full channel/chat fetch capabilities
        self.input_channel_filter = QLineEdit()
        self.input_channel_filter.setObjectName("KnownChannelInput")
        self.input_channel_filter.setPlaceholderText("Filter or ID...")
        self.input_channel_filter.setMinimumWidth(100)
        self.input_channel_filter.setMaximumWidth(125)
        self.input_channel_filter.setFixedHeight(30)
        self.input_channel_filter.textChanged.connect(self.filter_channels_list)
        self.input_channel_filter.returnPressed.connect(self.on_fetch_clicked)
        ch_header.addWidget(self.input_channel_filter)

        # Unified alias so any code referencing self.input_channel continues to work seamlessly
        self.input_channel = self.input_channel_filter

        # Fetch Media Button (preserves fetch media functionality)
        self.btn_fetch = QPushButton("Fetch Media")
        self.btn_fetch.setObjectName("KnownChannelFetchBtn")
        self.btn_fetch.setFixedHeight(30)
        self.btn_fetch.setCursor(Qt.PointingHandCursor)
        self.btn_fetch.clicked.connect(self.on_fetch_clicked)
        ch_header.addWidget(self.btn_fetch)

        # Refresh button with theme-aware icon
        self.btn_refresh_channels = QPushButton()
        self.btn_refresh_channels.setObjectName("IconButtonSmall")
        self.btn_refresh_channels.setFixedSize(30, 30)
        self.btn_refresh_channels.setIconSize(QSize(14, 14))
        self.btn_refresh_channels.setToolTip("Refresh channel list from Telegram")
        self.btn_refresh_channels.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_channels.clicked.connect(self.on_refresh_channels_clicked)
        ch_header.addWidget(self.btn_refresh_channels)

        ch_layout.addLayout(ch_header)

        # Subtitle & Hints
        lbl_ch_desc = QLabel("Filter saved channels, or enter any public username, invite link, or numeric ID to fetch media.")
        lbl_ch_desc.setObjectName("MutedText")
        lbl_ch_desc.setWordWrap(True)
        ch_layout.addWidget(lbl_ch_desc)

        # Scroll Area for Channel Rows
        self.channels_scroll = QScrollArea()
        self.channels_scroll.setWidgetResizable(True)
        self.channels_scroll.setFrameShape(QFrame.NoFrame)
        self.channels_scroll.setMinimumHeight(280)
        self.channels_scroll.setMaximumHeight(520)
        self.channels_scroll.setStyleSheet("background: transparent;")

        self.channels_container = QWidget()
        self.channels_container.setStyleSheet("background: transparent;")
        self.channels_layout = QVBoxLayout(self.channels_container)
        self.channels_layout.setContentsMargins(0, 0, 4, 0)
        self.channels_layout.setSpacing(8)
        self.channels_layout.setAlignment(Qt.AlignTop)

        self.channels_scroll.setWidget(self.channels_container)
        ch_layout.addWidget(self.channels_scroll)

        # No match feedback label for filtering
        self.lbl_filter_no_match = QLabel()
        self.lbl_filter_no_match.setObjectName("MutedText")
        self.lbl_filter_no_match.setAlignment(Qt.AlignCenter)
        self.lbl_filter_no_match.setStyleSheet("padding: 24px; font-size: 13px; color: #71717A;")
        self.lbl_filter_no_match.hide()
        ch_layout.addWidget(self.lbl_filter_no_match)

        # Empty State
        self.empty_channels_frame = QFrame()
        self.empty_channels_frame.setObjectName("EmptyChannelsState")
        empty_layout = QVBoxLayout(self.empty_channels_frame)
        empty_layout.setContentsMargins(16, 20, 16, 20)
        empty_layout.setSpacing(8)
        empty_layout.setAlignment(Qt.AlignCenter)

        lbl_empty_title = QLabel("No Saved Channels Yet")
        lbl_empty_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        lbl_empty_title.setAlignment(Qt.AlignCenter)

        lbl_empty_desc = QLabel("Enter a channel username or link in the search bar above, or browse in Explore to automatically save channels here.")
        lbl_empty_desc.setObjectName("MutedText")
        lbl_empty_desc.setAlignment(Qt.AlignCenter)
        lbl_empty_desc.setWordWrap(True)

        btn_go_explore = QPushButton("Browse Channels in Explore")
        btn_go_explore.setObjectName("SecondaryButton")
        btn_go_explore.setCursor(Qt.PointingHandCursor)
        btn_go_explore.setFixedWidth(210)
        btn_go_explore.clicked.connect(lambda: self.switch_page("Explore", 1))

        empty_layout.addWidget(lbl_empty_title)
        empty_layout.addWidget(lbl_empty_desc)
        empty_layout.addWidget(btn_go_explore, 0, Qt.AlignCenter)
        ch_layout.addWidget(self.empty_channels_frame)

        layout.addWidget(channels_card)
        layout.addStretch()
        
        self.card_widgets = {} # task_id -> DownloadCard
        self.update_home_icons(self._is_dark_mode())
        self.refresh_channels_list()

    def _is_dark_mode(self) -> bool:
        """Determines if the application is currently running in dark mode."""
        from ui.views.settings_view import load_config
        try:
            cfg = load_config()
            val = cfg.get("dark_mode", None)
            if val is not None:
                return bool(val)
            import ui.app as main_app
            return main_app.is_system_dark_mode()
        except Exception:
            return False

    def update_home_icons(self, is_dark: bool):
        """Updates icons on the Home page according to the active theme."""
        if hasattr(self, 'btn_refresh_channels') and self.btn_refresh_channels:
            refresh_file = "refresh_white.png" if is_dark else "refresh_black.png"
            p = get_resource_path(os.path.join("assets", "icons", refresh_file))
            if os.path.exists(p):
                self.btn_refresh_channels.setIcon(QIcon(p))

        copy_file = "copy_white.png" if is_dark else "copy_black.png"
        cp = get_resource_path(os.path.join("assets", "icons", copy_file))
        if os.path.exists(cp) and hasattr(self, '_channel_copy_buttons'):
            icon = QIcon(cp)
            for btn in self._channel_copy_buttons:
                try:
                    btn.setIcon(icon)
                except Exception:
                    pass

    def on_refresh_channels_clicked(self):
        """Refreshes the local DB cache and optionally asks Telegram for fresh dialogs."""
        self.refresh_channels_list()
        if self.worker:
            try:
                self.worker.fetch_user_dialogs()
            except Exception:
                pass
        self.lbl_status_msg.setText("Refreshing channels...")

    def filter_channels_list(self, query: str):
        """Filters the displayed channels list in real-time."""
        query = query.strip().lower()
        visible_count = 0
        for i in range(self.channels_layout.count()):
            item = self.channels_layout.itemAt(i)
            w = item.widget() if item else None
            if w and hasattr(w, "channel_data"):
                data = w.channel_data
                title = str(data.get("title") or "").lower()
                username = str(data.get("username") or "").lower()
                cid = str(data.get("channel_id") or "").lower()
                matches = (not query) or (query in title) or (query in username) or (query in cid)
                w.setVisible(matches)
                if matches:
                    visible_count += 1

        total = len(getattr(self, '_all_cached_channels', []))
        if hasattr(self, 'lbl_channels_count'):
            if query:
                self.lbl_channels_count.setText(f"{visible_count}/{total}")
            else:
                self.lbl_channels_count.setText(str(total))

    def on_avatar_ready(self, cid: str, path: str):
        """Efficiently updates a single channel row's avatar without rebuilding the entire list."""
        if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
            return
        cid_clean = str(cid).replace("-100", "", 1) if str(cid).startswith("-100") else str(cid)
        row = getattr(self, '_channel_row_widgets', {}).get(cid_clean)
        if row and hasattr(row, 'avatar_label'):
            pix = QPixmap(path)
            if not pix.isNull():
                from ui.views.explore_view import make_circular_avatar
                row.avatar_label.setPixmap(make_circular_avatar(pix, 36))
                row.avatar_label.setStyleSheet("background: transparent; border-radius: 18px;")

    def refresh_channels_list(self):
        """Rebuilds the Known Channels list from the DB cache with UI updates paused."""
        from database import get_cached_channels_list
        try:
            channels = get_cached_channels_list()
        except Exception:
            channels = []

        self._all_cached_channels = channels
        self._channel_copy_buttons = []
        self._channel_row_widgets = {}

        if hasattr(self, 'channels_scroll') and self.channels_scroll:
            self.channels_scroll.setUpdatesEnabled(False)

        try:
            # Clear existing rows
            while self.channels_layout.count():
                item = self.channels_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()

            count = len(channels)
            self.lbl_channels_count.setText(str(count))

            if not channels:
                self.empty_channels_frame.show()
                self.channels_scroll.hide()
                self.input_channel_filter.show()
                return

            self.empty_channels_frame.hide()
            self.channels_scroll.show()
            self.input_channel_filter.show()

            for ch in channels:
                row = self._build_channel_row(ch)
                self.channels_layout.addWidget(row)

            self.channels_layout.addStretch()

            # Re-apply active filter if text exists
            if self.input_channel_filter.text():
                self.filter_channels_list(self.input_channel_filter.text())
        finally:
            if hasattr(self, 'channels_scroll') and self.channels_scroll:
                self.channels_scroll.setUpdatesEnabled(True)

    def _build_channel_row(self, ch):
        """Builds a modern row widget: avatar + title/badge + sublabel + ID badge + copy icon + fetch button."""
        row = QFrame()
        row.setObjectName("ChannelRow")
        row.setAttribute(Qt.WA_StyledBackground, True)
        row.setCursor(Qt.PointingHandCursor)
        row.channel_data = ch

        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 10, 14, 10)
        rl.setSpacing(12)

        # 1. Circle Avatar with dynamic hash color
        # 1. Circle Avatar (Real profile picture if cached, else fallback initials)
        title = ch.get("title") or ch.get("username") or "Unknown Channel"
        initials = "".join([w[0] for w in title.split() if w][:2]).upper()
        if not initials:
            initials = title[:2].upper() if title else "TG"
        bg_hex = get_avatar_color(title)

        avatar = QLabel()
        avatar.setFixedSize(36, 36)
        avatar.setAlignment(Qt.AlignCenter)

        cid_clean = str(ch.get("channel_id", "")).replace("-100", "", 1) if str(ch.get("channel_id", "")).startswith("-100") else str(ch.get("channel_id", ""))
        from resource_utils import get_project_root
        avatar_dir = os.path.join(get_project_root(), "cache", "avatars")
        avatar_path = os.path.join(avatar_dir, f"{cid_clean}.jpg")

        if os.path.exists(avatar_path) and os.path.getsize(avatar_path) > 0:
            pix = QPixmap(avatar_path)
            if not pix.isNull():
                from ui.views.explore_view import make_circular_avatar
                avatar.setPixmap(make_circular_avatar(pix, 36))
                avatar.setStyleSheet("background: transparent; border-radius: 18px;")
            else:
                avatar.setText(initials[:2])
                avatar.setStyleSheet(f"background-color: {bg_hex}; color: #FFFFFF; font-weight: 700; font-size: 12px; border-radius: 18px;")
        else:
            avatar.setText(initials[:2])
            avatar.setStyleSheet(f"background-color: {bg_hex}; color: #FFFFFF; font-weight: 700; font-size: 12px; border-radius: 18px;")

        rl.addWidget(avatar)

        # 2. Channel Title + Subtitle stack
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        lbl_name = QLabel(title)
        lbl_name.setObjectName("ChannelRowName")
        lbl_name.setCursor(Qt.PointingHandCursor)
        lbl_name.setToolTip("Click to fetch this channel")
        info_layout.addWidget(lbl_name)

        is_channel = ch.get("is_channel", 1)
        username = ch.get("username", "")
        if username:
            sub_text = username if username.startswith("@") else f"@{username}"
        else:
            sub_text = "Private Channel" if is_channel else "Private Group"
        lbl_sub = QLabel(sub_text)
        lbl_sub.setObjectName("ChannelRowSub")
        info_layout.addWidget(lbl_sub)

        rl.addLayout(info_layout, stretch=1)

        # 3. Channel ID Monospace Pill Badge
        cid = str(ch.get("channel_id", ""))
        full_id = f"-100{cid}" if cid.isdigit() and not cid.startswith("-100") else cid
        lbl_id = QLabel(full_id)
        lbl_id.setObjectName("ChannelRowID")
        lbl_id.setCursor(Qt.PointingHandCursor)
        lbl_id.setToolTip("Channel ID (Click to copy)")
        lbl_id.mousePressEvent = lambda e, fid=full_id, w=lbl_id: self._copy_channel_id(fid, w)
        rl.addWidget(lbl_id)

        # 4. Copy Icon Button
        is_dark = self._is_dark_mode()
        copy_icon_name = "copy_white.png" if is_dark else "copy_black.png"
        copy_icon_path = get_resource_path(os.path.join("assets", "icons", copy_icon_name))

        btn_copy = QPushButton()
        btn_copy.setObjectName("IconButtonSmall")
        btn_copy.setFixedSize(30, 30)
        btn_copy.setIconSize(QSize(14, 14))
        if os.path.exists(copy_icon_path):
            btn_copy.setIcon(QIcon(copy_icon_path))
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.setToolTip("Copy channel ID")
        btn_copy.clicked.connect(lambda checked=False, fid=full_id, b=btn_copy: self._copy_channel_id(fid, b))
        self._channel_copy_buttons.append(btn_copy)
        rl.addWidget(btn_copy)

        # 5. Fetch Button
        btn_fetch = QPushButton("Fetch")
        btn_fetch.setObjectName("ChannelFetchBtn")
        btn_fetch.setFixedHeight(30)
        btn_fetch.setCursor(Qt.PointingHandCursor)
        btn_fetch.setToolTip("Load and fetch media for this channel")
        btn_fetch.clicked.connect(lambda checked=False, fid=full_id: self._load_channel_by_id(fid))
        rl.addWidget(btn_fetch)

        # Clicking row also loads channel
        row.mousePressEvent = lambda e, fid=full_id: self._load_channel_by_id(fid)

        return row

    def _copy_channel_id(self, channel_id, widget=None):
        from PySide6.QtWidgets import QApplication, QToolTip
        from PySide6.QtGui import QCursor
        QApplication.clipboard().setText(channel_id)
        self.lbl_status_msg.setText(f"Channel ID copied: {channel_id}")
        if widget:
            QToolTip.showText(QCursor.pos(), "Copied!", widget, widget.rect(), 1500)

    def _load_channel_by_id(self, channel_id):
        """Fills the search box with the channel ID and triggers a fetch."""
        self.input_channel.setText(channel_id)
        self.on_fetch_clicked()

    def cache_resolved_channel(self, channel_obj):
        """Stores a resolved Telethon channel entity into DB and refreshes list."""
        if not channel_obj:
            return
        cid = getattr(channel_obj, 'id', None)
        if cid is None:
            return
        title = getattr(channel_obj, 'title', None) or ""
        username = getattr(channel_obj, 'username', '') or ""
        from database import cache_channel
        cache_channel(cid, title, f"@{username}" if username else "")
        self.refresh_channels_list()

    def switch_page(self, item_text, index):
        if "Home" in item_text:
            self.header.show()
            self.stacked_widget.setCurrentIndex(0)
            self.btn_home.setChecked(True)
        elif "Explore" in item_text:
            self.header.hide()
            self.stacked_widget.setCurrentIndex(1)
            self.btn_explore.setChecked(True)
            if not self.page_explore.all_channels and self.worker:
                self.worker.fetch_user_dialogs()
        elif "Queue" in item_text:
            self.header.hide()
            self.stacked_widget.setCurrentIndex(2)
            self.btn_queue.setChecked(True)
        elif "Files" in item_text:
            self.header.hide()
            self.page_files.refresh_list()
            self.stacked_widget.setCurrentIndex(3)
            self.btn_files.setChecked(True)
        elif "Settings" in item_text:
            self.header.hide()
            self.stacked_widget.setCurrentIndex(4)
            self.btn_settings.setChecked(True)
        else:
            self.header.hide()

        # Refresh nav icon colors to reflect checked state
        from ui.views.settings_view import load_config
        try:
            cfg = load_config()
            cfg_dark = cfg.get("dark_mode", None)
            if cfg_dark is None:
                import ui.app as main_app
                cfg_dark = main_app.is_system_dark_mode()
            else:
                cfg_dark = bool(cfg_dark)
            self.update_nav_icons(cfg_dark)
        except Exception:
            pass

    def start_explore_download(self, channel_id, selected_ids):
        """Starts batch download of selected videos from Explore."""
        if not selected_ids:
            return
        from ui.views.settings_view import load_config
        cfg = load_config()
        self.worker.start_download(
            channel_input=channel_id,
            media_id=6,
            download_path=cfg.get("download_path", "downloads"),
            download_limit=cfg.get("download_limit", 5),
            max_speed_kb=cfg.get("max_speed_kb", 0),
            selected_message_ids=selected_ids,
        )

    def set_theme(self, is_dark: bool):
        self.setUpdatesEnabled(False)
        try:
            import ui.app as main_app
            main_app.apply_theme(is_dark)
            self.update_nav_icons(is_dark)
            if hasattr(self, 'page_files') and hasattr(self.page_files, 'update_theme'):
                self.page_files.update_theme(is_dark)
            if hasattr(self, 'page_explore') and hasattr(self.page_explore, 'update_theme'):
                self.page_explore.update_theme(is_dark)
            self.update_home_icons(is_dark)
        finally:
            self.setUpdatesEnabled(True)
            self.repaint()

    # ---------------------------------------------------------
    # Actions & Signals
    # ---------------------------------------------------------
    def connect_signals(self):
        self.worker.signals.auth_needed.connect(self.prompt_login)
        self.worker.signals.code_needed.connect(self.prompt_code)
        self.worker.signals.password_needed.connect(self.prompt_password)
        self.worker.signals.auth_success.connect(self.on_auth_success)
        self.worker.signals.auth_error.connect(self.show_auth_error)
        
        self.worker.signals.media_list_fetched.connect(self.show_media_browser)
        self.worker.signals.channel_fetched.connect(self.add_download_card)
        self.worker.signals.download_progress.connect(self.update_progress)
        self.worker.signals.file_progress.connect(self.update_file_progress)
        self.worker.signals.file_completed.connect(self.on_file_completed)
        self.worker.signals.download_completed.connect(self.on_download_completed)
        self.worker.signals.error_occurred.connect(self.on_fetch_error)
        
        self.page_settings.logoutRequested.connect(self.logout)
        if hasattr(self.worker.signals, 'dialogs_fetched'):
            self.worker.signals.dialogs_fetched.connect(lambda dialogs: self.refresh_channels_list())
        if hasattr(self.worker.signals, 'avatar_ready'):
            self.worker.signals.avatar_ready.connect(self.on_avatar_ready)
        # sidebar signals are now handled by button connects

    def on_download_completed(self, task_id, folder_name):
        if task_id in self.card_widgets:
            card = self.card_widgets[task_id]
            title = card.lbl_title.text()
            self.page_queue.active_layout.removeWidget(card)
            card.deleteLater()
            del self.card_widgets[task_id]
            self.page_queue.add_completed_item(title, folder_name, task_id)
            self.page_files.refresh_list()
            
            # Tray notification
            self.tray_icon.showMessage(
                "Download Completed",
                f"Successfully downloaded: {title}",
                QSystemTrayIcon.Information,
                3000
            )

    def prompt_login(self):
        self._is_authenticating = True
        self.sidebarWidget.hide()
        self.header.hide()
        self.page_login.reset_to_start()
        self.stacked_widget.setCurrentWidget(self.page_login)

    def prompt_code(self, phone):
        self.page_login.show_otp_step()

    def prompt_password(self):
        self.page_login.show_pwd_step()
        
    def show_auth_error(self, err_msg):
        auth_dialogs.show_auth_error(self, err_msg)
        self.page_login.reset_to_start()
            
    def on_auth_success(self):
        if self._is_authenticating:
            self.sidebarWidget.show()
            self.switch_page("Home", 0)
            self._is_authenticating = False
            auth_dialogs.show_auth_success(self)
        self.load_active_tasks_from_worker()
        if self.worker:
            self.worker.fetch_user_dialogs()
        
    def load_active_tasks_from_worker(self):
        print("DEBUG: load_active_tasks_from_worker started")
        if self._tasks_loaded:
            print("DEBUG: tasks already loaded, skipping")
            return
        self._tasks_loaded = True
        
        try:
            from core_downloader import load_active_tasks, save_active_tasks
            tasks = load_active_tasks()
            if not isinstance(tasks, list):
                print(f"Warning: active_tasks.json is not a list. Type: {type(tasks)}")
                tasks = []
                
            # Initial deduplication
            seen = set()
            deduped = []
            for t in tasks:
                if not isinstance(t, dict): continue
                chan = str(t.get("channel_input", "")).strip()
                chan_key = chan.rstrip('/').split('/')[-1].replace("-100", "", 1)
                topic = t.get("topic_id")
                media = t.get("media_id", 6)
                key = (chan_key, topic, media)
                if key not in seen:
                    seen.add(key)
                    deduped.append(t)
            
            if len(deduped) != len(tasks):
                save_active_tasks(deduped)
                tasks = deduped
            
            from ui.views.settings_view import load_config
            cfg = load_config()
            cfg_speed = cfg.get("max_speed_kb", 0)
            cfg_limit = cfg.get("download_limit", 5)

            # 🟢 Smart Startup Loader
            for i, t in enumerate(tasks):
                if not isinstance(t, dict): continue
                chan = t.get("channel_input")
                media = t.get("media_id", 6)
                print(f"DEBUG: Processing task {i}: {chan}_{media}")
                if not chan: continue
                
                is_paused = bool(t.get("paused", True))
                
                # If it's paused, just show the card (no network)
                if is_paused:
                    # In UI, we don't 'clean' the ID anymore, we use what's in the task
                    # but ensure we handle the -100 prefix consistently.
                    ch_id_full = str(chan)
                    m_id = t.get('media_id', 6)
                    self.add_download_card({
                        "task_id": f"{ch_id_full}_{m_id}",
                        "title": t.get("title") or f"Saved Task: {chan}",
                        "is_paused": True,
                        "download_path": t.get("download_path") or cfg.get("download_path", "downloads"),
                        "download_limit": cfg_limit,
                        "max_speed_kb": cfg_speed,
                        "media_type": m_id,
                        "completed": t.get("completed", 0),
                        "folder_name": t.get("folder_name") or t.get("download_path", "downloads")
                    }, t.get("total_items", 0))
                else:
                    # Stagger starts to avoid UI choking
                    def delayed_start(t_data=t):
                        try:
                            self.worker.start_download(
                                channel_input=t_data.get("channel_input"),
                                media_id=t_data.get("media_id", 6),
                                download_path=t_data.get("download_path") or cfg.get("download_path", "downloads"),
                                download_limit=cfg_limit,
                                max_speed_kb=cfg_speed,
                                is_paused=False,
                                selected_message_ids=t_data.get("selected_message_ids", None)
                            )
                        except Exception as e:
                            print(f"Startup task error: {e}")
                            
                    QTimer.singleShot(max(10, i * 500), delayed_start)
                    
        except Exception as startup_err:
            print(f"Critical startup loading error: {startup_err}")
            import traceback
            traceback.print_exc()
        
    def on_fetch_clicked(self):
        channel = self.input_channel.text().strip()
        if not channel: return
        
        # 🚀 Instant Load to Bulk Mode or Cache
        from database import get_cached_media, cache_channel
        cached = get_cached_media(channel)
        if cached:
            # 📒 Show this channel in Known Channels (id came from cache rows)
            try:
                cache_channel(str(cached[0]["channel_id"]), "", channel)
                self.refresh_channels_list()
            except Exception:
                pass
            # Reconstruct categorized dict from DB rows
            c_dict = {k.lower(): [] for k in ["Media", "Files", "ZIPs", "Music", "Voice", "Links", "GIFs", "Chat", "All"]}
            import collections
            MockMsg = collections.namedtuple('MockMsg', ['id', 'message', 'date', 'size', 'media_type', 'is_mock'])
            for row in cached:
                m = MockMsg(id=row["msg_id"], message=row["title"], date=row["date"], size=row["size"], media_type=row["media_type"], is_mock=True)
                cat = row["media_type"].lower()
                if cat in c_dict:
                    c_dict[cat].append(m)
                
                # ZIPs also belong in Files
                if cat == 'zips':
                    c_dict['files'].append(m)
                    
                c_dict["all"].append(m)
                
            for k in c_dict:
                c_dict[k].sort(key=lambda x: x.id, reverse=True)
            
            # Show dialog immediately with cached data
            self.show_media_browser(channel, None, c_dict)
        else:
            # Show dialog immediately in Bulk Download Mode
            self.show_media_browser(channel, None, None)

    def show_media_browser(self, channel_input, channel_obj, messages_dict):
        # 🔄 Update existing dialog if it's already open (Instant Loading Flow)
        if self._active_media_browser and self._active_media_browser.isVisible():
            self._active_media_browser.refresh_content(messages_dict)
            return

        # 🔄 Selection Persistence Reset
        if self._reselect_task_id and self._reselect_task_id in self.card_widgets:
            self.card_widgets[self._reselect_task_id].set_reselect_loading(False)
            
        self.btn_fetch.setText("Fetch Media")
        self.btn_fetch.setEnabled(True)
        self.input_channel.clear()
        
        # If we came from cache, channel_obj might be None
        if not channel_obj:
            title = str(channel_input)
        else:
            title = getattr(channel_obj, 'title', None)
            if not title:
                first = getattr(channel_obj, 'first_name', '') or ''
                last = getattr(channel_obj, 'last_name', '') or ''
                title = f"{first} {last}".strip()
            if not title:
                title = getattr(channel_obj, 'username', None)
            if not title:
                title = getattr(channel_obj, 'id', str(channel_input))
            title = str(title)
        
        # 📒 Cache the resolved channel so its ID is available below the search box
        self.cache_resolved_channel(channel_obj)
        
        # 🌙 Theme Support
        from ui.views.settings_view import load_config
        cfg = load_config()
        is_dark = cfg.get("dark_mode", False)

        # 🔄 Selection Persistence for Re-select from SQLite
        existing_ids = []
        if self._reselect_task_id:
            from database import get_task_db
            try:
                ch_in, m_id_str = self._reselect_task_id.rsplit('_', 1)
                task_data = get_task_db(ch_in, int(m_id_str))
                if task_data:
                    existing_ids = task_data.get("selected_message_ids", [])
            except: pass
            
        dialog = MediaBrowserDialog(title, messages_dict, self, previous_selected_ids=existing_ids, is_dark=is_dark)
        self._active_media_browser = dialog
        
        dialog.fetch_requested.connect(lambda: self._trigger_specific_fetch(channel_input, dialog))
        
        # Start thumbnail loading for real messages from Telegram worker
        if messages_dict:
            all_real_msgs = []
            for msg_list in messages_dict.values():
                if isinstance(msg_list, list):
                    for m in msg_list:
                        if not getattr(m, 'is_mock', False) and hasattr(m, 'id'):
                            all_real_msgs.append(m)
            if all_real_msgs:
                # Connect worker thumbnail_ready signal so downloaded thumbs update in real-time
                if hasattr(self.worker, 'signals') and hasattr(self.worker.signals, 'thumbnail_ready'):
                    self.worker.signals.thumbnail_ready.connect(
                        lambda ch_id, m_id, path: dialog.apply_thumbnail(m_id, path)
                    )
                # Fetch live Telegram thumbnails in background
                if hasattr(self.worker, 'fetch_channel_thumbnails'):
                    cid = getattr(channel_obj, 'id', channel_input) if channel_obj else channel_input
                    self.worker.fetch_channel_thumbnails(cid, all_real_msgs)
                # Also load any already-cached thumbnail files
                client = self.worker.get_client() if hasattr(self.worker, 'get_client') else None
                if client:
                    thumb_worker = ThumbnailWorker(client, all_real_msgs, dialog)
                    dialog.set_thumbnail_worker(thumb_worker)
        
        if dialog.exec():
            if dialog.is_bulk_mode():
                bulk_media_ids = dialog.get_bulk_selections()
                if not bulk_media_ids:
                    self._active_media_browser = None
                    return
                for m_id in bulk_media_ids:
                    self.worker.start_download(
                        channel_input=channel_input, 
                        media_id=m_id, 
                        download_path=cfg.get("download_path", "downloads"), 
                        download_limit=cfg.get("download_limit", 5), 
                        max_speed_kb=cfg.get("max_speed_kb", 0),
                        selected_message_ids=None, # This triggers the unbounded limit=None bulk fetch
                        task_id=None
                    )
            else:
                selected_msgs = dialog.get_selected_messages()
                if not selected_msgs:
                    self._active_media_browser = None
                    return # they selected nothing
                    
                selected_ids = [m.id for m in selected_msgs]
                
                # If re-selecting, we use existing task_id
                target_task_id = self._reselect_task_id
                self._reselect_task_id = None # Clear context
                
                self.worker.start_download(
                    channel_input=channel_input, 
                    media_id=6, # 6 is ALL
                    download_path=cfg.get("download_path", "downloads"), 
                    download_limit=cfg.get("download_limit", 5), 
                    max_speed_kb=cfg.get("max_speed_kb", 0),
                    selected_message_ids=selected_ids,
                    task_id=target_task_id # If this is set, worker will update existing task
                )
        
        self._active_media_browser = None

    def _trigger_specific_fetch(self, channel_input, dialog):
        dialog.btn_load_specific.setText("Fetching... Please wait.")
        dialog.btn_load_specific.setEnabled(False)
        from ui.views.settings_view import load_config
        cfg = load_config()
        fetch_limit = cfg.get("initial_fetch_limit", 2000)
        self.worker.fetch_media_list(channel_input, limit=fetch_limit)

    def on_fetch_error(self, channel, err_msg):
        if self._reselect_task_id and self._reselect_task_id in self.card_widgets:
            self.card_widgets[self._reselect_task_id].set_reselect_loading(False)
            self._reselect_task_id = None
            
        self.btn_fetch.setText("Fetch Media")
        self.btn_fetch.setEnabled(True)
        QMessageBox.critical(self, "Fetch Error", f"Failed to fetch content for {channel}:\n{err_msg}")

    def add_download_card(self, data, total_items):
        task_id = data["task_id"]
        
        # 📒 Cache the resolved channel ID so it shows up in Known Channels
        from database import cache_channel
        try:
            cache_channel(
                data.get("channel_input", ""),
                data.get("title", ""),
                ""
            )
            self.refresh_channels_list()
        except Exception:
            pass
        
        # 🛡️ SMART LOOKUP: If we can't find by task_id, look for a 'ghost' card that was
        # started by username/input but now has this resolved ID.
        if task_id not in self.card_widgets:
            ch_resolved = str(data.get("channel_input", ""))
            original_in = str(data.get("original_input", ""))
            m_id = str(data.get("media_id", 6))
            topic_id = str(data.get("topic_id")) if data.get("topic_id") is not None else None
            
            for old_id, card in list(self.card_widgets.items()):
                # Parse old_id: {chan}_{topic}_{media} or {chan}_{media}
                parts = old_id.split('_')
                if len(parts) >= 3:
                    old_chan = "_".join(parts[:-2])
                    old_topic = parts[-2]
                    old_media = parts[-1]
                elif len(parts) == 2:
                    old_chan = parts[0]
                    old_topic = None
                    old_media = parts[1]
                else:
                    continue

                # Media ID must match
                if old_media != m_id:
                    continue
                # Topic ID must match if present
                if topic_id is not None and old_topic != topic_id:
                    continue

                # Match by original user input OR by numeric ID if it was partially resolved
                # We also check for -100 stripped versions to be super safe.
                if (old_chan == original_in or 
                    old_chan == ch_resolved or 
                    old_chan.replace('-100', '', 1) == ch_resolved.replace('-100', '', 1)):
                    
                    print(f"DEBUG: Successfully hijacked ghost card {old_id} -> {task_id}")
                    # Re-map the card in our tracking dict
                    del self.card_widgets[old_id]
                    self.card_widgets[task_id] = card
                    card.task_id = task_id # Update card's own property
                    break

        if task_id in self.card_widgets:
            # Refresh placeholder card with real metadata
            card = self.card_widgets[task_id]
            card.refresh_from_metadata(
                title=data["title"],
                total_items=total_items,
                completed=data.get("completed", 0),
                files_metadata=data.get("files_metadata", []),
                is_paused=data.get("is_paused", card.is_paused) # Maintain local state if not provided
            )
            return
            
        print(f"DEBUG: Creating new card for {task_id}")
        is_paused = data.get("is_paused", False)
        card = DownloadCard(
            task_id=task_id,
            title=data["title"],
            total_items=total_items,
            folder_name=data.get("folder_name", "downloads"),
            media_type=data.get("media_type", 6),
            parent_worker=self.worker,
            completed=data.get("completed", 0),
            is_paused=is_paused,
            download_path=data.get("download_path", "downloads"),
            download_limit=data.get("download_limit", 5),
            max_speed_kb=data.get("max_speed_kb", 0),
            files_metadata=data.get("files_metadata", [])
        )
        self.page_queue.active_layout.addWidget(card)
        self.card_widgets[task_id] = card
        self.page_queue.set_controls_visible(True)
        
        # Connect signals
        card.reselectRequested.connect(self.reselect_task_media)
        card.removeRequested.connect(self.remove_task)
        card.moveUpRequested.connect(self.move_task_up)
        card.moveDownRequested.connect(self.move_task_down)

    def move_card(self, card, direction):
        """direction: -1 (up), 1 (down)"""
        layout = self.page_queue.active_layout
        idx = layout.indexOf(card)
        new_idx = idx + direction
        if 0 <= new_idx < layout.count():
            layout.removeWidget(card)
            layout.insertWidget(new_idx, card)

    def update_progress(self, task_id, current, total):
        if task_id in self.card_widgets:
            self.card_widgets[task_id].update_progress(current, total)
            self.refresh_global_status()

    def update_file_progress(self, task_id, msg_id, current_bytes, total_bytes, speed_str):
        if task_id in self.card_widgets:
            self.card_widgets[task_id].update_file_progress(msg_id, current_bytes, total_bytes, speed_str)
            
            # Update session stats (rough estimate based on speed * interval if we had a timer, 
            # but worker emits current_bytes. We'll use a better approach: track per-file delta)
            # Actually, for session stats, let's just track completed items' total size or use a simpler counter.
            
            self.refresh_global_status()

    def refresh_global_status(self):
        # Global status update
        import humanize
        all_speeds = [c.last_speed_val for c in self.card_widgets.values() if hasattr(c, 'last_speed_val')]
        total_speed = sum(all_speeds)
        speed_text = f"{humanize.naturalsize(total_speed*1024)}/s" if total_speed > 0 else "0 B/s"
        
        # Calculate overall progress
        total_items = sum(c.total_items for c in self.card_widgets.values())
        total_completed = sum(c.completed for c in self.card_widgets.values())
        progress_pct = (total_completed * 100 / total_items) if total_items > 0 else 0
        
        # Session stats
        session_text = f" | Session: {humanize.naturalsize(self._session_downloaded)}" if self._session_downloaded > 0 else ""
        
        status_text = f"Speed: {speed_text}{session_text} | Total Progress: {progress_pct:.1f}% | Queue: {len(self.card_widgets)} tasks"
        self.lbl_status_msg.setText(status_text)
        
        # 🟢 Tray Tooltip
        tray_tip = f"TG Private Grab - {speed_text}\nProgress: {progress_pct:.1f}% ({total_completed}/{total_items})"
        if len(self.card_widgets) > 1:
            tray_tip += f"\nQueue: {len(self.card_widgets)} active tasks"
        self.tray_icon.setToolTip(tray_tip)

    def on_file_completed(self, task_id, msg_id):
        if task_id in self.card_widgets:
            # Add to session downloaded
            card = self.card_widgets[task_id]
            if msg_id in card.file_rows:
                # We need the size of the completed file. 
                # Let's extract it from metadata if available.
                for meta in card.files_metadata:
                    if meta["id"] == msg_id:
                        self._session_downloaded += meta.get("size", 0)
                        break
            
            self.card_widgets[task_id].mark_file_completed(msg_id)
            self.refresh_global_status()

    def remove_task(self, task_id):
        if task_id in self.card_widgets:
            reply = QMessageBox.question(self, "Remove Task", "Are you sure you want to remove this task from the queue?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
                
            card = self.card_widgets[task_id]
            # 1. Stop if running
            self.worker.pause_download(task_id)
            # 2. Remove from worker tracking & files
            from core_downloader import load_active_tasks, save_active_tasks
            tasks = load_active_tasks()
            
            # Reconstruct the logic to match the actual task data structure
            new_tasks = []
            for t in tasks:
                tk_chan = str(t.get("channel_input")).replace("-100", "", 1)
                tk_media = t.get("media_id")
                tk_topic = t.get("topic_id")
                # Construct the ID the same way we do in the worker for comparison
                gen_id = f"{tk_chan}_{tk_topic}_{tk_media}" if tk_topic else f"{tk_chan}_{tk_media}"
                # Handle the -100 prefix in task_id parameter too
                clean_tid = str(task_id).replace("-100", "", 1)
                if gen_id != clean_tid:
                    new_tasks.append(t)
            save_active_tasks(new_tasks)
            # 3. Final cleanup from UI
            card.deleteLater()
            del self.card_widgets[task_id]
            
            if not self.card_widgets:
                self.page_queue.set_controls_visible(False)

    def move_task_up(self, task_id):
        if task_id in self.card_widgets:
            card = self.card_widgets[task_id]
            idx = self.page_queue.active_layout.indexOf(card)
            if idx > 0:
                self.page_queue.active_layout.removeWidget(card)
                self.page_queue.active_layout.insertWidget(idx - 1, card)

    def move_task_down(self, task_id):
        if task_id in self.card_widgets:
            card = self.card_widgets[task_id]
            idx = self.page_queue.active_layout.indexOf(card)
            # Count includes the stretch item at the end
            if idx < self.page_queue.active_layout.count() - 2: 
                self.page_queue.active_layout.removeWidget(card)
                self.page_queue.active_layout.insertWidget(idx + 1, card)

    def reselect_task_media(self, task_id):
        # 1. Extract channel name/ID from task_id (format: ID_mediaID)
        try:
            self._reselect_task_id = task_id # Set context for the upcoming browser
            if task_id in self.card_widgets:
                self.card_widgets[task_id].set_reselect_loading(True)
                
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            
            channel_input, media_id_str = task_id.rsplit('_', 1)
            # 2. Trigger a normal fetch for this channel
            self.input_channel.setText(channel_input)
            self.on_fetch_clicked()
        except Exception as e:
            self._reselect_task_id = None
            print(f"Reselect error: {e}")

    def pause_all_downloads(self):
        for task_id, card in self.card_widgets.items():
            if not card.is_paused:
                card.toggle_pause()

    def resume_all_downloads(self):
        for task_id, card in self.card_widgets.items():
            if card.is_paused:
                card.toggle_pause()

    def re_fetch_from_history(self, channel_id):
        self.input_channel.setText(str(channel_id))
        self.switch_page("Home", 0)
        self.on_fetch_clicked()

    def logout(self):
        reply = QMessageBox.question(self, "Logout", "Are you sure you want to log out? This will pause all downloads and clear your session.", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.pause_all_downloads()
            # Clear all current cards from memory/UI
            for task_id in list(self.card_widgets.keys()):
                self.remove_task(task_id)
                
            self.worker.logout()
            
            # Clear persistent queue safely
            try:
                from core_downloader import save_active_tasks
                save_active_tasks([])
            except Exception:
                pass
                
            self.worker.signals.auth_needed.emit()
