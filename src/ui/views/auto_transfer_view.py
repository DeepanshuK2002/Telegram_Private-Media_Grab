"""
Auto Transfer view — multiple independent source → destination rules.

Each rule watches one source channel/group and re-uploads every new media post
to the selected destination groups/channels (and optionally routes through a
specific download account and upload account).
Files are staged in auto_transfer_cache/ and deleted automatically after every
send succeeds.
"""
import os
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QFrame,
    QCheckBox, QPlainTextEdit, QStyledItemDelegate, QStyleOptionViewItem,
    QProgressBar
)
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor

from ui.views.settings_view import load_config
from ui.theme import get_tokens
from database import get_cached_channels_list
from accounts import get_accounts, get_active_account_id
from auto_transfer import (
    get_rules, save_rules, add_rule, update_rule, remove_rule, cache_dir,
)
from ui.components.searchable_combobox import SearchableComboBox


def _is_dark() -> bool:
    try:
        return bool(load_config().get("dark_mode", False))
    except Exception:
        return False


def _tokens() -> dict:
    return get_tokens(_is_dark())


MEDIA_LABELS = {
    "Videos": "videos",
    "All": "all",
    "Images": "images",
    "Documents / PDFs": "documents",
    "Audio": "audio",
    "Text/Chat": "text",
}
MEDIA_KEYS = {v: k for k, v in MEDIA_LABELS.items()}


class _AccountTagDelegate(QStyledItemDelegate):
    """Paints an account-ownership tag on the right margin of each destination row."""

    def paint(self, painter, option, index):
        tag = index.data(Qt.UserRole + 1)
        # Reserve space on the right for the tag so the title elides before it.
        opt = QStyleOptionViewItem(option)
        if tag:
            fm = painter.fontMetrics()
            tag_w = fm.horizontalAdvance(str(tag)) + 14
            opt.rect = QRect(opt.rect.left(), opt.rect.top(),
                             max(0, opt.rect.width() - tag_w), opt.rect.height())
        super().paint(painter, opt, index)
        if not tag:
            return
        painter.save()
        try:
            from ui.theme import get_tokens
            from ui.views.settings_view import load_config
            is_dark = bool(load_config().get("dark_mode", False))
            muted = get_tokens(is_dark).get("muted_foreground", "#71717A")
        except Exception:
            muted = "#71717A"
        fm = painter.fontMetrics()
        rect = option.rect
        tag_w = fm.horizontalAdvance(str(tag)) + 14
        x = rect.right() - tag_w + 6
        y = rect.top() + (rect.height() + fm.ascent() - fm.descent()) // 2
        painter.setPen(QColor(muted))
        painter.drawText(x, y, str(tag))
        painter.restore()


class AutoTransferView(QWidget):
    """Auto Transfer page: manage multiple source → destination rules."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self._selected_rule_id = None
        self._account_status = {}
        self._account_events_connected = False
        self._status_base = "No rule selected."
        self._dl_last = None
        self._ul_last = None
        self._dl_text = ""
        self._ul_text = ""
        self.setup_ui()
        self.load_state()

    def set_worker(self, worker):
        self.worker = worker
        if worker:
            worker.signals.auto_transfer_log.connect(self.on_log)
            worker.signals.auto_transfer_finished.connect(self.on_finished)
            try:
                worker.signals.auto_transfer_status.connect(self.on_status)
            except Exception:
                pass
            try:
                worker.signals.auto_transfer_download_progress.connect(self.on_dl_progress)
            except Exception:
                pass
            try:
                worker.signals.auto_transfer_upload_progress.connect(self.on_ul_progress)
            except Exception:
                pass
            if not self._account_events_connected:
                try:
                    worker.signals.account_event.connect(self._on_account_event)
                except Exception:
                    pass
                self._account_events_connected = True
            self._schedule_account_check()

    # ------------------------------------------------------------------ UI

    def setup_ui(self):
        t = _tokens()
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)

        # ── Left card: rules list ──────────────────────────────────────
        left = QFrame()
        left.setObjectName("WhiteCard")
        left.setFixedWidth(300)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 14, 16, 14)
        left_layout.setSpacing(8)

        lbl_title = QLabel("Auto Transfer")
        lbl_title.setObjectName("PageTitle")
        left_layout.addWidget(lbl_title)

        lbl_sub = QLabel("Independent source → destination rules. Each rule keeps its own last-seen state.")
        lbl_sub.setObjectName("MutedText")
        lbl_sub.setWordWrap(True)
        left_layout.addWidget(lbl_sub)

        self.rules_list = QListWidget()
        self.rules_list.setObjectName("RulesList")
        self.rules_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.rules_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.rules_list.setSpacing(2)
        self.rules_list.currentItemChanged.connect(self._on_rule_selected)
        left_layout.addWidget(self.rules_list, stretch=1)

        row = QHBoxLayout()
        self.btn_add_rule = QPushButton("Add Rule")
        self.btn_add_rule.setObjectName("SecondaryButton")
        self.btn_add_rule.setFixedHeight(32)
        self.btn_add_rule.setCursor(Qt.PointingHandCursor)
        self.btn_add_rule.clicked.connect(self.on_add_rule)
        row.addWidget(self.btn_add_rule, stretch=1)

        self.btn_del_rule = QPushButton("Delete")
        self.btn_del_rule.setObjectName("LogoutBtn")
        self.btn_del_rule.setFixedHeight(32)
        self.btn_del_rule.setCursor(Qt.PointingHandCursor)
        self.btn_del_rule.clicked.connect(self.on_delete_rule)
        row.addWidget(self.btn_del_rule)
        left_layout.addLayout(row)

        self.btn_check_now = QPushButton("Check Now (All Rules)")
        self.btn_check_now.setObjectName("VercelButton")
        self.btn_check_now.setFixedHeight(38)
        self.btn_check_now.setCursor(Qt.PointingHandCursor)
        self.btn_check_now.clicked.connect(self.on_check_now_clicked)
        left_layout.addWidget(self.btn_check_now)

        note = QLabel("Runs every 30 minutes while the app is open, plus once on app start. Cached files are deleted after sending. Transfers keep running in the background even if you leave this page — the indicator above shows progress.")
        note.setObjectName("HelpPoint")
        note.setWordWrap(True)
        left_layout.addWidget(note)

        root.addWidget(left)

        # ── Right card: selected rule editor (compact grid) ─────────────
        right = QFrame()
        right.setObjectName("WhiteCard")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 14, 16, 14)
        right_layout.setSpacing(8)

        # Row 1 — name + enable toggle
        edit_header = QHBoxLayout()
        edit_header.setSpacing(8)
        self.lbl_name = QLabel("(Select a rule)")
        self.lbl_name.setObjectName("SectionSmall")
        edit_header.addWidget(self.lbl_name, stretch=1)
        self.chk_enabled = QCheckBox("Enabled")
        self.chk_enabled.setCursor(Qt.PointingHandCursor)
        edit_header.addWidget(self.chk_enabled)
        right_layout.addLayout(edit_header)

        # Row 2 — source (wide) + media type (narrow) side by side
        row_sm = QHBoxLayout()
        row_sm.setSpacing(12)
        col_src = QVBoxLayout()
        col_src.setSpacing(4)
        lbl_src = QLabel("Source channel / group (watched)")
        lbl_src.setObjectName("FieldLabel")
        col_src.addWidget(lbl_src)
        self.combo_source = SearchableComboBox()
        self.combo_source.setMinimumHeight(34)
        col_src.addWidget(self.combo_source)
        row_sm.addLayout(col_src, stretch=3)

        col_type = QVBoxLayout()
        col_type.setSpacing(4)
        lbl_type = QLabel("Media type")
        lbl_type.setObjectName("FieldLabel")
        col_type.addWidget(lbl_type)
        self.combo_media = SearchableComboBox()
        self.combo_media.addItems(list(MEDIA_LABELS.keys()))
        self.combo_media.setMinimumHeight(34)
        col_type.addWidget(self.combo_media)
        row_sm.addLayout(col_type, stretch=2)
        right_layout.addLayout(row_sm)

        self.chk_include_existing = QCheckBox("Include backlog (media already in the source)")
        self.chk_include_existing.setCursor(Qt.PointingHandCursor)
        right_layout.addWidget(self.chk_include_existing)

        # Row 3 — download + upload account side by side
        row_acc = QHBoxLayout()
        row_acc.setSpacing(12)
        col_dl = QVBoxLayout()
        col_dl.setSpacing(4)
        lbl_dl_acc = QLabel("Download from account")
        lbl_dl_acc.setObjectName("FieldLabel")
        col_dl.addWidget(lbl_dl_acc)
        self.combo_download_account = SearchableComboBox()
        self.combo_download_account.setMinimumHeight(34)
        col_dl.addWidget(self.combo_download_account)
        row_acc.addLayout(col_dl, stretch=1)

        col_ul = QVBoxLayout()
        col_ul.setSpacing(4)
        lbl_ul_acc = QLabel("Upload via account")
        lbl_ul_acc.setObjectName("FieldLabel")
        col_ul.addWidget(lbl_ul_acc)
        self.combo_upload_account = SearchableComboBox()
        self.combo_upload_account.setMinimumHeight(34)
        col_ul.addWidget(self.combo_upload_account)
        row_acc.addLayout(col_ul, stretch=1)
        right_layout.addLayout(row_acc)

        # Row 4 — destinations header (count + actions on the same line)
        dest_header = QHBoxLayout()
        dest_header.setSpacing(8)
        lbl_dest = QLabel("Destinations (where to send the content)")
        lbl_dest.setObjectName("FieldLabel")
        dest_header.addWidget(lbl_dest, stretch=1)
        self.lbl_selected = QLabel("0 selected")
        self.lbl_selected.setObjectName("MutedText")
        dest_header.addWidget(self.lbl_selected)
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.setObjectName("SecondaryButton")
        self.btn_select_all.setFixedHeight(28)
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        self.btn_select_all.clicked.connect(self.select_all)
        dest_header.addWidget(self.btn_select_all)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setObjectName("SecondaryButton")
        self.btn_clear.setFixedHeight(28)
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear_selection)
        dest_header.addWidget(self.btn_clear)
        right_layout.addLayout(dest_header)

        self.search = QLineEdit()
        self.search.setObjectName("VercelInput")
        self.search.setPlaceholderText("Filter groups & channels…")
        self.search.setMinimumHeight(34)
        self.search.textChanged.connect(self.populate_destinations)
        right_layout.addWidget(self.search)

        self.dest_list = QListWidget()
        self.dest_list.setObjectName("DestList")
        self.dest_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.dest_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.dest_list.setItemDelegate(_AccountTagDelegate(self.dest_list))
        self.dest_list.itemChanged.connect(self._on_item_changed)
        self.dest_list.setMinimumHeight(80)
        right_layout.addWidget(self.dest_list, stretch=1)

        # Save + cache folder on one row
        row_save = QHBoxLayout()
        row_save.setSpacing(8)
        self.btn_save = QPushButton("Save Rule")
        self.btn_save.setObjectName("VercelButton")
        self.btn_save.setFixedHeight(36)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self.on_save_rule)
        row_save.addWidget(self.btn_save, stretch=1)

        self.btn_run = QPushButton("Run")
        self.btn_run.setObjectName("SecondaryButton")
        self.btn_run.setFixedHeight(36)
        self.btn_run.setMinimumWidth(70)
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.setToolTip("Save this rule and run it now (manual sync)")
        self.btn_run.clicked.connect(self.on_run_clicked)
        row_save.addWidget(self.btn_run)

        self.btn_open_cache = QPushButton("Open Cache Folder")
        self.btn_open_cache.setObjectName("SecondaryButton")
        self.btn_open_cache.setFixedHeight(36)
        self.btn_open_cache.setCursor(Qt.PointingHandCursor)
        self.btn_open_cache.clicked.connect(self.open_cache_folder)
        row_save.addWidget(self.btn_open_cache)
        right_layout.addLayout(row_save)

        # Run status / progress (visible while a transfer is running)
        run_status_row = QHBoxLayout()
        run_status_row.setSpacing(8)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate (busy) while running
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        self.progress.setObjectName("TransferProgress")
        run_status_row.addWidget(self.progress, stretch=1)
        self.lbl_run_status = QLabel("Idle")
        self.lbl_run_status.setObjectName("MutedText")
        run_status_row.addWidget(self.lbl_run_status)
        right_layout.addLayout(run_status_row)

        self.lbl_status = QLabel("No rule selected.")
        self.lbl_status.setObjectName("HelpPoint")
        self.lbl_status.setWordWrap(True)
        right_layout.addWidget(self.lbl_status)

        lbl_log = QLabel("Log")
        lbl_log.setObjectName("LogTitle")
        right_layout.addWidget(lbl_log)

        self.log = QPlainTextEdit()
        self.log.setObjectName("ConsoleLog")
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(64)
        right_layout.addWidget(self.log, stretch=1)

        root.addWidget(right, stretch=1)

    def is_dark_theme(self):
        return _is_dark()

    # ------------------------------------------------------------------ data

    def load_state(self):
        self._all_channels = self._load_channel_list()
        self._refresh_account_combos()
        self.populate_source_combos()
        self._refresh_rules_list()

    def _schedule_account_check(self, attempts=0):
        if not self.worker:
            return
        if getattr(self.worker, "loop", None):
            try:
                self.worker.check_all_accounts()
            except Exception:
                pass
            return
        if attempts < 20:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(250, lambda: self._schedule_account_check(attempts + 1))

    def _on_account_event(self, event):
        try:
            parts = event.split(":", 2)
            kind = parts[0]
            acc_id = parts[1] if len(parts) > 1 else ""
            payload = parts[2] if len(parts) > 2 else ""
            if kind == "status":
                self._account_status[str(acc_id)] = (payload == "1")
                self._refresh_account_tags()
        except Exception:
            pass

    def _account_name(self, account_id):
        try:
            from accounts import get_accounts
            for acc in get_accounts():
                if str(acc.get("id")) == str(account_id):
                    return acc.get("name") or str(account_id)
        except Exception:
            pass
        return str(account_id)

    def _account_tag(self, account_ids):
        if not account_ids:
            return "—"
        tags = []
        for aid in account_ids:
            aid = str(aid).strip()
            if not aid:
                continue
            name = self._account_name(aid)
            status = self._account_status.get(aid)
            active = aid == str(get_active_account_id())
            if active:
                sym = "●" if status is not False else "○"
            else:
                sym = "✓" if status is True else ("✗" if status is False else "?")
            tags.append(f"{name} {sym}")
        if len(tags) > 2:
            return tags[0] + f"  (+{len(tags) - 1})"
        return "  ·  ".join(tags)

    def _refresh_account_tags(self):
        try:
            for i in range(self.dest_list.count()):
                item = self.dest_list.item(i)
                if item is None:
                    continue
                full_id = item.data(Qt.UserRole)
                # find account_ids for this channel
                accs = []
                for fid, title, _p, aids in self._all_channels:
                    if fid == full_id:
                        accs = aids
                        break
                item.setData(Qt.UserRole + 1, self._account_tag(accs))
            self.dest_list.viewport().update()
        except Exception:
            pass

    def _load_channel_list(self):
        try:
            cached = get_cached_channels_list() or []
        except Exception:
            return []
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
            account_ids = [x for x in str(ch.get("account_ids") or "").split(",") if x.strip()]
            items.append((full_id, title, bool(ch.get("pinned", 0)), account_ids))
        items.sort(key=lambda t: (0 if t[2] else 1, t[1].lower()))
        return items

    def _refresh_account_combos(self):
        active_id = get_active_account_id()
        accounts = get_accounts()
        accounts_sorted = sorted(accounts, key=lambda a: (0 if a.get("id") == active_id else 1, (a.get("name") or "").lower()))
        for combo in (self.combo_download_account, self.combo_upload_account):
            combo.blockSignals(True)
            combo.clear()
            for acc in accounts_sorted:
                acc_id = str(acc.get("id"))
                label = acc.get("name") or acc_id
                if acc_id == active_id:
                    label = f"{label}  (Active)"
                combo.addItem(label, acc_id)
            combo.blockSignals(False)

    def populate_source_combos(self):
        """Fill the source combo with the cached channels/groups."""
        self.combo_source.clear()
        for full_id, title, _pinned, _accs in self._all_channels:
            self.combo_source.addItem(f"{title}  ({full_id})", full_id)

    def populate_destinations(self):
        """Fill the destinations checklist for the selected rule."""
        query = self.search.text().strip().lower() if hasattr(self, "search") else ""
        saved_dests = []
        if self._selected_rule_id:
            for r in get_rules():
                if r.get("id") == self._selected_rule_id:
                    saved_dests = r.get("destination_ids") or []
                    break
        self.dest_list.blockSignals(True)
        self.dest_list.clear()
        for full_id, title, _pinned, account_ids in self._all_channels:
            if query and (query not in title.lower()):
                continue
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, full_id)
            item.setData(Qt.UserRole + 1, self._account_tag(account_ids))
            item.setToolTip(f"{title}\n{full_id}\nAccounts: {self._account_tag(account_ids)}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if full_id in saved_dests else Qt.Unchecked)
            self.dest_list.addItem(item)
        self.dest_list.blockSignals(False)
        self._update_count()

    def _refresh_rules_list(self, select_id: str = None):
        self.rules_list.blockSignals(True)
        self.rules_list.clear()
        rules = get_rules()
        for i, r in enumerate(rules, 1):
            name = r.get("name") or f"Rule {i}"
            status = "ON" if r.get("enabled") else "OFF"
            dests = len(r.get("destination_ids") or [])
            src = ""
            for full_id, title, _, _ in self._all_channels:
                if full_id == r.get("source_channel_id"):
                    src = f" → {title[:36]}"
                    break
            item = QListWidgetItem(f"{status}  {name}{src}  ({dests} dest)")
            item.setData(Qt.UserRole, r.get("id"))
            self.rules_list.addItem(item)
        self.rules_list.blockSignals(False)

        target = select_id or self._selected_rule_id
        if target:
            for i in range(self.rules_list.count()):
                if self.rules_list.item(i).data(Qt.UserRole) == target:
                    self.rules_list.setCurrentRow(i)
                    return
        if self.rules_list.count():
            self.rules_list.setCurrentRow(0)

    def load_rule_into_editor(self, rule_id: str):
        if not rule_id:
            return
        self._selected_rule_id = rule_id
        rules = get_rules()
        rule = next((r for r in rules if r.get("id") == rule_id), None)
        if not rule:
            return

        # Name + enabled
        self.lbl_name.setText(rule.get("name") or "Rule")
        self.chk_enabled.blockSignals(True)
        self.chk_enabled.setChecked(bool(rule.get("enabled", False)))
        self.chk_enabled.blockSignals(False)

        # Source combo
        src_id = rule.get("source_channel_id", "")
        self.combo_source.blockSignals(True)
        idx = self.combo_source.findData(src_id)
        if idx >= 0:
            self.combo_source.setCurrentIndex(idx)
        self.combo_source.blockSignals(False)

        # Media type
        media_key = rule.get("media_type", "videos")
        label = MEDIA_KEYS.get(media_key, "Videos")
        self.combo_media.setCurrentText(label)

        # Include backlog
        self.chk_include_existing.blockSignals(True)
        self.chk_include_existing.setChecked(bool(rule.get("include_existing", False)))
        self.chk_include_existing.blockSignals(False)

        # Accounts
        for combo, key in ((self.combo_download_account, "download_account_id"), (self.combo_upload_account, "upload_account_id")):
            acc_id = rule.get(key) or get_active_account_id()
            combo.blockSignals(True)
            idx = combo.findData(acc_id)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        # Destinations
        self.populate_destinations()

        # Status line (per-rule)
        base = (
            f"Last run: {rule.get('last_run') or 'never'}  ·  "
            f"last seen msg: {rule.get('last_seen_msg_id', 0)}"
        )
        self._status_base = base
        self._dl_last = None
        self._ul_last = None
        self.lbl_status.setText(base)

    def _selected_rule_data(self) -> dict:
        """Return a snapshot of the editor fields for the selected rule."""
        rules = get_rules()
        rule = next((r for r in rules if r.get("id") == self._selected_rule_id), None)
        if rule is None:
            return {}
        out = dict(rule)
        out["name"] = self.lbl_name.text().strip() or rule.get("name", "Rule")
        out["enabled"] = self.chk_enabled.isChecked()
        out["source_channel_id"] = str(self.combo_source.currentData() or "")
        out["media_type"] = MEDIA_LABELS.get(self.combo_media.currentText(), "videos")
        out["include_existing"] = self.chk_include_existing.isChecked()
        out["download_account_id"] = str(self.combo_download_account.currentData() or "")
        out["upload_account_id"] = str(self.combo_upload_account.currentData() or "")
        out["destination_ids"] = self.selected_destinations()
        return out

    # ------------------------------------------------------------------ rules list

    def _on_rule_selected(self, current, previous):
        if current is None:
            self._selected_rule_id = None
            self.lbl_name.setText("(Select a rule)")
            self._status_base = "No rule selected."
            self.lbl_status.setText(self._status_base)
            return
        self._selected_rule_id = current.data(Qt.UserRole)
        self.load_rule_into_editor(self._selected_rule_id)

    def on_add_rule(self):
        new_rule = add_rule()
        self._selected_rule_id = new_rule.get("id")
        self._refresh_rules_list(select_id=self._selected_rule_id)
        self.on_log("Added a new rule. Select its source and destinations, then enable + Save.")

    def on_delete_rule(self):
        if not self._selected_rule_id:
            return
        from PySide6.QtWidgets import QMessageBox
        name = self.lbl_name.text() or "this rule"
        answer = QMessageBox.question(
            self, "Delete Rule",
            f"Delete '{name}'?\nThis does not delete any Telegram data, just the rule.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        remove_rule(self._selected_rule_id)
        self.load_state()
        self.on_log("Rule deleted.")

    def _on_item_changed(self, item):
        self._update_count()

    def _update_count(self):
        count = sum(1 for i in range(self.dest_list.count()) if self.dest_list.item(i).checkState() == Qt.Checked)
        self.lbl_selected.setText(f"{count} selected")

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

    # ------------------------------------------------------------------ actions

    def on_save_rule(self):
        data = self._selected_rule_data()
        if not data:
            self.on_log("No rule selected.")
            return
        if not data.get("source_channel_id"):
            self.on_log("Pick a source channel/group first.")
            return
        if not data.get("destination_ids"):
            self.on_log("Pick at least one destination group/channel.")
            return
        if not update_rule(data["id"], **{k: v for k, v in data.items() if k != "id"}):
            self.on_log("Could not save rule.")
            return
        # Refresh the rules list to reflect name/enabled state
        self._refresh_rules_list(select_id=data["id"])
        self._status_base = f"Saved. Last run: {data.get('last_run') or 'never'}  ·  last seen msg: {data.get('last_seen_msg_id', 0)}"
        self.lbl_status.setText(self._status_base)
        self.on_log(f"Saved rule '{data.get('name')}'.")

    def on_check_now_clicked(self):
        if not self.worker:
            self.on_log("Telegram client not ready.")
            return
        self.on_save_rule()
        self.on_log("Checking all enabled rules…")
        self.btn_check_now.setEnabled(False)
        self.btn_check_now.setText("Checking…")
        self.worker.run_auto_transfer_check()

    def on_run_clicked(self):
        if not self._selected_rule_id:
            self.on_log("Select a rule first.")
            return
        if not self.worker:
            self.on_log("Telegram client not ready.")
            return
        self.on_save_rule()
        rule_id = self._selected_rule_id
        name = self.lbl_name.text() or "rule"
        self.on_log(f"Running '{name}' now…")
        self.btn_run.setEnabled(False)
        self.btn_run.setText("Running…")
        self.worker.run_auto_transfer_single(rule_id)

    def on_log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{ts}] {msg}")

    def on_finished(self):
        self.btn_check_now.setEnabled(True)
        self.btn_check_now.setText("Check Now (All Rules)")
        self.btn_run.setEnabled(True)
        self.btn_run.setText("Run")
        self.progress.setVisible(False)
        self.lbl_run_status.setText("Idle")
        self._dl_last = None
        self._ul_last = None
        self._dl_text = ""
        self._ul_text = ""
        self.lbl_status.setText(self._status_base)
        self.load_state()

    def on_status(self, text):
        text = (text or "").strip()
        if text:
            self.progress.setVisible(True)
            self.lbl_run_status.setText(text)
        else:
            self.progress.setVisible(False)
            self.lbl_run_status.setText("Idle")
            self._dl_last = None
            self._ul_last = None
            self._dl_text = ""
            self._ul_text = ""
            self.lbl_status.setText(self._status_base)

    def _fmt_size(self, b):
        b = float(b or 0)
        if b >= 1024 * 1024 * 1024:
            return f"{b/1024/1024/1024:.2f} GB"
        if b >= 1024 * 1024:
            return f"{b/1024/1024:.2f} MB"
        if b >= 1024:
            return f"{b/1024:.1f} KB"
        return f"{int(b)} B"

    def on_dl_progress(self, filename, current, total):
        import time as _t
        now = _t.time()
        speed = 0.0
        if self._dl_last is not None:
            dt = now - self._dl_last[1]
            if dt > 0:
                speed = (current - self._dl_last[0]) / dt
        self._dl_last = (current, now)
        if total:
            remaining = max(0, total - current)
            pct = int(current * 100 / total) if total else 0
            speed_txt = f" @ {self._fmt_size(speed)}/s" if speed > 0 else ""
            seg = "\u2193 " + filename + ": " + self._fmt_size(current) + "/" + self._fmt_size(total) + " (" + self._fmt_size(remaining) + " left, " + str(pct) + "%)" + speed_txt
        else:
            seg = "\u2193 " + filename + ": " + self._fmt_size(current) + ((" @ " + self._fmt_size(speed) + "/s") if speed > 0 else "")
        self._dl_text = seg
        ul_txt = getattr(self, "_ul_text", "")
        suffix = seg + (("  \u00b7  " + ul_txt) if ul_txt else "")
        self.lbl_status.setText(self._status_base + "  \u00b7  " + suffix)

    def on_ul_progress(self, filename, dest, current, total):
        import time as _t
        now = _t.time()
        speed = 0.0
        if self._ul_last is not None:
            dt = now - self._ul_last[1]
            if dt > 0:
                speed = (current - self._ul_last[0]) / dt
        self._ul_last = (current, now)
        if total:
            remaining = max(0, total - current)
            pct = int(current * 100 / total) if total else 0
            speed_txt = f" @ {self._fmt_size(speed)}/s" if speed > 0 else ""
            seg = "\u2191 " + filename + "\u2192" + dest + ": " + self._fmt_size(current) + "/" + self._fmt_size(total) + " (" + self._fmt_size(remaining) + " left, " + str(pct) + "%)" + speed_txt
        else:
            seg = "\u2191 " + filename + "\u2192" + dest + ": " + self._fmt_size(current) + ((" @ " + self._fmt_size(speed) + "/s") if speed > 0 else "")
        self._ul_text = seg
        dl_txt = getattr(self, "_dl_text", "")
        suffix = (dl_txt + "  \u00b7  " + seg) if dl_txt else seg
        self.lbl_status.setText(self._status_base + "  \u00b7  " + suffix)

    def open_cache_folder(self):
        folder = cache_dir()
        os.makedirs(folder, exist_ok=True)
        try:
            os.startfile(folder)
        except Exception:
            pass

    def update_theme(self, is_dark: bool):
        for combo_name in ("combo_source", "combo_media", "combo_download_account", "combo_upload_account"):
            combo = getattr(self, combo_name, None)
            if combo is not None and hasattr(combo, "refresh_theme"):
                combo.refresh_theme()
