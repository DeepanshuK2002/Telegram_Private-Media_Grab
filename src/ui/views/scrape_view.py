"""
TeleScrap view — integrated member scraper (based on github.com/ephell/Telescrape, MIT).
Uses the app's logged-in Telethon client via the worker. Exports member lists to CSV.
"""
import os
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QFrame,
    QCheckBox, QPlainTextEdit
)
from PySide6.QtCore import Qt
from resource_utils import get_project_root
from ui.views.settings_view import load_config
from ui.theme import get_tokens
from database import get_cached_channels_list
from telescrape import scrape_output_dir
from ui.components.searchable_combobox import SearchableComboBox


def _is_dark() -> bool:
    try:
        cfg = load_config()
        return bool(cfg.get("dark_mode", False))
    except Exception:
        return False


def _tokens() -> dict:
    return get_tokens(_is_dark())


class ScrapeView(QWidget):
    """TeleScrap page: pick groups/channels, toggle filters, scrape members to CSV."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.is_dark_theme = _is_dark()
        self.setup_ui()
        self.populate_channels()

    def set_worker(self, worker):
        self.worker = worker
        if worker:
            worker.signals.scrape_log.connect(self.on_scrape_log)
            worker.signals.scrape_finished.connect(self.on_scrape_finished)

    # ------------------------------------------------------------------ UI

    def setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)

        # ── Left card: target selection ─────────────────────────────────
        left = QFrame()
        left.setObjectName("WhiteCard")
        left.setFixedWidth(400)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)

        lbl_title = QLabel("TeleScrap")
        lbl_title.setObjectName("PageTitle")
        left_layout.addWidget(lbl_title)

        lbl_sub = QLabel("Extract member lists, message history and channel/group metadata into CSV.")
        lbl_sub.setObjectName("MutedText")
        lbl_sub.setWordWrap(True)
        left_layout.addWidget(lbl_sub)

        self.search = QLineEdit()
        self.search.setObjectName("VercelInput")
        self.search.setPlaceholderText("Filter groups & channels…")
        self.search.setMinimumHeight(36)
        self.search.textChanged.connect(self.populate_channels)
        left_layout.addWidget(self.search)

        tools = QHBoxLayout()
        self.lbl_count = QLabel("0 selected")
        self.lbl_count.setObjectName("MutedText")
        tools.addWidget(self.lbl_count)
        tools.addStretch()
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.setObjectName("SecondaryButton")
        self.btn_select_all.setFixedHeight(28)
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        self.btn_select_all.clicked.connect(self.select_all)
        tools.addWidget(self.btn_select_all)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setObjectName("SecondaryButton")
        self.btn_clear.setFixedHeight(28)
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear_selection)
        tools.addWidget(self.btn_clear)
        left_layout.addLayout(tools)

        self.channel_list = QListWidget()
        self.channel_list.setObjectName("DestList")
        self.channel_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.channel_list.itemChanged.connect(self._on_item_changed)
        left_layout.addWidget(self.channel_list, stretch=1)

        root.addWidget(left)

        # ── Right card: filters + run ───────────────────────────────────
        right = QFrame()
        right.setObjectName("WhiteCard")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(10)

        lbl_filters = QLabel("Filters")
        lbl_filters.setObjectName("SectionSmall")
        right_layout.addWidget(lbl_filters)

        self.checkboxes = {}
        checkbox_specs = [
            ("exclude_yourself", "Exclude yourself", True),
            ("exclude_admins", "Exclude admins", True),
            ("exclude_bots", "Exclude bots", True),
            ("exclude_deleted_users", "Exclude deleted accounts", True),
            ("exclude_restricted_users", "Exclude restricted users", True),
            ("exclude_scam_flagged_users", "Exclude scam-flagged users", True),
            ("exclude_fake_flagged_users", "Exclude fake-flagged users", True),
            ("exclude_users_in_contacts", "Exclude users in your contacts", True),
            ("exclude_users_with_hidden_last_seen_online", "Exclude hidden last-seen/online", False),
            ("only_premium", "Only Premium members", False),
        ]
        cb_col = QVBoxLayout()
        cb_col.setSpacing(6)
        for key, label, default in checkbox_specs:
            cb = QCheckBox(label)
            cb.setChecked(default)
            self.checkboxes[key] = cb
            cb_col.addWidget(cb)
        right_layout.addLayout(cb_col)

        activity_row = QHBoxLayout()
        lbl_activity = QLabel("Active in last")
        lbl_activity.setObjectName("FieldLabel")
        activity_row.addWidget(lbl_activity)
        self.combo_activity = SearchableComboBox()
        self.combo_activity.addItems(["Any time", "2 days", "7 days", "30 days"])
        self.combo_activity.setFixedWidth(150)
        self.combo_activity.setFixedHeight(36)
        activity_row.addWidget(self.combo_activity)
        activity_row.addStretch()
        right_layout.addLayout(activity_row)

        right_layout.addStretch()

        # Messages scrape row
        msg_row = QHBoxLayout()
        msg_row.setSpacing(8)
        lbl_msg = QLabel("Messages:")
        lbl_msg.setObjectName("FieldLabel")
        msg_row.addWidget(lbl_msg)
        self.combo_msg_limit = SearchableComboBox()
        self.combo_msg_limit.addItems(["100", "500", "1000", "All"])
        self.combo_msg_limit.setFixedWidth(110)
        self.combo_msg_limit.setFixedHeight(32)
        msg_row.addWidget(self.combo_msg_limit)
        self.btn_scrape_messages = QPushButton("Scrape Messages")
        self.btn_scrape_messages.setObjectName("SecondaryButton")
        self.btn_scrape_messages.setFixedHeight(32)
        self.btn_scrape_messages.setCursor(Qt.PointingHandCursor)
        self.btn_scrape_messages.clicked.connect(self.on_scrape_messages_clicked)
        msg_row.addWidget(self.btn_scrape_messages)
        right_layout.addLayout(msg_row)

        # Run row
        run_row = QHBoxLayout()
        run_row.setSpacing(8)
        self.btn_scrape = QPushButton("Scrape Members")
        self.btn_scrape.setObjectName("VercelButton")
        self.btn_scrape.setFixedHeight(40)
        self.btn_scrape.setCursor(Qt.PointingHandCursor)
        self.btn_scrape.clicked.connect(self.on_scrape_clicked)
        run_row.addWidget(self.btn_scrape, stretch=1)
        self.btn_export_channels = QPushButton("Export Channel List")
        self.btn_export_channels.setObjectName("SecondaryButton")
        self.btn_export_channels.setFixedHeight(40)
        self.btn_export_channels.setCursor(Qt.PointingHandCursor)
        self.btn_export_channels.setToolTip("Export your cached channel/group list to CSV")
        self.btn_export_channels.clicked.connect(self.on_export_channels_clicked)
        run_row.addWidget(self.btn_export_channels)
        right_layout.addLayout(run_row)

        open_row = QHBoxLayout()
        self.btn_open_folder = QPushButton("Open Output Folder")
        self.btn_open_folder.setObjectName("SecondaryButton")
        self.btn_open_folder.setFixedHeight(30)
        self.btn_open_folder.setCursor(Qt.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self.open_output_folder)
        open_row.addWidget(self.btn_open_folder)
        lbl_out = QLabel(f"Saves to: scraped_members/")
        lbl_out.setObjectName("HelpPoint")
        open_row.addWidget(lbl_out)
        open_row.addStretch()
        right_layout.addLayout(open_row)

        lbl_log = QLabel("Log")
        lbl_log.setObjectName("LogTitle")
        right_layout.addWidget(lbl_log)

        self.log = QPlainTextEdit()
        self.log.setObjectName("ConsoleLog")
        self.log.setReadOnly(True)
        self.log.setFixedHeight(150)
        right_layout.addWidget(self.log)

        root.addWidget(right, stretch=1)

    # ------------------------------------------------------------------ data

    def populate_channels(self):
        query = self.search.text().strip().lower() if hasattr(self, "search") else ""
        self.channel_list.blockSignals(True)
        self.channel_list.clear()
        try:
            cached = get_cached_channels_list() or []
        except Exception:
            cached = []
        items = []
        for ch in cached:
            is_channel = bool(ch.get("is_channel", 0))
            is_group = bool(ch.get("is_group", 0))
            if not (is_channel or is_group):
                continue
            cid = str(ch.get("channel_id") or ch.get("id") or "").strip()
            if not cid:
                continue
            full_id = cid if cid.startswith("-") else f"-100{cid}"
            title = str(ch.get("title") or "Untitled")
            if query and (query not in title.lower() and query not in str(ch.get("username") or "").lower()):
                continue
            items.append((full_id, title, is_channel, is_group, ch))
        items.sort(key=lambda t: (0 if t[4].get("pinned") else 1, t[1].lower()))
        for full_id, title, is_channel, is_group, ch in items:
            kind = "Channel" if is_channel else "Group"
            uname = ch.get("username") or ""
            sub = uname if uname else kind
            item = QListWidgetItem(f"{title}  ·  {sub}")
            item.setData(Qt.UserRole, full_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.channel_list.addItem(item)
        self.channel_list.blockSignals(False)
        self._update_count()

    def _on_item_changed(self, item):
        self._update_count()

    def _update_count(self):
        count = sum(1 for i in range(self.channel_list.count()) if self.channel_list.item(i).checkState() == Qt.Checked)
        self.lbl_count.setText(f"{count} selected")

    def select_all(self):
        for i in range(self.channel_list.count()):
            self.channel_list.item(i).setCheckState(Qt.Checked)
        self._update_count()

    def clear_selection(self):
        for i in range(self.channel_list.count()):
            self.channel_list.item(i).setCheckState(Qt.Unchecked)
        self._update_count()

    def selected_ids(self):
        return [self.channel_list.item(i).data(Qt.UserRole)
                for i in range(self.channel_list.count())
                if self.channel_list.item(i).checkState() == Qt.Checked]

    # ------------------------------------------------------------------ scrape

    def on_scrape_clicked(self):
        ids = self.selected_ids()
        if not ids:
            self.on_scrape_log("Select at least one group or channel first.")
            return
        if not self.worker:
            self.on_scrape_log("Telegram client not ready.")
            return
        options = {key: cb.isChecked() for key, cb in self.checkboxes.items()}
        options["user_active_in_last_days"] = [0, 2, 7, 30][self.combo_activity.currentIndex()]
        self.btn_scrape.setEnabled(False)
        self.btn_scrape.setText("Scraping…")
        self.on_scrape_log(f"Starting scrape of {len(ids)} target(s)...")
        self.worker.scrape_members(ids, options)

    def on_scrape_log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{ts}] {msg}")

    def on_scrape_finished(self):
        self.btn_scrape.setEnabled(True)
        self.btn_scrape.setText("Scrape Members")
        if hasattr(self, 'btn_scrape_messages'):
            self.btn_scrape_messages.setEnabled(True)
            self.btn_scrape_messages.setText("Scrape Messages")

    def on_scrape_messages_clicked(self):
        ids = self.selected_ids()
        if not ids:
            self.on_scrape_log("Select at least one group or channel first.")
            return
        if not self.worker:
            self.on_scrape_log("Telegram client not ready.")
            return
        limit_text = self.combo_msg_limit.currentText()
        limit = None if limit_text == "All" else int(limit_text)
        self.btn_scrape_messages.setEnabled(False)
        self.btn_scrape_messages.setText("Exporting…")
        self.on_scrape_log(f"Exporting up to {limit or 'ALL'} messages per selected target…")
        self.worker.scrape_messages(ids, limit)

    def on_export_channels_clicked(self):
        if not self.worker:
            self.on_scrape_log("Telegram client not ready.")
            return
        self.on_scrape_log("Exporting channel/group list…")
        self.worker.scrape_channels_csv()

    def open_output_folder(self):
        folder = scrape_output_dir()
        os.makedirs(folder, exist_ok=True)
        try:
            os.startfile(folder)
        except Exception:
            pass

    def update_theme(self, is_dark: bool):
        self.is_dark_theme = is_dark
        if hasattr(self, "combo_activity") and hasattr(self.combo_activity, "refresh_theme"):
            self.combo_activity.refresh_theme()
        if hasattr(self, "combo_msg_limit") and hasattr(self.combo_msg_limit, "refresh_theme"):
            self.combo_msg_limit.refresh_theme()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
