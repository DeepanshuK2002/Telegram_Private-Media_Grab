import re
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, 
    QLineEdit, QDialog, QListWidget, QListWidgetItem, 
    QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal, QPoint

COUNTRIES = [
    {"name": "India", "code": "+91", "iso": "IN"},
    {"name": "United States", "code": "+1", "iso": "US"},
    {"name": "United Kingdom", "code": "+44", "iso": "GB"},
    {"name": "Canada", "code": "+1", "iso": "CA"},
    {"name": "Australia", "code": "+61", "iso": "AU"},
    {"name": "Germany", "code": "+49", "iso": "DE"},
    {"name": "France", "code": "+33", "iso": "FR"},
    {"name": "Russia", "code": "+7", "iso": "RU"},
    {"name": "United Arab Emirates", "code": "+971", "iso": "AE"},
    {"name": "Saudi Arabia", "code": "+966", "iso": "SA"},
    {"name": "Singapore", "code": "+65", "iso": "SG"},
    {"name": "Malaysia", "code": "+60", "iso": "MY"},
    {"name": "Indonesia", "code": "+62", "iso": "ID"},
    {"name": "Philippines", "code": "+63", "iso": "PH"},
    {"name": "Pakistan", "code": "+92", "iso": "PK"},
    {"name": "Bangladesh", "code": "+880", "iso": "BD"},
    {"name": "Nepal", "code": "+977", "iso": "NP"},
    {"name": "Sri Lanka", "code": "+94", "iso": "LK"},
    {"name": "Italy", "code": "+39", "iso": "IT"},
    {"name": "Spain", "code": "+34", "iso": "ES"},
    {"name": "Netherlands", "code": "+31", "iso": "NL"},
    {"name": "Switzerland", "code": "+41", "iso": "CH"},
    {"name": "Sweden", "code": "+46", "iso": "SE"},
    {"name": "Norway", "code": "+47", "iso": "NO"},
    {"name": "Poland", "code": "+48", "iso": "PL"},
    {"name": "Ukraine", "code": "+380", "iso": "UA"},
    {"name": "Turkey", "code": "+90", "iso": "TR"},
    {"name": "Japan", "code": "+81", "iso": "JP"},
    {"name": "South Korea", "code": "+82", "iso": "KR"},
    {"name": "China", "code": "+86", "iso": "CN"},
    {"name": "Hong Kong", "code": "+852", "iso": "HK"},
    {"name": "Taiwan", "code": "+886", "iso": "TW"},
    {"name": "Vietnam", "code": "+84", "iso": "VN"},
    {"name": "Thailand", "code": "+66", "iso": "TH"},
    {"name": "New Zealand", "code": "+64", "iso": "NZ"},
    {"name": "Brazil", "code": "+55", "iso": "BR"},
    {"name": "Mexico", "code": "+52", "iso": "MX"},
    {"name": "Argentina", "code": "+54", "iso": "AR"},
    {"name": "Colombia", "code": "+57", "iso": "CO"},
    {"name": "Chile", "code": "+56", "iso": "CL"},
    {"name": "Egypt", "code": "+20", "iso": "EG"},
    {"name": "South Africa", "code": "+27", "iso": "ZA"},
    {"name": "Nigeria", "code": "+234", "iso": "NG"},
    {"name": "Kenya", "code": "+254", "iso": "KE"},
    {"name": "Iran", "code": "+98", "iso": "IR"},
    {"name": "Iraq", "code": "+964", "iso": "IQ"},
    {"name": "Israel", "code": "+972", "iso": "IL"},
    {"name": "Oman", "code": "+968", "iso": "OM"},
    {"name": "Qatar", "code": "+974", "iso": "QA"},
    {"name": "Kuwait", "code": "+965", "iso": "KW"},
    {"name": "Bahrain", "code": "+973", "iso": "BH"},
    {"name": "Portugal", "code": "+351", "iso": "PT"},
    {"name": "Greece", "code": "+30", "iso": "GR"},
    {"name": "Austria", "code": "+43", "iso": "AT"},
    {"name": "Belgium", "code": "+32", "iso": "BE"},
    {"name": "Ireland", "code": "+353", "iso": "IE"},
    {"name": "Denmark", "code": "+45", "iso": "DK"},
    {"name": "Finland", "code": "+358", "iso": "FI"},
    {"name": "Czech Republic", "code": "+420", "iso": "CZ"},
    {"name": "Hungary", "code": "+36", "iso": "HU"},
    {"name": "Romania", "code": "+40", "iso": "RO"},
]


class CountryPickerPopover(QDialog):
    countrySelected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CountryPickerPopover")
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(300)
        self.setFixedHeight(320)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Search box
        self.search_input = QLineEdit()
        self.search_input.setObjectName("CountrySearchInput")
        self.search_input.setPlaceholderText("Search country...")
        self.search_input.setFixedHeight(34)
        self.search_input.textChanged.connect(self.filter_countries)
        layout.addWidget(self.search_input)

        # Country list
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("CountryList")
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.list_widget)

        self.populate_list(COUNTRIES)

    def populate_list(self, countries):
        self.list_widget.clear()
        for c in countries:
            item_text = f"{c['iso']}  •  {c['name']}  ({c['code']})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, c)
            self.list_widget.addItem(item)

    def filter_countries(self, query):
        q = query.strip().lower()
        if not q:
            filtered = COUNTRIES
        else:
            filtered = [
                c for c in COUNTRIES 
                if q in c["name"].lower() or q in c["code"].lower() or q in c["iso"].lower()
            ]
        self.populate_list(filtered)

    def on_item_clicked(self, item):
        country_data = item.data(Qt.UserRole)
        if country_data:
            self.countrySelected.emit(country_data)
        self.accept()

    def show_at(self, target_widget):
        self.search_input.clear()
        self.populate_list(COUNTRIES)
        # Position right below the phone input container or target widget
        anchor = target_widget.parentWidget() if target_widget.parentWidget() else target_widget
        width = max(300, anchor.width())
        self.setFixedWidth(width)
        pos = anchor.mapToGlobal(QPoint(0, anchor.height() + 4))
        self.move(pos)
        self.show()
        self.search_input.setFocus()


class ShadcnPhoneInput(QWidget):
    returnPressed = Signal()
    countryChanged = Signal(dict)
    textChanged = Signal(str)

    def __init__(self, parent=None, default_country="IN"):
        super().__init__(parent)
        self.current_country = self._find_country(default_country) or COUNTRIES[0]
        self.setup_ui()

    def _find_country(self, identifier: str):
        target = identifier.strip().upper()
        for c in COUNTRIES:
            if c["iso"] == target or c["code"] == identifier:
                return c
        return None

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Country Selector Trigger Button (Flag + Code + Chevron)
        self.btn_country = QPushButton()
        self.btn_country.setObjectName("PhoneCountryButton")
        self.btn_country.setCursor(Qt.PointingHandCursor)
        self.btn_country.setFixedHeight(40)
        self._update_button_label()
        self.btn_country.clicked.connect(self._open_popover)
        layout.addWidget(self.btn_country)

        # 2. Phone Number Input Field
        self.line_edit = QLineEdit()
        self.line_edit.setObjectName("PhoneNumberInput")
        self.line_edit.setPlaceholderText("Enter a phone number")
        self.line_edit.setFixedHeight(40)
        self.line_edit.returnPressed.connect(self.returnPressed.emit)
        self.line_edit.textChanged.connect(self.textChanged.emit)
        layout.addWidget(self.line_edit, stretch=1)

        # Popover instance
        self.popover = CountryPickerPopover(self)
        self.popover.countrySelected.connect(self.set_country)

    def _update_button_label(self):
        iso = self.current_country.get("iso", "")
        code = self.current_country.get("code", "")
        self.btn_country.setText(f"{iso}  {code}  ▾")

    def _open_popover(self):
        self.popover.show_at(self.btn_country)

    def set_country(self, country_data: dict):
        self.current_country = country_data
        self._update_button_label()
        self.countryChanged.emit(country_data)
        self.line_edit.setFocus()

    def set_country_by_code(self, code_or_iso: str):
        found = self._find_country(code_or_iso)
        if found:
            self.set_country(found)

    def get_full_phone(self) -> str:
        raw = self.line_edit.text().strip().replace(" ", "").replace("-", "")
        if not raw:
            return ""
        if raw.startswith("+"):
            return raw
        code = self.current_country.get("code", "+91")
        clean_number = raw.lstrip("0")
        return f"{code}{clean_number}"

    def text(self) -> str:
        return self.get_full_phone()

    def set_phone(self, phone_str: str):
        clean = phone_str.strip()
        if clean.startswith("+"):
            # Detect country code from string
            for c in sorted(COUNTRIES, key=lambda x: len(x["code"]), reverse=True):
                if clean.startswith(c["code"]):
                    self.set_country(c)
                    local_num = clean[len(c["code"]):].lstrip("0")
                    self.line_edit.setText(local_num)
                    return
        self.line_edit.setText(clean)

    def clear(self):
        self.line_edit.clear()

    @property
    def country_code(self) -> str:
        return self.current_country.get("code", "+91")
