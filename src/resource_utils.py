import os
import sys

def get_resource_path(relative_path: str) -> str:
    """Get the absolute path to a resource, supporting development, PyInstaller, and Nuitka bundles."""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller temporary extraction folder
        return os.path.join(sys._MEIPASS, relative_path)
    
    # Running as compiled binary (Nuitka or frozen executable)
    if getattr(sys, 'frozen', False) or '__compiled__' in globals():
        exe_dir = os.path.dirname(sys.executable)
        candidate = os.path.join(exe_dir, relative_path)
        if os.path.exists(candidate):
            return candidate

    # Development: Resources are relative to the 'src' directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(base_dir, relative_path)
    if os.path.exists(candidate):
        return candidate
        
    root_candidate = os.path.join(os.path.dirname(base_dir), relative_path)
    if os.path.exists(root_candidate):
        return root_candidate

    return candidate

def get_project_root() -> str:
    """Get the persistent project root where .env, config.json, and session files should be stored."""
    if getattr(sys, 'frozen', False) or '__compiled__' in globals():
        # Running as compiled binary
        return os.path.dirname(sys.executable)
    
    # Development: Root is one level above 'src/'
    # Assuming this file is in 'src/resource_utils.py'
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_app_icon():
    """
    Returns a multi-resolution QIcon with all size layers (16, 24, 32, 48, 64, 128, 256)
    loaded explicitly so the OS and Qt always render the pixel-perfect icon for title bars,
    taskbar, system tray, and alt-tab dialogs.
    """
    from PySide6.QtGui import QIcon
    from PySide6.QtCore import QSize

    icon = QIcon()
    size_map = [
        (16, os.path.join("assets", "logo_16.ico")),
        (24, os.path.join("assets", "logo_24.ico")),
        (32, os.path.join("assets", "logo_32.ico")),
        (48, os.path.join("assets", "logo_48.ico")),
        (64, os.path.join("assets", "logo_64.ico")),
        (128, os.path.join("assets", "logo_128.ico")),
        (256, os.path.join("assets", "logo_taskbar.ico")),
    ]
    for sz, rel in size_map:
        p = get_resource_path(rel)
        if os.path.exists(p):
            icon.addFile(p, QSize(sz, sz))

    multi_path = get_resource_path(os.path.join("assets", "logo.ico"))
    if os.path.exists(multi_path):
        icon.addFile(multi_path)

    return icon

def get_sidebar_logo_pixmap(size: int = 36):
    """
    Returns a crisp QPixmap specifically for the sidebar logo using assets/sidebar_logo.png,
    scaled smoothly with Qt.SmoothTransformation.
    """
    from PySide6.QtGui import QPixmap
    from PySide6.QtCore import Qt

    sidebar_png = get_resource_path(os.path.join("assets", "sidebar_logo.png"))
    if os.path.exists(sidebar_png):
        return QPixmap(sidebar_png).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    return get_logo_pixmap(size)

def get_logo_pixmap(size: int = 34):
    """
    Returns a crisp QPixmap for UI display scaled smoothly
    using high-resolution source or nearest discrete resolution.
    """
    from PySide6.QtGui import QPixmap
    from PySide6.QtCore import Qt

    # Best source for UI rendering is high-res PNG
    png_path = get_resource_path(os.path.join("assets", "logo.png"))
    if os.path.exists(png_path):
        return QPixmap(png_path).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    
    # Fallback to multi-res ICO or specific ICO
    ico_path = get_resource_path(os.path.join("assets", f"logo_{size}.ico"))
    if not os.path.exists(ico_path):
        ico_path = get_resource_path(os.path.join("assets", "logo.ico"))
    if os.path.exists(ico_path):
        return QPixmap(ico_path).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    return QPixmap()

def set_windows_taskbar_icon(hwnd: int):
    """
    Explicitly set Windows taskbar icon (ICON_BIG, 256x256) and
    titlebar icon (ICON_SMALL, 16x16) via the Win32 API.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        taskbar_ico = get_resource_path(os.path.join("assets", "logo_taskbar.ico"))
        small_ico = get_resource_path(os.path.join("assets", "logo_16.ico"))

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        if os.path.exists(taskbar_ico):
            hicon_big = ctypes.windll.user32.LoadImageW(
                None, taskbar_ico, IMAGE_ICON, 0, 0, LR_LOADFROMFILE
            )
            if hicon_big:
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)

        if os.path.exists(small_ico):
            hicon_small = ctypes.windll.user32.LoadImageW(
                None, small_ico, IMAGE_ICON, 0, 0, LR_LOADFROMFILE
            )
            if hicon_small:
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
    except Exception as e:
        print(f"Failed to set Windows taskbar icon: {e}", file=sys.stderr)

