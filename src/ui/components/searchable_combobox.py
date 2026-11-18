"""
SearchableComboBox — shadcn/ui-style combobox for the Vercel/Monochrome UI:
an input-like collapsed face that opens a frameless popup with a search field,
a filterable list and an empty state ("No items found.").

API mirrors the QComboBox bits used across the app:
    addItem(text, userData=None) / addItems([...])
    clear(), count()
    currentText(), currentIndex(), itemData(i)
    setCurrentText(text), setCurrentIndex(i)
    signals: currentIndexChanged(int), currentTextChanged(str)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QFrame, QApplication
)
from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import QPixmap, QIcon


def _lucide_svg(paths: str, color: str, size: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        'viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round">{paths}</svg>'
    )


CHEVRON_DOWN = '<path d="m6 9 6 6 6-6"/>'
SEARCH_ICON = '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>'


def _svg_icon(paths: str, color: str, size: int = 16) -> QIcon:
    pix = QPixmap()
    pix.loadFromData(_lucide_svg(paths, color, size).encode("utf-8"), "SVG")
    return QIcon(pix)


def _theme() -> dict:
    """Derived palette for the combobox, sourced from the single token module."""
    try:
        from ui.views.settings_view import load_config
        is_dark = bool(load_config().get("dark_mode", False))
    except Exception:
        is_dark = False
    from ui.theme import get_tokens
    t = get_tokens(is_dark)
    return {
        "is_dark": is_dark,
        "face_bg": t["card"], "face_bg_hover": t["muted"],
        "face_border": t["border"], "face_border_hover": t["border_strong"],
        "face_border_open": t["accent"],
        "text": t["foreground"], "muted": t["muted_foreground"],
        "popup_bg": t["popover"], "popup_border": t["border"],
        "item_hover": "rgba(255, 255, 255, 0.06)" if is_dark else t["muted"],
        "item_selected": t["accent_soft"],
        "item_selected_text": t["selected_text"],
        "input_bg": t["card"],
    }


class _ComboboxPopup(QWidget):
    """Frameless popup: search field + filterable list + empty state."""

    MAX_VISIBLE = 8
    ITEM_HEIGHT = 34

    def __init__(self, owner: "SearchableComboBox"):
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.owner = owner
        self._theme = _theme()
        self._build_ui()

    def _build_ui(self):
        t = self._theme
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QFrame()
        card.setObjectName("ComboboxPopupCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet(f"""
            QFrame#ComboboxPopupCard {{
                background-color: {t['popup_bg']};
                border: 1px solid {t['popup_border']};
                border-radius: 10px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(6)

        # Search field (with leading search icon)
        search_wrap = QWidget()
        search_wrap.setStyleSheet(f"""
            QWidget#ComboboxSearchWrap {{
                background-color: {t['input_bg']};
                border: 1px solid {t['popup_border']};
                border-radius: 6px;
            }}
        """)
        search_wrap.setObjectName("ComboboxSearchWrap")
        sw_layout = QHBoxLayout(search_wrap)
        sw_layout.setContentsMargins(8, 0, 8, 0)
        sw_layout.setSpacing(6)
        lbl_icon = QLabel()
        icon_pix = QPixmap()
        icon_pix.loadFromData(_lucide_svg(SEARCH_ICON, t["muted"], 14).encode("utf-8"), "SVG")
        lbl_icon.setPixmap(icon_pix)
        lbl_icon.setFixedWidth(16)
        sw_layout.addWidget(lbl_icon)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.setFrame(False)
        self.search.setFixedHeight(30)
        self.search.setStyleSheet(f"QLineEdit {{ background: transparent; border: none; font-size: 13px; color: {t['text']}; }}")
        self.search.textChanged.connect(self._filter)
        self.search.keyPressEvent = self._on_search_key
        sw_layout.addWidget(self.search, stretch=1)
        card_layout.addWidget(search_wrap)

        # Filterable list
        self.list = QListWidget()
        self.list.setObjectName("ComboboxList")
        self.list.setFrameShape(QFrame.NoFrame)
        self.list.setIconSize(QSize(16, 16))
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setStyleSheet(f"""
            QListWidget#ComboboxList {{
                background-color: transparent;
                outline: 0;
                font-size: 13px;
                color: {t['text']};
            }}
            QListWidget#ComboboxList::item {{
                padding: 4px 10px;
                border-radius: 6px;
                min-height: 26px;
            }}
            QListWidget#ComboboxList::item:hover {{
                background-color: {t['item_hover']};
            }}
            QListWidget#ComboboxList::item:selected {{
                background-color: {t['item_selected']};
                color: {t['item_selected_text']};
            }}
        """)
        self.list.itemClicked.connect(self._select_item)
        card_layout.addWidget(self.list)

        # Empty state
        self.empty = QLabel("No items found.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet(f"color: {t['muted']}; font-size: 13px; padding: 14px 0;")
        self.empty.hide()
        card_layout.addWidget(self.empty)

        root.addWidget(card)

    def _filter(self, query: str):
        query = query.strip().lower()
        visible = 0
        for i in range(self.owner.count()):
            text = self.owner._items[i]["text"]
            match = (query in text.lower()) if query else True
            item = self.list.item(i)
            if item is not None:
                item.setHidden(not match)
            if match:
                visible += 1
        self.empty.setVisible(visible == 0)
        self._resize_height()
        if visible:
            row = self.list.currentRow()
            if row < 0 or row >= self.list.count() or self.list.item(row).isHidden():
                self.list.setCurrentRow(self._first_visible())

    def _first_visible(self) -> int:
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is not None and not item.isHidden():
                return i
        return -1

    def _on_search_key(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.hide()
            return
        if key == Qt.Key_Down:
            row = self._first_visible()
            if row >= 0:
                self.list.setCurrentRow(row)
                self.list.setFocus()
                item = self.list.item(row)
                if item:
                    self.list.scrollToItem(item)
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            row = self.list.currentRow()
            if row < 0:
                row = self._first_visible()
            if row >= 0:
                self.list.setCurrentRow(row)
                self._select_item(self.list.item(row))
            return
        # Default: keep the base QLineEdit behavior (text insertion etc.)
        QLineEdit.keyPressEvent(self.search, event)

    def _resize_height(self):
        visible = sum(1 for i in range(self.list.count())
                     if self.list.item(i) is not None and not self.list.item(i).isHidden())
        visible = max(1, min(visible, self.MAX_VISIBLE))
        list_h = visible * self.ITEM_HEIGHT + 4
        self.list.setFixedHeight(list_h)
        self.adjustSize()

    def _select_item(self, item: QListWidgetItem):
        if item is None or item.isHidden():
            return
        index = self.list.row(item)
        # Map back through hidden filtering: list rows correspond to owner indices 1:1
        self.owner._select_index(index)
        self.hide()

    def show_at(self):
        t = self._theme = _theme()
        self.list.clear()
        blank_pix = QPixmap(16, 16)
        blank_pix.fill(Qt.transparent)
        blank = QIcon(blank_pix)
        check_icon = _svg_icon('<path d="M20 6 9 17l-5-5"/>', t["item_selected_text"], 16)
        for i in range(self.owner.count()):
            text = self.owner._items[i]["text"]
            item = QListWidgetItem(text)
            item.setIcon(check_icon if i == self.owner.currentIndex() else blank)
            item.setSizeHint(QSize(0, self.ITEM_HEIGHT))
            self.list.addItem(item)
        self.search.clear()
        self._filter("")
        # Ensure the owner's current selection is the highlighted row
        self.list.setCurrentRow(self.owner.currentIndex() if self.owner.currentIndex() >= 0 else self._first_visible())
        width = max(220, self.owner.width())
        self.setFixedWidth(width)
        self._resize_height()

        # Position directly below the face widget, clamped to the screen's
        # available geometry so the popup never overflows the edges
        bottom_left = self.owner.mapToGlobal(self.owner.rect().bottomLeft())
        top_left = self.owner.mapToGlobal(self.owner.rect().topLeft())
        pos = QPoint(bottom_left.x(), bottom_left.y() + 4)

        screen = QApplication.screenAt(top_left) or QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            # Clamp horizontal: if it would overflow on the right, align its right edge to the face's right edge
            if pos.x() + width > geo.right() - 8:
                right_align = self.owner.mapToGlobal(self.owner.rect().bottomRight()).x() - width
                pos.setX(max(geo.left() + 8, min(right_align, geo.right() - width - 8)))
            # Flip above the face if there isn't enough room below
            if pos.y() + self.height() > geo.bottom() - 8:
                pos.setY(top_left.y() - self.height() - 4)
        self.move(pos)
        self.show()
        self.activateWindow()
        self.search.setFocus()


class SearchableComboBox(QWidget):
    """shadcn-style collapsed face: current value + chevron; click toggles popup."""

    currentIndexChanged = Signal(int)
    currentTextChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._current_index = -1
        self._popup = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._face = QPushButton()
        self._face.setObjectName("SearchableComboFace")
        self._face.setCursor(Qt.PointingHandCursor)
        self._face.clicked.connect(self._toggle_popup)
        self._face.setMinimumHeight(36)
        self._face.setStyleSheet(self._face_style())
        layout.addWidget(self._face)
        self._apply_face_text()

    # ------------------------------------------------------------------ API

    def _theme(self):
        return _theme()

    def _face_style(self) -> str:
        t = self._theme()
        return f"""
            QPushButton#SearchableComboFace {{
                background-color: {t['face_bg']};
                color: {t['text']};
                border: 1px solid {t['face_border']};
                border-radius: 6px;
                padding: 0 10px;
                font-size: 13px;
                font-weight: 500;
                text-align: left;
            }}
            QPushButton#SearchableComboFace:hover {{
                background-color: {t['face_bg_hover']};
                border-color: {t['face_border_hover']};
            }}
            QPushButton#SearchableComboFace:pressed {{
                border-color: {t['face_border_open']};
            }}
        """

    def _apply_face_text(self):
        t = self._theme()
        prefix = self._items[self._current_index]["text"] if 0 <= self._current_index < len(self._items) else ""
        self._face.setText("  " + prefix)
        self._face.setIcon(_svg_icon(CHEVRON_DOWN, t["muted"], 14))
        self._face.setIconSize(QSize(14, 14))

    def refresh_theme(self):
        self._face.setStyleSheet(self._face_style())
        self._apply_face_text()
        if self._popup is not None:
            self._popup.deleteLater()
            self._popup = None

    def refresh_popup_theme(self):
        # Keep the face in sync with theme changes without recreating the popup
        self._face.setStyleSheet(self._face_style())
        self._apply_face_text()

    def addItem(self, text, userData=None):
        self._items.append({"text": str(text), "data": userData})
        if self._current_index == -1:
            self._current_index = 0
        self._apply_face_text()

    def addItems(self, texts):
        for text in texts:
            self.addItem(text)

    def clear(self):
        self._items = []
        self._current_index = -1
        self._apply_face_text()

    def count(self):
        return len(self._items)

    def currentIndex(self):
        return self._current_index

    def currentData(self):
        return self.itemData(self._current_index)

    def currentText(self):
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index]["text"]
        return ""

    def itemData(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]["data"]
        return None

    def findData(self, data) -> int:
        for i, item in enumerate(self._items):
            if item["data"] == data:
                return i
        return -1

    def setCurrentIndex(self, index: int):
        if index < 0:
            index = 0 if self._items else -1
        if index >= len(self._items):
            return
        if self._current_index == index:
            return
        self._current_index = index
        self._apply_face_text()
        self.currentIndexChanged.emit(index)
        self.currentTextChanged.emit(self.currentText())

    def setCurrentText(self, text: str):
        for i, item in enumerate(self._items):
            if item["text"] == text:
                self.setCurrentIndex(i)
                return
        # Append if missing (QComboBox editable-ish behavior)
        self.addItem(text)
        self.setCurrentIndex(self.count() - 1)

    def blockSignals(self, block: bool) -> bool:
        prev = super().blockSignals(block)
        self._face.blockSignals(block)
        return prev

    def setFixedWidth(self, w):
        super().setFixedWidth(w)
        self._face.setFixedWidth(w)

    def setFixedHeight(self, h):
        super().setFixedHeight(h)
        self._face.setFixedHeight(h)

    def setMinimumHeight(self, h):
        super().setMinimumHeight(h)
        self._face.setMinimumHeight(h)

    # ------------------------------------------------------------------ popup

    def _toggle_popup(self):
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
            return
        popup = _ComboboxPopup(self)
        self._popup = popup
        popup.show_at()

    def _select_index(self, index: int):
        if 0 <= index < len(self._items):
            self.setCurrentIndex(index)
