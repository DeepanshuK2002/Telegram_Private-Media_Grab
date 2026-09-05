from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QStackedWidget, QFrame, QSizePolicy, QComboBox
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QIcon, QPixmap, QDesktopServices, QFontMetrics, QShowEvent
import os
from ui.components.phone_input import ShadcnPhoneInput

COUNTRY_CODES = [
    ("+91 (India)", "+91"),
    ("+1 (USA / Canada)", "+1"),
    ("+44 (UK)", "+44"),
    ("+7 (Russia)", "+7"),
    ("+971 (UAE)", "+971"),
    ("+966 (Saudi Arabia)", "+966"),
    ("+65 (Singapore)", "+65"),
    ("+60 (Malaysia)", "+60"),
    ("+62 (Indonesia)", "+62"),
    ("+63 (Philippines)", "+63"),
    ("+92 (Pakistan)", "+92"),
    ("+880 (Bangladesh)", "+880"),
    ("+977 (Nepal)", "+977"),
    ("+94 (Sri Lanka)", "+94"),
    ("+49 (Germany)", "+49"),
    ("+33 (France)", "+33"),
    ("+39 (Italy)", "+39"),
    ("+34 (Spain)", "+34"),
    ("+31 (Netherlands)", "+31"),
    ("+41 (Switzerland)", "+41"),
    ("+46 (Sweden)", "+46"),
    ("+47 (Norway)", "+47"),
    ("+48 (Poland)", "+48"),
    ("+380 (Ukraine)", "+380"),
    ("+90 (Turkey)", "+90"),
    ("+81 (Japan)", "+81"),
    ("+82 (South Korea)", "+82"),
    ("+86 (China)", "+86"),
    ("+852 (Hong Kong)", "+852"),
    ("+886 (Taiwan)", "+886"),
    ("+84 (Vietnam)", "+84"),
    ("+66 (Thailand)", "+66"),
    ("+61 (Australia)", "+61"),
    ("+64 (New Zealand)", "+64"),
    ("+55 (Brazil)", "+55"),
    ("+52 (Mexico)", "+52"),
    ("+54 (Argentina)", "+54"),
    ("+57 (Colombia)", "+57"),
    ("+56 (Chile)", "+56"),
    ("+20 (Egypt)", "+20"),
    ("+27 (South Africa)", "+27"),
    ("+234 (Nigeria)", "+234"),
    ("+254 (Kenya)", "+254"),
    ("+98 (Iran)", "+98"),
    ("+964 (Iraq)", "+964"),
    ("+972 (Israel)", "+972"),
    ("+968 (Oman)", "+968"),
    ("+974 (Qatar)", "+974"),
    ("+965 (Kuwait)", "+965"),
    ("+973 (Bahrain)", "+973"),
    ("+351 (Portugal)", "+351"),
    ("+30 (Greece)", "+30"),
    ("+43 (Austria)", "+43"),
    ("+32 (Belgium)", "+32"),
    ("+353 (Ireland)", "+353"),
    ("+45 (Denmark)", "+45"),
    ("+358 (Finland)", "+358"),
    ("+420 (Czech Republic)", "+420"),
    ("+36 (Hungary)", "+36"),
    ("+40 (Romania)", "+40"),
]

class LoginView(QWidget):
    login_started = Signal(str, str, str)   # api_id, api_hash, phone
    code_submitted = Signal(str)            # code
    password_submitted = Signal(str)        # password

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_env_defaults()

    def setup_ui(self):
        self.setObjectName("LoginView")
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        # Outer flex min-h-screen items-center justify-center bg-black
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignCenter)

        # ── Form container: w-full max-w-[400px] p-8 space-y-6 ──────────────
        self.card = QFrame()
        self.card.setObjectName("VercelLoginForm")
        self.card.setFixedWidth(400)
        self.card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(20)

        # ── Brand Header: flex flex-col items-center space-y-4 ───────────────
        header_box = QVBoxLayout()
        header_box.setAlignment(Qt.AlignCenter)
        header_box.setSpacing(8)

        # Title: text-2xl font-semibold tracking-tight mt-2
        self.lbl_title = QLabel("Log in to TG Private Grab")
        self.lbl_title.setObjectName("VercelTitle")
        self.lbl_title.setAlignment(Qt.AlignCenter)

        # Subtitle
        self.lbl_header_subtitle = QLabel("Enter your Telegram API credentials to get started")
        self.lbl_header_subtitle.setObjectName("VercelSubtitle")
        self.lbl_header_subtitle.setAlignment(Qt.AlignCenter)
        self.lbl_header_subtitle.setWordWrap(True)
        self._fit_header_subtitle()

        header_box.addWidget(self.lbl_title)
        header_box.addWidget(self.lbl_header_subtitle)
        card_layout.addLayout(header_box)

        # ── Step Stack ──────────────────────────────────────────────────────
        self.stack = QStackedWidget()

        # ═════════════════════════════════════════════════════════════════════
        # Step 1 – Telegram API Credentials Form
        # ═════════════════════════════════════════════════════════════════════
        page1 = QWidget()
        l1 = QVBoxLayout(page1)
        l1.setContentsMargins(0, 0, 0, 0)
        l1.setSpacing(16)

        # Error label for Step 1
        self.lbl_error_p1 = QLabel("")
        self.lbl_error_p1.setObjectName("VercelError")
        self.lbl_error_p1.setAlignment(Qt.AlignCenter)
        self.lbl_error_p1.setWordWrap(True)
        self.lbl_error_p1.hide()
        l1.addWidget(self.lbl_error_p1)

        def _create_field(label_text, placeholder):
            box = QVBoxLayout()
            box.setSpacing(6)
            lbl = QLabel(label_text)
            lbl.setObjectName("VercelLabel")
            inp = QLineEdit()
            inp.setObjectName("VercelInput")
            inp.setPlaceholderText(placeholder)
            inp.setMinimumHeight(38)
            box.addWidget(lbl)
            box.addWidget(inp)
            return box, inp

        # API ID
        g1, self.inp_api_id = _create_field("API ID", "e.g. 12345678")
        l1.addLayout(g1)

        # API Hash
        g2, self.inp_api_hash = _create_field("API HASH", "32-character hex string")
        l1.addLayout(g2)

        # Phone Number using ShadcnPhoneInput (matches shadcn-phone-input.vercel.app)
        box_phone = QVBoxLayout()
        box_phone.setSpacing(6)
        lbl_phone = QLabel("PHONE NUMBER")
        lbl_phone.setObjectName("VercelLabel")

        self.phone_input = ShadcnPhoneInput(self, default_country="IN")
        self.inp_phone = self.phone_input.line_edit

        box_phone.addWidget(lbl_phone)
        box_phone.addWidget(self.phone_input)
        l1.addLayout(box_phone)

        # Connect return key to submit
        self.inp_api_id.returnPressed.connect(self.on_send_code)
        self.inp_api_hash.returnPressed.connect(self.on_send_code)
        self.phone_input.returnPressed.connect(self.on_send_code)

        # Submit button: rounded-md bg-white px-4 py-2.5 text-sm font-medium text-black
        self.btn_send_code = QPushButton("Continue with Credentials")
        self.btn_send_code.setObjectName("VercelButton")
        self.btn_send_code.setMinimumHeight(40)
        self.btn_send_code.setCursor(Qt.PointingHandCursor)
        self.btn_send_code.clicked.connect(self.on_send_code)
        l1.addWidget(self.btn_send_code)

        # Footer Link: text-center text-xs text-zinc-500
        footer_link = QLabel('Need API credentials? <a href="https://my.telegram.org">Get them on my.telegram.org ↗</a>')
        footer_link.setObjectName("VercelFooter")
        footer_link.setAlignment(Qt.AlignCenter)
        footer_link.setOpenExternalLinks(True)
        l1.addWidget(footer_link)

        # ═════════════════════════════════════════════════════════════════════
        # Step 2 – OTP Verification
        # ═════════════════════════════════════════════════════════════════════
        page2 = QWidget()
        l2 = QVBoxLayout(page2)
        l2.setContentsMargins(0, 0, 0, 0)
        l2.setSpacing(16)

        hint2 = QLabel("Enter the login code sent to your Telegram app or SMS.")
        hint2.setObjectName("VercelSubtitle")
        hint2.setAlignment(Qt.AlignCenter)
        hint2.setWordWrap(True)

        self.lbl_error_p2 = QLabel("")
        self.lbl_error_p2.setObjectName("VercelError")
        self.lbl_error_p2.setAlignment(Qt.AlignCenter)
        self.lbl_error_p2.setWordWrap(True)
        self.lbl_error_p2.hide()

        g_code, self.inp_code = _create_field("VERIFICATION CODE", "Enter 5-digit code")
        self.inp_code.setAlignment(Qt.AlignCenter)
        self.inp_code.returnPressed.connect(self.on_submit_code)

        self.btn_submit_code = QPushButton("Verify & Continue")
        self.btn_submit_code.setObjectName("VercelButton")
        self.btn_submit_code.setMinimumHeight(40)
        self.btn_submit_code.setCursor(Qt.PointingHandCursor)
        self.btn_submit_code.clicked.connect(self.on_submit_code)

        self.btn_back = QPushButton("← Back to Credentials")
        self.btn_back.setObjectName("VercelBackLink")
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.clicked.connect(self.reset_to_start)

        l2.addWidget(hint2)
        l2.addWidget(self.lbl_error_p2)
        l2.addLayout(g_code)
        l2.addWidget(self.btn_submit_code)
        l2.addWidget(self.btn_back)

        # ═════════════════════════════════════════════════════════════════════
        # Step 3 – 2FA Password
        # ═════════════════════════════════════════════════════════════════════
        page3 = QWidget()
        l3 = QVBoxLayout(page3)
        l3.setContentsMargins(0, 0, 0, 0)
        l3.setSpacing(16)

        hint3 = QLabel("Two-step verification (2FA) password required.")
        hint3.setObjectName("VercelSubtitle")
        hint3.setAlignment(Qt.AlignCenter)
        hint3.setWordWrap(True)

        self.lbl_error_p3 = QLabel("")
        self.lbl_error_p3.setObjectName("VercelError")
        self.lbl_error_p3.setAlignment(Qt.AlignCenter)
        self.lbl_error_p3.setWordWrap(True)
        self.lbl_error_p3.hide()

        g_pwd, self.inp_pwd = _create_field("2FA PASSWORD", "Your cloud password")
        self.inp_pwd.setEchoMode(QLineEdit.Password)
        self.inp_pwd.returnPressed.connect(self.on_submit_pwd)

        self.btn_submit_pwd = QPushButton("Submit Password")
        self.btn_submit_pwd.setObjectName("VercelButton")
        self.btn_submit_pwd.setMinimumHeight(40)
        self.btn_submit_pwd.setCursor(Qt.PointingHandCursor)
        self.btn_submit_pwd.clicked.connect(self.on_submit_pwd)

        self.btn_back_pwd = QPushButton("← Back to Credentials")
        self.btn_back_pwd.setObjectName("VercelBackLink")
        self.btn_back_pwd.setCursor(Qt.PointingHandCursor)
        self.btn_back_pwd.clicked.connect(self.reset_to_start)

        l3.addWidget(hint3)
        l3.addWidget(self.lbl_error_p3)
        l3.addLayout(g_pwd)
        l3.addWidget(self.btn_submit_pwd)
        l3.addWidget(self.btn_back_pwd)

        self.stack.addWidget(page1)
        self.stack.addWidget(page2)
        self.stack.addWidget(page3)

        card_layout.addWidget(self.stack)
        outer.addWidget(self.card, 0, Qt.AlignCenter)

    def _fit_header_subtitle(self):
        """QLabel heightForWidth can ignore wrapped text height when QSS
        padding is applied, which clips descenders. Force enough height."""
        lbl = self.lbl_header_subtitle
        width = lbl.width()
        if width <= 0:  # not laid out yet — use the card content width
            width = self.card.width() - 64 if self.card.width() > 0 else 336
        fm = lbl.fontMetrics()
        text_rect = fm.boundingRect(0, 0, width, 2000, Qt.TextWordWrap, lbl.text())
        # +8px for the QSS padding (4px top + 4px bottom) + a little breathing room
        needed = text_rect.height() + 14
        if lbl.minimumHeight() < needed:
            lbl.setMinimumHeight(needed)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        self._fit_header_subtitle()

    # ── helpers & event handlers ──────────────────────────────────────────

    def show_error(self, err_msg: str):
        idx = self.stack.currentIndex()
        if idx == 0:
            self.lbl_error_p1.setText(err_msg)
            self.lbl_error_p1.show()
            self.btn_send_code.setEnabled(True)
            self.btn_send_code.setText("Continue with Credentials")
        elif idx == 1:
            self.lbl_error_p2.setText(err_msg)
            self.lbl_error_p2.show()
            self.btn_submit_code.setEnabled(True)
            self.btn_submit_code.setText("Verify & Continue")
        elif idx == 2:
            self.lbl_error_p3.setText(err_msg)
            self.lbl_error_p3.show()
            self.btn_submit_pwd.setEnabled(True)
            self.btn_submit_pwd.setText("Submit Password")

    def clear_errors(self):
        self.lbl_error_p1.clear()
        self.lbl_error_p1.hide()
        self.lbl_error_p2.clear()
        self.lbl_error_p2.hide()
        self.lbl_error_p3.clear()
        self.lbl_error_p3.hide()

    def load_env_defaults(self):
        from dotenv import load_dotenv
        from resource_utils import get_project_root
        env_path = os.path.join(get_project_root(), '.env')
        load_dotenv(env_path)

        api_id   = os.getenv('API_ID')
        api_hash = os.getenv('API_HASH')
        phone    = os.getenv('PHONE')
        
        if api_id:
            api_id = str(api_id).strip("'").strip('"')
            self.inp_api_id.setText(api_id)
        if api_hash:
            api_hash = str(api_hash).strip("'").strip('"')
            self.inp_api_hash.setText(api_hash)
        if phone:
            phone = str(phone).strip("'").strip('"').strip()
            self.phone_input.set_phone(phone)

    def on_send_code(self):
        self.clear_errors()
        api_id   = self.inp_api_id.text().strip()
        api_hash = self.inp_api_hash.text().strip()
        raw_phone = self.phone_input.line_edit.text().strip()
        phone = self.phone_input.get_full_phone()

        if not api_id:
            self.show_error("Please enter your Telegram API ID.")
            self.inp_api_id.setFocus()
            return
        if not api_id.isdigit():
            self.show_error("API ID must be numeric digits (e.g. 12345678).")
            self.inp_api_id.setFocus()
            return
        if not api_hash:
            self.show_error("Please enter your Telegram API Hash.")
            self.inp_api_hash.setFocus()
            return
        if not raw_phone or not phone:
            self.show_error("Please enter your phone number.")
            self.phone_input.line_edit.setFocus()
            return

        from resource_utils import get_project_root
        env_path = os.path.join(get_project_root(), '.env')
        try:
            lines = []
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            env_data = {}
            for line in lines:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    env_data[k.strip()] = v.strip()
            env_data["API_ID"] = api_id
            env_data["API_HASH"] = api_hash
            env_data["PHONE"] = phone
            with open(env_path, "w", encoding="utf-8") as f:
                for k, v in env_data.items():
                    f.write(f"{k}={v}\n")
        except Exception as e:
            print(f"Error saving .env: {e}")

        self.btn_send_code.setEnabled(False)
        self.btn_send_code.setText("Connecting…")
        self.login_started.emit(api_id, api_hash, phone)

    def on_submit_code(self):
        self.clear_errors()
        code = self.inp_code.text().strip()
        if not code:
            self.show_error("Please enter the verification code.")
            self.inp_code.setFocus()
            return
        self.btn_submit_code.setEnabled(False)
        self.btn_submit_code.setText("Verifying…")
        self.code_submitted.emit(code)

    def on_submit_pwd(self):
        self.clear_errors()
        pwd = self.inp_pwd.text().strip()
        if not pwd:
            self.show_error("Please enter your 2FA password.")
            self.inp_pwd.setFocus()
            return
        self.btn_submit_pwd.setEnabled(False)
        self.btn_submit_pwd.setText("Verifying…")
        self.password_submitted.emit(pwd)

    def show_otp_step(self):
        self.clear_errors()
        self.inp_code.clear()
        self.btn_submit_code.setEnabled(True)
        self.btn_submit_code.setText("Verify & Continue")
        self.stack.setCurrentIndex(1)
        self.inp_code.setFocus()

    def show_pwd_step(self):
        self.clear_errors()
        self.inp_pwd.clear()
        self.btn_submit_pwd.setEnabled(True)
        self.btn_submit_pwd.setText("Submit Password")
        self.stack.setCurrentIndex(2)
        self.inp_pwd.setFocus()

    def reset_to_start(self, error_msg=None):
        self.clear_errors()
        self.btn_send_code.setEnabled(True)
        self.btn_send_code.setText("Continue with Credentials")
        self.stack.setCurrentIndex(0)
        if error_msg:
            self.show_error(error_msg)
