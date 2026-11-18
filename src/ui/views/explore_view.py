import os
import html
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QListWidget, QListWidgetItem, QScrollArea, 
    QFrame, QGridLayout, QCheckBox, QSizePolicy, QStackedWidget,
    QStackedLayout, QSplitter, QApplication, QComboBox
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont, QCursor, QPainterPath
from resource_utils import get_resource_path, get_project_root
from ui.components.clean_combobox import CleanComboBox, create_clean_menu
from ui.components.searchable_combobox import SearchableComboBox
from ui.components.thumbnail_worker import ThumbnailWorker
from ui.views.settings_view import load_config
from database import get_cached_channels_list, cache_channels_list, set_channel_pinned, get_pinned_channels, get_media_states, get_media_downloaded_path


def make_lucide_refresh_icon(color: str, angle: float = 0) -> QIcon:
    """Lucide-style refresh-cw icon, optionally rotated (for the spin animation)."""
    paths = (
        '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>'
        '<path d="M21 3v5h-5"/>'
        '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>'
        '<path d="M3 21v-5h5"/>'
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round"><g transform="rotate({angle:.1f} 12 12)">{paths}</g></svg>'
    )
    pix = QPixmap()
    pix.loadFromData(svg.encode("utf-8"), "SVG")
    return QIcon(pix)


def _T(is_dark: bool) -> dict:
    """Semantic theme tokens (ui/theme.py) for the given theme flag."""
    from ui.theme import get_tokens
    return get_tokens(is_dark)


def format_bytes(size_bytes):
    if not size_bytes or size_bytes <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{int(size_bytes)} B"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def make_lucide_icon(name: str, color: str) -> QIcon:
    """Render a Lucide-style stroke icon (24x24, stroke-width 1.5) to a QIcon."""
    paths = {
        "download": '<path d="M12 15V3"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/>',
        "check": '<path d="M20 6 9 17l-5-5"/>',
        "resume": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
        "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
    }
    body = paths.get(name, paths["download"])
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    )
    pixmap = QPixmap()
    pixmap.loadFromData(svg.encode("utf-8"), "SVG")
    return QIcon(pixmap)


def dl_state_color(state: str, is_dark: bool) -> str:
    if state == "done":
        return "#10B981"   # green check
    if state == "resume":
        return "#F59E0B"   # amber resume/incomplete
    return _T(is_dark)["subtle_foreground"]  # idle download


def dl_state_icon_name(state: str) -> str:
    return {"done": "check", "resume": "resume"}.get(state, "download")


def _make_stat_item(icon: str, label: str) -> QWidget:
    """Creates a small stat block: icon + label, like Telegram's media counts."""
    w = QWidget()
    w.setObjectName("MediaStatItem")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    lay.setAlignment(Qt.AlignVCenter)

    ico = QLabel(icon)
    ico.setStyleSheet("font-size: 13px;")
    lay.addWidget(ico)

    lbl = QLabel(label)
    lbl.setObjectName("MediaStatLabel")
    lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
    lay.addWidget(lbl)

    return w


AVATAR_COLORS = [
    "#EF4444", "#F97316", "#F59E0B", "#10B981", 
    "#06B6D4", "#3B82F6", "#6366F1", "#8B5CF6", 
    "#EC4899", "#14B8A6"
]

def get_avatar_color(text: str) -> str:
    val = sum(ord(c) for c in (text or "TG"))
    return AVATAR_COLORS[val % len(AVATAR_COLORS)]


def make_circular_avatar(pixmap: QPixmap, size: int) -> QPixmap:
    """Takes a pixmap and clips it into a smooth, antialiased circular avatar."""
    if not pixmap or pixmap.isNull():
        return pixmap
    scaled = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    w = scaled.width()
    h = scaled.height()
    crop_x = max(0, (w - size) // 2)
    crop_y = max(0, (h - size) // 2)
    cropped = scaled.copy(crop_x, crop_y, size, size)

    target = QPixmap(size, size)
    target.fill(Qt.transparent)

    painter = QPainter(target)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, cropped)
    painter.end()

    return target


def make_rounded_thumbnail(pixmap: QPixmap, w: int, h: int, radius: int = 8) -> QPixmap:
    """Clips and rounds pixmap to specified w, h with smooth antialiased corners."""
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


def reveal_download_folder(channel_id, msg_id):
    """Open the folder containing the downloaded file in Explorer."""
    folder = None
    try:
        path = get_media_downloaded_path(channel_id, msg_id)
    except Exception:
        path = None
    if path:
        path = os.path.normpath(str(path))
        if os.path.isfile(path):
            folder = os.path.dirname(path)
        elif os.path.isdir(path):
            folder = path
        else:
            folder = os.path.dirname(path)
    if folder and os.path.isdir(folder):
        try:
            os.startfile(folder)
        except Exception as e:
            print(f"reveal_download_folder error: {e}")


class HoverIconButton(QPushButton):
    """QPushButton that emits enter/leave events as a hover signal."""
    hovered = Signal(bool)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.hovered.emit(True)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.hovered.emit(False)


class HoverCopyLabel(QLabel):
    """Plain text label with pointer cursor: brightens on hover, emits clicked
    on mouse release (used for the channel-ID copy control)."""
    clicked = Signal()

    def __init__(self, text: str, parent=None, base_color: str = "#71717A", hover_color: str = "#3B82F6"):
        super().__init__(text, parent)
        self._base_color = base_color
        self._hover_color = hover_color
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"color: {self._base_color}; background: transparent; font-size: 13px;")
        self.setText(text)

    def enterEvent(self, event):
        self.setStyleSheet(f"color: {self._hover_color}; background: transparent; font-size: 13px;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(f"color: {self._base_color}; background: transparent; font-size: 13px;")
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class HoverPinButton(QPushButton):
    """Pin button that glows white/black on hover."""
    def __init__(self, parent_item, parent=None):
        super().__init__(parent)
        self.parent_item = parent_item
        self._hovered = False

    def enterEvent(self, event):
        super().enterEvent(event)
        self._hovered = True
        self.parent_item._update_pin_icon()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hovered = False
        self.parent_item._update_pin_icon()

    @property
    def is_hovered(self):
        return self._hovered


# ── Chat feed bubble helpers (used only by the "All" media view) ─────────────

AUDIO_EXTS = {"mp3", "wav", "ogg", "m4a", "flac", "aac", "opus", "wma"}
TEXT_EXTS = {"txt", "md", "csv", "log", "json", "xml", "srt", "yaml", "ini"}
ARCHIVE_EXTS = {"zip", "rar", "7z", "tar", "gz", "bz2", "xz"}
PDF_EXTS = {"pdf"}


def _bubble_kind(data: dict) -> str:
    """Classify a media item for icon purposes."""
    fname = str(data.get("filename", "") or "").lower()
    ext = fname.rsplit(".", 1)[-1] if "." in fname else ""
    mime = str(data.get("mime_type", "") or "").lower()
    if mime.startswith("audio") or ext in AUDIO_EXTS:
        return "audio"
    if mime.startswith("video") or ext in {"mp4", "mkv", "mov", "webm", "avi", "wmv", "m4v"}:
        return "video"
    if mime.startswith("image") or ext in {"jpg", "jpeg", "png", "gif", "webp", "bmp"}:
        return "image"
    if mime == "application/pdf" or ext in PDF_EXTS:
        return "pdf"
    if mime.startswith("text") or ext in TEXT_EXTS:
        return "text"
    if ext in ARCHIVE_EXTS:
        return "archive"
    return "file"


def make_file_icon(kind: str, size: int = 46) -> QPixmap:
    """Render a colored solid circle with a SOLID (filled) white Lucide file icon,
    details punched out in the background color."""
    palette = {
        "audio": "#10B981",
        "text": "#8B5CF6",
        "archive": "#F59E0B",
        "pdf": "#3B82F6",
        "file": "#3B82F6",
    }
    bg = palette.get(kind, "#3B82F6")
    # Solid lucide-file silhouette
    silhouette = '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" fill="#FFFFFF"/>'
    # Folded corner punch-out
    fold = '<path d="M14 2 L14 8 L20 8 Z" fill="{bg}"/>'.format(bg=bg)
    base = silhouette + fold
    punchouts = {
        "text": (
            base
            + f'<rect x="8.6" y="9" width="4.5" height="1.4" rx="0.7" fill="{bg}"/>'
            + f'<rect x="8.6" y="12.4" width="7" height="1.4" rx="0.7" fill="{bg}"/>'
            + f'<rect x="8.6" y="15.8" width="7" height="1.4" rx="0.7" fill="{bg}"/>'
        ),
        "audio": (
            base
            + f'<circle cx="10.3" cy="16.8" r="1.9" fill="{bg}"/>'
            + f'<rect x="12" y="9.4" width="1.6" height="7.6" fill="{bg}"/>'
            + f'<path d="M12 9.4 L16.6 8.1 L16.6 10.3 L12 11.5 Z" fill="{bg}"/>'
        ),
        "archive": (
            base
            + f'<rect x="10.8" y="9.5" width="2.4" height="2.4" rx="0.7" fill="{bg}"/>'
            + f'<rect x="10.8" y="13.3" width="2.4" height="2.4" rx="0.7" fill="{bg}"/>'
            + f'<rect x="10.8" y="16.8" width="2.4" height="2.4" rx="0.7" fill="{bg}"/>'
        ),
        "pdf": base,
        "file": base,
    }
    body = punchouts.get(kind, base)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        'viewBox="0 0 24 24">'
        f'<circle cx="12" cy="12" r="12" fill="{bg}"/>'
        f'<g transform="translate(4.6 4.6) scale(0.615)">{body}</g>'
        '</svg>'
    )
    pix = QPixmap()
    pix.loadFromData(svg.encode("utf-8"), "SVG")
    return pix


def make_play_overlay(size: int = 56) -> QPixmap:
    """Semi-transparent dark circle with a white play triangle (video preview)."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(0, 0, 0, 150))
    painter.drawEllipse(0, 0, size, size)
    cx, cy = size / 2, size / 2
    r = size * 0.24
    tri = QPainterPath()
    tri.moveTo(cx - r * 0.75, cy - r)
    tri.lineTo(cx - r * 0.75, cy + r)
    tri.lineTo(cx + r, cy)
    tri.closeSubpath()
    painter.setBrush(QColor("#FFFFFF"))
    painter.drawPath(tri)
    painter.end()
    return pix


class ChatBubbleWidget(QFrame):
    """Compact Telegram-style message bubble used by the 'All' media feed.
    Documents/txt/audio get a colorful circular file icon; videos/images show
    the thumbnail preview (videos get a play overlay). Click toggles selection."""
    selectionChanged = Signal(int, bool)  # (msg_id, is_selected)
    downloadSingle = Signal(dict)         # video_data

    def __init__(self, data: dict, is_dark: bool = False, dl_state: str = "download", parent=None):
        super().__init__(parent)
        self.video_data = data
        self.msg_id = data["id"]
        self.is_dark = is_dark
        self.is_selected = False
        self._raw_pixmap = None
        self.kind = _bubble_kind(data)
        self.dl_state = dl_state  # "download" | "done" | "resume"
        self.setObjectName("ChatBubble")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(280)
        self.setMaximumWidth(440)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Thumbnail preview for video/image (top of bubble) ──
        if self.kind in ("video", "image"):
            self.thumb_container = QFrame()
            self.thumb_container.setFixedHeight(190)
            self.thumb_container.setObjectName("VideoThumbBox")
            self.thumb_container.setStyleSheet("""
                QFrame#VideoThumbBox {
                    background-color: #09090B;
                    border-radius: 10px;
                }
            """)
            thumb_stack = QStackedLayout(self.thumb_container)
            thumb_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)

            self.lbl_thumb = QLabel()
            self.lbl_thumb.setAlignment(Qt.AlignCenter)
            self.lbl_thumb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.lbl_thumb.setStyleSheet("font-size: 28px; background: transparent; color: #52525B;")
            thumb_stack.addWidget(self.lbl_thumb)

            overlay = QWidget()
            overlay.setStyleSheet("background: transparent;")
            ov = QVBoxLayout(overlay)
            ov.setContentsMargins(8, 8, 8, 8)
            ov.addStretch(1)

            if self.kind == "video":
                play_row = QHBoxLayout()
                play_row.addStretch()
                self.lbl_play = QLabel()
                self.lbl_play.setFixedSize(56, 56)
                self.lbl_play.setPixmap(make_play_overlay(56))
                self.lbl_play.setStyleSheet("background: transparent;")
                play_row.addWidget(self.lbl_play)
                play_row.addStretch()
                ov.addLayout(play_row)
                ov.addStretch(1)

            bottom_row = QHBoxLayout()
            dur_str = self.video_data.get("duration_str", "")
            if dur_str and self.kind == "video":
                dur_lbl = QLabel(dur_str)
                dur_lbl.setStyleSheet("""
                    background-color: rgba(0, 0, 0, 0.82); color: #FFFFFF;
                    font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: 4px;
                """)
                bottom_row.addWidget(dur_lbl)
            bottom_row.addStretch()
            ov.addLayout(bottom_row)
            thumb_stack.addWidget(overlay)
            layout.addWidget(self.thumb_container)

        # ── Body row: icon (files only) + filename/size/timestamp ──
        body = QHBoxLayout()
        body.setSpacing(12)
        body.setContentsMargins(2, 0, 2, 0)

        if self.kind not in ("video", "image"):
            self.lbl_icon = QLabel()
            self.lbl_icon.setFixedSize(46, 46)
            self.lbl_icon.setPixmap(make_file_icon(self.kind, 46))
            self.lbl_icon.setStyleSheet("background: transparent;")
            body.addWidget(self.lbl_icon, alignment=Qt.AlignVCenter)
        else:
            self.lbl_icon = None

        info = QVBoxLayout()
        info.setSpacing(2)

        raw_title = str(self.video_data.get("title") or self.video_data.get("filename", "")).strip()
        fname = str(self.video_data.get("filename", raw_title)).strip()
        self.lbl_title = QLabel(fname)
        self.lbl_title.setObjectName("ChatBubbleTitle")
        self.lbl_title.setWordWrap(False)
        self.lbl_title.setMaximumWidth(320)
        self.lbl_title.setToolTip(html.escape(fname))
        title_color = _T(self.is_dark)["foreground"]
        self.lbl_title.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {title_color}; background: transparent;"
        )

        # Download state button, inline with the title (download / check / resume)
        title_row = QHBoxLayout()
        title_row.setSpacing(4)
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.addWidget(self.lbl_title)
        title_row.addStretch()
        self.btn_dl_state = self._make_dl_state_button()
        title_row.addWidget(self.btn_dl_state)
        info.addLayout(title_row)

        size_str = format_bytes(self.video_data.get("size_bytes", 0))
        dur_str = str(self.video_data.get("duration_str", "") or "").strip()
        size_display = f"{size_str}  ·  {dur_str}" if dur_str else size_str
        size_color = _T(self.is_dark)["subtle_foreground"]
        self.lbl_size = QLabel(size_display)
        self.lbl_size.setStyleSheet(f"font-size: 12px; color: {size_color}; background: transparent;")
        info.addWidget(self.lbl_size)
        body.addLayout(info, stretch=1)

        layout.addLayout(body)

        # ── Timestamp row (bottom-right) ──
        ts_row = QHBoxLayout()
        ts_row.setContentsMargins(0, 0, 2, 0)
        ts_row.addStretch()
        date_str = str(self.video_data.get("date_str", ""))
        self.lbl_date = QLabel(date_str)
        self.lbl_date.setStyleSheet("font-size: 11px; color: #8E8E93; background: transparent;")
        ts_row.addWidget(self.lbl_date)
        layout.addLayout(ts_row)

        self._update_selected_style()

    def _make_dl_state_button(self) -> QPushButton:
        """Inline download-state button: download (idle), check (downloaded),
        RotateCcw (incomplete — click to resume from where it stopped)."""
        btn = HoverIconButton()
        btn.setFixedSize(26, 26)
        btn.setCursor(Qt.PointingHandCursor if self.dl_state != "done" else Qt.PointingHandCursor)
        tooltips = {
            "download": "Download immediately",
            "done": "Downloaded — click to open the folder it was saved to",
            "resume": "Download incomplete — click to resume the remaining parts",
        }
        btn.setToolTip(tooltips.get(self.dl_state, "Download"))
        btn.clicked.connect(self._on_dl_state_clicked)
        btn.hovered.connect(self._on_dl_hover)
        self._style_dl_state_button(btn)
        return btn

    def _style_dl_state_button(self, btn: QPushButton = None):
        btn = btn or getattr(self, 'btn_dl_state', None)
        if btn is None:
            return
        color = dl_state_color(self.dl_state, self.is_dark)
        btn.setIcon(make_lucide_icon(dl_state_icon_name(self.dl_state), color))
        btn.setIconSize(QSize(16, 16))
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent; border: none; border-radius: 13px;
            }
            QPushButton:hover {
                background-color: rgba(59, 130, 246, 0.12);
            }
        """)

    def _on_dl_hover(self, hovered: bool):
        """On hover, a completed download's check icon swaps to a folder icon."""
        if self.dl_state != "done":
            return
        if hovered:
            self.btn_dl_state.setIcon(make_lucide_icon("folder", "#3B82F6"))
            self.btn_dl_state.setToolTip("Open the folder this file was saved to")
        else:
            self.btn_dl_state.setIcon(make_lucide_icon("check", dl_state_color("done", self.is_dark)))
            self.btn_dl_state.setToolTip("Downloaded — click to open the folder it was saved to")

    def _on_dl_state_clicked(self):
        if self.dl_state == "done":
            # Open the folder the file was downloaded to
            reveal_download_folder(self.video_data.get("channel_id", ""), self.msg_id)
            return
        # Normal download and resume both go through the same worker request;
        # the downloader continues from the existing .part file, if any.
        self.downloadSingle.emit(self.video_data)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._raw_pixmap:
            self._update_thumbnail_display()

    def set_thumbnail(self, pixmap: QPixmap):
        if pixmap and not pixmap.isNull() and hasattr(self, 'thumb_container'):
            self._raw_pixmap = pixmap
            self._update_thumbnail_display()

    def _update_thumbnail_display(self):
        if not hasattr(self, 'thumb_container'):
            return
        if self._raw_pixmap and not self._raw_pixmap.isNull():
            w = max(280, self.thumb_container.width())
            h = self.thumb_container.height()
            rounded = make_rounded_thumbnail(self._raw_pixmap, w, h, radius=10)
            self.lbl_thumb.setPixmap(rounded)
            self.lbl_thumb.setText("")

    def update_theme(self, is_dark: bool):
        self.is_dark = is_dark
        title_color = _T(is_dark)["foreground"]
        size_color = _T(is_dark)["subtle_foreground"]
        self.lbl_title.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {title_color}; background: transparent;"
        )
        self.lbl_size.setStyleSheet(f"font-size: 12px; color: {size_color}; background: transparent;")
        self._style_dl_state_button()
        self._update_selected_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.pos())
            if child is not getattr(self, 'btn_dl_state', None):
                self.set_selected(not self.is_selected)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self._update_selected_style()
        self.selectionChanged.emit(self.msg_id, self.is_selected)

    def _update_selected_style(self):
        if self.is_selected:
            bg = "rgba(59, 130, 246, 0.14)" if self.is_dark else "rgba(37, 99, 235, 0.09)"
            border = "#3B82F6" if self.is_dark else "#2563EB"
            self.setStyleSheet(f"""
                QFrame#ChatBubble {{
                    background-color: {bg}; border: 2px solid {border}; border-radius: 14px;
                }}
            """)
        else:
            bg = "#18181B" if self.is_dark else "#FFFFFF"
            border = "#27272A" if self.is_dark else "#E4E4E7"
            hover = "#3F3F46" if self.is_dark else "#A1A1AA"
            self.setStyleSheet(f"""
                QFrame#ChatBubble {{
                    background-color: {bg}; border: 1px solid {border}; border-radius: 14px;
                }}
                QFrame#ChatBubble:hover {{ border-color: {hover}; }}
            """)


class ChannelListItem(QWidget):
    """Custom widget for channels in the left list with real profile avatar support."""
    pinToggled = Signal(str, bool)  # (channel_id, is_pinned)

    def __init__(self, data: dict, is_dark: bool = False, parent=None):
        super().__init__(parent)
        self.data = data
        self.is_dark_theme = is_dark
        self.setObjectName("ChannelListItem")
        self.is_pinned = bool(data.get("pinned", 0))
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        # 1. Circle Avatar (Real photo if cached, else fallback initials)
        title = self.data.get("title", "Untitled")
        initials = "".join([w[0] for w in title.split() if w][:2]).upper() or "TG"
        bg_hex = get_avatar_color(title)

        self.avatar = QLabel()
        self.avatar.setFixedSize(40, 40)
        self.avatar.setAlignment(Qt.AlignCenter)

        # Check local cache for channel profile photo
        cid = str(self.data.get("id", "")).replace("-100", "", 1) if str(self.data.get("id", "")).startswith("-100") else str(self.data.get("id", ""))
        avatar_dir = os.path.join(get_project_root(), "cache", "avatars")
        avatar_path = os.path.join(avatar_dir, f"{cid}.jpg")

        if os.path.exists(avatar_path) and os.path.getsize(avatar_path) > 0:
            pix = QPixmap(avatar_path)
            if not pix.isNull():
                self.avatar.setPixmap(make_circular_avatar(pix, 40))
                self.avatar.setText("")
                self.avatar.setStyleSheet("background: transparent; border-radius: 20px;")
            else:
                self._set_fallback_avatar(initials, bg_hex)
        else:
            self._set_fallback_avatar(initials, bg_hex)

        layout.addWidget(self.avatar)

        # 2. Channel Title & Subtitle Stack
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignVCenter)

        lbl_title = QLabel(title)
        lbl_title.setObjectName("ChannelListTitle")
        lbl_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        
        username = self.data.get("username", "")
        if not username:
            if self.data.get("is_channel"):
                username = "Channel"
            elif self.data.get("is_group"):
                username = "Group"
            else:
                username = "Chat"

        lbl_sub = QLabel(username)
        lbl_sub.setObjectName("ChannelListSub")
        lbl_sub.setStyleSheet("color: #71717A; font-size: 11px;")

        info_layout.addWidget(lbl_title)
        info_layout.addWidget(lbl_sub)
        layout.addLayout(info_layout, stretch=1)

        # 3. Pin button — marks channel as a favorite for quick access
        self.btn_pin = HoverPinButton(self)
        self.btn_pin.setFixedSize(28, 28)
        self.btn_pin.setCursor(Qt.PointingHandCursor)
        self.btn_pin.setToolTip("Unpin channel" if self.is_pinned else "Pin channel")
        self.btn_pin.setIcon(self._lucide_pin_icon(self._pin_color()))
        self.btn_pin.setIconSize(QSize(16, 16))
        self.btn_pin.setStyleSheet(self._pin_style())
        self.btn_pin.clicked.connect(self._toggle_pin)
        layout.addWidget(self.btn_pin)

    def _pin_style(self):
        """No hover background — icon color carries the state, glow on hover."""
        glow_color = "rgba(255, 255, 255, 0.35)" if self.is_dark_theme else "rgba(0, 0, 0, 0.25)"
        return f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 14px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: transparent;
            }}
        """

    def _hover_glow_icon(self) -> QIcon:
        """Return QIcon with glow color for hover state (white/black per theme)."""
        color = "#FFFFFF" if self.is_dark_theme else "#09090B"
        return self._lucide_pin_icon(color)

    def _lucide_pin_icon(self, color: str) -> QIcon:
        """Return QIcon built from the provided Lucide pin SVG with explicit color.
        Filled when pinned, outline when not pinned."""
        if color is None:
            color = "#FFFFFF" if self.is_dark_theme else "#09090B"
        fill = color if self.is_pinned else "none"
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
            f'fill="{fill}" stroke="{color}" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round" class="lucide lucide-pin preview-icon">'
            '<path d="M12 17v5"/>'
            '<path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/>'
            '</svg>'
        )
        pixmap = QPixmap()
        pixmap.loadFromData(svg.encode("utf-8"), "SVG")
        return QIcon(pixmap)

    def _pin_color(self) -> str:
        """Determine the pin icon color based on pinned state, hover, and theme."""
        # On hover: always white/black (glow) regardless of pinned state
        if hasattr(self.btn_pin, 'is_hovered') and self.btn_pin.is_hovered:
            return "#FFFFFF" if self.is_dark_theme else "#09090B"
        if self.is_pinned:
            return "#FFFFFF" if self.is_dark_theme else "#09090B"
        # Not pinned: grayish
        return "#9CA3AF" if self.is_dark_theme else "#6B7280"

    def _update_pin_icon(self):
        """Refresh the pin icon based on current hover/pinned/theme state."""
        self.btn_pin.setIcon(self._lucide_pin_icon(self._pin_color()))
        self.btn_pin.setIconSize(QSize(16, 16))

    def set_theme(self, is_dark: bool):
        """Update the pin icon color for light/dark theme."""
        self.is_dark_theme = is_dark
        self.btn_pin.setIcon(self._lucide_pin_icon(self._pin_color()))
        self.btn_pin.setIconSize(QSize(16, 16))
        self.btn_pin.setStyleSheet(self._pin_style())

    def _set_fallback_avatar(self, initials: str, bg_hex: str):
        self.avatar.setText(initials[:2])
        self.avatar.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_hex};
                color: #FFFFFF;
                font-weight: 700;
                font-size: 13px;
                border-radius: 20px;
            }}
        """)

    def set_avatar_pixmap(self, pixmap: QPixmap):
        if pixmap and not pixmap.isNull():
            self.avatar.setPixmap(make_circular_avatar(pixmap, 40))
            self.avatar.setText("")
            self.avatar.setStyleSheet("background: transparent; border-radius: 20px;")

    def set_pinned(self, pinned: bool):
        """Update the pinned state and refresh the pin button UI."""
        self.is_pinned = pinned
        self.btn_pin.setIcon(self._lucide_pin_icon(self._pin_color()))
        self.btn_pin.setIconSize(QSize(16, 16))
        self.btn_pin.setToolTip("Unpin channel" if pinned else "Pin channel")
        self.btn_pin.setStyleSheet(self._pin_style())

    def _toggle_pin(self):
        new_state = not self.is_pinned
        cid = str(self.data.get("id", ""))
        self.set_pinned(new_state)
        self.pinToggled.emit(cid, new_state)


class VideoCardWidget(QFrame):
    """Card representing a video message with thumbnail, metadata, checkbox, and 1-click download."""
    selectionChanged = Signal(int, bool) # (msg_id, is_selected)
    downloadSingle = Signal(dict)        # video_data

    def __init__(self, video_data: dict, is_dark: bool = False, dl_state: str = "download", parent=None):
        super().__init__(parent)
        self.video_data = video_data
        self.msg_id = video_data["id"]
        self.is_selected = False
        self.is_dark = is_dark
        self.dl_state = dl_state  # "download" | "done" | "resume"
        self._raw_pixmap = None
        self.setObjectName("VideoCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(200)
        self.setMaximumWidth(16777215)
        self.setFixedHeight(320)
        self.setCursor(Qt.PointingHandCursor)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 10)
        main_layout.setSpacing(8)

        # ── 1. Thumbnail Container (16:9 Full-Bleed with Floating Overlays) ────
        self.thumb_container = QFrame()
        self.thumb_container.setFixedHeight(168)
        self.thumb_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.thumb_container.setObjectName("VideoThumbBox")
        self.thumb_container.setStyleSheet("""
            QFrame#VideoThumbBox {
                background-color: #09090B;
                border-radius: 8px;
            }
        """)
        
        # Stacked layout: image at base (layer 0), overlays floating on top (layer 1)
        thumb_stack = QStackedLayout(self.thumb_container)
        thumb_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)

        # Base layer: Full-bleed thumbnail image
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setAlignment(Qt.AlignCenter)
        self.lbl_thumb.setText("▶")
        self.lbl_thumb.setStyleSheet("font-size: 28px; background: transparent; color: #52525B;")
        self.lbl_thumb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        thumb_stack.addWidget(self.lbl_thumb)

        # Overlay layer: Controls floating above thumbnail
        overlay_widget = QWidget()
        overlay_widget.setStyleSheet("background: transparent;")
        t_layout = QVBoxLayout(overlay_widget)
        t_layout.setContentsMargins(8, 8, 8, 8)

        # Top overlay row (Checkbox on left, quick single download on right)
        top_overlay = QHBoxLayout()
        self.chk = QCheckBox()
        self.chk.setCursor(Qt.PointingHandCursor)
        self.chk.stateChanged.connect(self._on_check_toggled)
        top_overlay.addWidget(self.chk)
        top_overlay.addStretch()

        self.btn_quick_dl = HoverIconButton()
        self.btn_quick_dl.setFixedSize(28, 28)
        self.btn_quick_dl.setCursor(Qt.PointingHandCursor)
        self.btn_quick_dl.hovered.connect(self._on_quick_dl_hover)
        self._update_quick_dl_button()
        top_overlay.addWidget(self.btn_quick_dl)
        t_layout.addLayout(top_overlay)

        t_layout.addStretch(1)

        # Bottom overlay row (Resolution on left, Duration pill on right)
        bottom_overlay = QHBoxLayout()
        res_str = self.video_data.get("resolution", "")
        if res_str:
            h_res = res_str.split("x")[-1] if "x" in res_str else res_str
            res_lbl = f"{h_res}p" if h_res.isdigit() else res_str
            self.lbl_res = QLabel(res_lbl)
            self.lbl_res.setStyleSheet("""
                background-color: rgba(0, 0, 0, 0.75);
                color: #E4E4E7;
                font-size: 10px;
                font-weight: 600;
                padding: 2px 6px;
                border-radius: 4px;
            """)
            bottom_overlay.addWidget(self.lbl_res)
        
        bottom_overlay.addStretch()

        dur_str = self.video_data.get("duration_str", "")
        if dur_str:
            self.lbl_dur = QLabel(dur_str)
            self.lbl_dur.setStyleSheet("""
                background-color: rgba(0, 0, 0, 0.85);
                color: #FFFFFF;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 7px;
                border-radius: 4px;
            """)
            bottom_overlay.addWidget(self.lbl_dur)
        t_layout.addLayout(bottom_overlay)

        thumb_stack.addWidget(overlay_widget)
        main_layout.addWidget(self.thumb_container)

        # ── 2. Metadata Section ──────────────────────────────────────────────
        meta_layout = QVBoxLayout()
        meta_layout.setContentsMargins(4, 2, 4, 2)
        meta_layout.setSpacing(6)

        raw_title = (self.video_data.get("title", "") or self.video_data.get("filename", "")).strip()
        self.lbl_title = QLabel()
        self.lbl_title.setObjectName("VideoCardTitle")
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.lbl_title.setFixedHeight(68)
        escaped_tip = html.escape(raw_title).replace("\n", "<br>")
        self.lbl_title.setToolTip(f"<div style='font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; font-size: 12px; line-height: 1.4;'>{escaped_tip}</div>")

        # On card face, show the clean primary title block (up to first 3 lines)
        title_blocks = [p.strip() for p in raw_title.split("\n\n") if p.strip()]
        if title_blocks:
            first_block = title_blocks[0]
            lines = [l.strip() for l in first_block.splitlines() if l.strip()]
            display_title = "\n".join(lines[:3])
        else:
            display_title = raw_title
        self.lbl_title.setText(display_title)

        title_color = _T(self.is_dark)["foreground"]
        self.lbl_title.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {title_color}; padding: 2px 0px 2px 0px;")
        meta_layout.addWidget(self.lbl_title)

        # Bottom row with size & date
        row_stats = QHBoxLayout()
        size_str = format_bytes(self.video_data.get("size_bytes", 0))
        dur_str = str(self.video_data.get("duration_str", "") or "").strip()
        size_display = f"{size_str}  ·  {dur_str}" if dur_str else size_str
        self.lbl_size = QLabel(size_display)
        size_color = _T(self.is_dark)["subtle_foreground"]
        self.lbl_size.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {size_color};")

        date_str = self.video_data.get("date_str", "")
        self.lbl_date = QLabel(date_str)
        self.lbl_date.setStyleSheet("font-size: 11px; color: #71717A;")

        row_stats.addWidget(self.lbl_size)
        row_stats.addStretch()
        row_stats.addWidget(self.lbl_date)
        meta_layout.addLayout(row_stats)

        main_layout.addLayout(meta_layout)
        self._update_card_style()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._raw_pixmap:
            self._update_thumbnail_display()

    def set_thumbnail(self, pixmap: QPixmap):
        if pixmap and not pixmap.isNull():
            self._raw_pixmap = pixmap
            self._update_thumbnail_display()

    def _update_thumbnail_display(self):
        if self._raw_pixmap and not self._raw_pixmap.isNull():
            w = max(200, self.thumb_container.width())
            h = self.thumb_container.height()
            if h <= 0:
                h = 168
            rounded = make_rounded_thumbnail(self._raw_pixmap, w, h, radius=8)
            self.lbl_thumb.setPixmap(rounded)
            self.lbl_thumb.setText("")

    def update_theme(self, is_dark: bool):
        self.is_dark = is_dark
        title_color = _T(is_dark)["foreground"]
        size_color = _T(is_dark)["subtle_foreground"]
        self.lbl_title.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {title_color}; padding: 2px 0px 2px 0px;")
        self.lbl_size.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {size_color};")
        self._update_card_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Clicking anywhere on the card toggles selection (unless clicking child button)
            child = self.childAt(event.pos())
            if child != self.btn_quick_dl and child != self.chk:
                self.set_selected(not self.is_selected)
        super().mousePressEvent(event)

    def _on_check_toggled(self, state):
        self.is_selected = (state == Qt.Checked.value or state == True)
        self._update_card_style()
        self.selectionChanged.emit(self.msg_id, self.is_selected)

    def _update_quick_dl_button(self):
        """Sync the overlay quick-download button with the download state:
        download (idle), check (downloaded), RotateCcw (resume)."""
        state = getattr(self, 'dl_state', 'download')
        tooltips = {
            "download": "Download this video immediately",
            "done": "Downloaded — click to open the folder it was saved to",
            "resume": "Download incomplete — click to resume the remaining parts",
        }
        self.btn_quick_dl.setToolTip(tooltips.get(state, "Download"))
        icon_color = {"done": "#10B981", "resume": "#F59E0B"}.get(state, "#FFFFFF")
        self.btn_quick_dl.setIcon(make_lucide_icon(dl_state_icon_name(state), icon_color))
        self.btn_quick_dl.setIconSize(QSize(16, 16))
        self.btn_quick_dl.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 0.65);
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 14px;
            }
            QPushButton:hover {
                background-color: #000000;
                border-color: #FFFFFF;
            }
        """)
        self.btn_quick_dl.clicked.connect(self._on_quick_dl_clicked)

    def _on_quick_dl_clicked(self):
        if getattr(self, 'dl_state', 'download') == 'done':
            # Open the folder the file was downloaded to
            reveal_download_folder(self.video_data.get("channel_id", ""), self.msg_id)
            return
        self.downloadSingle.emit(self.video_data)

    def _on_quick_dl_hover(self, hovered: bool):
        """On hover, a completed download's check icon swaps to a folder icon."""
        if getattr(self, 'dl_state', 'download') != 'done':
            return
        if hovered:
            self.btn_quick_dl.setIcon(make_lucide_icon("folder", "#3B82F6"))
            self.btn_quick_dl.setToolTip("Open the folder this file was saved to")
        else:
            self.btn_quick_dl.setIcon(make_lucide_icon("check", "#10B981"))
            self.btn_quick_dl.setToolTip("Downloaded — click to open the folder it was saved to")

    def set_selected(self, selected: bool):
        if self.is_selected != selected:
            self.is_selected = selected
            self.chk.blockSignals(True)
            self.chk.setChecked(selected)
            self.chk.blockSignals(False)
            self._update_card_style()
            self.selectionChanged.emit(self.msg_id, self.is_selected)

    def _update_card_style(self):
        if self.is_selected:
            bg = "rgba(59, 130, 246, 0.12)" if self.is_dark else "rgba(37, 99, 235, 0.08)"
            border_col = "#3B82F6" if self.is_dark else "#2563EB"
            self.setStyleSheet(f"""
                QFrame#VideoCard {{
                    background-color: {bg};
                    border: 2px solid {border_col};
                    border-radius: 10px;
                }}
            """)
        else:
            bg = "#18181B" if self.is_dark else "#FFFFFF"
            border_col = "#27272A" if self.is_dark else "#E4E4E7"
            self.setStyleSheet(f"""
                QFrame#VideoCard {{
                    background-color: {bg};
                    border: 1px solid {border_col};
                    border-radius: 10px;
                }}
                QFrame#VideoCard:hover {{
                    border-color: {"#52525B" if self.is_dark else "#A1A1AA"};
                }}
            """)


class ExploreView(QWidget):
    """
    Explore View: A Telegram-like UI for discovering channels and bulk downloading videos.
    """
    downloadRequested = Signal(str, list) # (channel_id, [selected_message_ids])
    switchToQueueRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_channels = []
        self.filtered_channels = []
        self.current_channel_id = None
        self.current_channel_data = None
        self.current_videos = []
        self.selected_ids = set()
        self.video_cards = {} # msg_id -> VideoCardWidget
        self._channel_index = {} # clean id -> QListWidgetItem
        self._active_channel_item = None # currently selected left sidebar item
        self._channel_list_items = [] # ChannelListItem widgets for theme updates
        self.worker = None
        self.thumb_worker = None
        self.is_dark_theme = False
        self.current_media_type = "videos"  # "all", "videos", "images", "documents", "audio", "text"
        try:
            cfg = load_config()
            self.is_dark_theme = bool(cfg.get("dark_mode", False))
        except Exception:
            pass

        self.setup_ui()
        self.load_cached_channels()

    def set_worker(self, worker):
        self.worker = worker
        if self.worker:
            self.worker.signals.dialogs_fetched.connect(self.on_dialogs_fetched)
            self.worker.signals.channel_videos_fetched.connect(self.on_channel_videos_fetched)
            self.worker.signals.explore_loading.connect(self.on_explore_loading)
            self.worker.signals.explore_error.connect(self.on_explore_error)
            if hasattr(self.worker.signals, 'avatar_ready'):
                self.worker.signals.avatar_ready.connect(self.on_avatar_ready)
            if hasattr(self.worker.signals, 'thumbnail_ready'):
                self.worker.signals.thumbnail_ready.connect(self.on_thumbnail_ready)

    def load_cached_channels(self):
        cached = get_cached_channels_list()
        if not cached:
            return

        normalized = []
        for ch in cached:
            cid = str(ch.get("channel_id") or ch.get("id") or "").strip()
            if not cid:
                continue
            # cache_channel() stores ids without the -100 prefix; add it back
            full_id = f"-100{cid}" if cid.isdigit() and not cid.startswith("-") else cid
            uname = str(ch.get("username") or "").strip()
            # Keep only real @usernames; cache rows created by the media-fetch
            # path sometimes put a raw numeric id into this column.
            uname = uname if (uname.startswith("@") and len(uname) > 1) else ""
            normalized.append({
                "id": full_id,
                "raw_id": full_id,
                "title": ch.get("title") or "Untitled",
                "username": uname,
                "is_channel": bool(ch.get("is_channel")),
                "is_group": bool(ch.get("is_group")),
                "is_user": False,
                "unread_count": ch.get("unread_count", 0),
                "date": ch.get("date") or "",
                "pinned": bool(ch.get("pinned", 0)),
            })

        self.all_channels = normalized
        self.filter_channels()

    def setup_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ═════════════════════════════════════════════════════════════════════
        # Left Panel: Telegram Channels & Chats Sidebar (Width: 320px)
        # ═════════════════════════════════════════════════════════════════════
        left_panel = QFrame()
        left_panel.setObjectName("ExploreLeftSidebar")
        left_panel.setFixedWidth(320)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 20, 16, 16)
        left_layout.setSpacing(12)

        # Header Row
        left_header = QHBoxLayout()
        self.lbl_channels_title = QLabel("Channels & Chats")
        self.lbl_channels_title.setObjectName("MainHeader")
        self.lbl_channels_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        
        self.lbl_channel_count = QLabel("0")
        self.lbl_channel_count.setStyleSheet("""
            font-size: 12px;
            font-weight: 500;
            color: #71717A;
            background-color: transparent;
            border: none;
            padding: 0px;
        """)

        left_header.addWidget(self.lbl_channels_title)
        left_header.addSpacing(6)
        left_header.addWidget(self.lbl_channel_count)
        left_header.addStretch()

        self.btn_refresh_channels = QPushButton()
        self.btn_refresh_channels.setObjectName("IconButton")
        self.btn_refresh_channels.setFixedSize(32, 32)
        self.btn_refresh_channels.setIconSize(QSize(14, 14))
        self.btn_refresh_channels.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_channels.setToolTip("Refresh channel list and current media")
        self.btn_refresh_channels.clicked.connect(self.refresh_channels_from_telegram)
        left_header.addWidget(self.btn_refresh_channels)
        left_layout.addLayout(left_header)

        # Channel Search Bar (Telegram-style search)
        self.search_channels = QLineEdit()
        self.search_channels.setObjectName("SearchInput")
        self.search_channels.setPlaceholderText("Search")
        self.search_channels.setMinimumHeight(36)
        self.search_channels.textChanged.connect(self.on_search_text_changed)
        left_layout.addWidget(self.search_channels)

        # Search header (shown when search is active) - Telegram style "Search messages in"
        self.search_header = QFrame()
        self.search_header.setObjectName("SearchHeader")
        self.search_header.setStyleSheet("""
            QFrame#SearchHeader {
                background-color: #1A1A1B;
                border-bottom: 1px solid #27272A;
            }
        """)
        self.search_header.hide()
        search_header_layout = QHBoxLayout(self.search_header)
        search_header_layout.setContentsMargins(12, 8, 12, 8)
        search_header_layout.setSpacing(8)

        self.lbl_search_in = QLabel("Search messages in")
        self.lbl_search_in.setObjectName("MutedText")
        self.lbl_search_in.setStyleSheet("font-size: 13px; color: #8E8E93;")
        search_header_layout.addWidget(self.lbl_search_in)

        self.combo_search_channel = SearchableComboBox()
        self.combo_search_channel.setFixedWidth(150)
        self.combo_search_channel.setFixedHeight(30)
        search_header_layout.addWidget(self.combo_search_channel)

        self.btn_close_search = QPushButton("✕")
        self.btn_close_search.setFixedSize(28, 28)
        self.btn_close_search.setCursor(Qt.PointingHandCursor)
        self.btn_close_search.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8E8E93;
                font-size: 16px;
                border: none;
                border-radius: 14px;
            }
            QPushButton:hover {
                background-color: #27272A;
                color: #FFFFFF;
            }
        """)
        self.btn_close_search.clicked.connect(self.close_search)
        search_header_layout.addWidget(self.btn_close_search)

        left_layout.addWidget(self.search_header)

        # Empty search state (magnifying glass + "Search for messages")
        self.search_empty = QWidget()
        self.search_empty.setObjectName("SearchEmpty")
        self.search_empty.hide()
        search_empty_layout = QVBoxLayout(self.search_empty)
        search_empty_layout.setAlignment(Qt.AlignCenter)
        search_empty_layout.setSpacing(12)

        self.lbl_search_icon = QLabel("🔍")
        self.lbl_search_icon.setStyleSheet("font-size: 64px;")
        self.lbl_search_icon.setAlignment(Qt.AlignCenter)
        search_empty_layout.addWidget(self.lbl_search_icon)

        self.lbl_search_empty_text = QLabel("Search for messages")
        self.lbl_search_empty_text.setStyleSheet("font-size: 15px; color: #8E8E93; font-weight: 500;")
        self.lbl_search_empty_text.setAlignment(Qt.AlignCenter)
        search_empty_layout.addWidget(self.lbl_search_empty_text)

        left_layout.addWidget(self.search_empty, stretch=1)

        # Filter Segment Buttons (All, Pinned, Channels, Groups)
        filter_tabs = QHBoxLayout()
        filter_tabs.setSpacing(6)
        self.btn_tab_all = QPushButton("All")
        self.btn_tab_pinned = QPushButton("Pinned")
        self.btn_tab_channels = QPushButton("Channels")
        self.btn_tab_groups = QPushButton("Groups")

        self.current_filter_tab = "all"
        for btn, tab_id in [(self.btn_tab_all, "all"), (self.btn_tab_pinned, "pinned"), (self.btn_tab_channels, "channels"), (self.btn_tab_groups, "groups")]:
            btn.setObjectName("TabPill")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, tid=tab_id: self.set_filter_tab(tid))
            filter_tabs.addWidget(btn)

        self.btn_tab_all.setChecked(True)
        left_layout.addLayout(filter_tabs)

        # Channels List Widget
        self.channel_list = QListWidget()
        self.channel_list.setObjectName("ExploreChannelList")
        self.channel_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.channel_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.channel_list.itemClicked.connect(self.on_channel_item_clicked)
        left_layout.addWidget(self.channel_list, stretch=1)

        root_layout.addWidget(left_panel)

        # ═════════════════════════════════════════════════════════════════════
        # Right Panel: Video Grid & Bulk Downloader
        # ═════════════════════════════════════════════════════════════════════
        right_panel = QWidget()
        right_panel.setObjectName("ExploreRightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(24, 20, 24, 16)
        right_layout.setSpacing(14)

        # ── 1. Top Channel Info & Actions Bar ──
        self.top_bar = QFrame()
        self.top_bar.setObjectName("ChannelNameCard")
        # Telegram-style flat name card: title bold, muted grey subtitle below
        top_bar_layout = QVBoxLayout(self.top_bar)
        top_bar_layout.setContentsMargins(2, 2, 2, 2)
        top_bar_layout.setSpacing(4)

        # Row 1: Avatar | Channel Title | Select All | Refresh (all inline)
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        row1.setAlignment(Qt.AlignVCenter)

        # Channel Avatar
        self.lbl_active_avatar = QLabel("TG")
        self.lbl_active_avatar.setFixedSize(44, 44)
        self.lbl_active_avatar.setAlignment(Qt.AlignCenter)
        self.lbl_active_avatar.setStyleSheet("""
            background-color: #3B82F6;
            color: #FFFFFF;
            font-weight: bold;
            font-size: 15px;
            border-radius: 22px;
        """)
        row1.addWidget(self.lbl_active_avatar)

        # Channel Title + Sub info (center, stretch)
        title_info = QVBoxLayout()
        title_info.setSpacing(0)
        title_info.setAlignment(Qt.AlignVCenter)

        self.lbl_active_channel_title = QLabel("Select a channel to explore media")
        self.lbl_active_channel_title.setWordWrap(True)
        title_info.addWidget(self.lbl_active_channel_title)

        # ID + media count on one inline line
        id_row = QHBoxLayout()
        id_row.setSpacing(6)
        id_row.setContentsMargins(0, 0, 0, 0)
        id_row.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.lbl_active_channel_id = HoverCopyLabel("")
        self.lbl_active_channel_id.setObjectName("MutedText")
        self.lbl_active_channel_id.setToolTip("Click to copy channel ID")
        self.lbl_active_channel_id.clicked.connect(self._copy_channel_id)
        self.lbl_active_channel_id.setVisible(False)
        id_row.addWidget(self.lbl_active_channel_id)

        self.lbl_id_sep = QLabel("•")
        self.lbl_id_sep.setStyleSheet("color: #71717A; font-size: 13px; background: transparent;")
        self.lbl_id_sep.setVisible(False)
        id_row.addWidget(self.lbl_id_sep)

        self.lbl_active_channel_sub = QLabel("No channel selected")
        self.lbl_active_channel_sub.setObjectName("MutedText")
        id_row.addWidget(self.lbl_active_channel_sub)
        id_row.addStretch()
        title_info.addLayout(id_row)

        row1.addLayout(title_info, stretch=1)

        # Select All button (inline right)
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.setObjectName("SecondaryButton")
        self.btn_select_all.setFixedHeight(30)
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        self.btn_select_all.clicked.connect(self.toggle_select_all)
        row1.addWidget(self.btn_select_all)

        top_bar_layout.addLayout(row1)

        right_layout.addWidget(self.top_bar)

        # ── 2. Video Search & Filter Toolbar ─────────────────────────────────
        self.toolbar_widget = QWidget()
        toolbar = QHBoxLayout(self.toolbar_widget)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(10)

        self.search_videos = QLineEdit()
        self.search_videos.setObjectName("VercelInput")
        self.search_videos.setPlaceholderText("Filter videos by title or filename...")
        self.search_videos.setMinimumHeight(36)
        self.search_videos.textChanged.connect(self.apply_video_filter)
        toolbar.addWidget(self.search_videos, stretch=3)

        self.combo_sort = SearchableComboBox()
        self.combo_sort.addItems(["Newest First", "Oldest First", "Largest First", "Smallest First"])
        self.combo_sort.currentIndexChanged.connect(self.apply_video_sort)
        toolbar.addWidget(self.combo_sort, stretch=1)

        # Media type filter (Videos, Images, Documents, Audio, Text, All)
        self.combo_media_type = SearchableComboBox()
        self.combo_media_type.addItems(["All", "Videos", "Images", "Documents", "Audio", "Text/Chat"])
        self.combo_media_type.setCurrentText("Videos")
        self.combo_media_type.setFixedWidth(130)
        self.combo_media_type.currentIndexChanged.connect(self.on_media_type_changed)
        toolbar.addWidget(self.combo_media_type, stretch=1)

        right_layout.addWidget(self.toolbar_widget)

        # ── 3. Notification Banner (Toast) ───────────────────────────────────
        self.banner = QFrame()
        self.banner.setObjectName("SuccessBanner")
        self.banner.setStyleSheet("""
            QFrame#SuccessBanner {
                background-color: #ECFDF5;
                border: 1px solid #A7F3D0;
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        b_layout = QHBoxLayout(self.banner)
        b_layout.setContentsMargins(8, 6, 8, 6)
        self.lbl_banner_msg = QLabel("")
        self.lbl_banner_msg.setStyleSheet("color: #065F46; font-size: 12px; font-weight: 500;")
        self.btn_view_queue = QPushButton("View in Queue →")
        self.btn_view_queue.setObjectName("SecondaryButton")
        self.btn_view_queue.setFixedHeight(26)
        self.btn_view_queue.setCursor(Qt.PointingHandCursor)
        self.btn_view_queue.clicked.connect(lambda: self.switchToQueueRequested.emit())
        b_layout.addWidget(self.lbl_banner_msg)
        b_layout.addStretch()
        b_layout.addWidget(self.btn_view_queue)
        self.banner.hide()
        right_layout.addWidget(self.banner)

        # ── 4a. Empty Placeholder (shown until a channel is selected) ─────────
        self.right_placeholder = QWidget()
        ph_layout = QVBoxLayout(self.right_placeholder)
        ph_layout.setContentsMargins(24, 24, 24, 24)
        ph_layout.setAlignment(Qt.AlignCenter)
        ph_layout.setSpacing(6)

        self.lbl_ph_title = QLabel("Select a channel to explore media")
        self.lbl_ph_title.setAlignment(Qt.AlignCenter)
        self.lbl_ph_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #09090B;")
        self.lbl_ph_title.setWordWrap(True)

        self.lbl_ph_sub = QLabel("No channel is selected.")
        self.lbl_ph_sub.setObjectName("MutedText")
        self.lbl_ph_sub.setAlignment(Qt.AlignCenter)
        self.lbl_ph_sub.setWordWrap(True)

        ph_layout.addWidget(self.lbl_ph_title)
        ph_layout.addWidget(self.lbl_ph_sub)
        right_layout.addWidget(self.right_placeholder, stretch=1)

        # ── 4. Main Video Cards Area (Scroll Area with Grid) ─────────────────
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("ExploreScroll")
        self.scroll_area.setStyleSheet("border: none; background-color: transparent;")

        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setContentsMargins(4, 4, 4, 16)
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.scroll_content)

        # Status / Empty state placeholder
        self.lbl_empty_state = QLabel("← Select a channel from the left sidebar to view all its videos.")
        self.lbl_empty_state.setObjectName("MutedText")
        self.lbl_empty_state.setAlignment(Qt.AlignCenter)
        self.lbl_empty_state.setStyleSheet("font-size: 14px; font-weight: 500; padding: 60px;")

        self.stack_videos = QStackedWidget()
        self.stack_videos.addWidget(self.lbl_empty_state) # Index 0
        self.stack_videos.addWidget(self.scroll_area)      # Index 1

        right_layout.addWidget(self.stack_videos, stretch=1)

        # ── 5. Bottom Bulk Floating Bar (Appears when items are selected) ─────
        self.bottom_bar = QFrame()
        self.bottom_bar.setObjectName("WhiteCard")
        self.bottom_bar.setStyleSheet("""
            QFrame#WhiteCard {
                border-top: 2px solid #3B82F6;
            }
        """)
        bb_layout = QHBoxLayout(self.bottom_bar)
        bb_layout.setContentsMargins(16, 10, 16, 10)
        
        self.lbl_bottom_stats = QLabel("0 videos selected")
        self.lbl_bottom_stats.setStyleSheet("font-size: 13px; font-weight: 600;")
        
        self.btn_bottom_clear = QPushButton("Clear Selection")
        self.btn_bottom_clear.setObjectName("SecondaryButton")
        self.btn_bottom_clear.setFixedHeight(34)
        self.btn_bottom_clear.setCursor(Qt.PointingHandCursor)
        self.btn_bottom_clear.clicked.connect(self.clear_selection)

        self.btn_bottom_download = QPushButton("Download Selected Videos")
        self.btn_bottom_download.setObjectName("VercelButton")
        self.btn_bottom_download.setFixedHeight(34)
        self.btn_bottom_download.setCursor(Qt.PointingHandCursor)
        self.btn_bottom_download.clicked.connect(self.on_download_selected_clicked)

        bb_layout.addWidget(self.lbl_bottom_stats)
        bb_layout.addStretch()
        bb_layout.addWidget(self.btn_bottom_clear)
        bb_layout.addWidget(self.btn_bottom_download)
        self.bottom_bar.hide()
        right_layout.addWidget(self.bottom_bar)

        root_layout.addWidget(right_panel, stretch=1)

        # Initialize refresh icons
        self.update_theme(self.is_dark_theme)
        # Right panel shows only a hint until a channel is selected
        self._update_right_placeholder()

    def update_theme(self, is_dark: bool):
        self.is_dark_theme = is_dark
        suffix = "_white.png" if is_dark else "_black.png"
        icon_path = get_resource_path(os.path.join("assets", "icons", f"refresh{suffix}"))
        if os.path.exists(icon_path):
            self.btn_refresh_channels.setIcon(QIcon(icon_path))

        # Update tabs style
        tab_active_bg = "#27272A" if is_dark else "#09090B"
        tab_active_fg = "#FFFFFF" if is_dark else "#FFFFFF"
        tab_inactive_bg = "transparent"
        tab_inactive_fg = "#A1A1AA" if is_dark else "#71717A"

        for btn, tid in [(self.btn_tab_all, "all"), (self.btn_tab_pinned, "pinned"), (self.btn_tab_channels, "channels"), (self.btn_tab_groups, "groups")]:
            is_active = (self.current_filter_tab == tid)
            bg = tab_active_bg if is_active else tab_inactive_bg
            fg = tab_active_fg if is_active else tab_inactive_fg
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {fg};
                    border: 1px solid {'transparent' if is_active else ('#27272A' if is_dark else '#E4E4E7')};
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 500;
                    padding: 2px 10px;
                }}
            """)

        # Update placeholder hint colors per theme
        ph_title_color = _T(is_dark)["foreground"]
        ph_sub_color = "#A1A1AA" if is_dark else "#71717A"
        self.lbl_ph_title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {ph_title_color};")
        self.lbl_ph_sub.setStyleSheet(f"font-size: 12px; color: {ph_sub_color};")

        # Refresh searchable dropdown faces/icons for the active theme
        for combo_name in ("combo_sort", "combo_media_type", "combo_search_channel"):
            combo = getattr(self, combo_name, None)
            if combo is not None and hasattr(combo, "refresh_theme"):
                combo.refresh_theme()

        # Flat Telegram-style channel name card: transparent bar, bold title,
        # muted grey subtitle below (no card chrome).
        title_color = "#FFFFFF" if is_dark else "#09090B"
        self.top_bar.setStyleSheet("QFrame#ChannelNameCard { background-color: transparent; border: none; border-radius: 0px; }")
        self.lbl_active_channel_title.setStyleSheet(
            f"font-weight: 700; font-size: 13px; color: {title_color}; background-color: transparent;"
        )
        self.lbl_active_channel_sub.setStyleSheet(
            f"font-size: 12px; color: {'#A1A1AA' if is_dark else '#71717A'}; background-color: transparent; padding: 0px;"
        )

        # Update all video cards with new theme
        for card in self.video_cards.values():
            if hasattr(card, 'update_theme'):
                card.update_theme(is_dark)

        # Update pin icon color on all channel list items
        for widget in self._channel_list_items:
            if hasattr(widget, 'set_theme'):
                widget.set_theme(is_dark)

    def set_filter_tab(self, tab_id: str):
        self.current_filter_tab = tab_id
        for btn, tid in [(self.btn_tab_all, "all"), (self.btn_tab_pinned, "pinned"), (self.btn_tab_channels, "channels"), (self.btn_tab_groups, "groups")]:
            btn.setChecked(tid == tab_id)
        self.update_theme(self.is_dark_theme)
        self.filter_channels()

    def on_search_text_changed(self):
        """Handler for search text changes - delegates to filter_channels."""
        self.filter_channels()

    def filter_channels(self):
        query = self.search_channels.text().strip().lower()
        tab = self.current_filter_tab

        # Show/hide search header based on whether there's a query
        if query:
            self.search_header.show()
            # Populate the "Search messages in" dropdown with current channel
            self.combo_search_channel.blockSignals(True)
            self.combo_search_channel.clear()
            if self.current_channel_data:
                self.combo_search_channel.addItem(
                    self.current_channel_data.get("title", "This Channel"),
                    self.current_channel_data.get("id", "")
                )
            else:
                self.combo_search_channel.addItem("This Channel", "")
            self.combo_search_channel.blockSignals(False)
        else:
            self.search_header.hide()

        self.filtered_channels = []
        for ch in self.all_channels:
            title = ch.get("title", "").lower()
            uname = ch.get("username", "").lower()
            
            if query and (query not in title and query not in uname):
                continue
                
            if tab == "pinned":
                if not ch.get("pinned"):
                    continue
            elif tab == "channels" and not ch.get("is_channel"):
                continue
            elif tab == "groups" and not ch.get("is_group"):
                continue
                
            self.filtered_channels.append(ch)

        self.render_channel_list()

        # Show empty search state when there's a query but no results
        if query and not self.filtered_channels:
            self.channel_list.hide()
            self.search_empty.show()
        else:
            self.search_empty.hide()
            self.channel_list.show()

    def close_search(self):
        """Clear the search and return to normal channel list view."""
        had_query = bool(self.search_channels.text().strip())
        self.search_channels.clear()
        self.search_header.hide()
        self.search_empty.hide()
        self.channel_list.show()
        # Clearing the line edit emits textChanged -> on_search_text_changed ->
        # filter_channels when a query was present; when the field was already
        # empty there is nothing to re-filter, so no re-render is needed.

    def render_channel_list(self):
        self.channel_list.clear()
        # O(1) lookup: clean channel id -> QListWidgetItem for fast avatar updates
        self._channel_index = {}
        self._channel_list_items = []
        self.lbl_channel_count.setText(str(len(self.filtered_channels)))

        for ch in self.filtered_channels:
            item = QListWidgetItem(self.channel_list)
            item.setSizeHint(QSize(280, 58))
            item.setData(Qt.UserRole, ch)

            cid = str(ch.get("id", ""))
            cid_clean = cid.replace("-100", "", 1) if cid.startswith("-100") else cid
            self._channel_index[cid_clean] = item

            widget = ChannelListItem(ch, is_dark=self.is_dark_theme)
            widget.pinToggled.connect(self.on_channel_pin_toggled)
            self.channel_list.setItemWidget(item, widget)
            self._channel_list_items.append(widget)

    def _start_refresh_spin(self):
        """Start the rotating animation on the sidebar refresh icon."""
        self._spin_angle = 0.0
        if getattr(self, '_spin_timer', None) and self._spin_timer.isActive():
            return
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._on_refresh_spin_tick)
        self._spin_timer.start(30)  # ~33 fps

    def _on_refresh_spin_tick(self):
        self._spin_angle = (self._spin_angle + 24.0) % 360.0
        color = "#EDEDED" if self.is_dark_theme else "#09090B"
        self.btn_refresh_channels.setIcon(make_lucide_refresh_icon(color, self._spin_angle))
        self.btn_refresh_channels.setIconSize(QSize(16, 16))

    def _stop_refresh_spin(self):
        if getattr(self, '_spin_timer', None):
            self._spin_timer.stop()
        # Restore the static themed refresh icon
        self.update_theme(self.is_dark_theme)

    def refresh_channels_from_telegram(self):
        """Single refresh entry point: refresh both the channel/group list
        and the content of the currently open group/channel."""
        self._start_refresh_spin()
        if self.worker:
            self.worker.fetch_user_dialogs()
        # Also reload the media of the currently open group/channel
        self.refresh_current_channel_videos()
        # Safety net: stop the spin if the refresh takes unusually long
        QTimer.singleShot(5000, self._stop_refresh_spin)

    def on_dialogs_fetched(self, dialogs: list):
        # Refresh finished (or list fetch returned) — stop the spinner
        self._stop_refresh_spin()
        # Merge pinned state from existing channels so refreshes don't clear pins
        pinned_map = {str(ch.get("id", "")): bool(ch.get("pinned", 0)) for ch in self.all_channels}
        for d in dialogs:
            cid = str(d.get("id", ""))
            if cid in pinned_map:
                d["pinned"] = pinned_map[cid]
        self.all_channels = dialogs
        self.filter_channels()

    def on_channel_pin_toggled(self, channel_id: str, is_pinned: bool):
        """Persist the pin state and refresh the channel list."""
        set_channel_pinned(channel_id, is_pinned)
        # Update the pinned flag in all_channels so the UI reflects the change
        for ch in self.all_channels:
            if str(ch.get("id", "")) == channel_id:
                ch["pinned"] = 1 if is_pinned else 0
                break
        # Refresh to reflect pinned ordering (pinned first in "All" view)
        self.filter_channels()
        status = "pinned" if is_pinned else "unpinned"

    def on_avatar_ready(self, channel_id: str, avatar_path: str):
        """Called when a channel/chat profile picture has been downloaded to disk."""
        if not os.path.exists(avatar_path) or os.path.getsize(avatar_path) == 0:
            return
        pix = QPixmap(avatar_path)
        if pix.isNull():
            return

        cid_clean = str(channel_id).replace("-100", "", 1) if str(channel_id).startswith("-100") else str(channel_id)

        # 1. Update left channel list items via O(1) index
        item = getattr(self, '_channel_index', {}).get(cid_clean)
        if item:
            widget = self.channel_list.itemWidget(item)
            if widget and hasattr(widget, 'set_avatar_pixmap'):
                widget.set_avatar_pixmap(pix)

        # 2. Update active channel header avatar if currently viewing this channel
        if self.current_channel_id:
            curr_clean = str(self.current_channel_id).replace("-100", "", 1) if str(self.current_channel_id).startswith("-100") else str(self.current_channel_id)
            if curr_clean == cid_clean:
                self.lbl_active_avatar.setPixmap(make_circular_avatar(pix, 36))
                self.lbl_active_avatar.setText("")
                self.lbl_active_avatar.setStyleSheet("background: transparent; border-radius: 22px;")

    def on_explore_loading(self, is_loading: bool, status_text: str):
        if is_loading:
            if not self.current_videos:
                self.lbl_empty_state.setText(f"⌛ {status_text or 'Loading...'}")
                self.stack_videos.setCurrentIndex(0)
        else:
            if not self.current_videos and self.current_channel_id:
                self.lbl_empty_state.setText("No videos found in this channel.")
                self.stack_videos.setCurrentIndex(0)

    def on_explore_error(self, err_msg: str):
        self.lbl_empty_state.setText(f"⚠️ {err_msg}")
        self.stack_videos.setCurrentIndex(0)

    def _update_right_placeholder(self):
        """Before any channel is chosen, the right panel shows only a hint."""
        has_channel = bool(self.current_channel_id)
        self.right_placeholder.setVisible(not has_channel)

        if has_channel:
            self.top_bar.show()
            self.toolbar_widget.show()
            if self.banner.isVisible():
                self.banner.show()
            self.stack_videos.show()
            self.bottom_bar.show()
        else:
            self.top_bar.hide()
            self.toolbar_widget.hide()
            self.banner.hide()
            self.stack_videos.hide()
            self.bottom_bar.hide()

    def on_channel_item_clicked(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return

        # Whether a search query was active — closing the search may re-render
        # the channel list and replace the list item widgets.
        search_was_active = bool(self.search_channels.text().strip())

        # Apply active background to selected channel in left sidebar
        if self._active_channel_item is not None:
            self._active_channel_item.setBackground(QColor("#FFFFFF" if not self.is_dark_theme else "#18181B"))
        item.setBackground(QColor("#F3F4F6" if not self.is_dark_theme else "#27272A"))
        self._active_channel_item = item

        self.current_channel_id = str(data["id"])
        self.current_channel_data = data
        
        # Show the interactive right panel once a channel is selected
        self._update_right_placeholder()

        # Update top bar title
        title = data.get("title", "Untitled")
        self.lbl_active_channel_title.setText(title)

        # Check if profile picture is cached on disk
        cid_clean = str(data["id"]).replace("-100", "", 1) if str(data["id"]).startswith("-100") else str(data["id"])
        avatar_dir = os.path.join(get_project_root(), "cache", "avatars")
        avatar_path = os.path.join(avatar_dir, f"{cid_clean}.jpg")

        if os.path.exists(avatar_path) and os.path.getsize(avatar_path) > 0:
            pix = QPixmap(avatar_path)
            if not pix.isNull():
                self.lbl_active_avatar.setPixmap(make_circular_avatar(pix, 36))
                self.lbl_active_avatar.setText("")
                self.lbl_active_avatar.setStyleSheet("background: transparent; border-radius: 22px;")
            else:
                self._set_active_fallback_avatar(title)
        else:
            self._set_active_fallback_avatar(title)
            if self.worker and hasattr(self.worker, 'fetch_channel_avatar'):
                self.worker.fetch_channel_avatar(str(data["id"]))

        username = data.get("username", "")
        # Show the channel ID as a separate clickable-copy label, count goes in sub text
        self._set_channel_id_label(str(data['id']))
        self.lbl_active_channel_sub.setText("Loading media...")

        # Reset selection
        self.clear_selection()

        # Fetch media via worker (respects current media type filter)
        if self.worker:
            self.worker.fetch_channel_media(self.current_channel_id, media_type=self.current_media_type)

        # Close search mode if active — must run last, because closing an active
        # search re-renders the channel list and replaces the list item widgets
        # the click handler was just working with.
        self.close_search()
        if search_was_active:
            # The list was re-rendered, so the old item reference is stale now.
            self._active_channel_item = None

    def _set_active_fallback_avatar(self, title: str):
        initials = "".join([w[0] for w in title.split() if w][:2]).upper() or "TG"
        bg_hex = get_avatar_color(title)
        self.lbl_active_avatar.setPixmap(QPixmap())
        self.lbl_active_avatar.setText(initials[:2])
        self.lbl_active_avatar.setStyleSheet(f"""
            background-color: {bg_hex};
            color: #FFFFFF;
            font-weight: bold;
            font-size: 15px;
            border-radius: 22px;
        """)

    def refresh_current_channel_videos(self):
        if self.current_channel_id and self.worker:
            self.worker.fetch_channel_media(self.current_channel_id, media_type=self.current_media_type)

    def on_media_type_changed(self):
        """User switched the media type filter; re-fetch the current channel with the new type."""
        type_map = {
            "All": "all",
            "Videos": "videos",
            "Images": "images",
            "Documents": "documents",
            "Audio": "audio",
            "Text/Chat": "text",
        }
        self.current_media_type = type_map.get(self.combo_media_type.currentText(), "videos")
        if self.current_channel_id and self.worker:
            self.worker.fetch_channel_media(self.current_channel_id, media_type=self.current_media_type)

    def on_channel_videos_fetched(self, channel_id: str, videos: list):
        if str(channel_id) != str(self.current_channel_id):
            return
            
        self.current_videos = videos
        count = len(videos)
        uname = self.current_channel_data.get("username", "") if self.current_channel_data else ""
        type_label_map = {"all": "media item", "videos": "video", "images": "image",
                          "documents": "document", "audio": "audio", "text": "message"}
        item_label = type_label_map.get(self.current_media_type, "media item")
        plural = item_label + ("s" if count != 1 else "")
        if uname:
            sub_text = f"{uname} • {count} {plural}"
        else:
            sub_text = f"{count} {plural}"
        self.lbl_active_channel_sub.setText(sub_text)

        if not videos:
            type_label = {"all": "media", "videos": "videos", "images": "images",
                          "documents": "documents", "audio": "audio", "text": "text"}.get(
                              self.current_media_type, "media")
            self.lbl_empty_state.setText(f"No {type_label} found in this channel.")
            self.stack_videos.setCurrentIndex(0)
            return

        self.apply_video_filter()

    def on_thumbnail_ready(self, channel_id: str, msg_id: int, file_path: str):
        cid_clean = str(channel_id).replace("-100", "", 1) if str(channel_id).startswith("-100") else str(channel_id)
        curr_clean = str(self.current_channel_id).replace("-100", "", 1) if str(self.current_channel_id).startswith("-100") else str(self.current_channel_id)
        if cid_clean == curr_clean and msg_id in self.video_cards:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                pix = QPixmap(file_path)
                if not pix.isNull():
                    self.video_cards[msg_id].set_thumbnail(pix)

    def _make_date_pill(self, date_str: str) -> QLabel:
        """Telegram-style centered date separator pill (e.g., 'Nov 17, 2026')."""
        lbl = QLabel(date_str)
        bg = "#27272A" if self.is_dark_theme else "#E4E4E7"
        fg = "#A1A1AA" if self.is_dark_theme else "#52525B"
        lbl.setStyleSheet(
            f"background-color: {bg}; color: {fg}; font-size: 11px; font-weight: 600; "
            f"padding: 3px 14px; border-radius: 10px;"
        )
        lbl.setAlignment(Qt.AlignCenter)
        return lbl

    def _chat_avatar_label(self, ch: dict) -> QLabel:
        """Small circular avatar (32px) for the chat feed rows."""
        label = QLabel()
        label.setFixedSize(32, 32)
        label.setAlignment(Qt.AlignCenter)

        cid = str(ch.get("channel_id", ""))
        cid_clean = cid.replace("-100", "", 1) if cid.startswith("-100") else cid
        avatar_path = os.path.join(get_project_root(), "cache", "avatars", f"{cid_clean}.jpg")

        if os.path.exists(avatar_path) and os.path.getsize(avatar_path) > 0:
            pix = QPixmap(avatar_path)
            if not pix.isNull():
                label.setPixmap(make_circular_avatar(pix, 32))
                return label

        title = ""
        if self.current_channel_data:
            title = self.current_channel_data.get("title", "")
        if not title:
            title = ch.get("channel_title") or "TG"
        initials = "".join([w[0] for w in str(title).split() if w][:2]).upper() or "TG"
        label.setText(initials[:2])
        label.setStyleSheet(
            f"background-color: {get_avatar_color(str(title))}; color: #FFFFFF; "
            f"font-weight: 700; font-size: 11px; border-radius: 16px;"
        )
        return label

    def _render_chat_feed(self, videos: list):
        """'All' media view: chat-style vertical feed.
        Each message row is left-aligned (avatar + bubble with a fixed max
        width) and a centered date pill separates different days — content
        never stretches to the full panel width."""
        self._current_cols = 1
        for c in range(10):
            self.grid_layout.setColumnStretch(c, 1 if c == 0 else 0)

        # Look up per-message download states once for this render pass
        dl_states = {}
        if self.current_channel_id:
            try:
                raw_states = get_media_states(self.current_channel_id)
                dl_states = {
                    mid: ("done" if s == "completed" else ("resume" if s == "partial" else "download"))
                    for mid, s in raw_states.items()
                }
            except Exception:
                dl_states = {}

        last_date = None
        row_idx = 0
        for v in videos:
            date_str = v.get("date_str", "")
            if date_str and date_str != last_date:
                pill = self._make_date_pill(date_str)
                self.grid_layout.addWidget(pill, row_idx, 0, Qt.AlignHCenter | Qt.AlignTop)
                row_idx += 1
                last_date = date_str

            card = ChatBubbleWidget(v, is_dark=self.is_dark_theme, dl_state=dl_states.get(v["id"], "download"))
            card.selectionChanged.connect(self.on_video_selection_changed)
            card.downloadSingle.connect(self.on_single_download_requested)

            # Instant disk cache check for thumbnail
            cid_clean = str(v.get("channel_id", "")).replace("-100", "", 1) if str(v.get("channel_id", "")).startswith("-100") else str(v.get("channel_id", ""))
            thumb_path = os.path.join(get_project_root(), "cache", "thumbnails", f"{cid_clean}_{v['id']}.jpg")
            if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
                pix = QPixmap(thumb_path)
                if not pix.isNull():
                    card.set_thumbnail(pix)

            # Preserve selection state
            if v["id"] in self.selected_ids:
                card.set_selected(True)

            self.video_cards[v["id"]] = card

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 2, 4, 2)
            row_layout.setSpacing(8)
            row_layout.addWidget(self._chat_avatar_label(v), alignment=Qt.AlignBottom)
            row_layout.addWidget(card)
            row_layout.addStretch(1)
            self.grid_layout.addWidget(row, row_idx, 0)
            row_idx += 1

        self.stack_videos.setCurrentIndex(1)
        self.update_selection_counters()

    def apply_video_filter(self):
        query = self.search_videos.text().strip().lower()
        filtered = []
        for v in self.current_videos:
            title = v.get("title", "").lower()
            fname = v.get("filename", "").lower()
            if query and (query not in title and query not in fname):
                continue
            filtered.append(v)

        self.render_video_grid(filtered)

    def apply_video_sort(self):
        self.apply_video_filter()

    CHAT_FEED_TYPES = ("all", "videos", "images", "documents", "audio", "text")

    def compute_columns(self) -> int:
        """Determines responsive column count.
        Chat-feed media types (all/videos/images/documents/audio/text) force a single
        vertical column (chat-like) — cards are never stretched across the panel."""
        if self.current_media_type in self.CHAT_FEED_TYPES:
            return 1
        viewport_w = self.scroll_area.viewport().width()
        if viewport_w <= 0:
            viewport_w = max(400, self.width() - 320 - 48)

        # STRICT RULE: Never more than 3 cards in a row
        if viewport_w >= 620:
            return 3
        elif viewport_w >= 420:
            return 2
        else:
            return 1

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.relayout_grid_if_needed()

    def relayout_grid_if_needed(self):
        # The chat feed manages its own rows; skip re-gridding for chat-feed types
        if self.current_media_type in self.CHAT_FEED_TYPES:
            return
        new_cols = self.compute_columns()
        if hasattr(self, '_current_cols') and new_cols != self._current_cols and self.video_cards:
            self._current_cols = new_cols
            cards = list(self.video_cards.values())

            # Detach items from grid without destroying them
            while self.grid_layout.count():
                self.grid_layout.takeAt(0)

            # Update column stretch factors so all columns share space evenly
            for c in range(10):
                self.grid_layout.setColumnStretch(c, 1 if c < new_cols else 0)

            for idx, card in enumerate(cards):
                row = idx // new_cols
                col = idx % new_cols
                self.grid_layout.addWidget(card, row, col)

    def render_video_grid(self, videos: list):
        # Clear existing grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.video_cards.clear()

        if not videos:
            self.lbl_empty_state.setText("No matching videos.")
            self.stack_videos.setCurrentIndex(0)
            return

        # Sort order
        sort_mode = self.combo_sort.currentText()
        if sort_mode == "Newest First":
            videos = sorted(videos, key=lambda x: x.get("id", 0), reverse=True)
        elif sort_mode == "Oldest First":
            videos = sorted(videos, key=lambda x: x.get("id", 0))
        elif sort_mode == "Largest First":
            videos = sorted(videos, key=lambda x: x.get("size_bytes", 0), reverse=True)
        elif sort_mode == "Smallest First":
            videos = sorted(videos, key=lambda x: x.get("size_bytes", 0))

        # Chat-feed media types: vertical left-aligned chat layout, bubble cards
        if self.current_media_type in self.CHAT_FEED_TYPES:
            self._render_chat_feed(videos)
            return

        # Render in responsive columns (guaranteed at most 3 cards per row)
        cols = self.compute_columns()
        self._current_cols = cols

        # Look up per-message download states once for this render pass
        dl_states = {}
        if self.current_channel_id:
            try:
                raw_states = get_media_states(self.current_channel_id)
                dl_states = {
                    mid: ("done" if s == "completed" else ("resume" if s == "partial" else "download"))
                    for mid, s in raw_states.items()
                }
            except Exception:
                dl_states = {}

        # Configure column stretch so all columns share width evenly
        for c in range(10):
            self.grid_layout.setColumnStretch(c, 1 if c < cols else 0)

        for idx, v in enumerate(videos):
            card = VideoCardWidget(v, is_dark=self.is_dark_theme, dl_state=dl_states.get(v["id"], "download"))
            card.selectionChanged.connect(self.on_video_selection_changed)
            card.downloadSingle.connect(self.on_single_download_requested)
            
            # Instant disk cache check for thumbnail
            cid_clean = str(v.get("channel_id", "")).replace("-100", "", 1) if str(v.get("channel_id", "")).startswith("-100") else str(v.get("channel_id", ""))
            thumb_path = os.path.join(get_project_root(), "cache", "thumbnails", f"{cid_clean}_{v['id']}.jpg")
            if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
                pix = QPixmap(thumb_path)
                if not pix.isNull():
                    card.set_thumbnail(pix)

            # Preserve selection state
            if v["id"] in self.selected_ids:
                card.set_selected(True)
                
            self.video_cards[v["id"]] = card
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

        self.stack_videos.setCurrentIndex(1)
        self.update_selection_counters()

    def on_video_selection_changed(self, msg_id: int, is_selected: bool):
        if is_selected:
            self.selected_ids.add(msg_id)
        else:
            self.selected_ids.discard(msg_id)
        self.update_selection_counters()

    def toggle_select_all(self):
        all_visible_ids = list(self.video_cards.keys())
        if not all_visible_ids:
            return

        # If all visible are selected -> deselect all; otherwise select all visible
        if all(mid in self.selected_ids for mid in all_visible_ids):
            for mid, card in self.video_cards.items():
                card.set_selected(False)
            self.btn_select_all.setText("Select All")
        else:
            for mid, card in self.video_cards.items():
                card.set_selected(True)
            self.btn_select_all.setText("Deselect All")

        self.update_selection_counters()

    def clear_selection(self):
        self.selected_ids.clear()
        for card in self.video_cards.values():
            card.set_selected(False)
        self.btn_select_all.setText("Select All")
        self.update_selection_counters()

    def update_selection_counters(self):
        count = len(self.selected_ids)
        total_bytes = 0
        for v in self.current_videos:
            if v["id"] in self.selected_ids:
                total_bytes += v.get("size_bytes", 0)

        size_text = format_bytes(total_bytes)
        summary_text = f"<b>{count}</b> video{'s' if count != 1 else ''} selected ({size_text})"
        self.lbl_bottom_stats.setText(summary_text)

        btn_text = f"Download Selected ({count})" if count > 0 else "Download Selected"
        self.btn_bottom_download.setText(btn_text)

        enabled = (count > 0)
        self.bottom_bar.setVisible(enabled)

    def _set_channel_id_label(self, channel_id: str):
        """Set the channel ID segment of the inline subtitle row (plain text; click copies)."""
        self.lbl_active_channel_id.setText(f"ID: {channel_id}")
        self.lbl_active_channel_id.setVisible(True)
        self.lbl_id_sep.setVisible(True)

    def _copy_channel_id(self):
        from PySide6.QtWidgets import QApplication, QToolTip
        from PySide6.QtGui import QCursor
        cid = str(self.current_channel_id or "")
        if cid:
            QApplication.clipboard().setText(cid)
            try:
                QToolTip.showText(QCursor.pos(), "Channel ID copied!", self.lbl_active_channel_id,
                                  self.lbl_active_channel_id.rect(), 1500)
            except Exception:
                pass

    def on_single_download_requested(self, video_data: dict):
        if not self.current_channel_id:
            return
        msg_id = video_data["id"]
        fname = video_data.get("filename", f"video_{msg_id}")
        self.downloadRequested.emit(str(self.current_channel_id), [msg_id])
        self.show_toast(f"Queued '{fname}' for download!")

    def on_download_selected_clicked(self):
        if not self.current_channel_id or not self.selected_ids:
            return
        ids_list = sorted(list(self.selected_ids))
        self.downloadRequested.emit(str(self.current_channel_id), ids_list)
        count = len(ids_list)
        self.show_toast(f"Queued {count} video{'s' if count != 1 else ''} for download!")
        self.clear_selection()

    def show_toast(self, message: str):
        self.lbl_banner_msg.setText(f"✓ {message}")
        self.banner.show()
        QTimer.singleShot(6000, self.banner.hide)
