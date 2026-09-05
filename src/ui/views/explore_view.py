import os
import html
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QListWidget, QListWidgetItem, QScrollArea, 
    QFrame, QGridLayout, QCheckBox, QSizePolicy, QStackedWidget,
    QStackedLayout, QSplitter, QApplication
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont, QCursor, QPainterPath
from resource_utils import get_resource_path, get_project_root
from ui.components.clean_combobox import CleanComboBox, create_clean_menu
from ui.components.thumbnail_worker import ThumbnailWorker
from ui.views.settings_view import load_config
from database import get_cached_channels_list, cache_channels_list


def format_bytes(size_bytes):
    if not size_bytes or size_bytes <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{int(size_bytes)} B"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


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


class ChannelListItem(QWidget):
    """Custom widget for channels in the left list with real profile avatar support."""
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.data = data
        self.setObjectName("ChannelListItem")
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


class VideoCardWidget(QFrame):
    """Card representing a video message with thumbnail, metadata, checkbox, and 1-click download."""
    selectionChanged = Signal(int, bool) # (msg_id, is_selected)
    downloadSingle = Signal(dict)        # video_data

    def __init__(self, video_data: dict, is_dark: bool = False, parent=None):
        super().__init__(parent)
        self.video_data = video_data
        self.msg_id = video_data["id"]
        self.is_selected = False
        self.is_dark = is_dark
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

        self.btn_quick_dl = QPushButton("↓")
        self.btn_quick_dl.setFixedSize(28, 28)
        self.btn_quick_dl.setCursor(Qt.PointingHandCursor)
        self.btn_quick_dl.setToolTip("Download this video immediately")
        self.btn_quick_dl.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 0.65);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 14px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #000000;
                border-color: #FFFFFF;
            }
        """)
        self.btn_quick_dl.clicked.connect(lambda: self.downloadSingle.emit(self.video_data))
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

        title_color = "#EDEDED" if self.is_dark else "#09090B"
        self.lbl_title.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {title_color}; padding: 2px 0px 2px 0px;")
        meta_layout.addWidget(self.lbl_title)

        # Bottom row with size & date
        row_stats = QHBoxLayout()
        size_str = format_bytes(self.video_data.get("size_bytes", 0))
        self.lbl_size = QLabel(size_str)
        size_color = "#A1A1AA" if self.is_dark else "#52525B"
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
        title_color = "#EDEDED" if is_dark else "#09090B"
        size_color = "#A1A1AA" if is_dark else "#52525B"
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
        self.worker = None
        self.thumb_worker = None
        self.is_dark_theme = False
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
        if cached:
            self.all_channels = cached
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
        self.btn_refresh_channels.setToolTip("Refresh channel list from Telegram")
        self.btn_refresh_channels.clicked.connect(self.refresh_channels_from_telegram)
        left_header.addWidget(self.btn_refresh_channels)
        left_layout.addLayout(left_header)

        # Channel Search Bar
        self.search_channels = QLineEdit()
        self.search_channels.setObjectName("VercelInput")
        self.search_channels.setPlaceholderText("Search channels...")
        self.search_channels.setMinimumHeight(36)
        self.search_channels.textChanged.connect(self.filter_channels)
        left_layout.addWidget(self.search_channels)

        # Filter Segment Buttons (All, Channels, Groups)
        filter_tabs = QHBoxLayout()
        filter_tabs.setSpacing(6)
        self.btn_tab_all = QPushButton("All")
        self.btn_tab_channels = QPushButton("Channels")
        self.btn_tab_groups = QPushButton("Groups")

        self.current_filter_tab = "all"
        for btn, tab_id in [(self.btn_tab_all, "all"), (self.btn_tab_channels, "channels"), (self.btn_tab_groups, "groups")]:
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

        # ── 1. Top Channel Info & Actions Bar ────────────────────────────────
        self.top_bar = QFrame()
        self.top_bar.setObjectName("WhiteCard")
        top_bar_layout = QHBoxLayout(self.top_bar)
        top_bar_layout.setContentsMargins(16, 12, 16, 12)
        top_bar_layout.setSpacing(12)

        # Channel Avatar & Title
        self.lbl_active_avatar = QLabel("TG")
        self.lbl_active_avatar.setFixedSize(36, 36)
        self.lbl_active_avatar.setAlignment(Qt.AlignCenter)
        self.lbl_active_avatar.setStyleSheet("""
            background-color: #3B82F6;
            color: #FFFFFF;
            font-weight: bold;
            font-size: 13px;
            border-radius: 18px;
        """)

        active_title_box = QVBoxLayout()
        active_title_box.setSpacing(2)
        self.lbl_active_channel_title = QLabel("Select a channel to explore videos")
        self.lbl_active_channel_title.setStyleSheet("font-weight: 600; font-size: 14px;")
        
        self.lbl_active_channel_sub = QLabel("No channel selected")
        self.lbl_active_channel_sub.setObjectName("MutedText")
        self.lbl_active_channel_sub.setStyleSheet("font-size: 11px;")

        active_title_box.addWidget(self.lbl_active_channel_title)
        active_title_box.addWidget(self.lbl_active_channel_sub)

        top_bar_layout.addWidget(self.lbl_active_avatar)
        top_bar_layout.addLayout(active_title_box)
        top_bar_layout.addStretch()

        # Selection Summary (hidden from top bar; shown in bottom bar upon selection)
        self.lbl_selection_summary = QLabel("")
        self.lbl_selection_summary.hide()

        # Select All / Deselect All Button
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.setObjectName("SecondaryButton")
        self.btn_select_all.setFixedHeight(34)
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        self.btn_select_all.clicked.connect(self.toggle_select_all)
        top_bar_layout.addWidget(self.btn_select_all)

        # Refresh Videos in channel button
        self.btn_refresh_videos = QPushButton()
        self.btn_refresh_videos.setObjectName("IconButton")
        self.btn_refresh_videos.setFixedSize(34, 34)
        self.btn_refresh_videos.setIconSize(QSize(14, 14))
        self.btn_refresh_videos.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_videos.setToolTip("Reload videos for this channel")
        self.btn_refresh_videos.clicked.connect(self.refresh_current_channel_videos)
        top_bar_layout.addWidget(self.btn_refresh_videos)

        right_layout.addWidget(self.top_bar)

        # ── 2. Video Search & Filter Toolbar ─────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search_videos = QLineEdit()
        self.search_videos.setObjectName("VercelInput")
        self.search_videos.setPlaceholderText("Filter videos by title or filename...")
        self.search_videos.setMinimumHeight(36)
        self.search_videos.textChanged.connect(self.apply_video_filter)
        toolbar.addWidget(self.search_videos, stretch=3)

        self.combo_sort = CleanComboBox()
        self.combo_sort.addItems(["Newest First", "Oldest First", "Largest First", "Smallest First"])
        self.combo_sort.currentIndexChanged.connect(self.apply_video_sort)
        toolbar.addWidget(self.combo_sort, stretch=1)

        right_layout.addLayout(toolbar)

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

    def update_theme(self, is_dark: bool):
        self.is_dark_theme = is_dark
        suffix = "_white.png" if is_dark else "_black.png"
        icon_path = get_resource_path(os.path.join("assets", "icons", f"refresh{suffix}"))
        if os.path.exists(icon_path):
            self.btn_refresh_channels.setIcon(QIcon(icon_path))
            self.btn_refresh_videos.setIcon(QIcon(icon_path))

        # Update tabs style
        tab_active_bg = "#27272A" if is_dark else "#09090B"
        tab_active_fg = "#FFFFFF" if is_dark else "#FFFFFF"
        tab_inactive_bg = "transparent"
        tab_inactive_fg = "#A1A1AA" if is_dark else "#71717A"

        for btn, tid in [(self.btn_tab_all, "all"), (self.btn_tab_channels, "channels"), (self.btn_tab_groups, "groups")]:
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

        # Update all video cards with new theme
        for card in self.video_cards.values():
            if hasattr(card, 'update_theme'):
                card.update_theme(is_dark)

    def set_filter_tab(self, tab_id: str):
        self.current_filter_tab = tab_id
        for btn, tid in [(self.btn_tab_all, "all"), (self.btn_tab_channels, "channels"), (self.btn_tab_groups, "groups")]:
            btn.setChecked(tid == tab_id)
        self.update_theme(self.is_dark_theme)
        self.filter_channels()

    def filter_channels(self):
        query = self.search_channels.text().strip().lower()
        tab = self.current_filter_tab

        self.filtered_channels = []
        for ch in self.all_channels:
            title = ch.get("title", "").lower()
            uname = ch.get("username", "").lower()
            
            if query and (query not in title and query not in uname):
                continue
                
            if tab == "channels" and not ch.get("is_channel"):
                continue
            if tab == "groups" and not ch.get("is_group"):
                continue
                
            self.filtered_channels.append(ch)

        self.render_channel_list()

    def render_channel_list(self):
        self.channel_list.clear()
        # O(1) lookup: clean channel id -> QListWidgetItem for fast avatar updates
        self._channel_index = {}
        self.lbl_channel_count.setText(str(len(self.filtered_channels)))

        for ch in self.filtered_channels:
            item = QListWidgetItem(self.channel_list)
            item.setSizeHint(QSize(280, 58))
            item.setData(Qt.UserRole, ch)

            cid = str(ch.get("id", ""))
            cid_clean = cid.replace("-100", "", 1) if cid.startswith("-100") else cid
            self._channel_index[cid_clean] = item

            widget = ChannelListItem(ch)
            self.channel_list.setItemWidget(item, widget)

    def refresh_channels_from_telegram(self):
        if self.worker:
            self.worker.fetch_user_dialogs()

    def on_dialogs_fetched(self, dialogs: list):
        self.all_channels = dialogs
        self.filter_channels()

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
                self.lbl_active_avatar.setStyleSheet("background: transparent; border-radius: 18px;")

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

    def on_channel_item_clicked(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
            
        self.current_channel_id = str(data["id"])
        self.current_channel_data = data
        
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
                self.lbl_active_avatar.setStyleSheet("background: transparent; border-radius: 18px;")
            else:
                self._set_active_fallback_avatar(title)
        else:
            self._set_active_fallback_avatar(title)
            if self.worker and hasattr(self.worker, 'fetch_channel_avatar'):
                self.worker.fetch_channel_avatar(str(data["id"]))

        username = data.get("username", "") or (f"ID: {data['id']}")
        self.lbl_active_channel_sub.setText(f"{username} • Loading videos...")

        # Reset selection
        self.clear_selection()

        # Fetch videos via worker
        if self.worker:
            self.worker.fetch_channel_videos(self.current_channel_id)

    def _set_active_fallback_avatar(self, title: str):
        initials = "".join([w[0] for w in title.split() if w][:2]).upper() or "TG"
        bg_hex = get_avatar_color(title)
        self.lbl_active_avatar.setPixmap(QPixmap())
        self.lbl_active_avatar.setText(initials[:2])
        self.lbl_active_avatar.setStyleSheet(f"""
            background-color: {bg_hex};
            color: #FFFFFF;
            font-weight: bold;
            font-size: 13px;
            border-radius: 18px;
        """)

    def refresh_current_channel_videos(self):
        if self.current_channel_id and self.worker:
            self.worker.fetch_channel_videos(self.current_channel_id)

    def on_channel_videos_fetched(self, channel_id: str, videos: list):
        if str(channel_id) != str(self.current_channel_id):
            return
            
        self.current_videos = videos
        count = len(videos)
        uname = self.current_channel_data.get("username", "") if self.current_channel_data else ""
        sub_text = f"{uname} • {count} video{'s' if count != 1 else ''}" if uname else f"{count} video{'s' if count != 1 else ''}"
        self.lbl_active_channel_sub.setText(sub_text)

        if not videos:
            self.lbl_empty_state.setText("No videos found in this channel.")
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

    def compute_columns(self) -> int:
        """Determines responsive column count: strictly 3 cards on full screen / wide views, responsive for smaller screens."""
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

        # Render in responsive columns (guaranteed at most 3 cards per row)
        cols = self.compute_columns()
        self._current_cols = cols

        # Configure column stretch so all columns share width evenly
        for c in range(10):
            self.grid_layout.setColumnStretch(c, 1 if c < cols else 0)

        for idx, v in enumerate(videos):
            card = VideoCardWidget(v, is_dark=self.is_dark_theme)
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
        self.lbl_selection_summary.setText(summary_text)
        self.lbl_bottom_stats.setText(summary_text)

        btn_text = f"Download Selected ({count})" if count > 0 else "Download Selected"
        self.btn_bottom_download.setText(btn_text)

        enabled = (count > 0)
        self.bottom_bar.setVisible(enabled)

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
