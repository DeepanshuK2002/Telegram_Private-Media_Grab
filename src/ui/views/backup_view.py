"""
Backup / Clone view — dump a channel/group to a local folder, or re-publish it to
another channel/group (message-by-message, media re-uploaded).
"""
import os
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QCheckBox, QPlainTextEdit, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt

from ui.views.settings_view import load_config
from ui.theme import get_tokens
from database import get_cached_channels_list
from backup import backup_root
from ui.components.searchable_combobox import SearchableComboBox


def _is_dark() -> bool:
    try:
        return bool(load_config().get("dark_mode", False))
    except Exception:
        return False


def _tokens() -> dict:
    return get_tokens(_is_dark())


class BackupView(QWidget):
    """Backup / Clone page: export a channel, or clone it into another channel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.setup_ui()
        self.populate()

    def set_worker(self, worker):
        self.worker = worker
        if worker:
            worker.signals.backup_log.connect(self.on_log)
            worker.signals.backup_finished.connect(self.on_finished)

    # ------------------------------------------------------------------ UI

    def setup_ui(self):
        t = _tokens()
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)

        left = QFrame()
        left.setObjectName("WhiteCard")
        left.setFixedWidth(430)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)

        lbl_title = QLabel("Backup / Clone")
        lbl_title.setObjectName("PageTitle")
        left_layout.addWidget(lbl_title)

        lbl_sub = QLabel("Backup: export a channel's media + messages into a local dated folder. Clone: re-publish the whole channel (message-by-message) into another channel/group.")
        lbl_sub.setObjectName("MutedText")
        lbl_sub.setWordWrap(True)
        left_layout.addWidget(lbl_sub)

        lbl_src = QLabel("Source channel / group")
        lbl_src.setObjectName("FieldLabel")
        left_layout.addWidget(lbl_src)
        self.combo_source = SearchableComboBox()
        self.combo_source.setMinimumHeight(36)
        left_layout.addWidget(self.combo_source)

        lbl_mode = QLabel("Mode")
        lbl_mode.setObjectName("FieldLabel")
        left_layout.addWidget(lbl_mode)
        self.radio_group = QButtonGroup(self)
        self.radio_backup = QRadioButton("Backup — download everything to a local folder")
        self.radio_clone = QRadioButton("Clone — re-publish into another channel/group")
        for rb in (self.radio_backup, self.radio_clone):
            rb.setCursor(Qt.PointingHandCursor)
            self.radio_group.addButton(rb)
            left_layout.addWidget(rb)
        self.radio_backup.setChecked(True)
        self.radio_clone.toggled.connect(self._on_mode_toggled)

        lbl_dest = QLabel("Destination (clone mode)")
        lbl_dest.setObjectName("FieldLabel")
        left_layout.addWidget(lbl_dest)
        self.combo_dest = SearchableComboBox()
        self.combo_dest.setMinimumHeight(36)
        self.combo_dest.setEnabled(False)
        left_layout.addWidget(self.combo_dest)

        lbl_inc = QLabel("What to include")
        lbl_inc.setObjectName("FieldLabel")
        left_layout.addWidget(lbl_inc)
        self.chk_media = QCheckBox("Media files (images, videos, documents, audio)")
        self.chk_media.setChecked(True)
        self.chk_text = QCheckBox("Text messages")
        self.chk_text.setChecked(True)
        left_layout.addWidget(self.chk_media)
        left_layout.addWidget(self.chk_text)

        limit_row = QHBoxLayout()
        lbl_limit = QLabel("Message limit")
        lbl_limit.setObjectName("FieldLabel")
        limit_row.addWidget(lbl_limit)
        self.combo_limit = SearchableComboBox()
        self.combo_limit.addItems(["All", "100", "500", "1000"])
        self.combo_limit.setFixedWidth(120)
        self.combo_limit.setFixedHeight(36)
        limit_row.addWidget(self.combo_limit)
        limit_row.addStretch()
        left_layout.addLayout(limit_row)

        left_layout.addStretch()

        row_btns = QHBoxLayout()
        row_btns.setSpacing(8)
        self.btn_start = QPushButton("Start Backup")
        self.btn_start.setObjectName("VercelButton")
        self.btn_start.setFixedHeight(38)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self.on_start_clicked)
        row_btns.addWidget(self.btn_start, stretch=1)
        self.btn_open = QPushButton("Open Backups Folder")
        self.btn_open.setObjectName("SecondaryButton")
        self.btn_open.setFixedHeight(38)
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.clicked.connect(self.open_backups_folder)
        row_btns.addWidget(self.btn_open)
        left_layout.addLayout(row_btns)

        self.lbl_status = QLabel("Idle")
        self.lbl_status.setObjectName("HelpPoint")
        self.lbl_status.setWordWrap(True)
        left_layout.addWidget(self.lbl_status)

        root.addWidget(left)

        right = QFrame()
        right.setObjectName("WhiteCard")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 18, 16, 18)
        right_layout.setSpacing(10)

        lbl_log = QLabel("Log")
        lbl_log.setObjectName("SectionSmall")
        right_layout.addWidget(lbl_log)

        self.log = QPlainTextEdit()
        self.log.setObjectName("ConsoleLog")
        self.log.setReadOnly(True)
        right_layout.addWidget(self.log, stretch=1)

        root.addWidget(right, stretch=1)

    def is_dark_theme(self):
        return _is_dark()

    def _on_mode_toggled(self, checked: bool):
        self.combo_dest.setEnabled(checked)
        self.btn_start.setText("Start Clone" if checked else "Start Backup")
        self.lbl_status.setText("Clone mode: re-publish into destination channel" if checked else "Backup mode: export to folder")

    # ------------------------------------------------------------------ data

    def populate(self):
        self.combo_source.clear()
        self.combo_dest.clear()
        try:
            cached = get_cached_channels_list() or []
        except Exception:
            cached = []
        items = []
        for ch in cached:
            if not (bool(ch.get("is_channel", 0)) or bool(ch.get("is_group", 0))):
                continue
            cid = str(ch.get("channel_id") or ch.get("id") or "").strip()
            if not cid:
                continue
            full_id = cid if cid.startswith("-") else f"-100{cid}"
            title = str(ch.get("title") or "Untitled")
            items.append((full_id, title, bool(ch.get("pinned", 0))))
        items.sort(key=lambda t: (0 if t[2] else 1, t[1].lower()))
        for full_id, title, _ in items:
            self.combo_source.addItem(title, full_id)
            self.combo_dest.addItem(title, full_id)

    def on_start_clicked(self):
        if not self.worker:
            self.on_log("Telegram client not ready.")
            return
        mode = "clone" if self.radio_clone.isChecked() else "backup"
        src = self.combo_source.currentData()
        if not src:
            self.on_log("Select a source channel/group first.")
            return
        dest = self.combo_dest.currentData() if mode == "clone" else ""
        if mode == "clone" and not dest:
            self.on_log("Select a destination channel/group for clone mode.")
            return
        limit_text = self.combo_limit.currentText()
        limit = None if limit_text == "All" else int(limit_text)
        self.btn_start.setEnabled(False)
        self.btn_start.setText("Working…")
        self.lbl_status.setText(f"{'Cloning' if mode == 'clone' else 'Backing up'}…")
        self.worker.run_backup(src, dest, mode, self.chk_media.isChecked(), self.chk_text.isChecked(), limit)

    def on_log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{ts}] {msg}")

    def on_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_start.setText("Start Clone" if self.radio_clone.isChecked() else "Start Backup")
        self.lbl_status.setText("Done — see log.")

    def open_backups_folder(self):
        folder = backup_root()
        try:
            os.startfile(folder)
        except Exception:
            pass

    def update_theme(self, is_dark: bool):
        for name in ("combo_source", "combo_dest", "combo_limit"):
            combo = getattr(self, name, None)
            if combo is not None and hasattr(combo, "refresh_theme"):
                combo.refresh_theme()
