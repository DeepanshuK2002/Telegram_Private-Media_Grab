"""
Auto Message view — write multiple messages (long/short text + emoji + optional image)
and re-send them to selected Telegram groups on a fixed interval.
"""
import os
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QFrame,
    QCheckBox, QComboBox, QPlainTextEdit, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from ui.views.settings_view import load_config
from ui.theme import get_tokens
from database import get_cached_channels_list
from auto_message import get_auto_message, save_auto_message
from ui.components.searchable_combobox import SearchableComboBox


def _is_dark() -> bool:
    try:
        return bool(load_config().get("dark_mode", False))
    except Exception:
        return False


def _tokens() -> dict:
    return get_tokens(_is_dark())


INTERVAL_OPTIONS = [
    ("Every 30 minutes", 30),
    ("Every 1 hour", 60),
    ("Every 3 hours", 180),
    ("Every 6 hours", 360),
    ("Every 12 hours", 720),
    ("Every 24 hours", 1440),
]


class AutoMessageView(QWidget):
    """Auto Message page: manage message library, destinations, schedule."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self._picked_image = ""
        self.setup_ui()
        self.load_state()

    def set_worker(self, worker):
        self.worker = worker
        if worker:
            worker.signals.auto_message_log.connect(self.on_log)
            worker.signals.auto_message_finished.connect(self.on_finished)

    # ------------------------------------------------------------------ UI

    def setup_ui(self):
        t = _tokens()
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)

        # ── Left card: configuration ─────────────────────────────────
        left = QFrame()
        left.setObjectName("WhiteCard")
        left.setFixedWidth(400)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)

        lbl_title = QLabel("Auto Message")
        lbl_title.setObjectName("PageTitle")
        left_layout.addWidget(lbl_title)

        lbl_sub = QLabel("Write one or more messages (text + emoji + optional image) and re-send them to your selected groups on a fixed schedule.")
        lbl_sub.setObjectName("MutedText")
        lbl_sub.setWordWrap(True)
        left_layout.addWidget(lbl_sub)

        self.chk_enabled = QCheckBox("Enable Auto Message")
        self.chk_enabled.setCursor(Qt.PointingHandCursor)
        left_layout.addWidget(self.chk_enabled)

        lbl_interval = QLabel("Send every")
        lbl_interval.setObjectName("FieldLabel")
        left_layout.addWidget(lbl_interval)
        self.combo_interval = SearchableComboBox()
        for label, _minutes in INTERVAL_OPTIONS:
            self.combo_interval.addItem(label)
        self.combo_interval.setMinimumHeight(36)
        left_layout.addWidget(self.combo_interval)

        lbl_rotation = QLabel("Rotation")
        lbl_rotation.setObjectName("FieldLabel")
        left_layout.addWidget(lbl_rotation)
        self.combo_rotation = SearchableComboBox()
        self.combo_rotation.addItems(["Round-robin (in order)", "Random each time"])
        self.combo_rotation.setMinimumHeight(36)
        left_layout.addWidget(self.combo_rotation)

        note = QLabel("Sends using your active account. Runs while the app is open, on the configured interval, plus on demand via 'Send Now'.")
        note.setObjectName("HelpPoint")
        note.setWordWrap(True)
        left_layout.addWidget(note)

        # ── Auto Reply Bot ──
        lbl_reply = QLabel("Auto Reply Bot")
        lbl_reply.setObjectName("SectionSmall")
        left_layout.addWidget(lbl_reply)
        self.chk_auto_reply = QCheckBox("Auto-reply to incoming private messages")
        self.chk_auto_reply.setCursor(Qt.PointingHandCursor)
        left_layout.addWidget(self.chk_auto_reply)
        self.input_reply_text = QPlainTextEdit()
        self.input_reply_text.setPlaceholderText("Your auto-reply message… (e.g. 'Hey! I'll get back to you soon 🙂')")
        self.input_reply_text.setFixedHeight(60)
        self.input_reply_text.setObjectName("ReplyBox")
        left_layout.addWidget(self.input_reply_text)
        reply_row = QHBoxLayout()
        lbl_cd = QLabel("Cooldown")
        lbl_cd.setObjectName("MutedText")
        reply_row.addWidget(lbl_cd)
        self.combo_cooldown = SearchableComboBox()
        self.combo_cooldown.addItems(["Once per 1 hour", "Once per 6 hours", "Once per 24 hours", "Once per week"])
        self.combo_cooldown.setFixedHeight(32)
        reply_row.addWidget(self.combo_cooldown, stretch=1)
        left_layout.addLayout(reply_row)

        left_layout.addStretch()

        row_btns = QHBoxLayout()
        row_btns.setSpacing(8)
        self.btn_save = QPushButton("Save Configuration")
        self.btn_save.setObjectName("VercelButton")
        self.btn_save.setFixedHeight(38)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self.on_save_clicked)
        row_btns.addWidget(self.btn_save, stretch=1)

        self.btn_send_now = QPushButton("Send Now")
        self.btn_send_now.setObjectName("SecondaryButton")
        self.btn_send_now.setFixedHeight(38)
        self.btn_send_now.setCursor(Qt.PointingHandCursor)
        self.btn_send_now.clicked.connect(self.on_send_now_clicked)
        row_btns.addWidget(self.btn_send_now)
        left_layout.addLayout(row_btns)

        self.lbl_status = QLabel("Not configured")
        self.lbl_status.setObjectName("HelpPoint")
        self.lbl_status.setWordWrap(True)
        left_layout.addWidget(self.lbl_status)

        root.addWidget(left)

        # ── Middle card: destinations ────────────────────────────────
        mid = QFrame()
        mid.setObjectName("WhiteCard")
        mid.setFixedWidth(320)
        mid_layout = QVBoxLayout(mid)
        mid_layout.setContentsMargins(16, 18, 16, 18)
        mid_layout.setSpacing(10)

        lbl_dest = QLabel("Destinations")
        lbl_dest.setObjectName("SectionSmall")
        mid_layout.addWidget(lbl_dest)

        self.search = QLineEdit()
        self.search.setObjectName("VercelInput")
        self.search.setPlaceholderText("Filter groups & channels…")
        self.search.setMinimumHeight(36)
        self.search.textChanged.connect(self.populate_destinations)
        mid_layout.addWidget(self.search)

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
        mid_layout.addLayout(tools)

        self.dest_list = QListWidget()
        self.dest_list.setObjectName("DestList")
        self.dest_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.dest_list.itemChanged.connect(self._on_item_changed)
        mid_layout.addWidget(self.dest_list, stretch=1)

        root.addWidget(mid)

        # ── Right card: messages library ─────────────────────────────
        right = QFrame()
        right.setObjectName("WhiteCard")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 18, 16, 18)
        right_layout.setSpacing(10)

        lbl_msgs = QLabel("Messages")
        lbl_msgs.setObjectName("SectionSmall")
        right_layout.addWidget(lbl_msgs)

        self.msg_list = QListWidget()
        self.msg_list.setObjectName("AutoMessageList")
        self.msg_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.msg_list.setSpacing(4)
        right_layout.addWidget(self.msg_list, stretch=1)

        # Add message form
        lbl_new = QLabel("Add a message")
        lbl_new.setObjectName("SectionSmall")
        right_layout.addWidget(lbl_new)

        self.input_text = QPlainTextEdit()
        self.input_text.setPlaceholderText("Type your message… (emoji supported, e.g. 🚀 Deal of the day! 🔥)")
        self.input_text.setFixedHeight(80)
        self.input_text.setObjectName("MessageCompose")
        right_layout.addWidget(self.input_text)

        img_row = QHBoxLayout()
        img_row.setSpacing(8)
        self.btn_pick_image = QPushButton("Attach Image…")
        self.btn_pick_image.setObjectName("SecondaryButton")
        self.btn_pick_image.setFixedHeight(30)
        self.btn_pick_image.setCursor(Qt.PointingHandCursor)
        self.btn_pick_image.clicked.connect(self.pick_image)
        img_row.addWidget(self.btn_pick_image)
        self.lbl_image = QLabel("No image attached")
        self.lbl_image.setObjectName("HelpPoint")
        img_row.addWidget(self.lbl_image, stretch=1)
        right_layout.addLayout(img_row)

        self.btn_add_msg = QPushButton("Add Message")
        self.btn_add_msg.setObjectName("VercelButton")
        self.btn_add_msg.setFixedHeight(36)
        self.btn_add_msg.setCursor(Qt.PointingHandCursor)
        self.btn_add_msg.clicked.connect(self.add_message)
        right_layout.addWidget(self.btn_add_msg)

        lbl_log = QLabel("Log")
        lbl_log.setObjectName("LogTitle")
        right_layout.addWidget(lbl_log)
        self.log = QPlainTextEdit()
        self.log.setObjectName("ConsoleLog")
        self.log.setReadOnly(True)
        self.log.setFixedHeight(90)
        right_layout.addWidget(self.log)

        root.addWidget(right, stretch=1)

    def is_dark_theme(self):
        return _is_dark()

    def _cooldown_hours(self) -> int:
        text = self.combo_cooldown.currentText()
        if "1 hour" in text:
            return 1
        if "6 hours" in text:
            return 6
        if "week" in text:
            return 168
        return 24

    def _cooldown_label(self, hours: int) -> str:
        if hours <= 1:
            return "Once per 1 hour"
        if hours <= 6:
            return "Once per 6 hours"
        if hours >= 24 * 7:
            return "Once per week"
        return "Once per 24 hours"

    # ------------------------------------------------------------------ data

    def populate_destinations(self):
        query = self.search.text().strip().lower() if hasattr(self, "search") else ""
        saved = set(get_auto_message()["destination_ids"])
        self.dest_list.blockSignals(True)
        self.dest_list.clear()
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
            if query and query not in title.lower() and query not in str(ch.get("username") or "").lower():
                continue
            items.append((full_id, title, bool(ch.get("is_channel", 0)), ch))
        items.sort(key=lambda t: (0 if t[3].get("pinned") else 1, t[1].lower()))
        for full_id, title, is_channel, ch in items:
            kind = "Channel" if is_channel else "Group"
            uname = ch.get("username") or ""
            sub = uname if uname else kind
            item = QListWidgetItem(f"{title}  ·  {sub}")
            item.setData(Qt.UserRole, full_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if full_id in saved else Qt.Unchecked)
            self.dest_list.addItem(item)
        self.dest_list.blockSignals(False)
        self._update_count()

    def _on_item_changed(self, item):
        self._update_count()

    def _update_count(self):
        count = sum(1 for i in range(self.dest_list.count()) if self.dest_list.item(i).checkState() == Qt.Checked)
        self.lbl_count.setText(f"{count} selected")

    def select_all(self):
        for i in range(self.dest_list.count()):
            self.dest_list.item(i).setCheckState(Qt.Checked)
        self._update_count()

    def clear_selection(self):
        for i in range(self.dest_list.count()):
            self.dest_list.item(i).setCheckState(Qt.Unchecked)
        self._update_count()

    def selected_destinations(self):
        return [self.dest_list.item(i).data(Qt.UserRole)
                for i in range(self.dest_list.count())
                if self.dest_list.item(i).checkState() == Qt.Checked]

    # ------------------------------------------------------------------ messages

    def render_messages(self):
        self.msg_list.clear()
        state = get_auto_message()
        for i, msg in enumerate(state["messages"], 1):
            text = msg.get("text", "").replace("\n", " ").strip()
            if len(text) > 80:
                text = text[:80] + "…"
            img = msg.get("image_path") or ""
            img_note = "  🖼" if img else ""
            label = f"{i}. {text or '(empty)'}{img_note}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, msg.get("id"))
            tooltip = (msg.get("text") or "")
            if img:
                tooltip += f"\n\n[image attached: {os.path.basename(img)}]"
            item.setToolTip(tooltip)
            font = item.font()
            font.setPointSize(11)
            item.setFont(font)
            item.setSizeHint(item.sizeHint().__class__(item.sizeHint().width(), 34))
            self.msg_list.addItem(item)

            row = QWidget()
            row.setAttribute(Qt.WA_TranslucentBackground, True)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 2, 6, 2)
            row_layout.setSpacing(0)
            lbl_text = QLabel(label)
            lbl_text.setObjectName("MsgItemText")
            row_layout.addWidget(lbl_text, stretch=1)
            btn = QPushButton("✕")
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip("Remove this message")
            btn.setObjectName("MsgCloseButton")
            btn.clicked.connect(lambda checked=False, mid=msg.get("id"): self.remove_message(mid))
            row_layout.addWidget(btn)
            self.msg_list.setItemWidget(item, row)

    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select image", "",
            "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp);;All files (*)",
        )
        if path:
            self._picked_image = path
            self.lbl_image.setText(os.path.basename(path))

    def add_message(self):
        text = self.input_text.toPlainText().strip()
        img = self._picked_image or ""
        if not text and not img:
            self.on_log("Message is empty — add text and/or an image.")
            return
        state = get_auto_message()
        msgs = list(state["messages"])
        msgs.append({"id": f"msg_{len(msgs)}_{int(time.time())}", "text": text, "image_path": img})
        save_auto_message(messages=msgs)
        self.input_text.clear()
        self._picked_image = ""
        self.lbl_image.setText("No image attached")
        self.render_messages()
        self._refresh_status_label()
        self.on_log(f"Added message #{len(msgs)}.")

    def remove_message(self, msg_id):
        state = get_auto_message()
        msgs = [m for m in state["messages"] if m.get("id") != msg_id]
        save_auto_message(messages=msgs)
        self.render_messages()
        self._refresh_status_label()
        self.on_log("Message removed.")

    # ------------------------------------------------------------------ state

    def load_state(self):
        state = get_auto_message()
        self.chk_enabled.setChecked(state["enabled"])
        # interval combo select
        target = state["interval_minutes"]
        for i, (_label, minutes) in enumerate(INTERVAL_OPTIONS):
            if minutes == target:
                self.combo_interval.blockSignals(True)
                self.combo_interval.setCurrentIndex(i)
                self.combo_interval.blockSignals(False)
                break
        self.combo_rotation.setCurrentText("Round-robin (in order)" if state["rotation"] != "random" else "Random each time")
        self.chk_auto_reply.setChecked(state.get("auto_reply_enabled", False))
        self.input_reply_text.setPlainText(state.get("auto_reply_text", ""))
        self.combo_cooldown.setCurrentText(self._cooldown_label(int(state.get("auto_reply_cooldown_hours", 24))))
        self.render_messages()
        self.populate_destinations()
        self._refresh_status_label()

    def _refresh_status_label(self):
        state = get_auto_message()
        parts = ["Enabled" if state["enabled"] else "Disabled"]
        parts.append(f"{len(state['messages'])} message(s)")
        parts.append(f"last run: {state['last_run'] or 'never'}")
        parts.append(f"sends: {state.get('send_count', 0)}")
        self.lbl_status.setText(" · ".join(parts))

    def on_save_clicked(self):
        target_label = self.combo_interval.currentText()
        minutes = next((m for _l, m in INTERVAL_OPTIONS if _l == target_label), 60)
        rotation = "random" if self.combo_rotation.currentText().startswith("Random") else "roundrobin"
        save_auto_message(
            enabled=self.chk_enabled.isChecked(),
            interval_minutes=minutes,
            rotation=rotation,
            destination_ids=self.selected_destinations(),
            auto_reply_enabled=self.chk_auto_reply.isChecked(),
            auto_reply_text=self.input_reply_text.toPlainText().strip(),
            auto_reply_cooldown_hours=self._cooldown_hours(),
        )
        self._refresh_status_label()
        self.on_log("Configuration saved.")

    def on_send_now_clicked(self):
        if not self.worker:
            self.on_log("Telegram client not ready.")
            return
        self.on_save_clicked()
        self.on_log("Sending now…")
        self.btn_send_now.setEnabled(False)
        self.btn_send_now.setText("Sending…")
        self.worker.send_auto_message()

    def on_log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{ts}] {msg}")

    def on_finished(self):
        self.btn_send_now.setEnabled(True)
        self.btn_send_now.setText("Send Now")
        self._refresh_status_label()

    def update_theme(self, is_dark: bool):
        for name in ("combo_interval", "combo_rotation", "combo_cooldown"):
            combo = getattr(self, name, None)
            if combo is not None and hasattr(combo, "refresh_theme"):
                combo.refresh_theme()
