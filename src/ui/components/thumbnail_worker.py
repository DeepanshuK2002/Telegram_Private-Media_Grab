import io
import os
import asyncio
from PySide6.QtCore import QThread, Signal, QObject, Qt
from PySide6.QtGui import QPixmap, QImage
from resource_utils import get_project_root


class ThumbnailSignals(QObject):
    thumbnail_ready = Signal(int, object)  # msg_id, QPixmap
    all_done = Signal()


class ThumbnailWorker(QThread):
    def __init__(self, telethon_client, messages, parent=None, loop=None):
        super().__init__(parent)
        self.client = telethon_client
        self.messages = messages  # list of Telethon Message objects
        self.signals = ThumbnailSignals()
        self._cancel = False
        self._loop = loop
        
        # Ensure thumbnail cache directory exists
        self.cache_dir = os.path.join(get_project_root(), "cache", "thumbnails")
        os.makedirs(self.cache_dir, exist_ok=True)

    def run(self):
        for msg in self.messages:
            if self._cancel or not msg:
                break
            chat_id = getattr(msg, 'chat_id', None) or getattr(msg, 'peer_id', None) or "tg"
            cid_str = str(chat_id).replace("-100", "", 1)
            cache_file = os.path.join(self.cache_dir, f"{cid_str}_{msg.id}.jpg")
            if os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
                pix = QPixmap(cache_file)
                if not pix.isNull() and not self._cancel:
                    self.signals.thumbnail_ready.emit(msg.id, pix)

        self.signals.all_done.emit()

    def cancel(self):
        self._cancel = True
