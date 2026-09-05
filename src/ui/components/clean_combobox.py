from PySide6.QtWidgets import QComboBox, QMenu
from PySide6.QtCore import Qt

class CleanComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._apply_popup_flags()

    def _apply_popup_flags(self):
        try:
            view = self.view()
            if view:
                win = view.window()
                if win:
                    win.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
                    win.setAttribute(Qt.WA_TranslucentBackground, True)
        except Exception:
            pass

    def showPopup(self):
        self._apply_popup_flags()
        super().showPopup()

def create_clean_menu(parent=None) -> QMenu:
    menu = QMenu(parent)
    menu.setWindowFlags(menu.windowFlags() | Qt.NoDropShadowWindowHint | Qt.FramelessWindowHint)
    menu.setAttribute(Qt.WA_TranslucentBackground, True)
    return menu
