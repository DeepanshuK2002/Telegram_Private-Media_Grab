import os
import sys
import re
import json
import urllib.request
from PySide6.QtCore import QThread, Signal

REPO_URL = "https://api.github.com/repos/DeepanshuK2002/Telegram_Private-Media_Grab/releases/latest"
REPO_PAGE = "https://github.com/DeepanshuK2002/Telegram_Private-Media_Grab/releases/latest"


class UpdateChecker(QThread):
    """Checks GitHub for a newer release and (optionally) downloads it silently."""
    update_found = Signal(str, str, str)  # version, asset_url, asset_name
    no_update = Signal()

    def __init__(self, current_version, parent=None):
        super().__init__(parent)
        self.current_version = current_version

    def run(self):
        try:
            req = urllib.request.Request(
                REPO_URL,
                headers={'User-Agent': 'TG-Private-Grab-Updater'}
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())

            latest_tag = (data.get("tag_name") or "").lstrip("v")
            current_clean = self.current_version.lstrip("v")

            if not self.is_newer(latest_tag, current_clean):
                self.no_update.emit()
                return

            # Find the Windows .exe asset (for silent in-app update)
            asset_url = ""
            asset_name = ""
            for asset in (data.get("assets") or []):
                name = (asset.get("name") or "")
                if name.lower().endswith(".exe"):
                    asset_url = asset.get("browser_download_url", "")
                    asset_name = name
                    break

            if not asset_url:
                # No exe asset attached -> fall back to opening the releases page
                self.update_found.emit(latest_tag, REPO_PAGE, "")
                return

            self.update_found.emit(latest_tag, asset_url, asset_name)
        except Exception as e:
            print(f"Update check failed: {e}")

    def is_newer(self, latest, current):
        try:
            def parse_v(v):
                return [int(x) for x in re.sub(r'[^0-9.]', '', v).split('.')]
            return parse_v(latest) > parse_v(current)
        except Exception:
            return latest != current


class UpdateDownloader(QThread):
    """Downloads the new release .exe in the background with progress."""
    progress = Signal(int, int)      # bytes_done, bytes_total
    finished = Signal(str)           # path to downloaded exe
    failed = Signal(str)             # error message

    def __init__(self, url, dest_path, parent=None):
        super().__init__(parent)
        self.url = url
        self.dest = dest_path
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'TG-Private-Grab-Updater'})
            with urllib.request.urlopen(req, timeout=30) as response:
                total = int(response.headers.get("Content-Length") or 0)
                done = 0
                with open(self.dest, "wb") as f:
                    while True:
                        chunk = response.read(1024 * 256)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        self.progress.emit(done, total)
                        if self._cancel:
                            self.failed.emit("Download cancelled.")
                            return
            if os.path.exists(self.dest) and os.path.getsize(self.dest) > 0:
                self.finished.emit(self.dest)
            else:
                self.failed.emit("Downloaded file is empty.")
        except Exception as e:
            try:
                if os.path.exists(self.dest):
                    os.remove(self.dest)
            except Exception:
                pass
            self.failed.emit(str(e))