from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QCheckBox, QComboBox, 
    QFrame, QFileDialog, QSpinBox, QMessageBox,
    QScrollArea, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
import json
import os
from resource_utils import get_project_root
from ui.components.clean_combobox import CleanComboBox

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
        self.setup_ui()

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
        self.combo_proxy_type = CleanComboBox()
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
