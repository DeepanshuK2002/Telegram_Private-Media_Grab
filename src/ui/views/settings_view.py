from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QComboBox,
    QFrame, QFileDialog, QSpinBox, QMessageBox,
    QScrollArea, QGridLayout, QListWidget, QListWidgetItem, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QUrl, QTimer
from PySide6.QtGui import QDesktopServices, QIcon
import json
import os
from resource_utils import get_project_root
from accounts import get_accounts, get_active_account_id, set_active_account_id, add_account, remove_account
from ui.components.clean_combobox import CleanComboBox
from ui.components.searchable_combobox import SearchableComboBox

CONFIG_FILE = os.path.join(get_project_root(), "config.json")

def load_config():
    default_config = {
        "download_path": "downloads",
        "download_limit": 5,
        "initial_fetch_limit": 2000,
        "max_speed_kb": 0,
        "forum_auto_separation": False,
        "rename_duplicates": True,
        "use_message_date": True,
        "prefix_file_date": True,
        "redownload_deleted": False,
        "dark_mode": True,
        "proxy": {
            "enabled": False,
            "type": "SOCKS5",
            "host": "",
            "port": "",
            "user": "",
            "pass": ""
        }
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception as e:
            print(f"Error loading config: {e}")
    return default_config

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

class SettingsView(QWidget):
    logoutRequested = Signal()
    themeToggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._worker_events_connected = False
        self._accounts_cache = []
        self._account_status = {}
        self.setup_ui()
        self.refresh_accounts()

    def setup_ui(self):
        # Root layout
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        # Container
        self.container = QWidget()
        self.scroll_layout = QVBoxLayout(self.container)
        self.scroll_layout.setContentsMargins(40, 32, 40, 48)
        self.scroll_layout.setSpacing(24)
        self.scroll_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # ── Header ────────────────────────────────────────────────────────────
        header_widget = QWidget()
        header_widget.setMaximumWidth(800)
        h_layout = QVBoxLayout(header_widget)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(4)

        lbl_header = QLabel("Settings")
        lbl_header.setObjectName("MainHeaderLarge")
        lbl_sub = QLabel("Manage your preferences, appearance, network connection, and account.")
        lbl_sub.setObjectName("MutedText")

        h_layout.addWidget(lbl_header)
        h_layout.addWidget(lbl_sub)
        self.scroll_layout.addWidget(header_widget)

        # ── Section 1: Appearance (Theme) ─────────────────────────────────────
        card_theme = self._create_card()
        theme_layout = QVBoxLayout(card_theme)
        theme_layout.setContentsMargins(28, 24, 28, 24)
        theme_layout.setSpacing(16)

        lbl_theme_title = QLabel("Appearance")
        lbl_theme_title.setObjectName("SectionHeader")
        theme_layout.addWidget(lbl_theme_title)

        theme_row = QHBoxLayout()
        theme_text_layout = QVBoxLayout()
        theme_text_layout.setSpacing(2)

        lbl_mode_title = QLabel("Dark Mode")
        lbl_mode_title.setObjectName("ControlLabel")
        lbl_mode_desc = QLabel("Use high-contrast pitch-black Vercel monochrome design")
        lbl_mode_desc.setObjectName("MutedText")
        theme_text_layout.addWidget(lbl_mode_title)
        theme_text_layout.addWidget(lbl_mode_desc)

        self.chk_dark_mode = QCheckBox("Dark Theme")
        self.chk_dark_mode.setCursor(Qt.PointingHandCursor)
        self.chk_dark_mode.toggled.connect(self._on_theme_toggled)

        theme_row.addLayout(theme_text_layout, stretch=1)
        theme_row.addWidget(self.chk_dark_mode)
        theme_layout.addLayout(theme_row)

        self.scroll_layout.addWidget(card_theme)

        # ── Section 1.5: Accounts (multi-account login) ───────────────────────
        card_acc = self._create_card()
        acc_layout = QVBoxLayout(card_acc)
        acc_layout.setContentsMargins(28, 24, 28, 24)
        acc_layout.setSpacing(12)

        lbl_acc_title = QLabel("Accounts")
        lbl_acc_title.setObjectName("SectionHeader")
        acc_layout.addWidget(lbl_acc_title)

        lbl_acc_desc = QLabel("Log in to multiple Telegram accounts — like Telegram itself. You can switch the active account, and Auto Transfer can download from one account and upload via another.")
        lbl_acc_desc.setObjectName("MutedText")
        lbl_acc_desc.setWordWrap(True)
        acc_layout.addWidget(lbl_acc_desc)

        self.accounts_list = QListWidget()
        self.accounts_list.setObjectName("accountsList")
        self.accounts_list.setFixedHeight(180)
        self._style_accounts_list()
        acc_layout.addWidget(self.accounts_list)

        acc_btn_row = QHBoxLayout()
        acc_btn_row.setSpacing(8)

        self.btn_add_account = QPushButton("Add Account…")
        self.btn_add_account.setObjectName("SecondaryButton")
        self.btn_add_account.setFixedHeight(34)
        self.btn_add_account.setCursor(Qt.PointingHandCursor)
        self.btn_add_account.clicked.connect(self.add_account_clicked)
        acc_btn_row.addWidget(self.btn_add_account)

        self.btn_login_account = QPushButton("Log In")
        self.btn_login_account.setObjectName("SecondaryButton")
        self.btn_login_account.setFixedHeight(34)
        self.btn_login_account.setCursor(Qt.PointingHandCursor)
        self.btn_login_account.clicked.connect(self.login_account_clicked)
        acc_btn_row.addWidget(self.btn_login_account)

        self.btn_set_active = QPushButton("Set Active")
        self.btn_set_active.setObjectName("SecondaryButton")
        self.btn_set_active.setFixedHeight(34)
        self.btn_set_active.setCursor(Qt.PointingHandCursor)
        self.btn_set_active.clicked.connect(self.set_active_clicked)
        acc_btn_row.addWidget(self.btn_set_active)

        self.btn_remove_account = QPushButton("Remove")
        self.btn_remove_account.setObjectName("LogoutBtn")
        self.btn_remove_account.setFixedHeight(34)
        self.btn_remove_account.setCursor(Qt.PointingHandCursor)
        self.btn_remove_account.clicked.connect(self.remove_account_clicked)
        acc_btn_row.addWidget(self.btn_remove_account)

        self.btn_refresh_accounts = QPushButton("Refresh Status")
        self.btn_refresh_accounts.setObjectName("SecondaryButton")
        self.btn_refresh_accounts.setFixedHeight(34)
        self.btn_refresh_accounts.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_accounts.clicked.connect(self.refresh_accounts_status_clicked)
        acc_btn_row.addWidget(self.btn_refresh_accounts)

        self.lbl_account_status = QLabel("Add an account or set one as active.")
        self.lbl_account_status.setObjectName("MutedText")
        self.lbl_account_status.setWordWrap(True)
        acc_layout.addWidget(self.lbl_account_status)

        self.scroll_layout.addWidget(card_acc)

        # ── Section 2: Download Settings ──────────────────────────────────────
        card_dl = self._create_card()
        dl_layout = QVBoxLayout(card_dl)
        dl_layout.setContentsMargins(28, 24, 28, 24)
        dl_layout.setSpacing(16)

        lbl_dl_title = QLabel("Download Settings")
        lbl_dl_title.setObjectName("SectionHeader")
        dl_layout.addWidget(lbl_dl_title)

        lbl_path_desc = QLabel("Primary Folder Path")
        lbl_path_desc.setObjectName("ControlLabel")
        dl_layout.addWidget(lbl_path_desc)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.input_path = QLineEdit("downloads")
        self.input_path.setObjectName("VercelInput")
        self.input_path.setFixedHeight(38)

        self.btn_browse = QPushButton("Browse Folder")
        self.btn_browse.setObjectName("SecondaryButton")
        self.btn_browse.setFixedHeight(38)
        self.btn_browse.setCursor(Qt.PointingHandCursor)
        self.btn_browse.clicked.connect(self.browse_path)

        self.btn_open = QPushButton("Open Folder")
        self.btn_open.setObjectName("SecondaryButton")
        self.btn_open.setFixedHeight(38)
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.clicked.connect(self.open_folder)

        path_row.addWidget(self.input_path, stretch=1)
        path_row.addWidget(self.btn_browse)
        path_row.addWidget(self.btn_open)
        dl_layout.addLayout(path_row)

        lbl_template_tip = QLabel("<b>Dynamic variables supported:</b> {channel}, {username}, {channel_id}, {category}, {year}, {month}, {day}")
        lbl_template_tip.setObjectName("MutedText")
        dl_layout.addWidget(lbl_template_tip)

        dl_layout.addWidget(self._create_divider())

        self.chk_forum_sep = QCheckBox("Enable Forum Topic Auto-separation")
        self.chk_forum_sep.setToolTip("Automatically download all topics from a forum into separate subfolders named after the topics.")
        dl_layout.addWidget(self.chk_forum_sep)

        self.chk_rename_duplicates = QCheckBox("Rename Duplicate Filenames")
        self.chk_rename_duplicates.setToolTip("Automatically append suffix (2, 3, etc.) to duplicate filenames instead of overwriting existing files.")
        dl_layout.addWidget(self.chk_rename_duplicates)

        self.chk_use_msg_date = QCheckBox("Set File Date to Message Date")
        self.chk_use_msg_date.setToolTip("Set the file's modified and created times to match the date and time when the message was sent to the chat.")
        dl_layout.addWidget(self.chk_use_msg_date)

        self.chk_prefix_file_date = QCheckBox("Prefix Filenames with Publication Date (YYYY-MM-DD)")
        self.chk_prefix_file_date.setToolTip("Prepend the message publication date (e.g. 2026-01-01_filename.mp4) to all downloaded media for tidy chronological organization.")
        dl_layout.addWidget(self.chk_prefix_file_date)

        self.chk_redownload_deleted = QCheckBox("Re-download Files If Deleted/Moved from Folder")
        self.chk_redownload_deleted.setToolTip("When enabled, if a downloaded file is moved or deleted from the destination folder, it will be re-downloaded on the next run.")
        dl_layout.addWidget(self.chk_redownload_deleted)

        self.scroll_layout.addWidget(card_dl)

        # ── Section 3: Connection & Proxy ─────────────────────────────────────
        card_conn = self._create_card()
        conn_layout = QVBoxLayout(card_conn)
        conn_layout.setContentsMargins(28, 24, 28, 24)
        conn_layout.setSpacing(16)

        lbl_conn_title = QLabel("Network & Proxy")
        lbl_conn_title.setObjectName("SectionHeader")
        conn_layout.addWidget(lbl_conn_title)

        self.chk_enable_proxy = QCheckBox("Enable Proxy Server Connection")
        self.chk_enable_proxy.setCursor(Qt.PointingHandCursor)
        conn_layout.addWidget(self.chk_enable_proxy)

        proxy_form = QVBoxLayout()
        proxy_form.setSpacing(10)

        proxy_row1 = QHBoxLayout()
        proxy_row1.setSpacing(8)
        self.combo_proxy_type = SearchableComboBox()
        self.combo_proxy_type.addItems(["SOCKS5", "SOCKS4", "HTTP"])
        self.combo_proxy_type.setFixedWidth(110)
        self.combo_proxy_type.setFixedHeight(38)

        self.input_proxy_host = QLineEdit()
        self.input_proxy_host.setObjectName("VercelInput")
        self.input_proxy_host.setPlaceholderText("Hostname / IP Address")
        self.input_proxy_host.setFixedHeight(38)

        self.input_proxy_port = QLineEdit()
        self.input_proxy_port.setObjectName("VercelInput")
        self.input_proxy_port.setPlaceholderText("Port")
        self.input_proxy_port.setFixedWidth(90)
        self.input_proxy_port.setFixedHeight(38)

        proxy_row1.addWidget(self.combo_proxy_type)
        proxy_row1.addWidget(self.input_proxy_host, stretch=1)
        proxy_row1.addWidget(self.input_proxy_port)
        proxy_form.addLayout(proxy_row1)

        proxy_row2 = QHBoxLayout()
        proxy_row2.setSpacing(8)
        self.input_proxy_user = QLineEdit()
        self.input_proxy_user.setObjectName("VercelInput")
        self.input_proxy_user.setPlaceholderText("Username (Optional)")
        self.input_proxy_user.setFixedHeight(38)

        self.input_proxy_pass = QLineEdit()
        self.input_proxy_pass.setObjectName("VercelInput")
        self.input_proxy_pass.setPlaceholderText("Password (Optional)")
        self.input_proxy_pass.setEchoMode(QLineEdit.Password)
        self.input_proxy_pass.setFixedHeight(38)

        proxy_row2.addWidget(self.input_proxy_user)
        proxy_row2.addWidget(self.input_proxy_pass)
        proxy_form.addLayout(proxy_row2)
        conn_layout.addLayout(proxy_form)

        self.scroll_layout.addWidget(card_conn)

        # ── Section 4: Performance & Limits ───────────────────────────────────
        card_perf = self._create_card()
        perf_layout = QVBoxLayout(card_perf)
        perf_layout.setContentsMargins(28, 24, 28, 24)
        perf_layout.setSpacing(16)

        lbl_perf_title = QLabel("Performance & Limits")
        lbl_perf_title.setObjectName("SectionHeader")
        perf_layout.addWidget(lbl_perf_title)

        limit_grid = QGridLayout()
        limit_grid.setHorizontalSpacing(16)
        limit_grid.setVerticalSpacing(12)
        limit_grid.setColumnStretch(1, 1)

        limit_grid.addWidget(QLabel("Concurrent Connections:", objectName="ControlLabel"), 0, 0)
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 100)
        self.spin_limit.setFixedHeight(34)
        limit_grid.addWidget(self.spin_limit, 0, 1)

        limit_grid.addWidget(QLabel("Global Download Speed Limit (KB/s):", objectName="ControlLabel"), 1, 0)
        self.spin_speed = QSpinBox()
        self.spin_speed.setRange(0, 999999)
        self.spin_speed.setFixedHeight(34)
        limit_grid.addWidget(self.spin_speed, 1, 1)

        limit_grid.addWidget(QLabel("Initial Media Fetch Limit (per type):", objectName="ControlLabel"), 2, 0)
        self.spin_fetch_limit = QSpinBox()
        self.spin_fetch_limit.setRange(10, 50000)
        self.spin_fetch_limit.setFixedHeight(34)
        limit_grid.addWidget(self.spin_fetch_limit, 2, 1)

        perf_layout.addLayout(limit_grid)
        perf_layout.addWidget(QLabel("Set 0 for unlimited speed. Concurrency increases parallel chunk downloads.", objectName="MutedText"))
        perf_layout.addWidget(QLabel("Initial Fetch Limit controls how many recent items are scanned when searching for a channel.", objectName="MutedText"))

        perf_layout.addWidget(self._create_divider())

        # Save Button
        self.btn_save = QPushButton("Save Settings")
        self.btn_save.setObjectName("VercelButton")
        self.btn_save.setFixedHeight(40)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self.save_settings)
        perf_layout.addWidget(self.btn_save)

        self.scroll_layout.addWidget(card_perf)

        # ── Section 5: About ──────────────────────────────────────────────────
        card_about = self._create_card()
        about_layout = QVBoxLayout(card_about)
        about_layout.setContentsMargins(28, 24, 28, 24)
        about_layout.setSpacing(12)

        lbl_about_title = QLabel("About TG Private Grab")
        lbl_about_title.setObjectName("SectionHeader")
        about_layout.addWidget(lbl_about_title)

        about_row = QHBoxLayout()
        about_text_layout = QVBoxLayout()
        about_text_layout.setSpacing(4)

        lbl_app_name = QLabel("TG Private Grab &nbsp;•&nbsp; <b>v2.8.2</b>")
        lbl_app_name.setObjectName("ControlLabel")
        lbl_app_desc = QLabel("High-performance Telegram media downloader with byte-range resuming and SQLite persistence.")
        lbl_app_desc.setObjectName("MutedText")
        about_text_layout.addWidget(lbl_app_name)
        about_text_layout.addWidget(lbl_app_desc)

        self.btn_github = QPushButton("View Releases")
        self.btn_github.setObjectName("SecondaryButton")
        self.btn_github.setFixedHeight(36)
        self.btn_github.setCursor(Qt.PointingHandCursor)
        self.btn_github.clicked.connect(self.open_releases)

        about_row.addLayout(about_text_layout, stretch=1)
        about_row.addWidget(self.btn_github)
        about_layout.addLayout(about_row)

        self.scroll_layout.addWidget(card_about)

        # ── Section 6: Danger Zone ────────────────────────────────────────────
        card_danger = QFrame()
        card_danger.setObjectName("DangerCard")
        card_danger.setMaximumWidth(800)

        danger_layout = QVBoxLayout(card_danger)
        danger_layout.setContentsMargins(28, 24, 28, 24)
        danger_layout.setSpacing(14)

        lbl_danger_header = QLabel("Danger Zone")
        lbl_danger_header.setObjectName("SectionHeader")
        lbl_danger_header.setStyleSheet("color: #EF4444;")
        danger_layout.addWidget(lbl_danger_header)

        danger_row = QHBoxLayout()
        danger_text = QVBoxLayout()
        danger_text.setSpacing(2)

        lbl_log_title = QLabel("Log out of Telegram")
        lbl_log_title.setStyleSheet("font-weight: 600; color: #EF4444; font-size: 13px;")
        lbl_log_desc = QLabel("This will clear your local session, disconnect from Telegram, and return to the login screen.")
        lbl_log_desc.setObjectName("MutedText")
        danger_text.addWidget(lbl_log_title)
        danger_text.addWidget(lbl_log_desc)

        self.btn_logout = QPushButton("Log out")
        self.btn_logout.setObjectName("LogoutBtn")
        self.btn_logout.setFixedHeight(36)
        self.btn_logout.setMinimumWidth(110)
        self.btn_logout.setCursor(Qt.PointingHandCursor)
        self.btn_logout.clicked.connect(self.logout_clicked)

        danger_row.addLayout(danger_text, stretch=1)
        danger_row.addWidget(self.btn_logout)
        danger_layout.addLayout(danger_row)

        self.scroll_layout.addWidget(card_danger)

        # Assemble into scroll area
        self.scroll_area.setWidget(self.container)
        root_layout.addWidget(self.scroll_area)

        self.load_settings()

    def _create_card(self):
        card = QFrame()
        card.setObjectName("WhiteCard")
        card.setMaximumWidth(800)
        return card

    def _create_divider(self):
        d = QFrame()
        d.setObjectName("Divider")
        d.setFrameShape(QFrame.HLine)
        d.setFixedHeight(1)
        return d

    def _on_theme_toggled(self, is_checked: bool):
        self.themeToggled.emit(is_checked)

    def _style_accounts_list(self):
        """Apply theme-aware styling to the accounts list widget."""
        try:
            cfg = load_config()
            is_dark = bool(cfg.get("dark_mode", False))
        except Exception:
            is_dark = False
        from ui.theme import get_tokens
        t = get_tokens(is_dark)
        item_hover = t['muted']
        self.accounts_list.setStyleSheet(f"""
            QListWidget#accountsList {{
                background-color: {t['card']};
                border: 1px solid {t['border']};
                border-radius: 6px;
                color: {t['foreground']};
                font-size: 12px;
                padding: 4px;
            }}
            QListWidget#accountsList::item {{
                border-radius: 4px;
                padding: 8px 10px;
                color: {t['foreground']};
            }}
            QListWidget#accountsList::item:hover {{
                background-color: {item_hover};
            }}
            QListWidget#accountsList::item:selected {{
                background-color: {t['accent_soft']};
                color: {t['selected_text']};
            }}
        """)

    def load_settings(self):
        config = load_config()

        # Dark theme
        dark_pref = config.get("dark_mode", True)
        if dark_pref is None:
            dark_pref = True
        self.chk_dark_mode.blockSignals(True)
        self.chk_dark_mode.setChecked(bool(dark_pref))
        self.chk_dark_mode.blockSignals(False)

        # Downloads
        self.input_path.setText(config.get("download_path", "downloads"))
        self.chk_forum_sep.setChecked(config.get("forum_auto_separation", False))
        self.chk_rename_duplicates.setChecked(config.get("rename_duplicates", True))
        self.chk_use_msg_date.setChecked(config.get("use_message_date", True))
        self.chk_prefix_file_date.setChecked(config.get("prefix_file_date", True))
        self.chk_redownload_deleted.setChecked(config.get("redownload_deleted", False))

        # Proxy
        proxy = config.get("proxy", {})
        self.chk_enable_proxy.setChecked(proxy.get("enabled", False))
        self.combo_proxy_type.setCurrentText(proxy.get("type", "SOCKS5"))
        self.input_proxy_host.setText(proxy.get("host", ""))
        self.input_proxy_port.setText(str(proxy.get("port", "")))
        self.input_proxy_user.setText(proxy.get("user", ""))
        self.input_proxy_pass.setText(proxy.get("pass", ""))

        # Performance
        self.spin_limit.setValue(config.get("download_limit", 5))
        self.spin_speed.setValue(config.get("max_speed_kb", 0))
        self.spin_fetch_limit.setValue(config.get("initial_fetch_limit", 2000))

    def save_settings(self):
        config = {
            "download_path": self.input_path.text(),
            "download_limit": self.spin_limit.value(),
            "initial_fetch_limit": self.spin_fetch_limit.value(),
            "max_speed_kb": self.spin_speed.value(),
            "forum_auto_separation": self.chk_forum_sep.isChecked(),
            "rename_duplicates": self.chk_rename_duplicates.isChecked(),
            "use_message_date": self.chk_use_msg_date.isChecked(),
            "prefix_file_date": self.chk_prefix_file_date.isChecked(),
            "redownload_deleted": self.chk_redownload_deleted.isChecked(),
            "dark_mode": self.chk_dark_mode.isChecked(),
            "proxy": {
                "enabled": self.chk_enable_proxy.isChecked(),
                "type": self.combo_proxy_type.currentText(),
                "host": self.input_proxy_host.text(),
                "port": self.input_proxy_port.text(),
                "user": self.input_proxy_user.text(),
                "pass": self.input_proxy_pass.text()
            }
        }
        save_config(config)

        # Sync existing database tasks with updated limits
        try:
            import sqlite3
            from database import DB_PATH
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE tasks SET max_speed_kb=?, download_limit=?", (self.spin_speed.value(), self.spin_limit.value()))
            conn.commit()
            conn.close()
        except Exception:
            pass

        QMessageBox.information(self, "Settings Saved", "Configuration saved successfully.")

    def browse_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Directory")
        if folder:
            self.input_path.setText(folder)

    def open_folder(self):
        path = self.input_path.text()
        if os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))
        else:
            QMessageBox.warning(self, "Folder Not Found", f"The directory does not exist yet:\n{path}")

    def open_releases(self):
        QDesktopServices.openUrl(QUrl("https://github.com/"))

    def logout_clicked(self):
        self.logoutRequested.emit()

    # ── Multi-account management ─────────────────────────────────────────

    def set_worker(self, worker):
        self._worker = worker
        if worker and not self._worker_events_connected:
            worker.signals.account_event.connect(self._on_account_event)
            self._worker_events_connected = True
            self._schedule_account_check()

    def _schedule_account_check(self, attempts=0):
        if not self._worker:
            return
        if getattr(self._worker, "loop", None):
            self.refresh_accounts(check=True)
            return
        if attempts < 20:
            QTimer.singleShot(250, lambda: self._schedule_account_check(attempts + 1))

    def refresh_accounts(self, check=True):
        # Rebuild the accounts list from config and (optionally) verify logins.
        accounts = get_accounts()
        self._accounts_cache = accounts
        active = get_active_account_id()

        self.accounts_list.clear()
        for acc in accounts:
            acc_id = acc.get("id")
            name = acc.get("name") or acc_id
            phone = (acc.get("phone") or "").strip()
            if phone and phone.replace(" ", "").replace("-", "").isdigit() and not phone.startswith("+"):
                phone = "+" + phone
            username = (acc.get("username") or "").strip()
            user_id = acc.get("user_id") or 0
            status = self._account_status.get(acc_id)
            if acc_id == active:
                if status is True:
                    status_txt = "  - Active - Logged in"
                elif status is False:
                    status_txt = "  - Active - Not logged in"
                else:
                    status_txt = "  - Active"
            elif status is True:
                status_txt = "  - Logged in"
            elif status is False:
                status_txt = "  - Not logged in"
            else:
                status_txt = "  - Not checked"

            phone_txt = phone if phone else "(phone not on file)"
            ident = ""
            if username:
                ident = "  -  @" + username
            elif user_id:
                ident = "  -  id " + str(user_id)
            item = QListWidgetItem(name + "  -  " + phone_txt + ident + status_txt)
            item.setToolTip(
                "Name: " + str(name) + "\n"
                "Phone: " + (phone or "(not recorded yet - log in to capture it)") + "\n"
                "Username: " + ("@" + username if username else "-") + "\n"
                "User ID: " + str(user_id or "-") + "\n"
                "Session: " + str(acc.get("session") or "-") + "\n"
                "Status: " + status_txt.strip()
            )
            item.setData(Qt.UserRole, acc_id)
            self.accounts_list.addItem(item)

        if check and self._worker:
            self._worker.check_all_accounts()

    def refresh_accounts_status_clicked(self):
        if not self._worker:
            QMessageBox.information(self, "Accounts", "Telegram client is not ready yet.")
            return
        self.lbl_account_status.setText("Checking login status...")
        self._worker.check_all_accounts()

    def _selected_account_id(self):
        item = self.accounts_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _account_name(self, account_id):
        for acc in self._accounts_cache or []:
            if acc.get("id") == account_id:
                return acc.get("name") or account_id
        return str(account_id)

    def _on_account_event(self, event: str):
        parts = event.split(":", 2)
        kind = parts[0]
        acc_id = parts[1] if len(parts) > 1 else ""
        payload = parts[2] if len(parts) > 2 else ""

        if kind == "status":
            self._account_status[acc_id] = (payload == "1")
            self.refresh_accounts(check=False)
        elif kind == "code_sent":
            phone = payload or acc_id
            self._prompt_account_code(acc_id, phone)
        elif kind == "password_needed":
            pwd, ok = QInputDialog.getText(self, "Two-Step Verification",
                                           "Enter your 2FA password:", QLineEdit.Password)
            if ok and pwd and self._worker:
                self._worker.submit_account_password(acc_id, pwd)
        elif kind == "success":
            self._account_status[acc_id] = True
            self.refresh_accounts(check=False)
            self.lbl_account_status.setText(f"Logged in: {self._account_name(acc_id)}")
            QMessageBox.information(self, "Account", f"'{self._account_name(acc_id)}' logged in successfully.")
        elif kind == "switched":
            self._account_status[acc_id] = True
            self.refresh_accounts(check=False)
            self.lbl_account_status.setText(f"Switched active account to: {self._account_name(acc_id)}")
        elif kind == "error":
            self._account_status[acc_id] = False
            self.refresh_accounts(check=False)
            self.lbl_account_status.setText(f"Login failed: {payload}")
            QMessageBox.critical(self, "Account Error", f"Could not log in:\n{payload}")

    def _prompt_account_code(self, account_id, phone):
        code, ok = QInputDialog.getText(self, "Verification Code",
                                        f"Enter the code sent to {phone}.\n"
                                        "(Check your Telegram app for this number, or SMS if app delivery failed.)")
        if ok and code and self._worker:
            self._worker.submit_account_code(account_id, code.strip())

    def add_account_clicked(self):
        name, ok = QInputDialog.getText(self, "Add Account", "Account name (e.g. Work, Personal, Seller1):")
        if not ok or not name.strip():
            return
        name = name.strip()
        phone, ok2 = QInputDialog.getText(self, "Add Account",
                                          "Phone number with country code (e.g. +1234567890).\nLeave empty to skip login for now:")
        acc = add_account(name, phone=phone.strip() if ok2 else "")
        self.refresh_accounts(check=False)
        if ok2 and phone.strip() and self._worker:
            self.lbl_account_status.setText(f"Logging in '{name}'…")
            self._worker.start_account_login(acc["id"], phone.strip())
        else:
            self.lbl_account_status.setText(f"Account '{name}' added. Click 'Log In' when you're ready.")

    def login_account_clicked(self):
        acc_id = self._selected_account_id()
        if not acc_id:
            QMessageBox.information(self, "Accounts", "Select an account from the list first.")
            return
        if not self._worker:
            QMessageBox.warning(self, "Accounts", "Telegram client is not ready yet.")
            return
        phone, ok = QInputDialog.getText(self, "Log In", f"Phone number for '{self._account_name(acc_id)}' (e.g. +1234567890):")
        if ok and phone.strip():
            self.lbl_account_status.setText(f"Logging in '{self._account_name(acc_id)}'…")
            self._worker.start_account_login(acc_id, phone.strip())

    def set_active_clicked(self):
        acc_id = self._selected_account_id()
        if not acc_id:
            QMessageBox.information(self, "Accounts", "Select an account from the list first.")
            return
        if self._worker:
            self._worker.switch_account(acc_id)
        else:
            set_active_account_id(acc_id)
            self.refresh_accounts(check=False)

    def remove_account_clicked(self):
        acc_id = self._selected_account_id()
        if not acc_id:
            QMessageBox.information(self, "Accounts", "Select an account from the list first.")
            return
        if acc_id == "default":
            QMessageBox.warning(self, "Remove Account", "The Main Account cannot be removed.")
            return
        answer = QMessageBox.question(self, "Remove Account",
                                      f"Remove '{self._account_name(acc_id)}'?\nIts Telegram session will be deleted from this device.",
                                      QMessageBox.Yes | QMessageBox.No)
        if answer == QMessageBox.Yes:
            remove_account(acc_id)
            self._account_status.pop(acc_id, None)
            self.refresh_accounts(check=False)
            self.lbl_account_status.setText(f"Removed '{self._account_name(acc_id)}'")
