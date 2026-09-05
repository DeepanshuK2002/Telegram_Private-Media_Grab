import os
import humanize
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QWidget, QScrollArea, QFrame, 
    QSizePolicy, QLineEdit, QDateEdit, QGridLayout, QToolButton, 
    QStackedWidget, QSpacerItem, QApplication, QCalendarWidget, QTableView
)
from PySide6.QtCore import Qt, Signal, QDate, QRegularExpression, QSize, QByteArray, QPoint
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont, QPainterPath, QPen, QBrush, QKeySequence, QPalette, QTextCharFormat
from PySide6.QtSvg import QSvgRenderer
from resource_utils import get_resource_path


# ===============================================================================
# Vercel Monochrome SVG Icons & Vector Renderer
# ===============================================================================

ICONS_SVG = {
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2" ry="2" stroke="currentColor" stroke-width="2" fill="none"/><line x1="16" y1="2" x2="16" y2="6" stroke="currentColor" stroke-width="2"/><line x1="8" y1="2" x2="8" y2="6" stroke="currentColor" stroke-width="2"/><line x1="3" y1="10" x2="21" y2="10" stroke="currentColor" stroke-width="2"/>',
    "layers": '<polygon points="12 2 2 7 12 12 22 7 12 2" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/><polyline points="2 17 12 22 22 17" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/><polyline points="2 12 12 17 22 12" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/>',
    "eye": '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke="currentColor" stroke-width="2" fill="none"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2" fill="none"/>',
    "photo": '<rect x="3" y="3" width="18" height="18" rx="2" ry="2" stroke="currentColor" stroke-width="2" fill="none"/><circle cx="8.5" cy="8.5" r="1.5" fill="currentColor"/><polyline points="21 15 16 10 5 21" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/>',
    "video": '<rect x="2" y="4" width="15" height="16" rx="2" stroke="currentColor" stroke-width="2" fill="none"/><polygon points="23 7 17 12 23 17 23 7" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" stroke-width="2" fill="none"/><polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="2" fill="none"/><line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" stroke-width="2"/><line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" stroke-width="2"/>',
    "music": '<path d="M9 18V5l12-2v13" stroke="currentColor" stroke-width="2" fill="none"/><circle cx="6" cy="18" r="3" stroke="currentColor" stroke-width="2" fill="none"/><circle cx="18" cy="16" r="3" stroke="currentColor" stroke-width="2" fill="none"/>',
    "archive": '<polyline points="21 8 21 21 3 21 3 8" stroke="currentColor" stroke-width="2" fill="none"/><rect x="1" y="3" width="22" height="5" stroke="currentColor" stroke-width="2" fill="none"/><line x1="10" y1="12" x2="14" y2="12" stroke="currentColor" stroke-width="2"/>',
    "voice": '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" stroke="currentColor" stroke-width="2" fill="none"/><path d="M19 10v2a7 7 0 0 1-14 0v-2" stroke="currentColor" stroke-width="2" fill="none"/><line x1="12" y1="19" x2="12" y2="23" stroke="currentColor" stroke-width="2"/><line x1="8" y1="23" x2="16" y2="23" stroke="currentColor" stroke-width="2"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" stroke="currentColor" stroke-width="2" fill="none"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" stroke="currentColor" stroke-width="2" fill="none"/>',
    "chat": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" stroke-width="2" fill="none"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" stroke="currentColor" stroke-width="2" fill="none"/><rect x="14" y="3" width="7" height="7" stroke="currentColor" stroke-width="2" fill="none"/><rect x="14" y="14" width="7" height="7" stroke="currentColor" stroke-width="2" fill="none"/><rect x="3" y="14" width="7" height="7" stroke="currentColor" stroke-width="2" fill="none"/>',
    "list": '<line x1="8" y1="6" x2="21" y2="6" stroke="currentColor" stroke-width="2"/><line x1="8" y1="12" x2="21" y2="12" stroke="currentColor" stroke-width="2"/><line x1="8" y1="18" x2="21" y2="18" stroke="currentColor" stroke-width="2"/><circle cx="4" cy="6" r="1" fill="currentColor"/><circle cx="4" cy="12" r="1" fill="currentColor"/><circle cx="4" cy="18" r="1" fill="currentColor"/>',
    "search": '<circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="2" fill="none"/><line x1="21" y1="21" x2="16.65" y2="16.65" stroke="currentColor" stroke-width="2"/>',
    "filter": '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" stroke="currentColor" stroke-width="2" fill="none"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="currentColor" stroke-width="2" fill="none"/><polyline points="7 10 12 15 17 10" stroke="currentColor" stroke-width="2" fill="none"/><line x1="12" y1="15" x2="12" y2="3" stroke="currentColor" stroke-width="2"/>',
    "close": '<line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2"/><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2"/>',
    "chevron_left": '<polyline points="15 18 9 12 15 6" stroke="currentColor" stroke-width="2" fill="none"/>',
    "chevron_right": '<polyline points="9 18 15 12 9 6" stroke="currentColor" stroke-width="2" fill="none"/>',
    "copy": '<rect x="9" y="9" width="13" height="13" rx="2" ry="2" stroke="currentColor" stroke-width="2" fill="none"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" stroke="currentColor" stroke-width="2" fill="none"/>',
    "play": '<polygon points="5 3 19 12 5 21 5 3" fill="currentColor"/>',
}

def render_svg_pixmap(name: str, color: str = "#000000", size: int = 20) -> QPixmap:
    """Renders a clean monochrome SVG icon into a high-DPI transparent QPixmap."""
    body = ICONS_SVG.get(name, ICONS_SVG["file"])
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}">{body}</svg>'
    svg = svg.replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return pix

def render_svg_qicon(name: str, color: str = "#000000", size: int = 20) -> QIcon:
    """Returns a QIcon made from the rendered SVG pixmap."""
    return QIcon(render_svg_pixmap(name, color, size))

def make_channel_avatar(title: str, size: int = 34, is_dark: bool = False) -> QPixmap:
    """Creates a smooth, minimalist Telegram channel profile avatar with initials."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    
    clean_title = str(title).replace("-100", "").replace("-", "").strip()
    
    # Modern Vercel muted background
    bg_color = QColor("#27272A" if is_dark else "#F4F4F5")
    border_color = QColor("#3F3F46" if is_dark else "#E4E4E7")
    
    path = QPainterPath()
    path.addEllipse(1, 1, size - 2, size - 2)
    painter.fillPath(path, bg_color)
    painter.setPen(QPen(border_color, 1.2))
    painter.drawPath(path)
    
    initial = clean_title[:2].upper() if clean_title else "TG"
    painter.setPen(QColor("#EDEDED" if is_dark else "#09090B"))
    font = QFont("Segoe UI", int(size * 0.35), QFont.Bold)
    painter.setFont(font)
    painter.drawText(0, 0, size, size, Qt.AlignCenter, initial)
    painter.end()
    return pix


# ===============================================================================
# CheckCircle - Minimalist Vercel Antialiased Checkmark Widget
# ===============================================================================
class CheckCircle(QWidget):
    """Clean Vercel-style antialiased check indicator matching style.qss."""
    def __init__(self, size=20, is_dark=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._checked = False
        self.is_dark = is_dark
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self.update()

    def isChecked(self):
        return self._checked

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        w = float(self.width())
        h = float(self.height())
        
        if self._checked:
            fill_color = QColor("#FFFFFF" if self.is_dark else "#000000")
            painter.setBrush(QBrush(fill_color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(1, 1, int(w - 2), int(h - 2), 4, 4)
            
            check_color = QColor("#000000" if self.is_dark else "#FFFFFF")
            pen = QPen(check_color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(w * 0.26, h * 0.52)
            path.lineTo(w * 0.43, h * 0.70)
            path.lineTo(w * 0.74, h * 0.32)
            painter.drawPath(path)
        else:
            bg = QColor("#18181B" if self.is_dark else "#FFFFFF")
            border = QColor("#3F3F46" if self.is_dark else "#D4D4D8")
            painter.setBrush(QBrush(bg))
            painter.setPen(QPen(border, 1.4))
            painter.drawRoundedRect(1, 1, int(w - 2), int(h - 2), 4, 4)
            
        painter.end()


# ===============================================================================
# Visual Helpers: Rounded Thumbnails & Category Configurations
# ===============================================================================

def make_rounded_thumbnail(pixmap: QPixmap, w: int, h: int, radius: int = 6) -> QPixmap:
    """Clips and rounds a pixmap to the requested width & height with antialiased corners."""
    if not pixmap or pixmap.isNull():
        return pixmap
    w = max(10, int(w))
    h = max(10, int(h))
    scaled = pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    crop_x = max(0, (scaled.width() - w) // 2)
    crop_y = max(0, (scaled.height() - h) // 2)
    cropped = scaled.copy(crop_x, crop_y, w, h)

    target = QPixmap(w, h)
    target.fill(Qt.transparent)

    painter = QPainter(target)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    path = QPainterPath()
    path.addRoundedRect(0, 0, w, h, radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, cropped)
    painter.end()

    return target


CATEGORY_CONFIG = {
    "all":   {"label": "All",    "icon": "layers",  "name": "All Media"},
    "media": {"label": "Media",  "icon": "video",   "name": "Photos & Videos"},
    "files": {"label": "Files",  "icon": "file",    "name": "Documents"},
    "music": {"label": "Audio",  "icon": "music",   "name": "Audio & Songs"},
    "zips":  {"label": "ZIPs",   "icon": "archive", "name": "Archives"},
    "voice": {"label": "Voice",  "icon": "voice",   "name": "Voice Notes"},
    "links": {"label": "Links",  "icon": "link",    "name": "Web Links"},
    "gifs":  {"label": "GIFs",   "icon": "video",   "name": "Animations"},
    "chat":  {"label": "Chat",   "icon": "chat",    "name": "Chat Messages"},
}

def get_cached_thumbnail_path(msg, channel_id=None):
    """Finds cached thumbnail in cache/thumbnails from project root or resource paths."""
    try:
        from resource_utils import get_project_root, get_resource_path
    except ImportError:
        get_project_root = lambda: os.getcwd()
        get_resource_path = lambda x: os.path.join(os.getcwd(), x)
    
    msg_id = getattr(msg, 'id', None)
    if not msg_id:
        return None
    cid = channel_id or getattr(msg, 'chat_id', None) or getattr(msg, 'peer_id', None) or ""
    cid_str = str(cid).replace("-100", "", 1) if str(cid).startswith("-100") else str(cid)
    
    candidates = [
        os.path.join(get_project_root(), "cache", "thumbnails"),
        os.path.join(get_resource_path("cache"), "thumbnails"),
        os.path.join(os.getcwd(), "cache", "thumbnails"),
    ]
    for d in candidates:
        if not os.path.isdir(d):
            continue
        if cid_str:
            target = os.path.join(d, f"{cid_str}_{msg_id}.jpg")
            if os.path.exists(target) and os.path.getsize(target) > 0:
                return target
        for fname in os.listdir(d):
            if fname.endswith(f"_{msg_id}.jpg") or fname == f"{msg_id}.jpg":
                cand = os.path.join(d, fname)
                if os.path.getsize(cand) > 0:
                    return cand
    return None


def generate_photo_thumbnail(w: int = 156, h: int = 120, is_dark: bool = False) -> QPixmap:
    """Generates a picturesque landscape photo thumbnail canvas."""
    pix = QPixmap(w, h)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    
    path = QPainterPath()
    path.addRoundedRect(0, 0, w, h, 6, 6)
    painter.setClipPath(path)
    
    # Sky gradient
    grad = QLinearGradient(0, 0, 0, h)
    if is_dark:
        grad.setColorAt(0.0, QColor("#2A2D34"))
        grad.setColorAt(1.0, QColor("#14161A"))
    else:
        grad.setColorAt(0.0, QColor("#E2E8F0"))
        grad.setColorAt(1.0, QColor("#CBD5E1"))
    painter.fillRect(0, 0, w, h, grad)
    
    # Sun / Moon
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#FBBF24" if not is_dark else "#F3F4F6"))
    painter.drawEllipse(w - int(w * 0.24), int(h * 0.13), int(w * 0.09), int(w * 0.09))
    
    # Mountain 1
    m1 = QPainterPath()
    m1.moveTo(int(w * 0.06), h)
    m1.lineTo(int(w * 0.35), int(h * 0.38))
    m1.lineTo(int(w * 0.64), h)
    m1.closeSubpath()
    painter.setBrush(QColor("#94A3B8" if not is_dark else "#334155"))
    painter.drawPath(m1)
    
    # Mountain 2
    m2 = QPainterPath()
    m2.moveTo(int(w * 0.42), h)
    m2.lineTo(int(w * 0.74), int(h * 0.29))
    m2.lineTo(int(w * 1.06), h)
    m2.closeSubpath()
    painter.setBrush(QColor("#64748B" if not is_dark else "#1E293B"))
    painter.drawPath(m2)
    
    painter.end()
    return pix


def generate_video_thumbnail(w: int = 156, h: int = 120, is_dark: bool = False) -> QPixmap:
    """Generates a dark cinema widescreen video thumbnail with frosted play badge."""
    pix = QPixmap(w, h)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    
    path = QPainterPath()
    path.addRoundedRect(0, 0, w, h, 6, 6)
    painter.setClipPath(path)
    
    # Cinema backdrop
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0.0, QColor("#18181B"))
    grad.setColorAt(0.5, QColor("#09090B"))
    grad.setColorAt(1.0, QColor("#18181B"))
    painter.fillRect(0, 0, w, h, grad)
    
    # Frosted Play Circle
    cx, cy, r = w / 2, h / 2, min(w, h) * 0.16
    painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
    painter.setBrush(QColor(0, 0, 0, 140))
    painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))
    
    # Play Triangle
    triangle = QPainterPath()
    tw = r * 0.5
    triangle.moveTo(cx - tw * 0.5, cy - tw * 0.7)
    triangle.lineTo(cx + tw * 0.7, cy)
    triangle.lineTo(cx - tw * 0.5, cy + tw * 0.7)
    triangle.closeSubpath()
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#FFFFFF"))
    painter.drawPath(triangle)
    
    painter.end()
    return pix


def detect_file_type_info(msg, is_dark=False):
    """Accurately detects type name, icon name, and background color for any Telegram message."""
    title = ""
    if getattr(msg, 'is_mock', False):
        title = getattr(msg, 'message', '')
    elif getattr(msg, 'file', None) and getattr(msg.file, 'name', None):
        title = msg.file.name
    elif getattr(msg, 'message', None):
        title = msg.message

    title_lower = str(title).lower().strip()
    ext = os.path.splitext(title_lower)[1]

    icon_name = "file"
    type_name = "DOC"
    bg_color = "#18181B" if is_dark else "#FAFAFA"

    # Photo check
    if ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"] or getattr(msg, 'photo', None) or "photo" in title_lower:
        return "photo", "PHOTO", bg_color

    # Video check
    if ext in [".mp4", ".mkv", ".avi", ".mov", ".webm"] or getattr(msg, 'video', None) or "video" in title_lower:
        return "video", "VIDEO", bg_color

    # Audio check
    if ext in [".mp3", ".flac", ".wav", ".aac", ".m4a"] or getattr(msg, 'audio', None) or "audio" in title_lower:
        return "music", "AUDIO", bg_color

    # Archive check
    if ext in [".zip", ".rar", ".7z", ".tar", ".gz"] or "album" in title_lower or "zip" in title_lower:
        return "archive", "ZIP", bg_color

    # Link check
    if "http://" in title_lower or "https://" in title_lower or getattr(msg, 'web_preview', None):
        return "link", "LINK", bg_color

    # Document check
    if ext in [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx"] or getattr(msg, 'document', None):
        if ext == ".pdf": return "file", "PDF", bg_color
        return "file", "DOC", bg_color

    # Mock media type fallback
    if getattr(msg, 'is_mock', False):
        cat = getattr(msg, 'media_type', '').lower()
        if cat in ['media', 'video']: return "video", "VIDEO", bg_color
        if cat in ['photo', 'photos', 'images']: return "photo", "PHOTO", bg_color
        if cat == 'music': return "music", "AUDIO", bg_color
        if cat == 'zips': return "archive", "ZIP", bg_color
        if cat == 'links': return "link", "LINK", bg_color
        if cat == 'voice': return "voice", "VOICE", bg_color
        if cat == 'chat': return "chat", "CHAT", bg_color

    return icon_name, type_name, bg_color


def generate_video_preview_pixmap(base_pixmap: QPixmap, w: int = 500, h: int = 340, is_dark: bool = False, title: str = "") -> QPixmap:
    """Creates a high-fidelity video preview canvas with centered play button."""
    target = QPixmap(w, h)
    target.fill(Qt.transparent)
    p = QPainter(target)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    
    if base_pixmap and not base_pixmap.isNull():
        scaled = base_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (w - scaled.width()) // 2
        y = (h - scaled.height()) // 2
        
        clip = QPainterPath()
        clip.addRoundedRect(x, y, scaled.width(), scaled.height(), 6, 6)
        p.setClipPath(clip)
        p.drawPixmap(x, y, scaled)
        p.setClipping(False)
        
        # Frosted glass play circle overlay
        play_size = 46
        px = w // 2 - play_size // 2
        py = h // 2 - play_size // 2
        p.setBrush(QBrush(QColor(0, 0, 0, 160)))
        p.setPen(QPen(QColor(255, 255, 255, 120), 1.5))
        p.drawEllipse(px, py, play_size, play_size)
        
        tri = QPainterPath()
        tri.moveTo(px + play_size * 0.40, py + play_size * 0.30)
        tri.lineTo(px + play_size * 0.70, py + play_size * 0.50)
        tri.lineTo(px + play_size * 0.40, py + play_size * 0.70)
        tri.closeSubpath()
        p.fillPath(tri, QColor("#FFFFFF"))
    else:
        # Sleek dark video player preview canvas
        p.setBrush(QBrush(QColor("#18181B" if is_dark else "#09090B")))
        p.setPen(QPen(QColor("#27272A" if is_dark else "#3F3F46"), 1.2))
        p.drawRoundedRect(2, 2, w - 4, h - 4, 6, 6)
        
        play_size = 52
        px = w // 2 - play_size // 2
        py = h // 2 - play_size // 2 - 12
        p.setBrush(QBrush(QColor(255, 255, 255, 25)))
        p.setPen(QPen(QColor(255, 255, 255, 90), 1.5))
        p.drawEllipse(px, py, play_size, play_size)
        
        tri = QPainterPath()
        tri.moveTo(px + play_size * 0.40, py + play_size * 0.30)
        tri.lineTo(px + play_size * 0.70, py + play_size * 0.50)
        tri.lineTo(px + play_size * 0.40, py + play_size * 0.70)
        tri.closeSubpath()
        p.fillPath(tri, QColor("#FFFFFF"))
        
        p.setPen(QColor("#EDEDED"))
        p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        p.drawText(0, py + play_size + 14, w, 20, Qt.AlignCenter, "VIDEO PREVIEW")
        
        p.setPen(QColor("#71717A"))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(0, py + play_size + 34, w, 18, Qt.AlignCenter, "Instant MTProto Telegram Stream Ready")
        
    p.end()
    return target


def generate_photo_preview_pixmap(base_pixmap: QPixmap, w: int = 500, h: int = 340, is_dark: bool = False, title: str = "") -> QPixmap:
    """Creates a high-fidelity photo preview canvas."""
    target = QPixmap(w, h)
    target.fill(Qt.transparent)
    p = QPainter(target)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    
    if base_pixmap and not base_pixmap.isNull():
        scaled = base_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (w - scaled.width()) // 2
        y = (h - scaled.height()) // 2
        
        clip = QPainterPath()
        clip.addRoundedRect(x, y, scaled.width(), scaled.height(), 6, 6)
        p.setClipPath(clip)
        p.drawPixmap(x, y, scaled)
    else:
        p.setBrush(QBrush(QColor("#18181B" if is_dark else "#F4F4F5")))
        p.setPen(QPen(QColor("#27272A" if is_dark else "#E4E4E7"), 1.2))
        p.drawRoundedRect(2, 2, w - 4, h - 4, 6, 6)
        
        icon_pix = render_svg_pixmap("photo", color="#A1A1AA" if is_dark else "#71717A", size=52)
        p.drawPixmap((w - 52) // 2, (h - 52) // 2 - 18, icon_pix)
        
        p.setPen(QColor("#EDEDED" if is_dark else "#09090B"))
        p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        p.drawText(0, (h - 52) // 2 + 44, w, 20, Qt.AlignCenter, "HIGH-RES PHOTO PREVIEW")
        
        p.setPen(QColor("#71717A"))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(0, (h - 52) // 2 + 66, w, 18, Qt.AlignCenter, "Telegram photo ready for download")
        
    p.end()
    return target


# ===============================================================================
# MediaPreviewDialog - Frameless Minimalist Media Preview Modal
# ===============================================================================
class MediaPreviewDialog(QDialog):
    """Frameless minimalist Vercel media preview modal with full photo/video preview,
    clean # badge (no background), bottom compact caption, and borderless ghost nav buttons."""
    selectionToggled = Signal(object, bool)

    def __init__(self, current_msg, all_msgs=None, is_dark=False, is_selected=False, initial_pixmap=None, parent=None):
        super().__init__(parent)
        self.all_msgs = all_msgs or [current_msg]
        self.current_idx = 0
        self._pixmap_cache = {}
        self._drag_pos = None

        if initial_pixmap and not initial_pixmap.isNull():
            self._pixmap_cache[getattr(current_msg, 'id', 0)] = initial_pixmap

        for i, m in enumerate(self.all_msgs):
            if getattr(m, 'id', None) == getattr(current_msg, 'id', None):
                self.current_idx = i
                break

        self.is_dark = is_dark
        self.is_selected = is_selected

        # Requirement 8: Remove title bar from media preview
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self.setMinimumSize(780, 560)
        self.resize(860, 580)
        self.setup_ui()
        self.load_current_media()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() <= 54:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def setup_ui(self):
        bg = "#000000" if self.is_dark else "#FFFFFF"
        header_bg = "#09090B" if self.is_dark else "#FFFFFF"
        border = "#27272A" if self.is_dark else "#E4E4E7"
        text_pri = "#EDEDED" if self.is_dark else "#09090B"
        text_sec = "#A1A1AA" if self.is_dark else "#71717A"
        pill_bg = "#18181B" if self.is_dark else "#F4F4F5"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                color: {text_pri};
                border: 1px solid {border};
                border-radius: 8px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }}
            QFrame#PreviewHeader {{
                background-color: {header_bg};
                border-bottom: 1px solid {border};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
            QLabel#PreviewHeaderTitle {{
                color: {text_pri};
                font-size: 14px;
                font-weight: 600;
            }}
            /* Requirement 5: In media preview section remove the background around the text # */
            QLabel#PreviewIdBadge {{
                background: transparent;
                border: none;
                color: {text_sec};
                font-size: 13px;
                font-weight: 500;
                font-family: "Consolas", monospace;
                padding: 0px 2px;
            }}
            QFrame#PreviewViewport {{
                background-color: {"#09090B" if self.is_dark else "#FAFAFA"};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            QFrame#PreviewSidebar {{
                background-color: {"#09090B" if self.is_dark else "#FFFFFF"};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            QLabel#SidebarHeader {{
                color: {text_pri};
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#MetaValue {{
                color: {text_pri};
                font-size: 12px;
                font-weight: 600;
            }}
            /* Requirement 7: Remove border and background of prev and next buttons, just hover text */
            QPushButton#GhostNavBtn {{
                background-color: transparent;
                border: none;
                color: {text_sec};
                font-size: 12px;
                font-weight: 500;
                padding: 4px 10px;
            }}
            QPushButton#GhostNavBtn:hover {{
                background-color: transparent;
                border: none;
                color: {text_pri};
            }}
            QPushButton#GhostNavBtn:disabled {{
                color: {"#3F3F46" if self.is_dark else "#D4D4D8"};
            }}
            QPushButton#VercelActionBtn {{
                background-color: {"#FFFFFF" if self.is_dark else "#000000"};
                color: {"#000000" if self.is_dark else "#FFFFFF"};
                border: 1px solid transparent;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
                padding: 8px 16px;
                min-height: 36px;
            }}
            QPushButton#VercelActionBtn:hover {{
                background-color: {"#E4E4E7" if self.is_dark else "#27272A"};
            }}
            QPushButton#VercelActionBtnSecondary {{
                background-color: {pill_bg};
                color: {text_pri};
                border: 1px solid {border};
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
                padding: 8px 16px;
                min-height: 36px;
            }}
            QPushButton#VercelActionBtnSecondary:hover {{
                background-color: {"#27272A" if self.is_dark else "#E4E4E7"};
                border-color: {"#3F3F46" if self.is_dark else "#D4D4D8"};
            }}
            QFrame#BottomCaptionBox {{
                background-color: {pill_bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
        """)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        root_frame = QFrame(self)
        root_frame.setObjectName("PreviewWindowFrame")
        outer_layout.addWidget(root_frame)

        layout = QVBoxLayout(root_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setObjectName("PreviewHeader")
        header.setFixedHeight(50)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(18, 6, 18, 6)
        h_layout.setSpacing(10)

        self.lbl_head_icon = QLabel()
        self.lbl_head_icon.setFixedSize(20, 20)
        h_layout.addWidget(self.lbl_head_icon)

        self.lbl_head_title = QLabel("Media Preview")
        self.lbl_head_title.setObjectName("PreviewHeaderTitle")
        h_layout.addWidget(self.lbl_head_title)

        # Requirement 5: remove background around text #
        self.lbl_head_badge = QLabel("#0")
        self.lbl_head_badge.setObjectName("PreviewIdBadge")
        h_layout.addWidget(self.lbl_head_badge)

        h_layout.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
                color: {text_sec};
            }}
            QPushButton:hover {{
                background-color: {pill_bg};
                color: {text_pri};
            }}
        """)
        btn_close.clicked.connect(self.close)
        h_layout.addWidget(btn_close)

        layout.addWidget(header)

        # Body: Viewport & Details Sidebar
        body_frame = QWidget()
        b_layout = QHBoxLayout(body_frame)
        b_layout.setContentsMargins(16, 14, 16, 14)
        b_layout.setSpacing(14)

        left_box = QVBoxLayout()
        left_box.setSpacing(10)

        self.viewport = QFrame()
        self.viewport.setObjectName("PreviewViewport")
        v_layout = QVBoxLayout(self.viewport)
        v_layout.setContentsMargins(8, 8, 8, 8)
        v_layout.setAlignment(Qt.AlignCenter)

        self.lbl_preview_display = QLabel()
        self.lbl_preview_display.setAlignment(Qt.AlignCenter)
        self.lbl_preview_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        v_layout.addWidget(self.lbl_preview_display)

        left_box.addWidget(self.viewport, stretch=1)

        # Navigation Toolbar: Requirement 7 (borderless, transparent, just hover text)
        nav_bar = QHBoxLayout()
        nav_bar.setSpacing(8)

        self.btn_prev = QPushButton("← Previous")
        self.btn_prev.setObjectName("GhostNavBtn")
        self.btn_prev.setCursor(Qt.PointingHandCursor)
        self.btn_prev.clicked.connect(self.prev_media)
        nav_bar.addWidget(self.btn_prev)

        self.lbl_counter = QLabel("1 of 1")
        self.lbl_counter.setAlignment(Qt.AlignCenter)
        self.lbl_counter.setStyleSheet(f"color: {text_sec}; font-size: 11px; font-weight: 500;")
        nav_bar.addWidget(self.lbl_counter, stretch=1)

        self.btn_next = QPushButton("Next →")
        self.btn_next.setObjectName("GhostNavBtn")
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.clicked.connect(self.next_media)
        nav_bar.addWidget(self.btn_next)

        left_box.addLayout(nav_bar)
        b_layout.addLayout(left_box, stretch=3)

        # Right Sidebar: Metadata & Actions
        self.sidebar = QFrame()
        self.sidebar.setObjectName("PreviewSidebar")
        self.sidebar.setFixedWidth(260)
        s_layout = QVBoxLayout(self.sidebar)
        s_layout.setContentsMargins(14, 14, 14, 14)
        s_layout.setSpacing(12)

        lbl_side_title = QLabel("Metadata & Attributes")
        lbl_side_title.setObjectName("SidebarHeader")
        s_layout.addWidget(lbl_side_title)

        self.lbl_meta_name = self._create_meta_row(s_layout, "FILE NAME", "-")
        self.lbl_meta_type = self._create_meta_row(s_layout, "MEDIA TYPE", "-")
        self.lbl_meta_size = self._create_meta_row(s_layout, "FILE SIZE", "-")
        self.lbl_meta_date = self._create_meta_row(s_layout, "MESSAGE DATE", "-")
        self.lbl_meta_id   = self._create_meta_row(s_layout, "TELEGRAM ID", "-")

        s_layout.addStretch()

        self.btn_toggle_select = QPushButton("Select for Download")
        self.btn_toggle_select.setObjectName("VercelActionBtn")
        self.btn_toggle_select.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_select.clicked.connect(self._toggle_selection)
        s_layout.addWidget(self.btn_toggle_select)

        btn_copy_info = QPushButton("Copy File Info")
        btn_copy_info.setObjectName("VercelActionBtnSecondary")
        btn_copy_info.setIcon(render_svg_qicon("copy", text_pri, 13))
        btn_copy_info.setCursor(Qt.PointingHandCursor)
        btn_copy_info.clicked.connect(self._copy_info)
        s_layout.addWidget(btn_copy_info)

        b_layout.addWidget(self.sidebar)
        layout.addWidget(body_frame, stretch=1)

    def _create_meta_row(self, layout, label, value):
        text_sec = "#A1A1AA" if self.is_dark else "#71717A"
        row = QVBoxLayout()
        row.setSpacing(2)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {text_sec}; font-size: 10px; font-weight: 600; letter-spacing: 0.05em;")
        val = QLabel(value)
        val.setObjectName("MetaValue")
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(lbl)
        row.addWidget(val)
        layout.addLayout(row)
        return val

    def load_current_media(self):
        if not self.all_msgs or self.current_idx < 0 or self.current_idx >= len(self.all_msgs):
            return

        msg = self.all_msgs[self.current_idx]
        total = len(self.all_msgs)
        self.lbl_counter.setText(f"{self.current_idx + 1} of {total}")
        self.btn_prev.setEnabled(self.current_idx > 0)
        self.btn_next.setEnabled(self.current_idx < total - 1)

        msg_id = getattr(msg, 'id', '0')
        # Requirement 5: remove background around text #
        self.lbl_head_badge.setText(f"#{msg_id}")
        self.lbl_meta_id.setText(f"Message #{msg_id}")

        icon_name, type_name, _ = detect_file_type_info(msg, is_dark=self.is_dark)
        self.lbl_head_icon.setPixmap(render_svg_pixmap(icon_name, color="#EDEDED" if self.is_dark else "#09090B", size=18))

        title = ""
        size_bytes = 0
        caption = ""

        if getattr(msg, 'is_mock', False):
            title = getattr(msg, 'message', '')
            size_bytes = getattr(msg, 'size', 0)
            caption = getattr(msg, 'message', '')
        else:
            if getattr(msg, 'file', None) and getattr(msg.file, 'name', None):
                title = msg.file.name
            elif getattr(msg, 'message', None):
                title = msg.message.split('\n')[0][:50]

            if getattr(msg, 'message', None):
                caption = msg.message

            if getattr(msg, 'file', None):
                size_bytes = msg.file.size
            elif getattr(msg, 'document', None):
                size_bytes = msg.document.size
            elif getattr(msg, 'photo', None):
                try: size_bytes = msg.photo.sizes[-1].size
                except: size_bytes = 0

        if not title:
            title = f"Telegram Item #{msg_id}"

        self.lbl_head_title.setText(f"Preview: {title[:42]}")
        self.lbl_meta_name.setText(title)
        self.lbl_meta_type.setText(type_name)
        self.lbl_meta_size.setText(humanize.naturalsize(size_bytes) if size_bytes else "0 B")

        m_date = getattr(msg, 'date', None)
        date_str = str(m_date)[:19] if m_date else "Unknown"
        self.lbl_meta_date.setText(date_str)

        # Requirement 4: Make sure for photos and video there will be a preview
        pix = self._pixmap_cache.get(msg_id, None)
        if not pix or pix.isNull():
            cid = getattr(msg, 'chat_id', None) or getattr(msg, 'peer_id', None) or "tg"
            cid_str = str(cid).replace("-100", "", 1)
            cache_file = os.path.join(get_resource_path("cache"), "thumbnails", f"{cid_str}_{msg_id}.jpg")
            if os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
                pix = QPixmap(cache_file)
                if pix and not pix.isNull():
                    self._pixmap_cache[msg_id] = pix

        # Render preview canvas based on media type
        if type_name == "VIDEO":
            video_preview = generate_video_preview_pixmap(pix, 480, 330, is_dark=self.is_dark, title=title)
            self.lbl_preview_display.setPixmap(video_preview)
        elif type_name == "PHOTO":
            photo_preview = generate_photo_preview_pixmap(pix, 480, 330, is_dark=self.is_dark, title=title)
            self.lbl_preview_display.setPixmap(photo_preview)
        elif pix and not pix.isNull():
            scaled = pix.scaled(480, 330, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            rounded = make_rounded_thumbnail(scaled, scaled.width(), scaled.height(), radius=6)
            self.lbl_preview_display.setPixmap(rounded)
        else:
            # Document/Audio/Archive clean preview card
            placeholder = QPixmap(360, 240)
            placeholder.fill(Qt.transparent)
            painter = QPainter(placeholder)
            painter.setRenderHint(QPainter.Antialiasing, True)
            
            card_bg = QColor("#18181B" if self.is_dark else "#F4F4F5")
            card_border = QColor("#27272A" if self.is_dark else "#E4E4E7")
            painter.setBrush(QBrush(card_bg))
            painter.setPen(QPen(card_border, 1.2))
            painter.drawRoundedRect(2, 2, 356, 236, 6, 6)
            
            icon_color = "#A1A1AA" if self.is_dark else "#71717A"
            icon_pix = render_svg_pixmap(icon_name, color=icon_color, size=52)
            painter.drawPixmap(int((360 - 52) / 2), 64, icon_pix)
            
            painter.setPen(QColor("#EDEDED" if self.is_dark else "#09090B"))
            painter.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
            painter.drawText(0, 134, 360, 24, Qt.AlignCenter, type_name)
            
            painter.setPen(QColor("#71717A"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(0, 160, 360, 20, Qt.AlignCenter, "Instant MTProto Telegram Preview")
            painter.end()
            self.lbl_preview_display.setPixmap(placeholder)

        self._update_select_btn_text()

    def prev_media(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self.load_current_media()

    def next_media(self):
        if self.current_idx < len(self.all_msgs) - 1:
            self.current_idx += 1
            self.load_current_media()

    def _update_select_btn_text(self):
        if self.is_selected:
            self.btn_toggle_select.setText("✓ Selected for Download")
            self.btn_toggle_select.setStyleSheet(f"""
                background-color: {"#FFFFFF" if self.is_dark else "#000000"};
                color: {"#000000" if self.is_dark else "#FFFFFF"};
                border: 1px solid transparent;
                border-radius: 6px;
                font-weight: 600;
            """)
        else:
            self.btn_toggle_select.setText("Select for Download")
            self.btn_toggle_select.setStyleSheet(f"""
                background-color: {"#18181B" if self.is_dark else "#FFFFFF"};
                color: {"#EDEDED" if self.is_dark else "#09090B"};
                border: 1px solid {"#27272A" if self.is_dark else "#E4E4E7"};
                border-radius: 6px;
                font-weight: 500;
            """)

    def _toggle_selection(self):
        self.is_selected = not self.is_selected
        self._update_select_btn_text()
        if self.all_msgs:
            msg = self.all_msgs[self.current_idx]
            self.selectionToggled.emit(msg, self.is_selected)

    def _copy_info(self):
        if not self.all_msgs: return
        msg = self.all_msgs[self.current_idx]
        caption = getattr(msg, 'message', '') or ''
        text = f"ID: {getattr(msg, 'id', '')}\nName: {self.lbl_meta_name.text()}\nSize: {self.lbl_meta_size.text()}\nDate: {self.lbl_meta_date.text()}"
        if caption:
            text += f"\nCaption: {caption}"
        QApplication.clipboard().setText(text)

    def _copy_caption(self):
        if not self.all_msgs: return
        msg = self.all_msgs[self.current_idx]
        caption = getattr(msg, 'message', '') or ''
        if caption:
            QApplication.clipboard().setText(caption)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left or event.key() == Qt.Key_A:
            self.prev_media()
        elif event.key() == Qt.Key_Right or event.key() == Qt.Key_D:
            self.next_media()
        elif event.key() == Qt.Key_Space:
            self._toggle_selection()
        elif event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


# ===============================================================================
# BulkCategoryCard - Interactive Selection Card for Bulk Mode
# ===============================================================================
class BulkCategoryCard(QFrame):
    """Clean Vercel WhiteCard for Bulk Download categories."""
    stateChanged = Signal(bool)

    def __init__(self, title, desc, icon_name, media_id, is_checked=False, is_dark=False, parent=None):
        super().__init__(parent)
        self.media_id = media_id
        self.icon_name = icon_name
        self.is_dark = is_dark
        self._checked = is_checked
        self.setObjectName("BulkCategoryCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(70)
        self.setup_ui(title, desc)
        self._update_style()

    def setup_ui(self, title, desc):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(14)

        self.icon_box = QLabel()
        self.icon_box.setObjectName("CategoryIconBox")
        self.icon_box.setFixedSize(38, 38)
        self.icon_box.setAlignment(Qt.AlignCenter)
        
        icon_color = "#EDEDED" if self.is_dark else "#09090B"
        self.icon_box.setPixmap(render_svg_pixmap(self.icon_name, color=icon_color, size=20))
        layout.addWidget(self.icon_box)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setAlignment(Qt.AlignVCenter)

        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("CategoryTitle")
        text_layout.addWidget(self.lbl_title)

        self.lbl_desc = QLabel(desc)
        self.lbl_desc.setObjectName("CategoryDesc")
        text_layout.addWidget(self.lbl_desc)

        layout.addLayout(text_layout, stretch=1)

        self.check_indicator = CheckCircle(20, is_dark=self.is_dark)
        layout.addWidget(self.check_indicator)

    def _update_style(self):
        self.setProperty("checked", "true" if self._checked else "false")
        self.check_indicator.setChecked(self._checked)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self._update_style()
        self.stateChanged.emit(self._checked)
        super().mousePressEvent(event)

    def setChecked(self, state):
        if self._checked != state:
            self._checked = state
            self._update_style()
            self.stateChanged.emit(self._checked)

    def isChecked(self):
        return self._checked


# ===============================================================================
# MediaGridItem - Minimalist Vercel Grid Card with Badges & Thumbnail
# ===============================================================================
class MediaGridItem(QFrame):
    """Minimalist Vercel-style grid item with monochrome vector icons,
    metadata badges, checkmark indicator, and instant preview action."""
    stateChanged = Signal(bool)
    previewRequested = Signal(object)

    def __init__(self, msg, is_dark=False, parent=None):
        super().__init__(parent)
        self.msg = msg
        self.is_dark = is_dark
        self._checked = False
        self._pixmap = None
        self.setObjectName("MediaGridItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(168, 208)
        self.setup_ui()
        self._update_check_visual()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Thumbnail Container
        self.thumb_container = QFrame()
        self.thumb_container.setObjectName("GridThumbBox")
        self.thumb_container.setFixedHeight(120)
        self.thumb_container.setStyleSheet("border-radius: 6px; background: transparent;")

        self.lbl_thumb = QLabel(self.thumb_container)
        self.lbl_thumb.setFixedSize(156, 120)
        self.lbl_thumb.setAlignment(Qt.AlignCenter)

        icon_name, type_name, bg_color = detect_file_type_info(self.msg, is_dark=self.is_dark)
        self._type_name = type_name
        self._icon_name = icon_name

        # Check for cached thumbnail file on disk
        cache_file = get_cached_thumbnail_path(self.msg)
        if cache_file and os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
            pix = QPixmap(cache_file)
            if pix and not pix.isNull():
                self._pixmap = pix
                self.lbl_thumb.setPixmap(make_rounded_thumbnail(pix, 156, 120, radius=6))

        if not self._pixmap:
            if type_name == "PHOTO":
                self._pixmap = generate_photo_thumbnail(156, 120, is_dark=self.is_dark)
                self.lbl_thumb.setPixmap(self._pixmap)
            elif type_name == "VIDEO":
                self._pixmap = generate_video_thumbnail(156, 120, is_dark=self.is_dark)
                self.lbl_thumb.setPixmap(self._pixmap)
            else:
                icon_color = "#A1A1AA" if self.is_dark else "#71717A"
                self.lbl_thumb.setPixmap(render_svg_pixmap(icon_name, color=icon_color, size=32))
                self.lbl_thumb.setStyleSheet(f"""
                    QLabel {{
                        border-radius: 6px;
                        background-color: {bg_color};
                        border: 1px solid {"#27272A" if self.is_dark else "#E4E4E7"};
                    }}
                """)

        # Overlay 1: Checkbox Top-Left
        self.check_indicator = CheckCircle(20, is_dark=self.is_dark, parent=self.thumb_container)
        self.check_indicator.move(6, 6)

        # Overlay 2: Type Badge Top-Right
        self.lbl_type_badge = QLabel(self.thumb_container)
        self.lbl_type_badge.setObjectName("GridTypeBadge")
        self.lbl_type_badge.setText(type_name)
        self.lbl_type_badge.setAlignment(Qt.AlignCenter)
        self.lbl_type_badge.setFixedHeight(18)
        self.lbl_type_badge.adjustSize()
        badge_w = max(36, self.lbl_type_badge.width() + 10)
        self.lbl_type_badge.setFixedWidth(badge_w)
        self.lbl_type_badge.move(156 - badge_w - 6, 6)

        # Overlay 3: Size Badge Bottom-Left
        size_str = self._get_size_str()
        self.lbl_meta_badge = QLabel(self.thumb_container)
        self.lbl_meta_badge.setObjectName("GridMetaBadge")
        self.lbl_meta_badge.setText(size_str)
        self.lbl_meta_badge.setAlignment(Qt.AlignCenter)
        self.lbl_meta_badge.setFixedHeight(18)
        self.lbl_meta_badge.adjustSize()
        meta_w = max(42, self.lbl_meta_badge.width() + 8)
        self.lbl_meta_badge.setFixedWidth(meta_w)
        self.lbl_meta_badge.move(6, 120 - 18 - 6)

        # Overlay 4: Dedicated Preview Button Bottom-Right
        self.btn_preview = QPushButton(self.thumb_container)
        self.btn_preview.setObjectName("GridPreviewBtn")
        self.btn_preview.setFixedSize(24, 24)
        eye_color = "#EDEDED" if self.is_dark else "#09090B"
        self.btn_preview.setIcon(render_svg_qicon("eye", eye_color, 13))
        self.btn_preview.setToolTip("Preview media & details")
        self.btn_preview.setCursor(Qt.PointingHandCursor)
        self.btn_preview.move(156 - 24 - 6, 120 - 24 - 6)
        self.btn_preview.clicked.connect(lambda: self.previewRequested.emit(self.msg))

        layout.addWidget(self.thumb_container)

        title_text = self._get_title_text()
        self.lbl_title = QLabel(title_text)
        self.lbl_title.setObjectName("GridItemTitle")
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setFixedHeight(34)
        self.lbl_title.setToolTip(f"{title_text} (ID: #{getattr(self.msg, 'id', '')})")
        layout.addWidget(self.lbl_title)

        date_str = self._get_date_str()
        self.lbl_date = QLabel(date_str)
        self.lbl_date.setObjectName("GridItemDate")
        layout.addWidget(self.lbl_date)

    def _get_size_str(self):
        msg_size = 0
        if getattr(self.msg, 'is_mock', False):
            msg_size = getattr(self.msg, 'size', 0)
        elif getattr(self.msg, 'file', None):
            msg_size = self.msg.file.size
        elif getattr(self.msg, 'document', None):
            msg_size = self.msg.document.size
        elif getattr(self.msg, 'photo', None):
            try: msg_size = self.msg.photo.sizes[-1].size
            except: msg_size = 0
        return humanize.naturalsize(msg_size) if msg_size else "0 B"

    def _get_title_text(self):
        title = ""
        if getattr(self.msg, 'is_mock', False):
            title = getattr(self.msg, 'message', '')
        elif getattr(self.msg, 'file', None) and getattr(self.msg.file, 'name', None):
            title = self.msg.file.name
        elif getattr(self.msg, 'message', None):
            title = self.msg.message.replace('\n', ' ').strip()
        if not title:
            title = f"Message #{getattr(self.msg, 'id', '0')}"
        return title

    def _get_date_str(self):
        m_date = getattr(self.msg, 'date', None)
        if not m_date: return ""
        if isinstance(m_date, str):
            return m_date[:10]
        try:
            return m_date.strftime("%b %d, %Y")
        except:
            return str(m_date)[:10]

    def set_thumbnail(self, pixmap):
        if pixmap and not pixmap.isNull():
            rounded = make_rounded_thumbnail(pixmap, 156, 120, radius=6)
            self.lbl_thumb.setPixmap(rounded)
            self._pixmap = pixmap

    def mouseDoubleClickEvent(self, event):
        self.previewRequested.emit(self.msg)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self._update_check_visual()
        self.stateChanged.emit(self._checked)
        super().mousePressEvent(event)

    def _update_check_visual(self):
        self.setProperty("checked", "true" if self._checked else "false")
        self.check_indicator.setChecked(self._checked)
        self.style().unpolish(self)
        self.style().polish(self)

    def setChecked(self, state):
        if self._checked != state:
            self._checked = state
            self._update_check_visual()

    def isChecked(self):
        return self._checked


# ===============================================================================
# SelectableMediaRow - Minimalist Vercel List Row Item
# ===============================================================================
class SelectableMediaRow(QFrame):
    """Clean Vercel compact list row item with metadata pills and quick preview."""
    stateChanged = Signal(bool)
    previewRequested = Signal(object)

    def __init__(self, msg, is_dark=False, parent=None):
        super().__init__(parent)
        self.msg = msg
        self.is_dark = is_dark
        self._pixmap = None
        self._checked = False
        self.setObjectName("SelectableRow")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(56)
        self.setup_ui()
        self._update_check_visual()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 14, 6)
        layout.setSpacing(12)

        self.check_indicator = CheckCircle(20, is_dark=self.is_dark)
        layout.addWidget(self.check_indicator)

        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedSize(38, 38)
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_thumb.setObjectName("RowThumbBox")

        icon_name, type_name, bg_color = detect_file_type_info(self.msg, is_dark=self.is_dark)
        cache_file = get_cached_thumbnail_path(self.msg)
        if cache_file and os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
            pix = QPixmap(cache_file)
            if pix and not pix.isNull():
                self._pixmap = pix
                self.lbl_thumb.setPixmap(make_rounded_thumbnail(pix, 38, 38, radius=6))

        if not self._pixmap:
            if type_name == "PHOTO":
                self.lbl_thumb.setPixmap(generate_photo_thumbnail(38, 38, is_dark=self.is_dark))
            elif type_name == "VIDEO":
                self.lbl_thumb.setPixmap(generate_video_thumbnail(38, 38, is_dark=self.is_dark))
            else:
                icon_color = "#A1A1AA" if self.is_dark else "#71717A"
                self.lbl_thumb.setPixmap(render_svg_pixmap(icon_name, color=icon_color, size=20))
                self.lbl_thumb.setStyleSheet(f"""
                    border-radius: 6px;
                    background-color: {bg_color};
                    border: 1px solid {"#27272A" if self.is_dark else "#E4E4E7"};
                """)
        layout.addWidget(self.lbl_thumb)

        info_stack = QVBoxLayout()
        info_stack.setSpacing(2)
        info_stack.setAlignment(Qt.AlignVCenter)

        title_text = self._get_title_text()
        self.lbl_title = QLabel(title_text)
        self.lbl_title.setObjectName("RowItemTitle")
        info_stack.addWidget(self.lbl_title)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)

        lbl_type = QLabel(type_name)
        lbl_type.setObjectName("TypePill")

        lbl_size = QLabel(self._get_size_str())
        lbl_size.setObjectName("SizeBadge")

        lbl_date = QLabel(self._get_date_str())
        lbl_date.setObjectName("RowItemDate")

        meta_row.addWidget(lbl_type)
        meta_row.addWidget(lbl_size)
        meta_row.addWidget(lbl_date)
        meta_row.addStretch()
        info_stack.addLayout(meta_row)

        layout.addLayout(info_stack, stretch=1)

        self.btn_preview = QPushButton("Preview")
        self.btn_preview.setObjectName("RowPreviewBtn")
        self.btn_preview.setIcon(render_svg_qicon("eye", "#A1A1AA" if self.is_dark else "#71717A", 13))
        self.btn_preview.setCursor(Qt.PointingHandCursor)
        self.btn_preview.clicked.connect(lambda: self.previewRequested.emit(self.msg))
        layout.addWidget(self.btn_preview)

    def _get_size_str(self):
        msg_size = 0
        if getattr(self.msg, 'is_mock', False):
            msg_size = getattr(self.msg, 'size', 0)
        elif getattr(self.msg, 'file', None):
            msg_size = self.msg.file.size
        elif getattr(self.msg, 'document', None):
            msg_size = self.msg.document.size
        elif getattr(self.msg, 'photo', None):
            try: msg_size = self.msg.photo.sizes[-1].size
            except: msg_size = 0
        return humanize.naturalsize(msg_size) if msg_size else "0 B"

    def _get_title_text(self):
        title = ""
        if getattr(self.msg, 'is_mock', False):
            title = getattr(self.msg, 'message', '')
        elif getattr(self.msg, 'file', None) and getattr(self.msg.file, 'name', None):
            title = self.msg.file.name
        elif getattr(self.msg, 'message', None):
            title = self.msg.message.replace('\n', ' ').strip()
        if not title:
            title = f"Message #{getattr(self.msg, 'id', '0')}"
        return title

    def _get_date_str(self):
        m_date = getattr(self.msg, 'date', None)
        if not m_date: return ""
        if isinstance(m_date, str):
            return m_date[:16]
        try:
            return m_date.strftime("%Y-%m-%d %H:%M")
        except:
            return str(m_date)[:16]

    def set_thumbnail(self, pixmap):
        if pixmap and not pixmap.isNull():
            rounded = make_rounded_thumbnail(pixmap, 38, 38, radius=6)
            self.lbl_thumb.setPixmap(rounded)
            self._pixmap = pixmap

    def mouseDoubleClickEvent(self, event):
        self.previewRequested.emit(self.msg)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self._update_check_visual()
        self.stateChanged.emit(self._checked)
        super().mousePressEvent(event)

    def _update_check_visual(self):
        self.setProperty("checked", "true" if self._checked else "false")
        self.check_indicator.setChecked(self._checked)
        self.style().unpolish(self)
        self.style().polish(self)

    def setChecked(self, state):
        if self._checked != state:
            self._checked = state
            self._update_check_visual()

    def isChecked(self):
        return self._checked


# ===============================================================================
# MediaBrowserDialog - Frameless Minimalist Vercel Media Browser
# ===============================================================================
class MediaBrowserDialog(QDialog):
    fetch_requested = Signal()

    def __init__(self, channel_title, messages_dict=None, parent=None, previous_selected_ids=None, is_dark=False):
        super().__init__(parent)
        self.channel_title = str(channel_title or "Telegram Media")
        self.previous_selected_ids = previous_selected_ids or []
        self.is_dark = is_dark
        self._is_grid_view = True
        self._current_tab_key = "all"
        self._thumbnail_items = {}
        self._thumb_worker = None
        self.messages = messages_dict or {}
        self.selected_messages = []
        self.bulk_cards = {}
        self.grid_items_list = []
        self.list_items_list = []
        self._drag_pos = None
        self._date_preset_active = "all"
        self.date_preset_pills = {}

        # Requirement 8: Remove title bar from fetch popup
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self.setWindowTitle(f"TG Private Grab - {self.channel_title}")
        from resource_utils import get_app_icon, set_windows_taskbar_icon
        self.setWindowIcon(get_app_icon())
        set_windows_taskbar_icon(int(self.winId()))

        self.setMinimumSize(880, 620)
        self.resize(1020, 680)

        self.setup_ui()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() <= 58:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def setup_ui(self):
        self.setObjectName("MediaBrowserDialog")
        
        bg = "#000000" if self.is_dark else "#FAFAFA"
        header_bg = "#09090B" if self.is_dark else "#FFFFFF"
        card_bg = "#121214" if self.is_dark else "#FFFFFF"
        card_hover = "#18181B" if self.is_dark else "#FAFAFA"
        border = "#27272A" if self.is_dark else "#E4E4E7"
        border_hover = "#3F3F46" if self.is_dark else "#D4D4D8"
        text_pri = "#EDEDED" if self.is_dark else "#09090B"
        text_sec = "#A1A1AA" if self.is_dark else "#71717A"
        text_muted = "#71717A" if self.is_dark else "#A1A1AA"
        input_bg = "#18181B" if self.is_dark else "#FFFFFF"
        pill_bg = "#18181B" if self.is_dark else "#F4F4F5"
        icons_dir = get_resource_path(os.path.join("assets", "icons")).replace("\\", "/")
        chevron_icon = "chevron_down_white.png" if self.is_dark else "chevron_down_black.png"

        self.setStyleSheet(f"""
            QDialog#MediaBrowserDialog {{
                background-color: {bg};
                color: {text_pri};
                border: 1px solid {border};
                border-radius: 8px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }}
            QFrame#TelegramHeader {{
                background-color: {header_bg};
                border-bottom: 1px solid {border};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
            QLabel#HeaderTitle {{
                color: {text_pri};
                font-size: 15px;
                font-weight: 600;
            }}
            QLabel#HeaderSubtitle {{
                color: {text_sec};
                font-size: 11px;
            }}
            /* Requirement 2: Remove the text id only keep the badge id */
            QLabel#HeaderIdBadge {{
                background-color: {pill_bg};
                color: {text_sec};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 11px;
                font-family: "Consolas", monospace;
            }}
            /* Requirement 3: Reduce height of bulk mode switch and inline buttons */
            QFrame#ModeSwitcherBox {{
                background-color: {pill_bg};
                border: 1px solid {border};
                border-radius: 6px;
                min-height: 30px;
                max-height: 30px;
            }}
            QPushButton#ModeSwitchTab {{
                background-color: transparent;
                color: {text_sec};
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 0px 10px;
                font-size: 11px;
                font-weight: 500;
                min-height: 22px;
                max-height: 22px;
            }}
            QPushButton#ModeSwitchTab:hover {{
                color: {text_pri};
            }}
            QPushButton#ModeSwitchTab[active="true"] {{
                background-color: {"#27272A" if self.is_dark else "#FFFFFF"};
                color: {"#FFFFFF" if self.is_dark else "#09090B"};
                border: 1px solid {"#3F3F46" if self.is_dark else "#E4E4E7"};
                font-weight: 600;
            }}
            QPushButton#ViewToggleBtn {{
                background-color: {pill_bg};
                border: 1px solid {border};
                border-radius: 5px;
                color: {text_sec};
                font-size: 11px;
                font-weight: 500;
                padding: 2px 8px;
                min-height: 26px;
                max-height: 26px;
            }}
            QPushButton#ViewToggleBtn:hover {{
                color: {text_pri};
                border-color: {border_hover};
            }}
            QPushButton#ViewToggleBtn[active="true"] {{
                background-color: {"#27272A" if self.is_dark else "#FFFFFF"};
                color: {"#FFFFFF" if self.is_dark else "#09090B"};
                border-color: {"#3F3F46" if self.is_dark else "#E4E4E7"};
                font-weight: 600;
            }}
            QPushButton#CloseBtn {{
                background-color: transparent;
                color: {text_sec};
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton#CloseBtn:hover {{
                background-color: {pill_bg};
                color: {text_pri};
            }}
            QFrame#HeroCard {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QLabel#HeroTitle {{
                color: {text_pri};
                font-size: 15px;
                font-weight: 600;
            }}
            QLabel#HeroDesc {{
                color: {text_sec};
                font-size: 12px;
                line-height: 1.4;
            }}
            QFrame#BulkCategoryCard {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QFrame#BulkCategoryCard:hover {{
                border-color: {border_hover};
                background-color: {card_hover};
            }}
            QFrame#BulkCategoryCard[checked="true"] {{
                border: 1px solid {"#FFFFFF" if self.is_dark else "#000000"};
                background-color: {"#18181B" if self.is_dark else "#FAFAFA"};
            }}
            QLabel#CategoryIconBox {{
                border-radius: 6px;
                background-color: {pill_bg};
                border: 1px solid {border};
            }}
            QLabel#CategoryTitle {{
                color: {text_pri};
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#CategoryDesc {{
                color: {text_sec};
                font-size: 11px;
            }}
            QFrame#CalloutBanner {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QLabel#CalloutTitle {{
                color: {text_pri};
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#CalloutDesc {{
                color: {text_sec};
                font-size: 11px;
            }}
            QLineEdit#ModernSearch {{
                background-color: {input_bg};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
                color: {text_pri};
            }}
            QLineEdit#ModernSearch:focus {{
                border-color: {"#71717A" if not self.is_dark else "#A1A1AA"};
            }}
            QDateEdit#FilterDateEdit, QLineEdit#FilterInput {{
                background-color: {input_bg};
                border: 1px solid {border};
                border-radius: 6px;
                color: {text_pri};
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 500;
                min-height: 34px;
                max-height: 34px;
                selection-background-color: {pill_bg};
                selection-color: {text_pri};
            }}
            QDateEdit#FilterDateEdit:hover, QLineEdit#FilterInput:hover {{
                border-color: {border_hover};
            }}
            QDateEdit#FilterDateEdit:focus, QLineEdit#FilterInput:focus {{
                border-color: {"#71717A" if not self.is_dark else "#A1A1AA"};
                background-color: {input_bg};
            }}
            QDateEdit#FilterDateEdit::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid {border};
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background-color: {pill_bg};
            }}
            QDateEdit#FilterDateEdit::drop-down:hover {{
                background-color: {card_hover};
            }}
            QDateEdit#FilterDateEdit::down-arrow {{
                image: url({icons_dir}/{chevron_icon});
                width: 10px;
                height: 10px;
            }}
            QLabel#FilterLabel {{
                color: {text_sec};
                font-size: 12px;
                font-weight: 600;
            }}
            QLabel#DateSeparator {{
                color: {text_sec};
                font-size: 13px;
                font-weight: bold;
                padding: 0 2px;
            }}
            QPushButton#DatePresetPill {{
                background-color: {pill_bg};
                color: {text_sec};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 500;
                min-height: 26px;
            }}
            QPushButton#DatePresetPill:hover {{
                color: {text_pri};
                border-color: {border_hover};
                background-color: {card_hover};
            }}
            QPushButton#DatePresetPill[active="true"] {{
                background-color: {"#FFFFFF" if self.is_dark else "#000000"};
                color: {"#000000" if self.is_dark else "#FFFFFF"};
                border-color: transparent;
                font-weight: 600;
            }}
            /* Calendar Widget Styling inside Dialog */
            QCalendarWidget {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QCalendarWidget QWidget#qt_calendar_navigationbar {{
                background-color: {header_bg};
                border-bottom: 1px solid {border};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                min-height: 38px;
            }}
            QCalendarWidget QToolButton {{
                color: {text_pri};
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                margin: 2px 4px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: 600;
            }}
            QCalendarWidget QToolButton:hover {{
                background-color: {card_hover};
                border-color: {border};
            }}
            QCalendarWidget QToolButton:pressed {{
                background-color: {border};
            }}
            QCalendarWidget QSpinBox {{
                color: {text_pri};
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 12px;
            }}
            QCalendarWidget QTableView {{
                background-color: {card_bg};
                selection-background-color: {"#FFFFFF" if self.is_dark else "#000000"};
                selection-color: {"#000000" if self.is_dark else "#FFFFFF"};
                color: {text_pri};
                border: none;
                outline: none;
            }}
            QCalendarWidget QHeaderView::section {{
                background-color: {header_bg};
                color: {text_sec};
                border: none;
                padding: 4px;
                font-size: 11px;
                font-weight: 600;
            }}
            QToolButton#FilterToggleBtn {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 6px;
                color: {text_pri};
                font-size: 12px;
                font-weight: 500;
                padding: 5px 12px;
                min-height: 22px;
            }}
            QToolButton#FilterToggleBtn:hover {{
                border-color: {border_hover};
                background-color: {card_hover};
            }}
            QToolButton#FilterToggleBtn[checked="true"] {{
                background-color: {"#FFFFFF" if self.is_dark else "#000000"};
                color: {"#000000" if self.is_dark else "#FFFFFF"};
                border-color: transparent;
            }}
            QPushButton#ActionPillBtn {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 6px;
                color: {text_pri};
                font-size: 12px;
                font-weight: 500;
                padding: 5px 12px;
                min-height: 22px;
            }}
            QPushButton#ActionPillBtn:hover {{
                border-color: {border_hover};
                background-color: {card_hover};
            }}
            QPushButton#CategoryFilterPill {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 6px;
                color: {text_sec};
                font-size: 11px;
                font-weight: 500;
                padding: 4px 10px;
            }}
            QPushButton#CategoryFilterPill:hover {{
                color: {text_pri};
                border-color: {border_hover};
            }}
            QPushButton#CategoryFilterPill[active="true"] {{
                background-color: {"#FFFFFF" if self.is_dark else "#000000"};
                color: {"#000000" if self.is_dark else "#FFFFFF"};
                border-color: transparent;
                font-weight: 600;
            }}
            QPushButton#CategoryFilterPill[dimmed="true"] {{
                color: {text_muted};
                opacity: 0.5;
            }}
            QFrame#MediaGridItem {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QFrame#MediaGridItem:hover {{
                border-color: {border_hover};
            }}
            QFrame#MediaGridItem[checked="true"] {{
                border: 1px solid {"#FFFFFF" if self.is_dark else "#000000"};
                background-color: {"#18181B" if self.is_dark else "#FAFAFA"};
            }}
            QLabel#GridTypeBadge {{
                background-color: {"#18181B" if self.is_dark else "#FFFFFF"};
                color: {"#EDEDED" if self.is_dark else "#09090B"};
                border: 1px solid {border};
                border-radius: 4px;
                font-size: 9px;
                font-weight: 700;
                padding: 1px 5px;
            }}
            QLabel#GridMetaBadge {{
                background-color: {"#18181B" if self.is_dark else "#FFFFFF"};
                color: {"#A1A1AA" if self.is_dark else "#71717A"};
                border: 1px solid {border};
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 1px 5px;
            }}
            QPushButton#GridPreviewBtn {{
                background-color: {"#18181B" if self.is_dark else "#FFFFFF"};
                border: 1px solid {border};
                border-radius: 4px;
            }}
            QPushButton#GridPreviewBtn:hover {{
                background-color: {"#27272A" if self.is_dark else "#F4F4F5"};
                border-color: {border_hover};
            }}
            QLabel#GridItemTitle {{
                color: {text_pri};
                font-size: 12px;
                font-weight: 600;
                line-height: 1.2;
            }}
            QLabel#GridItemDate {{
                color: {text_sec};
                font-size: 10px;
            }}
            QFrame#SelectableRow {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            QFrame#SelectableRow:hover {{
                border-color: {border_hover};
            }}
            QFrame#SelectableRow[checked="true"] {{
                background-color: {"#18181B" if self.is_dark else "#FAFAFA"};
                border: 1px solid {"#FFFFFF" if self.is_dark else "#000000"};
            }}
            QLabel#RowItemTitle {{
                color: {text_pri};
                font-size: 12px;
                font-weight: 600;
            }}
            QLabel#TypePill {{
                background-color: {pill_bg};
                color: {text_pri};
                border: 1px solid {border};
                border-radius: 3px;
                padding: 1px 5px;
                font-size: 9px;
                font-weight: 700;
            }}
            QLabel#SizeBadge {{
                background-color: {pill_bg};
                color: {text_sec};
                border: 1px solid {border};
                border-radius: 3px;
                padding: 1px 5px;
                font-size: 10px;
                font-weight: 500;
            }}
            QLabel#RowItemDate {{
                color: {text_muted};
                font-size: 10px;
            }}
            QPushButton#RowPreviewBtn {{
                background-color: {pill_bg};
                color: {text_pri};
                border: 1px solid {border};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 500;
                padding: 3px 10px;
                min-height: 24px;
            }}
            QPushButton#RowPreviewBtn:hover {{
                background-color: {card_hover};
                border-color: {border_hover};
            }}
            QFrame#TelegramFooter {{
                background-color: {header_bg};
                border-top: 1px solid {border};
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }}
            QLabel#FooterStatusChip {{
                background-color: {pill_bg};
                color: {text_sec};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 0 8px;
                font-size: 11px;
                font-weight: 500;
            }}
            QLabel#FooterStatusChip[active="true"] {{
                background-color: {"#FFFFFF" if self.is_dark else "#000000"};
                color: {"#000000" if self.is_dark else "#FFFFFF"};
                border-color: transparent;
                font-weight: 600;
            }}
            QPushButton#SecondaryBtn {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 5px;
                color: {text_pri};
                font-size: 12px;
                font-weight: 500;
                padding: 0 12px;
            }}
            QPushButton#SecondaryBtn:hover {{
                background-color: {card_hover};
                border-color: {border_hover};
            }}
            QPushButton#PrimarySuccessBtn {{
                background-color: {"#FFFFFF" if self.is_dark else "#000000"};
                color: {"#000000" if self.is_dark else "#FFFFFF"};
                border: 1px solid transparent;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 500;
                padding: 0 16px;
            }}
            QPushButton#PrimarySuccessBtn:hover {{
                background-color: {"#E4E4E7" if self.is_dark else "#27272A"};
            }}
            QPushButton#PrimarySuccessBtn:disabled {{
                background-color: {pill_bg};
                color: {text_muted};
                border-color: transparent;
            }}
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── 1. Header Bar with Channel Profile (Requirement 1 & 2 & 3) ────
        header = QFrame()
        header.setObjectName("TelegramHeader")
        header.setFixedHeight(58)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(18, 6, 18, 6)
        h_layout.setSpacing(12)

        # Requirement 1: Use channel profile in place of vercel logo
        channel_avatar = QLabel()
        channel_avatar.setPixmap(make_channel_avatar(self.channel_title, size=34, is_dark=self.is_dark))
        channel_avatar.setFixedSize(34, 34)
        h_layout.addWidget(channel_avatar)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(2)
        title_stack.setAlignment(Qt.AlignVCenter)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        lbl_title = QLabel(self.channel_title)
        lbl_title.setObjectName("HeaderTitle")
        title_row.addWidget(lbl_title)

        # Requirement 2: Remove the text "ID:" only keep the badge ID
        lbl_id = QLabel(f"{self.channel_title}")
        lbl_id.setObjectName("HeaderIdBadge")
        title_row.addWidget(lbl_id)
        title_row.addStretch()
        title_stack.addLayout(title_row)

        lbl_sub = QLabel("Minimalist Media Browser · Inspect, Preview & Download")
        lbl_sub.setObjectName("HeaderSubtitle")
        title_stack.addWidget(lbl_sub)

        h_layout.addLayout(title_stack)
        h_layout.addStretch()

        # Requirement 3: Reduced height bulk mode switch and inline buttons
        mode_box = QFrame()
        mode_box.setObjectName("ModeSwitcherBox")
        mode_box.setFixedHeight(30)
        mode_layout = QHBoxLayout(mode_box)
        mode_layout.setContentsMargins(3, 3, 3, 3)
        mode_layout.setSpacing(2)

        self.btn_mode_bulk = QPushButton("Bulk Mode")
        self.btn_mode_bulk.setObjectName("ModeSwitchTab")
        self.btn_mode_bulk.setIcon(render_svg_qicon("layers", text_sec, 12))
        self.btn_mode_bulk.setFixedHeight(22)
        self.btn_mode_bulk.setCursor(Qt.PointingHandCursor)
        self.btn_mode_bulk.clicked.connect(lambda: self._set_mode(0))
        mode_layout.addWidget(self.btn_mode_bulk)

        self.btn_mode_specific = QPushButton("Specific Files")
        self.btn_mode_specific.setObjectName("ModeSwitchTab")
        self.btn_mode_specific.setIcon(render_svg_qicon("file", text_sec, 12))
        self.btn_mode_specific.setFixedHeight(22)
        self.btn_mode_specific.setCursor(Qt.PointingHandCursor)
        self.btn_mode_specific.clicked.connect(lambda: self._set_mode(1))
        mode_layout.addWidget(self.btn_mode_specific)

        h_layout.addWidget(mode_box)
        h_layout.addStretch()

        # View Switcher (Grid / List) reduced height inline
        self.view_switch_box = QWidget()
        v_box_layout = QHBoxLayout(self.view_switch_box)
        v_box_layout.setContentsMargins(0, 0, 0, 0)
        v_box_layout.setSpacing(4)

        self.btn_view_grid = QPushButton("Grid")
        self.btn_view_grid.setObjectName("ViewToggleBtn")
        self.btn_view_grid.setIcon(render_svg_qicon("grid", text_sec, 12))
        self.btn_view_grid.setCursor(Qt.PointingHandCursor)
        self.btn_view_grid.clicked.connect(lambda: self._set_view(True))
        v_box_layout.addWidget(self.btn_view_grid)

        self.btn_view_list = QPushButton("List")
        self.btn_view_list.setObjectName("ViewToggleBtn")
        self.btn_view_list.setIcon(render_svg_qicon("list", text_sec, 12))
        self.btn_view_list.setCursor(Qt.PointingHandCursor)
        self.btn_view_list.clicked.connect(lambda: self._set_view(False))
        v_box_layout.addWidget(self.btn_view_list)

        h_layout.addWidget(self.view_switch_box)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("CloseBtn")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        h_layout.addWidget(btn_close)

        root_layout.addWidget(header)

        # ── 2. Content Stack (Mode 0: Bulk, Mode 1: Specific) ───────────────
        self.main_stack = QStackedWidget()

        # Page 0: Bulk View
        bulk_widget = QWidget()
        b_layout = QVBoxLayout(bulk_widget)
        b_layout.setContentsMargins(24, 18, 24, 18)
        b_layout.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(18, 14, 18, 14)
        hero_layout.setSpacing(16)

        hero_icon = QLabel()
        hero_icon.setPixmap(render_svg_pixmap("layers", color=text_pri, size=28))
        hero_layout.addWidget(hero_icon)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(3)
        lbl_ht = QLabel("Category Bulk Download")
        lbl_ht.setObjectName("HeroTitle")
        lbl_hd = QLabel("Download complete categories directly from Telegram without item limitations.\nBypasses the 2,000 message fetch limit and downloads media files in the background.")
        lbl_hd.setObjectName("HeroDesc")
        hero_text.addWidget(lbl_ht)
        hero_text.addWidget(lbl_hd)
        hero_layout.addLayout(hero_text, stretch=1)
        b_layout.addWidget(hero)

        # Category Cards Grid
        cat_grid = QGridLayout()
        cat_grid.setSpacing(12)

        categories = [
            ("All Media (Images, Videos)", "Download all photos, videos, and media files in one click (Recommended)", "layers", 6, True),
            ("Photos & Images", "JPG, PNG, WEBP, and photo albums", "photo", 1, False),
            ("Videos & Movies", "MP4, MKV, AVI, and video recordings", "video", 2, False),
            ("Documents & Archives", "PDF, ZIP, RAR, DOCX, APK files", "file", 3, False),
            ("Music & Audio", "MP3, FLAC, OGG, and voice messages", "music", 5, False),
        ]

        card_all = BulkCategoryCard(categories[0][0], categories[0][1], categories[0][2], categories[0][3], is_checked=categories[0][4], is_dark=self.is_dark)
        card_all.stateChanged.connect(self._on_bulk_card_changed)
        self.bulk_cards[6] = card_all
        cat_grid.addWidget(card_all, 0, 0, 1, 2)

        for idx, (title, desc, icon_key, media_id, default_check) in enumerate(categories[1:]):
            card = BulkCategoryCard(title, desc, icon_key, media_id, is_checked=default_check, is_dark=self.is_dark)
            card.stateChanged.connect(self._on_bulk_card_changed)
            self.bulk_cards[media_id] = card
            row = 1 + (idx // 2)
            col = idx % 2
            cat_grid.addWidget(card, row, col)

        b_layout.addLayout(cat_grid)

        # Callout Banner
        callout = QFrame()
        callout.setObjectName("CalloutBanner")
        co_layout = QHBoxLayout(callout)
        co_layout.setContentsMargins(18, 12, 18, 12)
        co_layout.setSpacing(14)

        co_icon = QLabel()
        co_icon.setPixmap(render_svg_pixmap("eye", color=text_sec, size=22))
        co_layout.addWidget(co_icon)

        co_text = QVBoxLayout()
        co_text.setSpacing(2)
        co_t = QLabel("Looking to inspect & cherry-pick specific files?")
        co_t.setObjectName("CalloutTitle")
        co_d = QLabel("Inspect individual messages, full-resolution preview, and select exact items.")
        co_d.setObjectName("CalloutDesc")
        co_text.addWidget(co_t)
        co_text.addWidget(co_d)
        co_layout.addLayout(co_text, stretch=1)

        self.btn_load_specific = QPushButton("Load && Select Specific Files")
        self.btn_load_specific.setObjectName("SecondaryBtn")
        self.btn_load_specific.setIcon(render_svg_qicon("search", text_pri, 14))
        self.btn_load_specific.setMinimumHeight(34)
        self.btn_load_specific.setCursor(Qt.PointingHandCursor)
        self.btn_load_specific.clicked.connect(lambda: self.fetch_requested.emit())
        co_layout.addWidget(self.btn_load_specific)

        b_layout.addWidget(callout)
        b_layout.addStretch()

        self.main_stack.addWidget(bulk_widget)

        # Page 1: Specific Selection View
        spec_widget = QWidget()
        s_layout = QVBoxLayout(spec_widget)
        s_layout.setContentsMargins(20, 12, 20, 12)
        s_layout.setSpacing(10)

        # Toolbar Row 1: Search, Filter toggle, Selection pills
        tb_layout = QHBoxLayout()
        tb_layout.setSpacing(8)

        self.inp_search = QLineEdit()
        self.inp_search.setObjectName("ModernSearch")
        self.inp_search.setPlaceholderText("Search media by name or caption...")
        self.inp_search.setClearButtonEnabled(True)
        self.inp_search.setFixedHeight(32)
        self.inp_search.textChanged.connect(self.filter_rows)
        tb_layout.addWidget(self.inp_search, stretch=1)

        self.btn_toggle_filters = QToolButton()
        self.btn_toggle_filters.setObjectName("FilterToggleBtn")
        self.btn_toggle_filters.setText("Filters")
        self.btn_toggle_filters.setIcon(render_svg_qicon("filter", text_pri, 13))
        self.btn_toggle_filters.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_toggle_filters.setCheckable(True)
        self.btn_toggle_filters.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_filters.setFixedHeight(32)
        self.btn_toggle_filters.clicked.connect(self.toggle_filters_area)
        tb_layout.addWidget(self.btn_toggle_filters)

        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.setObjectName("ActionPillBtn")
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        self.btn_select_all.setFixedHeight(32)
        self.btn_select_all.clicked.connect(lambda: self.set_all_rows(True))
        tb_layout.addWidget(self.btn_select_all)

        self.btn_select_vis = QPushButton("Select Visible")
        self.btn_select_vis.setObjectName("ActionPillBtn")
        self.btn_select_vis.setCursor(Qt.PointingHandCursor)
        self.btn_select_vis.setFixedHeight(32)
        self.btn_select_vis.clicked.connect(lambda: self.set_rows_visible(True))
        tb_layout.addWidget(self.btn_select_vis)

        self.btn_clear_sel = QPushButton("Clear")
        self.btn_clear_sel.setObjectName("ActionPillBtn")
        self.btn_clear_sel.setCursor(Qt.PointingHandCursor)
        self.btn_clear_sel.setFixedHeight(32)
        self.btn_clear_sel.clicked.connect(lambda: self.set_all_rows(False))
        tb_layout.addWidget(self.btn_clear_sel)

        s_layout.addLayout(tb_layout)

        # Advanced Filters Area
        self.filters_area = QFrame()
        self.filters_area.setObjectName("HeroCard")
        self.filters_area.setVisible(False)
        f_grid = QGridLayout(self.filters_area)
        f_grid.setContentsMargins(16, 14, 16, 14)
        f_grid.setHorizontalSpacing(14)
        f_grid.setVerticalSpacing(10)
        f_grid.setColumnStretch(0, 0)
        f_grid.setColumnStretch(1, 1)
        f_grid.setColumnStretch(2, 0)

        # Row 0: Date Range & Preset Pills
        lbl_date = QLabel("Date Range:")
        lbl_date.setObjectName("FilterLabel")
        f_grid.addWidget(lbl_date, 0, 0)

        self.date_start = QDateEdit()
        self.date_start.setObjectName("FilterDateEdit")
        self.date_start.setCalendarPopup(True)
        self.date_start.setDisplayFormat("yyyy-MM-dd")
        self.date_start.setFixedWidth(130)
        self.date_start.setFixedHeight(32)
        self.date_start.setDate(QDate.currentDate().addYears(-10))
        self._setup_styled_calendar(self.date_start.calendarWidget())
        self.date_start.dateChanged.connect(self._on_custom_date_changed)

        date_sep = QLabel("→")
        date_sep.setObjectName("DateSeparator")

        self.date_end = QDateEdit()
        self.date_end.setObjectName("FilterDateEdit")
        self.date_end.setCalendarPopup(True)
        self.date_end.setDisplayFormat("yyyy-MM-dd")
        self.date_end.setFixedWidth(130)
        self.date_end.setFixedHeight(32)
        self.date_end.setDate(QDate.currentDate())
        self._setup_styled_calendar(self.date_end.calendarWidget())
        self.date_end.dateChanged.connect(self._on_custom_date_changed)

        d_box = QHBoxLayout()
        d_box.setContentsMargins(0, 0, 0, 0)
        d_box.setSpacing(8)
        d_box.addWidget(self.date_start)
        d_box.addWidget(date_sep)
        d_box.addWidget(self.date_end)
        d_box.addSpacing(8)

        self.date_preset_pills = {}
        presets = [
            ("all", "All Time"),
            ("30d", "Past 30d"),
            ("7d", "Past 7d"),
            ("year", "This Year"),
        ]
        for pid, plabel in presets:
            btn_pill = QPushButton(plabel)
            btn_pill.setObjectName("DatePresetPill")
            btn_pill.setCursor(Qt.PointingHandCursor)
            btn_pill.setFixedHeight(32)
            btn_pill.clicked.connect(lambda _, p=pid: self._apply_date_preset(p))
            self.date_preset_pills[pid] = btn_pill
            d_box.addWidget(btn_pill)

        d_box.addStretch(1)
        f_grid.addLayout(d_box, 0, 1, 1, 2)
        self._update_preset_pill_ui("all")

        # Row 1: Size (MB)
        lbl_size = QLabel("Size (MB):")
        lbl_size.setObjectName("FilterLabel")
        f_grid.addWidget(lbl_size, 1, 0)

        self.size_min = QLineEdit()
        self.size_min.setObjectName("FilterInput")
        self.size_min.setPlaceholderText("Min MB")
        self.size_min.setFixedWidth(130)
        self.size_min.setFixedHeight(32)
        self.size_min.textChanged.connect(self.filter_rows)

        size_sep = QLabel("—")
        size_sep.setObjectName("DateSeparator")

        self.size_max = QLineEdit()
        self.size_max.setObjectName("FilterInput")
        self.size_max.setPlaceholderText("Max MB")
        self.size_max.setFixedWidth(130)
        self.size_max.setFixedHeight(32)
        self.size_max.textChanged.connect(self.filter_rows)

        sz_box = QHBoxLayout()
        sz_box.setContentsMargins(0, 0, 0, 0)
        sz_box.setSpacing(8)
        sz_box.addWidget(self.size_min)
        sz_box.addWidget(size_sep)
        sz_box.addWidget(self.size_max)
        sz_box.addStretch(1)
        f_grid.addLayout(sz_box, 1, 1)

        # Row 2: Regex Filter & Reset
        lbl_regex = QLabel("Regex Filter:")
        lbl_regex.setObjectName("FilterLabel")
        f_grid.addWidget(lbl_regex, 2, 0)

        self.inp_regex = QLineEdit()
        self.inp_regex.setObjectName("FilterInput")
        self.inp_regex.setPlaceholderText(r"e.g. ^IMG_.*\.jpg$")
        self.inp_regex.setFixedHeight(32)
        self.inp_regex.textChanged.connect(self.filter_rows)
        f_grid.addWidget(self.inp_regex, 2, 1)

        btn_reset = QPushButton("Reset Filters")
        btn_reset.setObjectName("ActionPillBtn")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.setFixedHeight(32)
        btn_reset.setFixedHeight(34)
        btn_reset.clicked.connect(self.reset_filters)
        f_grid.addWidget(btn_reset, 2, 2)

        s_layout.addWidget(self.filters_area)

        # Toolbar Row 2: Category Filter Pills
        self.pills_layout = QHBoxLayout()
        self.pills_layout.setSpacing(6)
        self.category_pills = {}

        self._rebuild_category_pills()
        s_layout.addLayout(self.pills_layout)

        # View Stack: Grid View vs List View
        self.view_stack = QStackedWidget()

        # Grid View
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setFrameShape(QFrame.NoFrame)
        self.grid_scroll.setStyleSheet("background: transparent;")

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.grid_scroll.setWidget(self.grid_container)
        self.view_stack.addWidget(self.grid_scroll)

        # List View
        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.NoFrame)
        self.list_scroll.setStyleSheet("background: transparent;")

        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(4, 4, 4, 4)
        self.list_layout.setSpacing(6)
        self.list_layout.setAlignment(Qt.AlignTop)

        self.list_scroll.setWidget(self.list_container)
        self.view_stack.addWidget(self.list_scroll)

        s_layout.addWidget(self.view_stack, stretch=1)
        self.main_stack.addWidget(spec_widget)

        root_layout.addWidget(self.main_stack, stretch=1)

        # ── 3. Bottom Footer ───────────────────────────────────────────────
        footer = QFrame()
        footer.setObjectName("TelegramFooter")
        footer.setFixedHeight(48)
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(18, 0, 18, 0)
        f_layout.setSpacing(8)

        self.lbl_status_chip = QLabel("Bulk Mode Active")
        self.lbl_status_chip.setObjectName("FooterStatusChip")
        self.lbl_status_chip.setFixedHeight(24)
        f_layout.addWidget(self.lbl_status_chip, alignment=Qt.AlignVCenter)

        f_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("SecondaryBtn")
        self.btn_cancel.setFixedHeight(30)
        self.btn_cancel.setFixedWidth(75)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        f_layout.addWidget(self.btn_cancel, alignment=Qt.AlignVCenter)

        self.btn_download = QPushButton("Start Bulk Download")
        self.btn_download.setObjectName("PrimarySuccessBtn")
        self.btn_download.setIcon(render_svg_qicon("download", "#000000" if self.is_dark else "#FFFFFF", 13))
        self.btn_download.setFixedHeight(30)
        self.btn_download.setCursor(Qt.PointingHandCursor)
        self.btn_download.clicked.connect(self.accept)
        f_layout.addWidget(self.btn_download, alignment=Qt.AlignVCenter)

        root_layout.addWidget(footer)

        self._populate_items()

        has_items = bool(self.messages and len(self.messages.get("all", [])) > 0)
        if has_items:
            self._set_mode(1)
        else:
            self._set_mode(0)

        self._set_view(True)

    def _set_mode(self, mode_idx):
        self.main_stack.setCurrentIndex(mode_idx)
        self.btn_mode_bulk.setProperty("active", "true" if mode_idx == 0 else "false")
        self.btn_mode_specific.setProperty("active", "true" if mode_idx == 1 else "false")
        self.btn_mode_bulk.style().unpolish(self.btn_mode_bulk)
        self.btn_mode_bulk.style().polish(self.btn_mode_bulk)
        self.btn_mode_specific.style().unpolish(self.btn_mode_specific)
        self.btn_mode_specific.style().polish(self.btn_mode_specific)

        self.view_switch_box.setVisible(mode_idx == 1)
        self.update_selected_count()

    def _set_view(self, is_grid):
        self._is_grid_view = is_grid
        self.btn_view_grid.setProperty("active", "true" if is_grid else "false")
        self.btn_view_list.setProperty("active", "true" if not is_grid else "false")
        self.btn_view_grid.style().unpolish(self.btn_view_grid)
        self.btn_view_grid.style().polish(self.btn_view_grid)
        self.btn_view_list.style().unpolish(self.btn_view_list)
        self.btn_view_list.style().polish(self.btn_view_list)
        self.view_stack.setCurrentIndex(0 if is_grid else 1)

    def _on_bulk_card_changed(self):
        self.update_selected_count()

    def _rebuild_category_pills(self):
        while self.pills_layout.count() > 0:
            item = self.pills_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.category_pills.clear()

        cats = ["all", "media", "files", "music", "zips", "voice", "links", "gifs", "chat"]
        for key in cats:
            count = len(self.messages.get(key, []))
            cfg = CATEGORY_CONFIG.get(key, {"label": key.capitalize()})
            label = f"{cfg['label']} ({count})"

            btn = QPushButton(label)
            btn.setObjectName("CategoryFilterPill")
            btn.setCursor(Qt.PointingHandCursor)
            if count == 0 and key != "all":
                btn.setProperty("dimmed", "true")
            if key == self._current_tab_key:
                btn.setProperty("active", "true")

            btn.clicked.connect(lambda checked=False, k=key: self._on_category_pill_clicked(k))
            self.category_pills[key] = btn
            self.pills_layout.addWidget(btn)

        self.pills_layout.addStretch()

    def _on_category_pill_clicked(self, key):
        self._current_tab_key = key
        for k, btn in self.category_pills.items():
            btn.setProperty("active", "true" if k == key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.filter_rows()

    def _populate_items(self):
        while self.grid_layout.count() > 0:
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        while self.list_layout.count() > 0:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.grid_items_list = []
        self.list_items_list = []
        self._thumbnail_items.clear()

        all_msgs = self.messages.get("all", [])
        col_count = 5

        if not all_msgs:
            empty_card = QFrame()
            empty_card.setObjectName("HeroCard")
            e_layout = QVBoxLayout(empty_card)
            e_layout.setContentsMargins(30, 40, 30, 40)
            e_layout.setAlignment(Qt.AlignCenter)
            e_layout.setSpacing(12)

            e_icon = QLabel()
            e_icon.setPixmap(render_svg_pixmap("download", color="#71717A", size=36))
            e_icon.setAlignment(Qt.AlignCenter)
            e_layout.addWidget(e_icon)

            e_title = QLabel("Channel Files Not Loaded Yet")
            e_title.setObjectName("HeroTitle")
            e_title.setAlignment(Qt.AlignCenter)
            e_layout.addWidget(e_title)

            e_desc = QLabel("Fetch up to 2,000 recent media items from this channel to preview thumbnails and select individual files.\nOr switch to Bulk Mode to start downloading entire categories instantly.")
            e_desc.setObjectName("HeroDesc")
            e_desc.setAlignment(Qt.AlignCenter)
            e_layout.addWidget(e_desc)

            btn_fetch_now = QPushButton("Load Files from Telegram")
            btn_fetch_now.setObjectName("PrimarySuccessBtn")
            btn_fetch_now.setIcon(render_svg_qicon("search", "#000000" if self.is_dark else "#FFFFFF", 14))
            btn_fetch_now.setMinimumHeight(38)
            btn_fetch_now.setCursor(Qt.PointingHandCursor)
            btn_fetch_now.clicked.connect(lambda: self.fetch_requested.emit())
            btn_box = QHBoxLayout()
            btn_box.addStretch()
            btn_box.addWidget(btn_fetch_now)
            btn_box.addStretch()
            e_layout.addLayout(btn_box)

            self.grid_layout.addWidget(empty_card, 0, 0, 1, 5)
            self.list_layout.addWidget(empty_card)
            self.update_selected_count()
            return

        for idx, msg in enumerate(all_msgs):
            grid_item = MediaGridItem(msg, is_dark=self.is_dark)
            if msg.id in self.previous_selected_ids:
                grid_item.setChecked(True)
            grid_item.stateChanged.connect(self._sync_item_selection)
            grid_item.previewRequested.connect(self.open_preview)
            self.grid_items_list.append(grid_item)

            row = idx // col_count
            col = idx % col_count
            self.grid_layout.addWidget(grid_item, row, col)

            list_item = SelectableMediaRow(msg, is_dark=self.is_dark)
            if msg.id in self.previous_selected_ids:
                list_item.setChecked(True)
            list_item.stateChanged.connect(self._sync_item_selection)
            list_item.previewRequested.connect(self.open_preview)
            self.list_items_list.append(list_item)
            self.list_layout.addWidget(list_item)

            self._register_thumbnail_item(msg.id, grid_item)
            self._register_thumbnail_item(msg.id, list_item)

        self.list_layout.addStretch()
        self.update_selected_count()

    def open_preview(self, msg):
        """Launches the frameless MediaPreviewDialog for the selected message."""
        all_msgs = [g.msg for g in self.grid_items_list if g.isVisible()]
        if not all_msgs:
            all_msgs = [msg]

        is_selected = False
        initial_pix = None
        for g in self.grid_items_list:
            if getattr(g.msg, 'id', None) == getattr(msg, 'id', None):
                is_selected = g.isChecked()
                initial_pix = g._pixmap
                break

        preview_dlg = MediaPreviewDialog(msg, all_msgs=all_msgs, is_dark=self.is_dark, is_selected=is_selected, initial_pixmap=initial_pix, parent=self)
        preview_dlg.selectionToggled.connect(self._on_preview_selection_toggled)
        preview_dlg.exec()

    def _on_preview_selection_toggled(self, msg, is_selected):
        msg_id = getattr(msg, 'id', None)
        if msg_id is None: return
        for g in self.grid_items_list:
            if g.msg.id == msg_id:
                g.setChecked(is_selected)
        for l in self.list_items_list:
            if l.msg.id == msg_id:
                l.setChecked(is_selected)
        self.update_selected_count()

    def _sync_item_selection(self, is_checked):
        sender = self.sender()
        if not sender: return
        msg_id = sender.msg.id

        for g in self.grid_items_list:
            if g.msg.id == msg_id and g != sender:
                g.setChecked(is_checked)
        for l in self.list_items_list:
            if l.msg.id == msg_id and l != sender:
                l.setChecked(is_checked)

        self.update_selected_count()

    def _register_thumbnail_item(self, msg_id, widget):
        if msg_id not in self._thumbnail_items:
            self._thumbnail_items[msg_id] = []
        self._thumbnail_items[msg_id].append(widget)

    def apply_thumbnail(self, msg_id, pixmap):
        if isinstance(pixmap, str):
            if os.path.exists(pixmap) and os.path.getsize(pixmap) > 0:
                pixmap = QPixmap(pixmap)
            else:
                return
        if not pixmap or pixmap.isNull():
            return
        for widget in self._thumbnail_items.get(msg_id, []):
            widget.set_thumbnail(pixmap)

    def set_thumbnail_worker(self, worker):
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.cancel()
        self._thumb_worker = worker
        worker.signals.thumbnail_ready.connect(self.apply_thumbnail)
        worker.start()

    def set_all_rows(self, state):
        for g in self.grid_items_list:
            g.setChecked(state)
        for l in self.list_items_list:
            l.setChecked(state)
        self.update_selected_count()

    def set_rows_visible(self, state):
        for g in self.grid_items_list:
            if g.isVisible():
                g.setChecked(state)
        for l in self.list_items_list:
            if l.isVisible():
                l.setChecked(state)
        self.update_selected_count()

    def toggle_filters_area(self, checked):
        self.filters_area.setVisible(checked)

    def _setup_styled_calendar(self, cal: QCalendarWidget):
        if not cal:
            return
        cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        cal.setDateEditEnabled(False)
        cal.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)

        card_bg = "#121214" if self.is_dark else "#FFFFFF"
        header_bg = "#18181B" if self.is_dark else "#F4F4F5"
        card_hover = "#27272A" if self.is_dark else "#E4E4E7"
        border = "#27272A" if self.is_dark else "#E4E4E7"
        border_hover = "#3F3F46" if self.is_dark else "#D4D4D8"
        text_pri = "#EDEDED" if self.is_dark else "#09090B"
        text_sec = "#A1A1AA" if self.is_dark else "#71717A"
        sel_bg = "#FFFFFF" if self.is_dark else "#000000"
        sel_fg = "#000000" if self.is_dark else "#FFFFFF"

        cal_qss = f"""
        QCalendarWidget {{
            background-color: {card_bg};
            border: 1px solid {border};
            border-radius: 8px;
        }}
        QCalendarWidget QWidget#qt_calendar_navigationbar {{
            background-color: {header_bg};
            border-bottom: 1px solid {border};
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            min-height: 38px;
        }}
        QCalendarWidget QToolButton {{
            color: {text_pri};
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 6px;
            margin: 2px 4px;
            padding: 4px 8px;
            font-size: 12px;
            font-weight: 600;
        }}
        QCalendarWidget QToolButton:hover {{
            background-color: {card_hover};
            border-color: {border_hover};
        }}
        QCalendarWidget QToolButton:pressed {{
            background-color: {border};
        }}
        QCalendarWidget QSpinBox {{
            color: {text_pri};
            background-color: {card_bg};
            border: 1px solid {border};
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 12px;
        }}
        QCalendarWidget QTableView {{
            background-color: {card_bg};
            selection-background-color: {sel_bg};
            selection-color: {sel_fg};
            color: {text_pri};
            border: none;
            outline: none;
        }}
        QCalendarWidget QHeaderView::section {{
            background-color: {header_bg};
            color: {text_sec};
            border: none;
            padding: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
        """
        cal.setStyleSheet(cal_qss)

        # Neutral weekday text format (prevent harsh red weekend days)
        fg_color = QColor(text_pri)
        fmt = QTextCharFormat()
        fmt.setForeground(fg_color)
        for day in [
            Qt.DayOfWeek.Monday, Qt.DayOfWeek.Tuesday, Qt.DayOfWeek.Wednesday,
            Qt.DayOfWeek.Thursday, Qt.DayOfWeek.Friday, Qt.DayOfWeek.Saturday,
            Qt.DayOfWeek.Sunday
        ]:
            cal.setWeekdayTextFormat(day, fmt)

        # Fix Windows/Fusion navy header bug on QCalendarWidget internal QTableView
        table_view = cal.findChild(QTableView, "qt_calendar_calendarview")
        if table_view:
            pal = table_view.palette()
            pal.setColor(QPalette.ColorRole.AlternateBase, QColor(card_bg))
            pal.setColor(QPalette.ColorRole.Base, QColor(card_bg))
            pal.setColor(QPalette.ColorRole.Window, QColor(card_bg))
            pal.setColor(QPalette.ColorRole.Text, QColor(text_pri))
            table_view.setPalette(pal)
            if table_view.horizontalHeader():
                h_pal = table_view.horizontalHeader().palette()
                h_pal.setColor(QPalette.ColorRole.AlternateBase, QColor(header_bg))
                h_pal.setColor(QPalette.ColorRole.Base, QColor(header_bg))
                h_pal.setColor(QPalette.ColorRole.Window, QColor(header_bg))
                h_pal.setColor(QPalette.ColorRole.Text, QColor(text_sec))
                table_view.horizontalHeader().setPalette(h_pal)

    def _apply_date_preset(self, preset: str):
        self._date_preset_active = preset
        today = QDate.currentDate()
        self.date_start.blockSignals(True)
        self.date_end.blockSignals(True)
        if preset == "all":
            self.date_start.setDate(today.addYears(-10))
            self.date_end.setDate(today)
        elif preset == "30d":
            self.date_start.setDate(today.addDays(-30))
            self.date_end.setDate(today)
        elif preset == "7d":
            self.date_start.setDate(today.addDays(-7))
            self.date_end.setDate(today)
        elif preset == "year":
            self.date_start.setDate(QDate(today.year(), 1, 1))
            self.date_end.setDate(today)
        self.date_start.blockSignals(False)
        self.date_end.blockSignals(False)
        self._update_preset_pill_ui(preset)
        self.filter_rows()

    def _on_custom_date_changed(self):
        self._update_preset_pill_ui(None)
        self.filter_rows()

    def _update_preset_pill_ui(self, active_preset):
        for pid, pill in getattr(self, "date_preset_pills", {}).items():
            is_act = (pid == active_preset)
            pill.setProperty("active", "true" if is_act else "false")
            pill.style().unpolish(pill)
            pill.style().polish(pill)
            pill.update()

    def reset_filters(self):
        self.inp_search.clear()
        self.inp_regex.clear()
        self.size_min.clear()
        self.size_max.clear()
        self._apply_date_preset("all")
        self.btn_toggle_filters.setChecked(False)
        self.filters_area.setVisible(False)
        self.filter_rows()

    def filter_rows(self, _=None):
        search_text = self.inp_search.text().lower().strip()
        regex_text = self.inp_regex.text().strip()

        start_date = self.date_start.date().toPython()
        end_date = self.date_end.date().toPython()

        try: min_bytes = float(self.size_min.text()) * 1024 * 1024 if self.size_min.text() else 0
        except ValueError: min_bytes = 0
        try: max_bytes = float(self.size_max.text()) * 1024 * 1024 if self.size_max.text() else float('inf')
        except ValueError: max_bytes = float('inf')

        regex = None
        if regex_text:
            regex = QRegularExpression(regex_text, QRegularExpression.CaseInsensitiveOption)

        cat_ids = set()
        if self._current_tab_key != "all":
            cat_ids = {m.id for m in self.messages.get(self._current_tab_key, [])}

        for i in range(len(self.grid_items_list)):
            grid_item = self.grid_items_list[i]
            list_item = self.list_items_list[i] if i < len(self.list_items_list) else None
            msg = grid_item.msg
            visible = True

            if self._current_tab_key != "all" and msg.id not in cat_ids:
                visible = False

            if visible and search_text:
                title = grid_item.lbl_title.text().lower()
                if search_text not in title:
                    visible = False

            if visible and regex:
                match = regex.match(grid_item.lbl_title.text())
                if not match.hasMatch():
                    visible = False

            if visible:
                m_date = None
                raw_date = getattr(msg, 'date', None)
                if isinstance(raw_date, str) and len(raw_date) >= 10:
                    try:
                        m_date = datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
                    except: pass
                elif raw_date:
                    try: m_date = raw_date.date()
                    except: pass
                if m_date and (m_date < start_date or m_date > end_date):
                    visible = False

            if visible:
                m_size = 0
                if getattr(msg, 'is_mock', False):
                    m_size = getattr(msg, 'size', 0)
                elif getattr(msg, 'file', None):
                    m_size = msg.file.size
                elif getattr(msg, 'document', None):
                    m_size = msg.document.size
                elif getattr(msg, 'photo', None):
                    try: m_size = msg.photo.sizes[-1].size
                    except: m_size = 0
                if m_size < min_bytes or m_size > max_bytes:
                    visible = False

            grid_item.setVisible(visible)
            if list_item:
                list_item.setVisible(visible)

    def update_selected_count(self):
        if self.is_bulk_mode():
            selected_cats = self.get_bulk_selections()
            count = len(selected_cats)
            if count > 0:
                self.lbl_status_chip.setText(f"{count} bulk categories selected")
                self.lbl_status_chip.setProperty("active", "true")
                self.btn_download.setEnabled(True)
                self.btn_download.setText(f"Start Bulk Download ({count})")
            else:
                self.lbl_status_chip.setText("No bulk categories selected")
                self.lbl_status_chip.setProperty("active", "false")
                self.btn_download.setEnabled(False)
                self.btn_download.setText("Select Categories")
        else:
            self.selected_messages.clear()
            total_bytes = 0
            for item in self.grid_items_list:
                if item.isChecked():
                    self.selected_messages.append(item.msg)
                    sz = 0
                    if getattr(item.msg, 'is_mock', False): sz = getattr(item.msg, 'size', 0)
                    elif getattr(item.msg, 'file', None): sz = item.msg.file.size
                    elif getattr(item.msg, 'document', None): sz = item.msg.document.size
                    total_bytes += sz

            count = len(self.selected_messages)
            if count > 0:
                size_str = humanize.naturalsize(total_bytes) if total_bytes else ""
                suffix = f" ({size_str})" if size_str else ""
                self.lbl_status_chip.setText(f"{count} files selected{suffix}")
                self.lbl_status_chip.setProperty("active", "true")
                self.btn_download.setEnabled(True)
                self.btn_download.setText(f"Download Selected ({count})")
            else:
                self.lbl_status_chip.setText("0 files selected")
                self.lbl_status_chip.setProperty("active", "false")
                self.btn_download.setEnabled(False)
                self.btn_download.setText("Download Selected")

        self.lbl_status_chip.style().unpolish(self.lbl_status_chip)
        self.lbl_status_chip.style().polish(self.lbl_status_chip)

    def get_selected_messages(self):
        return self.selected_messages

    def is_bulk_mode(self):
        return self.main_stack.currentIndex() == 0

    def get_bulk_selections(self):
        selected = []
        for media_id, card in self.bulk_cards.items():
            if card.isChecked():
                selected.append(media_id)
        return selected

    def refresh_content(self, messages_dict):
        current_selected = [m.id for m in self.get_selected_messages()]
        if self.previous_selected_ids:
            current_selected.extend(self.previous_selected_ids)
        self.previous_selected_ids = list(set(current_selected))

        self.messages = messages_dict or {}
        self._rebuild_category_pills()
        self._populate_items()
        self._set_mode(1)
        self.btn_load_specific.setText("Load && Select Specific Files")
        self.btn_load_specific.setEnabled(True)
