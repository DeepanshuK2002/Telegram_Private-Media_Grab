import asyncio
import os
import time
import threading
from PySide6.QtCore import QThread, Signal, QObject

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from core_downloader import (
    load_download_state,
    fetch_channel,
    get_messages_by_type,
    download_in_batches_headless,
    load_active_tasks,
    save_active_tasks,
    parse_channel_input
)
from utils.file_utils import get_media_filename
from resource_utils import get_project_root

class WorkerSignals(QObject):
    # Auth Signals
    auth_needed = Signal()          # Needs phone
    code_needed = Signal(str)       # Needs code for phone
    password_needed = Signal()      # Needs 2FA password
    auth_success = Signal()
    auth_error = Signal(str)
    
    # Download Signals
    media_list_fetched = Signal(str, object, object) # channel_input, channel_obj, messages_dict
    channel_fetched = Signal(object, int) # channel, total_messages
    download_progress = Signal(str, int, int) # task_id, current_items, total_items
    file_progress = Signal(str, int, int, int, str) # task_id, msg_id, current_bytes, total_bytes, speed_str
    file_completed = Signal(str, int) # task_id, msg_id
    download_completed = Signal(str, str) # task_id, folder_name
    error_occurred = Signal(str, str) # task_id, error_msg

    # Explore Signals
    dialogs_fetched = Signal(list) # list of channel/chat dicts
    channel_videos_fetched = Signal(str, list) # channel_id, list of video dicts
    explore_loading = Signal(bool, str) # is_loading, status_text
    explore_error = Signal(str) # error_msg
    avatar_ready = Signal(str, str) # channel_id, file_path
    thumbnail_ready = Signal(str, int, str) # channel_id, msg_id, file_path

    # TeleScrap Signals
    scrape_log = Signal(str)        # one status/log line per event
    scrape_finished = Signal()      # all entities processed

    # Auto Transfer Signals
    auto_transfer_log = Signal(str)  # one status/log line per event
    auto_transfer_status = Signal(str)  # current activity text ("" = idle)
    auto_transfer_download_progress = Signal(str, int, int)  # filename, current_bytes, total_bytes
    auto_transfer_upload_progress = Signal(str, str, int, int)  # filename, dest_title, current_bytes, total_bytes
    auto_transfer_finished = Signal()

    # Auto Message Signals
    auto_message_log = Signal(str)   # one status/log line per event
    auto_message_finished = Signal()

    # Backup / Clone Signals
    backup_log = Signal(str)         # one status/log line per event
    backup_finished = Signal()

    # Multi-account Signals
    account_event = Signal(str)  # code_sent:<id>:<phone> | success:<id> | password_needed:<id>
                                 # error:<id>:<msg> | status:<id>:<0|1> | switched:<id>


def build_proxy_dict():
    """Return a Telethon proxy dict from the saved proxy config, or None if disabled/invalid."""
    try:
        from ui.views.settings_view import load_config
        cfg = load_config()
        proxy = cfg.get("proxy") or {}
        if not proxy.get("enabled"):
            return None
        ptype = str(proxy.get("type") or "SOCKS5").lower()
        mapping = {"socks5": "socks5", "socks4": "socks4", "http": "http"}
        proxy_type = mapping.get(ptype, "socks5")
        host = str(proxy.get("host") or "").strip()
        port = str(proxy.get("port") or "").strip()
        if not host or not port:
            return None
        d = {"proxy_type": proxy_type, "addr": host, "port": int(port), "rdns": True}
        user = str(proxy.get("user") or "").strip()
        pwd = str(proxy.get("pass") or "")
        if user:
            d["username"] = user
            d["password"] = pwd
        return d
    except Exception:
        return None


class TelegramWorker(QThread):
    def __init__(self, session_name, api_id, api_hash, parent=None):
        super().__init__(parent)
        self.session_name = session_name
        self.api_id = api_id
        self.api_hash = api_hash
        self.signals = WorkerSignals()
        self.loop = None
        self.client = None
        self.clients = {}            # account_id -> TelegramClient (all accounts kept connected)
        self._pending_login = {}      # account_id -> phone (login flow in progress)
        self.task_cancel_events = {}
        self.running_tasks = {} # task_id -> future or task

    def get_client(self):
        return self.client

    def run(self):
        """Thread entry point. Starts the asyncio event loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            from accounts import get_active_account_id, get_account_credentials, account_session_path, get_accounts
            active = get_active_account_id()
            api_id, api_hash = get_account_credentials(active)
            session_full_path = account_session_path(active)
            if not api_id or not api_hash:
                # No usable credentials — fall back to legacy constructor args
                api_id, api_hash = self.api_id, self.api_hash
                session_full_path = os.path.join(get_project_root(), self.session_name)
            client = TelegramClient(session_full_path, api_id, api_hash, loop=self.loop,
                                    proxy=build_proxy_dict())
            self.client = client
            self.clients[active] = client
            self.loop.run_until_complete(self.check_auth())
            # Populate phone/identity + login status for every account now that
            # the event loop is running (set_worker's earlier call was a no-op
            # because self.loop was still None).
            try:
                self.loop.run_until_complete(self._check_all_accounts_coro())
            except Exception as e:
                print(f"check_all_accounts startup error: {e}")
        except Exception as e:
            print(f"Worker startup error: {e}")
            self.signals.auth_needed.emit()

        # Run forever processing asyncio tasks
        self.loop.run_forever()

    def set_credentials(self, api_id, api_hash):
        self.api_id = int(api_id)
        self.api_hash = api_hash

        async def _reinit():
            from accounts import get_active_account_id, account_session_path
            if self.client:
                await self.client.disconnect()
            session_full_path = account_session_path(get_active_account_id())
            self.client = TelegramClient(session_full_path, self.api_id, self.api_hash, loop=self.loop,
                                         proxy=build_proxy_dict())
            await self.check_auth()

        if self.loop:
            asyncio.run_coroutine_threadsafe(_reinit(), self.loop)

    def logout(self):
        async def _do_logout():
            if self.client:
                await self.client.log_out()
        if self.loop:
            asyncio.run_coroutine_threadsafe(_do_logout(), self.loop)

    def stop(self):
        if self.loop:
            for event in self.task_cancel_events.values():
                event.set()
            
            async def _cleanup():
                # Cleanly cancel any pending fetching or downloading tasks BEFORE disconnecting
                tasks = [t for t in asyncio.all_tasks(self.loop) if t is not asyncio.current_task()]
                for t in tasks:
                    t.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                if self.client:
                    await self.client.disconnect()
                    
            future = asyncio.run_coroutine_threadsafe(_cleanup(), self.loop)
            try:
                future.result(timeout=2.0)
            except Exception:
                pass
            
            self.loop.call_soon_threadsafe(self.loop.stop)

    # -------------------------------------------------------------------------
    # AUTHENTICATION
    # -------------------------------------------------------------------------
    async def check_auth(self):
        try:
            print("DEBUG: check_auth started, connecting client...")
            await self.client.connect()
            print("DEBUG: check_auth: connected. checking authorization...")
            if not await self.client.is_user_authorized():
                print("DEBUG: check_auth: NOT authorized, emitting auth_needed")
                self.signals.auth_needed.emit()
            else:
                print("DEBUG: check_auth: authorized, emitting auth_success")
                self.signals.auth_success.emit()
                # Capture the logged-in phone/identity so Settings can show it
                try:
                    from accounts import get_active_account_id
                    await self._store_account_identity(self.client, get_active_account_id())
                except Exception:
                    pass
        except Exception as e:
            print(f"DEBUG: check_auth error: {e}")
            self.signals.auth_error.emit(str(e))
            
    def start_login(self, api_id, api_hash, phone):
        self.api_id = int(api_id)
        self.api_hash = api_hash
        self.current_phone = phone
        
        async def _req():
            try:
                if self.client:
                    await self.client.disconnect()
                
                session_full_path = os.path.join(get_project_root(), self.session_name)
                self.client = TelegramClient(session_full_path, self.api_id, self.api_hash, loop=self.loop)
                await self.client.connect()
                
                if not await self.client.is_user_authorized():
                    await self.client.send_code_request(phone)
                    self.signals.code_needed.emit(phone)
                else:
                    await self.client.get_dialogs(limit=50)
                    self.signals.auth_success.emit()
            except Exception as e:
                self.signals.auth_error.emit(str(e))
                
        if self.loop:
            asyncio.run_coroutine_threadsafe(_req(), self.loop)

    def submit_code(self, code):
        async def _sub():
            try:
                from telethon.errors import SessionPasswordNeededError
                await self.client.sign_in(getattr(self, 'current_phone', ''), code)
                await self.client.get_dialogs(limit=50)
                self.signals.auth_success.emit()
            except SessionPasswordNeededError:
                self.signals.password_needed.emit()
            except Exception as e:
                self.signals.auth_error.emit(str(e))
        asyncio.run_coroutine_threadsafe(_sub(), self.loop)

    def submit_password(self, password):
        async def _pwd():
            try:
                await self.client.sign_in(password=password)
                await self.client.get_dialogs(limit=50)
                self.signals.auth_success.emit()
            except Exception as e:
                self.signals.auth_error.emit(str(e))
        asyncio.run_coroutine_threadsafe(_pwd(), self.loop)

    def logout_async(self):
        async def _logout():
            await self.client.log_out()
            self.signals.auth_needed.emit()
        asyncio.run_coroutine_threadsafe(_logout(), self.loop)

    # -------------------------------------------------------------------------
    # DOWNLOADS
    # -------------------------------------------------------------------------
    def fetch_media_list(self, channel_input, limit=None):
        """Called from Main UI to just fetch and group the messages for the modal."""
        asyncio.run_coroutine_threadsafe(self._fetch_media_list_coro(channel_input, limit), self.loop)

    async def _fetch_media_list_coro(self, channel_input, limit=None):
        try:
            clean_input, topic_id = parse_channel_input(channel_input)
            print(f"DEBUG: Fetching media list for input='{channel_input}' -> clean='{clean_input}', topic='{topic_id}', limit='{limit}'")
            channel = await fetch_channel(self.client, clean_input)
            
            # Fetch all types for the modal using centralized logic
            from core_downloader import fetch_categorized_media
            messages_dict = await fetch_categorized_media(self.client, channel, limit=limit, topic_id=topic_id)
            
            # Normalize keys to lowercase for UI compatibility if needed, 
            # though we can just update UI to use these keys.
            # Convert keys to lowercase to match previous contract
            messages_dict = {k.lower(): v for k, v in messages_dict.items()}
            
            self.signals.media_list_fetched.emit(channel_input, channel, messages_dict)
        except Exception as e:
            self.signals.error_occurred.emit(channel_input, f"Fetch Error: {str(e)}")

    def fetch_user_dialogs(self):
        """Fetches all channels and groups for the current Telegram account."""
        if not self.loop or not self.client:
            return
        asyncio.run_coroutine_threadsafe(self._fetch_user_dialogs_coro(), self.loop)

    async def _fetch_user_dialogs_coro(self):
        try:
            self.signals.explore_loading.emit(True, "Loading channels...")
            if not self.client.is_connected():
                await self.client.connect()
            if not await self.client.is_user_authorized():
                self.signals.explore_error.emit("Telegram session not authorized.")
                self.signals.explore_loading.emit(False, "")
                return

            dialogs = await self.client.get_dialogs(limit=150)
            result = []
            for d in dialogs:
                is_ch = getattr(d, 'is_channel', False)
                is_grp = getattr(d, 'is_group', False)
                is_user = getattr(d, 'is_user', False)
                entity = d.entity
                uname = getattr(entity, 'username', '') or ''
                title = d.name or getattr(entity, 'title', '') or getattr(entity, 'first_name', '') or "Untitled"
                
                result.append({
                    "id": str(d.id),
                    "raw_id": d.id,
                    "title": title,
                    "username": f"@{uname}" if uname else "",
                    "is_channel": is_ch,
                    "is_group": is_grp,
                    "is_user": is_user,
                    "unread_count": getattr(d, 'unread_count', 0),
                    "date": d.date.strftime("%b %d") if getattr(d, 'date', None) else "",
                })
            
            from accounts import get_active_account_id
            active_acc = get_active_account_id()
            from database import cache_channels_list
            try:
                cache_channels_list(result, account_id=active_acc)
            except Exception as ce:
                print(f"DEBUG: cache_channels_list error: {ce}")

            self.signals.dialogs_fetched.emit(result)
            self.signals.explore_loading.emit(False, "")

            # Start background avatar downloads
            asyncio.create_task(self._fetch_avatars_coro(dialogs))
        except Exception as e:
            print(f"DEBUG: fetch_user_dialogs error: {e}")
            self.signals.explore_error.emit(str(e))
            self.signals.explore_loading.emit(False, "")

    async def _fetch_avatars_coro(self, dialogs):
        from resource_utils import get_project_root
        avatar_dir = os.path.join(get_project_root(), "cache", "avatars")
        os.makedirs(avatar_dir, exist_ok=True)
        sem = asyncio.Semaphore(4)

        async def fetch_one(d):
            cid = str(d.id).replace("-100", "", 1) if str(d.id).startswith("-100") else str(d.id)
            avatar_path = os.path.join(avatar_dir, f"{cid}.jpg")
            if os.path.exists(avatar_path) and os.path.getsize(avatar_path) > 0:
                # Already on disk, UI already loaded it directly
                return

            entity = getattr(d, 'entity', None)
            if not entity:
                return

            if not getattr(entity, 'photo', None) and not getattr(entity, 'chat_photo', None):
                return

            async with sem:
                try:
                    path = await self.client.download_profile_photo(
                        entity, 
                        file=avatar_path, 
                        download_big=False
                    )
                    if path and os.path.exists(path) and os.path.getsize(path) > 0:
                        self.signals.avatar_ready.emit(str(d.id), path)
                except Exception:
                    pass

        tasks = [fetch_one(d) for d in dialogs[:60] if d]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def fetch_channel_avatar(self, channel_id):
        """Requests avatar download for a specific channel ID."""
        if not self.loop or not self.client:
            return
        asyncio.run_coroutine_threadsafe(self._fetch_single_avatar_coro(channel_id), self.loop)

    async def _fetch_single_avatar_coro(self, channel_id):
        from resource_utils import get_project_root
        avatar_dir = os.path.join(get_project_root(), "cache", "avatars")
        os.makedirs(avatar_dir, exist_ok=True)
        clean_cid = str(channel_id).replace("-100", "", 1) if str(channel_id).startswith("-100") else str(channel_id)
        avatar_path = os.path.join(avatar_dir, f"{clean_cid}.jpg")
        if os.path.exists(avatar_path) and os.path.getsize(avatar_path) > 0:
            self.signals.avatar_ready.emit(str(channel_id), avatar_path)
            return
        try:
            clean_id, _ = parse_channel_input(channel_id)
            channel = await fetch_channel(self.client, clean_id)
            path = await self.client.download_profile_photo(channel, file=avatar_path, download_big=False)
            if path and os.path.exists(path) and os.path.getsize(path) > 0:
                self.signals.avatar_ready.emit(str(channel_id), path)
        except Exception:
            pass

    def fetch_channel_videos(self, channel_id, limit=300):
        """Fetches video messages for a specific channel/chat (backward-compat wrapper)."""
        self.fetch_channel_media(channel_id, media_type="videos", limit=limit)

    def fetch_channel_media(self, channel_id, media_type="videos", limit=300):
        """Fetches media messages for a specific channel/chat by type.

        media_type: "all", "videos", "images", "documents", "audio", "text"
        """
        if not self.loop or not self.client:
            return
        asyncio.run_coroutine_threadsafe(self._fetch_channel_media_coro(channel_id, media_type, limit), self.loop)

    async def _fetch_channel_media_coro(self, channel_id, media_type="videos", limit=300):
        try:
            type_label = {
                "all": "media", "videos": "videos", "images": "images",
                "documents": "documents", "audio": "audio", "text": "text"
            }.get(media_type, "videos")
            self.signals.explore_loading.emit(True, f"Fetching {type_label}...")
            clean_id, topic_id = parse_channel_input(channel_id)
            channel = await fetch_channel(self.client, clean_id)

            # Ensure channel avatar is fetched and cached
            try:
                from resource_utils import get_project_root
                avatar_dir = os.path.join(get_project_root(), "cache", "avatars")
                os.makedirs(avatar_dir, exist_ok=True)
                clean_cid = str(channel_id).replace("-100", "", 1) if str(channel_id).startswith("-100") else str(channel_id)
                avatar_path = os.path.join(avatar_dir, f"{clean_cid}.jpg")
                if not os.path.exists(avatar_path) or os.path.getsize(avatar_path) == 0:
                    path = await self.client.download_profile_photo(channel, file=avatar_path, download_big=False)
                    if path and os.path.exists(path) and os.path.getsize(path) > 0:
                        self.signals.avatar_ready.emit(str(channel_id), path)
                else:
                    self.signals.avatar_ready.emit(str(channel_id), avatar_path)
            except Exception:
                pass

            from core_downloader import get_messages_by_type

            # Map media_type to media_choice used by get_messages_by_type
            media_choice_map = {
                "all": 6,
                "videos": 2,
                "images": 1,
                "documents": 3,
                "audio": 5,
                "text": None,
            }
            media_choice = media_choice_map.get(media_type, 2)

            kwargs = {}
            if topic_id is not None:
                kwargs['reply_to'] = topic_id

            if media_type == "text":
                messages = await self.client.get_messages(channel, limit=limit, **kwargs)
                messages = [m for m in messages if getattr(m, 'media', None) is None and (m.message or "").strip()]
            else:
                messages = await get_messages_by_type(self.client, channel, media_choice, limit=limit, topic_id=topic_id)

            sorted_msgs = sorted(messages, key=lambda m: m.id, reverse=True)

            ch_title = getattr(channel, 'title', getattr(channel, 'first_name', str(channel_id)))
            media_list = []

            for m in sorted_msgs:
                fname = ""
                if getattr(m, 'file', None) and m.file.name:
                    fname = m.file.name
                elif getattr(m, 'file', None) and m.file.ext:
                    ext = m.file.ext or ""
                    fname = f"{media_type}_{m.id}{ext}" if media_type != "text" else f"text_{m.id}.txt"
                else:
                    fname = f"{media_type}_{m.id}.dat" if media_type != "text" else f"text_{m.id}.txt"

                fsize = 0
                if getattr(m, 'file', None) and m.file.size:
                    fsize = m.file.size
                elif getattr(m, 'document', None) and m.document.size:
                    fsize = m.document.size

                duration_sec = 0
                width = 0
                height = 0
                if getattr(m, 'document', None) and hasattr(m.document, 'attributes'):
                    for attr in m.document.attributes:
                        if hasattr(attr, 'duration'):
                            duration_sec = attr.duration
                        if hasattr(attr, 'w') and hasattr(attr, 'h'):
                            width = attr.w
                            height = attr.h

                if duration_sec:
                    mins, secs = divmod(int(duration_sec), 60)
                    hours, mins = divmod(mins, 60)
                    if hours > 0:
                        dur_str = f"{hours}:{mins:02d}:{secs:02d}"
                    else:
                        dur_str = f"{mins}:{secs:02d}"
                else:
                    dur_str = ""

                date_val = getattr(m, 'date', None)
                date_str = date_val.strftime("%b %d, %Y") if date_val else ""
                caption = (m.message or "").strip()

                mime_type = ""
                if getattr(m, 'document', None):
                    mime_type = getattr(m.document, 'mime_type', '') or ''
                elif getattr(m, 'photo', None):
                    mime_type = "image/photo"

                media_list.append({
                    "id": m.id,
                    "channel_id": str(channel_id),
                    "channel_title": ch_title,
                    "filename": fname,
                    "title": caption if caption else fname,
                    "caption": caption,
                    "size_bytes": fsize,
                    "duration_sec": duration_sec,
                    "duration_str": dur_str,
                    "resolution": f"{width}x{height}" if width and height else "",
                    "date_str": date_str,
                    "msg_obj": m,
                    "media_type": media_type,
                    "mime_type": mime_type,
                })

            self.signals.channel_videos_fetched.emit(str(channel_id), media_list)
            self.signals.explore_loading.emit(False, "")

            real_msgs = [item.get("msg_obj") for item in media_list if item.get("msg_obj")]
            if real_msgs:
                asyncio.create_task(self._fetch_channel_thumbnails_coro(clean_id, real_msgs))
        except Exception as e:
            print(f"DEBUG: fetch_channel_media error: {e}")
            self.signals.explore_error.emit(f"Error fetching {media_type}: {str(e)}")
            self.signals.explore_loading.emit(False, "")

    def fetch_channel_thumbnails(self, channel_id, messages):
        """Fetches high quality thumbnails for the given channel videos in the background."""
        if self.loop and self.client:
            asyncio.run_coroutine_threadsafe(self._fetch_channel_thumbnails_coro(channel_id, messages), self.loop)

    async def _fetch_channel_thumbnails_coro(self, channel_id, messages):
        if not self.client or not messages:
            return
        try:
            from resource_utils import get_project_root
            from telethon.tl import types
            from telethon import utils
            thumb_dir = os.path.join(get_project_root(), "cache", "thumbnails")
            os.makedirs(thumb_dir, exist_ok=True)
            clean_cid = str(channel_id).replace("-100", "", 1) if str(channel_id).startswith("-100") else str(channel_id)

            sem = asyncio.Semaphore(4)

            async def download_one(msg):
                if not msg or not getattr(msg, 'id', None):
                    return
                cache_file = os.path.join(thumb_dir, f"{clean_cid}_{msg.id}.jpg")

                # If already cached and has real thumbnail size (> 2048 bytes), emit immediately
                if os.path.exists(cache_file) and os.path.getsize(cache_file) > 2048:
                    self.signals.thumbnail_ready.emit(str(channel_id), msg.id, cache_file)
                    return

                async with sem:
                    try:
                        downloaded = False
                        
                        # 1. Best PhotoSize from document.thumbs (skip VideoSize which is an mp4/video)
                        if getattr(msg, 'document', None):
                            thumbs = getattr(msg.document, 'thumbs', None) or []
                            photo_thumbs = [
                                t for t in thumbs 
                                if isinstance(t, (types.PhotoSize, types.PhotoSizeProgressive))
                            ]
                            if photo_thumbs:
                                photo_thumbs.sort(key=lambda t: getattr(t, 'size', 0) or (getattr(t, 'w', 0) * getattr(t, 'h', 0)))
                                best_thumb = photo_thumbs[-1]
                                res = await self.client.download_media(msg, file=cache_file, thumb=best_thumb)
                                if res and os.path.exists(cache_file) and os.path.getsize(cache_file) > 1000:
                                    downloaded = True

                        # 2. If msg is a photo
                        if not downloaded and getattr(msg, 'photo', None):
                            try:
                                res = await self.client.download_media(msg.photo, file=cache_file, thumb=-1)
                                if res and os.path.exists(cache_file) and os.path.getsize(cache_file) > 1000:
                                    downloaded = True
                            except Exception:
                                pass

                        # 3. Try standard download_media with thumb=-1
                        if not downloaded and getattr(msg, 'media', None):
                            try:
                                res = await self.client.download_media(msg, file=cache_file, thumb=-1)
                                if res and os.path.exists(cache_file) and os.path.getsize(cache_file) > 1000:
                                    downloaded = True
                            except Exception:
                                pass

                        # 4. Fallback to stripped thumb if no high-res thumb is available on Telegram
                        if not downloaded and getattr(msg, 'document', None):
                            thumbs = getattr(msg.document, 'thumbs', None) or []
                            for th in thumbs:
                                if isinstance(th, types.PhotoStrippedSize) and th.bytes:
                                    jpg_bytes = utils.stripped_photo_to_jpg(th.bytes)
                                    with open(cache_file, "wb") as f:
                                        f.write(jpg_bytes)
                                    downloaded = True
                                    break

                        if downloaded and os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
                            self.signals.thumbnail_ready.emit(str(channel_id), msg.id, cache_file)
                    except Exception as err:
                        print(f"DEBUG: Error downloading thumbnail for msg {msg.id}: {err}")

            tasks = [download_one(m) for m in messages if m]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"DEBUG: _fetch_channel_thumbnails_coro error: {e}")

    def start_download(self, channel_input, media_id, download_path, download_limit, max_speed_kb, is_paused=False, selected_message_ids=None, task_id=None):
        """Called from Main UI Thread. Schedules download in asyncio loop."""
        tasks = load_active_tasks()
        found = False
        found_task = None
        
        clean_input, topic_id = parse_channel_input(channel_input)
        print(f"DEBUG: Starting download for input='{channel_input}' -> clean='{clean_input}', topic='{topic_id}', media='{media_id}'")
        ch_clean = str(clean_input or "").replace("-100", "", 1)
        for t in tasks:
            if not isinstance(t, dict): continue
            # Match by explicit ID or by the same rule we use to generate task_id
            tk_chan = str(t.get("channel_input", "")).replace("-100", "", 1)
            tk_media = t.get("media_id")
            tk_topic = t.get("topic_id")
            
            # Reconstruct ID for comparison
            generated_id = f"{tk_chan}_{tk_topic}_{tk_media}" if tk_topic else f"{tk_chan}_{tk_media}"
            
            if task_id == generated_id or (task_id and t.get("task_id") == task_id):
                found_task = t
                break
            
            if not task_id and tk_chan == ch_clean and tk_media == media_id and tk_topic == topic_id:
                found_task = t
                break
        
        if found_task:
            t = found_task
            t["paused"] = is_paused
            t["download_path"] = download_path
            t["download_limit"] = download_limit
            t["max_speed_kb"] = max_speed_kb
            # Only overwrite selected_message_ids if it's explicitly provided
            if selected_message_ids is not None:
                if task_id:
                    # Explicit re-select: user chose a fresh set for this task
                    t["selected_message_ids"] = selected_message_ids
                else:
                    # Fresh add: merge the new videos into the existing task so
                    # previously queued (possibly unfinished) items are kept.
                    existing = t.get("selected_message_ids") or []
                    merged = list(dict.fromkeys(list(existing) + list(selected_message_ids)))
                    t["selected_message_ids"] = merged
                    selected_message_ids = merged
                t["total_items"] = len(t["selected_message_ids"])
                t["topic_id"] = topic_id # Ensure topic_id is updated
            else:
                selected_message_ids = t.get("selected_message_ids")
        if not bool(found_task):
            tasks.append({
                "channel_input": clean_input,
                "media_id": media_id,
                "topic_id": topic_id,
                "paused": is_paused,
                "download_path": download_path,
                "download_limit": download_limit,
                "max_speed_kb": max_speed_kb,
                "selected_message_ids": selected_message_ids,
                "title": f"Channel: {clean_input}", # Placeholder
                "total_items": len(selected_message_ids) if selected_message_ids else 0
            })
        save_active_tasks(tasks)

        # 🛡️ Prevent duplicate/competing loops for the same task
        # We start with the input-based ID as a temporary key
        actual_task_id = task_id or (f"{ch_clean}_{topic_id}_{media_id}" if topic_id else f"{ch_clean}_{media_id}")
        if actual_task_id in self.running_tasks:
            # We must be careful not to cancel the same task we JUST scheduled if this is called very rapidly,
            # but usually start_download is user-triggered.
            old_task = self.running_tasks[actual_task_id]
            if isinstance(old_task, asyncio.Task) and not old_task.done():
                old_task.cancel()
            elif hasattr(old_task, 'cancel'): # It might be a Future
                old_task.cancel()
                
        self.running_tasks[actual_task_id] = asyncio.run_coroutine_threadsafe(
            self._download_coro(channel_input, media_id, download_path, download_limit, max_speed_kb, is_paused, selected_message_ids, actual_task_id), 
            self.loop
        )

    def pause_download(self, task_id):
        if self.loop and task_id in self.task_cancel_events:
            event = self.task_cancel_events[task_id]
            self.loop.call_soon_threadsafe(event.set)
            
        try:
            parts = task_id.split('_')
            if len(parts) == 3:
                ch_id, topic_id_str, media_id_str = parts
                topic_id = int(topic_id_str)
            else:
                ch_id, media_id_str = parts
                topic_id = None
                
            media_id = int(media_id_str)
            ch_clean = ch_id.replace("-100", "", 1)
            tasks = load_active_tasks()
            for t in tasks:
                tk_chan = str(t.get("channel_input")).replace("-100", "", 1)
                tk_media = t.get("media_id")
                tk_topic = t.get("topic_id")
                
                if tk_chan == ch_clean and tk_media == media_id and tk_topic == topic_id:
                    t["paused"] = True
                    break
            save_active_tasks(tasks)
        except Exception:
            pass

    def resume_download(self, channel_input, media_id, download_path, download_limit, max_speed_kb):
        # Explicitly pass is_paused=False to resume
        self.start_download(channel_input, media_id, download_path, download_limit, max_speed_kb, is_paused=False, selected_message_ids=None)
        
    def cancel_download(self, task_id):
        self.pause_download(task_id)
        if task_id in self.task_cancel_events:
            del self.task_cancel_events[task_id]
            
        try:
            parts = task_id.split('_')
            if len(parts) == 3:
                ch_id, topic_id_str, media_id_str = parts
                topic_id = int(topic_id_str)
            else:
                ch_id, media_id_str = parts
                topic_id = None
                
            media_id = int(media_id_str)
            ch_clean = ch_id.replace("-100", "", 1)
            tasks = load_active_tasks()
            new_tasks = []
            for t in tasks:
                tk_chan = str(t.get("channel_input")).replace("-100", "", 1)
                tk_media = t.get("media_id")
                tk_topic = t.get("topic_id")
                
                if tk_chan == ch_clean and tk_media == media_id and tk_topic == topic_id:
                    continue
                new_tasks.append(t)
            save_active_tasks(new_tasks)
        except Exception:
            pass

    async def _download_coro(self, channel_input, media_id, download_path, download_limit, max_speed_kb, is_paused, selected_message_ids, original_task_id=None):
        try:
            clean_input, topic_id = parse_channel_input(channel_input)
            print(f"DEBUG: Download Coro for input='{channel_input}' -> clean='{clean_input}', topic='{topic_id}'")
            channel = await fetch_channel(self.client, clean_input)
            # Use the canonical numeric ID for task identification once resolved.
            # IN TELETHON: PeerChannel, PeerChat, and PeerUser have raw IDs. 
            # For channels, we must include the -100 prefix for stable global IDs.
            from telethon.utils import get_peer_id
            resolved_chan_id = str(get_peer_id(channel))
            task_id = f"{resolved_chan_id}_{topic_id}_{media_id}" if topic_id else f"{resolved_chan_id}_{media_id}"
            
            # 🛡️ ID HIJACK: If we were started with a username/title, switch the tracker to use the numeric ID
            if original_task_id and original_task_id != task_id:
                if original_task_id in self.running_tasks:
                    # Don't delete, just ensure we update the cancel event if it exists
                    if original_task_id in self.task_cancel_events:
                        self.task_cancel_events[task_id] = self.task_cancel_events.pop(original_task_id)
                
                # Check if another task with the REAL ID is already running
                if task_id in self.running_tasks and self.running_tasks[task_id] != asyncio.current_task():
                    old_t = self.running_tasks[task_id]
                    if not old_t.done():
                        old_t.cancel()
            
            self.running_tasks[task_id] = asyncio.current_task()
            
            # 0. Load the downloaded state (Isolated by channel ID)
            resolved_peer_id = None
            try:
                resolved_peer_id = get_peer_id(channel)
            except: pass
            downloaded_state = load_download_state(resolved_peer_id)

            # Safely get a display name for the entity (Channel, Chat, or User)
            title = getattr(channel, 'title', None)
            if not title:
                first = getattr(channel, 'first_name', '') or ''
                last = getattr(channel, 'last_name', '') or ''
                title = f"{first} {last}".strip()
            if not title:
                title = getattr(channel, 'username', None)
            if not title:
                title = f"Topic ID: {topic_id}" if topic_id else f"Channel ID: {getattr(channel, 'id', 'Unknown')}"
            
            # If it's a topic, append that to the title
            if topic_id:
                title = f"{title} (Topic: {topic_id})"
            
            # 1. Update active_tasks.json to use the numeric ID for future persistence
            try:
                tasks = load_active_tasks()
                updated_tasks = []
                found_and_updated = False
                
                ch_resolved_clean = resolved_chan_id.replace("-100", "", 1) if resolved_chan_id.startswith("-100") else resolved_chan_id
                for tk in tasks:
                    match = False
                    tk_chan_raw = str(tk.get("channel_input"))
                    tk_chan_clean = tk_chan_raw.replace("-100", "", 1) if tk_chan_raw.startswith("-100") else tk_chan_raw
                    # If this is the task we just resolved (either by input string or numeric ID)
                    if tk.get("media_id") == media_id and tk.get("topic_id") == topic_id:
                        # Match either by exact string OR by clean ID equivalence
                        if tk_chan_raw == str(channel_input) or tk_chan_clean == ch_resolved_clean:
                            match = True
                    
                    if match and not found_and_updated:
                        tk["channel_input"] = resolved_chan_id
                        tk["title"] = title # PERSIST TITLE
                        updated_tasks.append(tk)
                        found_and_updated = True
                    else:
                        updated_tasks.append(tk)
                
                # If for some reason it wasn't in the list, add it now (integrity check)
                if not found_and_updated:
                    updated_tasks.append({
                        "channel_input": resolved_chan_id,
                        "media_id": media_id,
                        "topic_id": topic_id,
                        "paused": is_paused,
                        "download_path": download_path,
                        "download_limit": download_limit,
                        "max_speed_kb": max_speed_kb,
                        "selected_message_ids": selected_message_ids
                    })
                save_active_tasks(updated_tasks)
            except Exception as e:
                print(f"Persistence update error: {e}")
                
            # 2. Emit placeholder so the card appears (using the stable numeric task_id)
            self.signals.channel_fetched.emit({
                "task_id": task_id,
                "title": f"Loading... ({title})",
                "total_items": 0,
                "completed": 0,
                "folder_name": download_path,
                "channel_input": resolved_chan_id,
                "original_input": channel_input, # CRITICAL: Tell UI where we came from
                "media_id": media_id,
                "is_paused": is_paused,
                "download_path": download_path,
                "download_limit": download_limit,
                "max_speed_kb": max_speed_kb,
                "files_metadata": []
            }, 0)

            # 3. Fetch real messages (this takes time)
            if selected_message_ids is not None:
                # Fast path: directly fetch selected messages
                raw_messages = await self.client.get_messages(channel, ids=selected_message_ids)
                # Client.get_messages with ids can return None for deleted/inaccessible messages
                messages = [m for m in raw_messages if m is not None]
            else:
                # Unbounded bulk fetch for entire categories
                messages = await get_messages_by_type(self.client, channel, media_id, limit=None, topic_id=topic_id)
            
            all_messages_count = len(messages)
            
            base_folder_map = {1: "images", 2: "videos", 3: "pdfs", 4: "zips", 5: "audio", 6: "all_media"}
            category_name = base_folder_map.get(media_id, "all_media")
            if topic_id:
                category_name = os.path.join(category_name, f"topic_{topic_id}")
            
            # 📂 Dynamic Path Templating
            # Supported: {channel}, {category}, {year}, {month}, {day}, {username}, {channel_id}
            from datetime import datetime
            now_dt = datetime.now()
            
            template = download_path
            # If the user just gave a plain path, we append the channel/category as default
            if "{" not in template:
                template = os.path.join(template, "{channel}", "{category}")
            
            safe_title = "".join([c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title])
            username_str = getattr(channel, 'username', '') or ''
            safe_username = "".join([c if c.isalnum() or c in ('-', '_') else '_' for c in username_str])
            if not safe_username:
                safe_username = safe_title
            
            safe_channel_id = "".join([c if c.isalnum() or c in ('-', '_') else '_' for c in resolved_chan_id])
            
            from ui.views.settings_view import load_config
            cfg = load_config()
            forum_auto_separation = cfg.get("forum_auto_separation", False)

            msg_folder_resolver = None
            
            # If it's a forum and auto-separation is enabled and we are not in a specific topic
            if forum_auto_separation and getattr(channel, 'forum', False) and topic_id is None:
                topic_map = {}
                try:
                    from telethon.tl.functions.channels import GetForumTopicsRequest
                    forums = await self.client(GetForumTopicsRequest(
                        channel=channel,
                        offset_date=None,
                        offset_id=0,
                        offset_topic=0,
                        limit=500
                    ))
                    if forums and getattr(forums, 'topics', None):
                        for t_obj in forums.topics:
                            topic_map[t_obj.id] = t_obj.title
                except Exception as fe:
                    print(f"Error fetching forum topics: {fe}")

                def resolver(message):
                    # Find topic ID
                    reply_to = getattr(message, 'reply_to', None)
                    msg_topic_id = None
                    if reply_to:
                        if getattr(reply_to, 'forum_topic', False) or getattr(reply_to, 'reply_to_top_id', None) is not None:
                            msg_topic_id = getattr(reply_to, 'reply_to_top_id', None) or getattr(reply_to, 'reply_to_msg_id', None)
                    
                    # Determine category subfolder name
                    base_folder_map = {1: "images", 2: "videos", 3: "pdfs", 4: "zips", 5: "audio", 6: "all_media"}
                    category_name = base_folder_map.get(media_id, "all_media")
                    
                    if msg_topic_id is not None:
                        topic_title = topic_map.get(msg_topic_id, None)
                        if topic_title:
                            safe_topic_title = "".join([c if c.isalnum() or c in (' ', '-', '_') else '_' for c in topic_title])
                            topic_subfolder = safe_topic_title
                        else:
                            topic_subfolder = f"topic_{msg_topic_id}"
                            category_name = os.path.join(category_name, topic_subfolder)
                    
                    msg_folder = template.format(
                        channel=safe_title,
                        category=category_name,
                        year=now_dt.strftime("%Y"),
                        month=now_dt.strftime("%m"),
                        day=now_dt.strftime("%d"),
                        username=safe_username,
                        channel_id=safe_channel_id
                    )
                    
                    if not os.path.isabs(msg_folder):
                        msg_folder = os.path.abspath(msg_folder)
                    os.makedirs(msg_folder, exist_ok=True)
                    return msg_folder

                msg_folder_resolver = resolver
            
            folder_name = template.format(
                channel=safe_title,
                category=category_name,
                year=now_dt.strftime("%Y"),
                month=now_dt.strftime("%m"),
                day=now_dt.strftime("%d"),
                username=safe_username,
                channel_id=safe_channel_id
            )
            
            os.makedirs(folder_name, exist_ok=True)
            
            # Ensure folder_name is absolute or correctly rooted
            if not os.path.isabs(folder_name):
                folder_name = os.path.abspath(folder_name)

            # 🛡️ Verify physical disk presence for downloaded files (support re-download if deleted)
            redownload_deleted = cfg.get("redownload_deleted", False)
            if redownload_deleted:
                from database import get_media_downloaded_path, unmark_media_completed
                prefix_file_date = cfg.get("prefix_file_date", True)
                actual_downloaded_state = set()
                c_id = str(resolved_chan_id).replace("-100", "", 1)
                for msg in messages:
                    fname = get_media_filename(msg, prefix_date=prefix_file_date)
                    target_f = msg_folder_resolver(msg) if msg_folder_resolver else folder_name
                    fpath = os.path.join(target_f, fname) if fname else None
                    if fpath and not os.path.exists(fpath):
                        db_fn = get_media_downloaded_path(c_id, msg.id)
                        if db_fn:
                            cand = os.path.join(target_f, db_fn) if not os.path.isabs(db_fn) else db_fn
                            if os.path.exists(cand):
                                fpath = cand
                    
                    # Check if file really exists on disk with non-zero bytes
                    if msg.id in downloaded_state and fpath and os.path.exists(fpath) and os.path.getsize(fpath) > 0:
                        actual_downloaded_state.add(msg.id)
                    elif msg.id in downloaded_state:
                        # File was deleted from disk! Unmark in DB
                        try:
                            unmark_media_completed(c_id, msg.id)
                        except Exception:
                            pass

                downloaded_state = actual_downloaded_state
            
            messages_to_download = [m for m in messages if m.id not in downloaded_state]
            total_items = all_messages_count
            completed_initial = len(downloaded_state)

            # 4. Emit the REAL metadata to update the placeholder card
            self.signals.channel_fetched.emit({
                "task_id": task_id,
                "title": title,
                "total_items": total_items,
                "completed": completed_initial,
                "folder_name": folder_name,
                "channel_input": resolved_chan_id,
                "original_input": channel_input, # Maintain origin trace!
                "media_id": media_id,
                "is_paused": is_paused,
                "download_path": download_path,
                "download_limit": download_limit,
                "max_speed_kb": max_speed_kb,
                "files_metadata": [] # Will populate in Card's refresh_from_metadata
            }, total_items)
            
            # 5. Update persistence with resolved metadata
            try:
                tasks = load_active_tasks()
                for tk in tasks:
                    tk_chan_clean = str(tk.get("channel_input")).replace("-100", "", 1)
                    if tk_chan_clean == resolved_chan_id.replace("-100", "", 1) and tk.get("media_id") == media_id and tk.get("topic_id") == topic_id:
                        tk["title"] = title
                        tk["total_items"] = total_items
                        tk["folder_name"] = folder_name
                        break
                save_active_tasks(tasks)
            except Exception: pass
            
            # Build actual files_metadata for current messages
            files_metadata = []
            prefix_file_date = cfg.get("prefix_file_date", True)
            for msg in messages:
                fname = get_media_filename(msg, prefix_date=prefix_file_date)
                fsize = 0
                try:
                    if getattr(msg, 'document', None):
                        fsize = getattr(msg.document, 'size', 0)
                    elif getattr(msg, 'photo', None):
                        if hasattr(msg.photo, 'sizes') and msg.photo.sizes:
                            for s in reversed(msg.photo.sizes):
                                if hasattr(s, 'size'):
                                    fsize = s.size
                                    break
                    elif getattr(msg, 'file', None) and getattr(msg.file, 'size', None):
                        fsize = msg.file.size
                    elif getattr(msg, 'size', None):
                        fsize = msg.size
                except Exception: pass

                files_metadata.append({
                    "id": msg.id,
                    "name": fname,
                    "size": fsize,
                    "completed": msg.id in downloaded_state
                })

            # Update the same card again with full file list
            self.signals.channel_fetched.emit({
                "task_id": task_id,
                "title": title,
                "total_items": total_items,
                "completed": completed_initial,
                "folder_name": folder_name,
                "channel_input": resolved_chan_id,
                "media_id": media_id,
                "is_paused": is_paused,
                "download_path": download_path,
                "download_limit": download_limit,
                "max_speed_kb": max_speed_kb,
                "topic_id": topic_id,
                "files_metadata": files_metadata
            }, total_items)
            
            if task_id in self.task_cancel_events:
                global_cancel_event = self.task_cancel_events[task_id]
            else:
                global_cancel_event = asyncio.Event()
                self.task_cancel_events[task_id] = global_cancel_event
            
            global_cancel_event.clear()
            
            if is_paused:
                global_cancel_event.set()
                return

            # Mark as running
            self.running_tasks[task_id] = asyncio.current_task()

            if not messages_to_download:
                self.signals.download_completed.emit(task_id, folder_name)
                if task_id in self.running_tasks: del self.running_tasks[task_id]
                return

            completed_count = [completed_initial]

            def on_file_complete(msg_id, paused=False, filepath=None, error=False):
                if not paused and not error:
                    self.signals.file_completed.emit(task_id, msg_id)
                    completed_count[0] += 1
                    self.signals.download_progress.emit(task_id, completed_count[0], total_items)
                    if completed_count[0] >= total_items:
                        # Remove from active tasks using the stable numeric ID
                        try:
                            tkList = load_active_tasks()
                            tkList = [tk for tk in tkList if not (str(tk.get("channel_input")) == resolved_chan_id and tk.get("media_id") == media_id and tk.get("topic_id") == topic_id)]
                            save_active_tasks(tkList)
                        except Exception as e:
                            print(f"Error removing task: {e}")
                        
                        self.signals.download_completed.emit(task_id, folder_name)

            def on_file_progress(msg_id, current, total, speed_str="0 KB/s"):
                self.signals.file_progress.emit(task_id, msg_id, current, total, speed_str)

            await download_in_batches_headless(
                client=self.client,
                channel=channel,
                messages=messages_to_download,
                folder_name=folder_name,
                batch_size=download_limit,
                downloaded_state=downloaded_state,
                progress_cb=on_file_progress,
                complete_cb=on_file_complete,
                task_cancel_event=global_cancel_event,
                max_speed_kb=max_speed_kb if max_speed_kb > 0 else None,
                msg_folder_resolver=msg_folder_resolver
            )

            if task_id in self.running_tasks:
                del self.running_tasks[task_id]

        except Exception as e:
            self.signals.error_occurred.emit(channel_input, str(e))

    # -------------------------------------------------------------------------
    # TeleScrap — member scraper (integrates ephell/Telescrape logic)
    # -------------------------------------------------------------------------
    def scrape_members(self, channel_ids, options):
        """Scrape member lists from the given channels/groups and export CSVs."""
        if not self.loop or not self.client:
            self.signals.scrape_log.emit("Telegram client not ready.")
            self.signals.scrape_finished.emit()
            return
        asyncio.run_coroutine_threadsafe(self._scrape_members_coro(channel_ids, options), self.loop)

    async def _scrape_members_coro(self, channel_ids, options):
        from telescrape import scrape_members as _scrape_members, extract_users_data, write_csv, scrape_output_dir
        out_dir = scrape_output_dir()
        os.makedirs(out_dir, exist_ok=True)
        total = len(channel_ids)
        self.signals.scrape_log.emit(f"Starting scrape of {total} group(s)/channel(s)...")
        for idx, ch_id in enumerate(channel_ids, 1):
            title = str(ch_id)
            try:
                clean_id, topic_id = parse_channel_input(str(ch_id))
                channel = await fetch_channel(self.client, clean_id)
                title = getattr(channel, 'title', clean_id) or str(ch_id)
                self.signals.scrape_log.emit(f"[{idx}/{total}] Scraping members of {title}...")
                users = await _scrape_members(self.client, channel, options)
                if users is None:
                    self.signals.scrape_log.emit(f"✗ {title}: admin privileges required to list members.")
                    continue
                data = extract_users_data(users)
                csv_path = write_csv(data, title, out_dir)
                self.signals.scrape_log.emit(f"✓ {title}: {len(users)} members → {os.path.basename(csv_path)}")
            except Exception as e:
                self.signals.scrape_log.emit(f"✗ {title}: {e}")
        self.signals.scrape_log.emit(f"Done. CSVs saved to: {out_dir}")
        self.signals.scrape_finished.emit()

    # -------------------------------------------------------------------------
    # Auto Message — re-send saved messages (text + emoji + optional image)
    # to selected groups on a fixed interval
    # -------------------------------------------------------------------------
    def send_auto_message(self):
        """Trigger one Auto Message cycle (from the interval timer or the UI)."""
        if not self.loop or not self.client:
            self.signals.auto_message_log.emit("Telegram client not ready.")
            self.signals.auto_message_finished.emit()
            return
        asyncio.run_coroutine_threadsafe(self._auto_message_coro(), self.loop)

    async def _auto_message_coro(self):
        import os as _os
        import random as _random
        from auto_message import get_auto_message, save_auto_message, now_str

        state = get_auto_message()
        if not state["enabled"]:
            return
        dests = state["destination_ids"]
        msgs = state["messages"]
        if not dests or not msgs:
            self.signals.auto_message_log.emit("Auto Message: no destinations or messages configured; skipping.")
            self.signals.auto_message_finished.emit()
            return

        # Pick which message goes out: round-robin or random
        idx = int(state.get("next_index") or 0)
        if state.get("rotation") == "random":
            idx = _random.randrange(len(msgs))
        else:
            idx = idx % len(msgs)
        msg = msgs[idx]
        text = (msg.get("text") or "").strip()
        img = msg.get("image_path") or ""
        have_img = bool(img) and _os.path.exists(img)
        if not text and not have_img:
            self.signals.auto_message_log.emit(f"Auto Message: message #{idx + 1} is empty; skipping.")
            self.signals.auto_message_finished.emit()
            return

        # Resolve destination entities
        dest_entities = []
        for d in dests:
            try:
                clean_id, _ = parse_channel_input(str(d))
                dest_entities.append(await fetch_channel(self.client, clean_id))
            except Exception as de:
                self.signals.auto_message_log.emit(f"Auto Message: cannot resolve {d}: {de}")
        if not dest_entities:
            self.signals.auto_message_log.emit("Auto Message: no reachable destination groups; skipping.")
            self.signals.auto_message_finished.emit()
            return

        sent = 0
        for dent in dest_entities:
            try:
                if have_img:
                    await self.client.send_file(dent, img, caption=text or None)
                else:
                    await self.client.send_message(dent, text)
                sent += 1
                self.signals.auto_message_log.emit(f"✓ Sent message #{idx + 1} to {getattr(dent, 'title', 'dest')}")
            except Exception as e:
                self.signals.auto_message_log.emit(f"✗ send to {getattr(dent, 'title', 'dest')}: {e}")

        # Advance rotation & stats
        if state.get("rotation") == "random":
            new_index = idx
        else:
            new_index = (idx + 1) % len(msgs)
        save_auto_message(
            last_run=now_str(),
            send_count=int(state.get("send_count") or 0) + 1,
            next_index=new_index,
        )
        self.signals.auto_message_log.emit(f"Auto Message: cycle done — sent to {sent}/{len(dest_entities)} group(s).")
        self.signals.auto_message_finished.emit()

    # -------------------------------------------------------------------------
    # Auto Reply Bot — auto-reply to incoming private messages
    # -------------------------------------------------------------------------
    def check_auto_reply(self):
        """Called every minute; sends the configured auto-reply to new private chats."""
        if not self.loop or not self.client:
            return
        asyncio.run_coroutine_threadsafe(self._auto_reply_coro(), self.loop)

    async def _auto_reply_coro(self):
        from datetime import datetime
        from auto_message import get_auto_message, save_auto_message
        state = get_auto_message()
        if not state.get("auto_reply_enabled"):
            return
        text = (state.get("auto_reply_text") or "").strip()
        if not text:
            return
        cooldown_hours = int(state.get("auto_reply_cooldown_hours") or 24)
        cooldown_sec = max(3600, cooldown_hours * 3600)
        last = dict(state.get("auto_reply_last_replied") or {})
        now = datetime.now().timestamp()

        try:
            dialogs = await self.client.get_dialogs(limit=40)
        except Exception as e:
            print(f"Auto reply dialogs error: {e}")
            return

        for d in dialogs:
            try:
                entity = getattr(d, 'entity', None)
                if (not getattr(d, 'is_user', False)) or entity is None:
                    continue
                uid = getattr(entity, 'id', None)
                if uid is None:
                    continue
                # Ignore Your Own Saved Messages and bots
                if getattr(entity, 'is_self', False):
                    continue
                if getattr(entity, 'bot', False):
                    continue
                if (d.unread_count or 0) <= 0:
                    continue
                last_ts = float(last.get(str(uid), 0) or 0)
                if now - last_ts < cooldown_sec:
                    continue
                await self.client.send_message(entity, text)
                first = (getattr(entity, 'first_name', '') or '').strip()
                name = first or str(uid)
                last[str(uid)] = now
                self.signals.auto_message_log.emit(f"✓ Auto-replied to {name}")
            except Exception as e:
                print(f"Auto reply send error: {e}")

        save_auto_message(auto_reply_last_replied=last)

    def scrape_messages(self, channel_ids, limit=1000):
        """Export message history of the selected channels/groups to CSVs."""
        if not self.loop or not self.client:
            self.signals.scrape_log.emit("Telegram client not ready.")
            self.signals.scrape_finished.emit()
            return
        asyncio.run_coroutine_threadsafe(self._scrape_messages_coro(channel_ids, limit), self.loop)

    async def _scrape_messages_coro(self, channel_ids, limit):
        from telescrape import scrape_messages, write_messages_csv, scrape_output_dir
        out_dir = scrape_output_dir()
        os.makedirs(out_dir, exist_ok=True)
        total = len(channel_ids)
        self.signals.scrape_log.emit(f"Exporting up to {limit if limit else 'ALL'} messages from {total} target(s)...")
        for idx, ch_id in enumerate(channel_ids, 1):
            title = str(ch_id)
            try:
                clean_id, topic_id = parse_channel_input(str(ch_id))
                channel = await fetch_channel(self.client, clean_id)
                title = getattr(channel, 'title', clean_id) or str(ch_id)
                rows = await scrape_messages(self.client, channel, limit=limit, topic_id=topic_id)
                csv_path = write_messages_csv(rows, f"{title}_messages", out_dir)
                self.signals.scrape_log.emit(f"✓ {title}: {len(rows)} messages → {os.path.basename(csv_path)}")
            except Exception as e:
                self.signals.scrape_log.emit(f"✗ {title}: {e}")
        self.signals.scrape_log.emit(f"Done. Message CSVs saved to: {out_dir}")
        self.signals.scrape_finished.emit()

    def scrape_channels_csv(self):
        """Export the cached channel/group list to a CSV."""
        if not self.loop:
            self.signals.scrape_log.emit("Telegram client not ready.")
            self.signals.scrape_finished.emit()
            return
        asyncio.run_coroutine_threadsafe(self._scrape_channels_coro(), self.loop)

    async def _scrape_channels_coro(self):
        try:
            from database import get_cached_channels_list
            from telescrape import export_channels_csv, scrape_output_dir
            channels = get_cached_channels_list() or []
            path = export_channels_csv(channels, scrape_output_dir())
            self.signals.scrape_log.emit(f"✓ Exported {len(channels)} channels/groups → {os.path.basename(path)}")
        except Exception as e:
            self.signals.scrape_log.emit(f"✗ Channel list export failed: {e}")
        self.signals.scrape_finished.emit()

    # -------------------------------------------------------------------------
    # Auto Transfer — watch a source channel and re-upload new media to groups
    # -------------------------------------------------------------------------
    def run_auto_transfer_check(self):
        """Trigger an Auto Transfer check (from the 30-minute timer or the UI)."""
        if not self.loop or not self.client:
            return
        asyncio.run_coroutine_threadsafe(self._auto_transfer_check_coro(), self.loop)

    async def _auto_transfer_check_coro(self):
        import re as _re
        from auto_transfer import (
            get_rules, update_rule, cache_dir, clean_cache,
            MEDIA_CHOICES, now_str,
        )
        from utils.file_utils import sanitize_filename
        from pdf_utils import remove_pdf_watermark

        from accounts import get_active_account_id
        active_id = get_active_account_id()

        rules = [r for r in get_rules() if r.get("enabled")]
        if not rules:
            self.signals.auto_transfer_status.emit("")
            self.signals.auto_transfer_finished.emit()
            return

        # Drop stale cache files (e.g. after a crash) before doing work
        try:
            clean_cache()
        except Exception:
            pass

        self.signals.auto_transfer_status.emit(f"Running {len(rules)} rule(s)…")
        for rule in rules:
            await self._run_auto_transfer_rule(rule, active_id)
        self.signals.auto_transfer_status.emit("")
        self.signals.auto_transfer_finished.emit()

    def run_auto_transfer_single(self, rule_id):
        """Trigger a single Auto Transfer rule run (manual, from the UI)."""
        if not self.loop or not self.client:
            return
        asyncio.run_coroutine_threadsafe(self._auto_transfer_single_coro(str(rule_id)), self.loop)

    async def _auto_transfer_single_coro(self, rule_id):
        from auto_transfer import get_rules, clean_cache
        from accounts import get_active_account_id
        active_id = get_active_account_id()
        rules = [r for r in get_rules() if str(r.get("id")) == str(rule_id)]
        if not rules:
            self.signals.auto_transfer_log.emit(f"Auto Transfer: rule '{rule_id}' not found.")
            self.signals.auto_transfer_finished.emit()
            return
        rule = rules[0]
        label = rule.get("name") or rule_id
        self.signals.auto_transfer_log.emit(f"[{label}] manual run started.")
        self.signals.auto_transfer_status.emit(f"{label}: running…")
        try:
            clean_cache()
        except Exception:
            pass
        await self._run_auto_transfer_rule(rule, active_id)
        self.signals.auto_transfer_status.emit("")
        self.signals.auto_transfer_finished.emit()

    async def _run_auto_transfer_rule(self, rule, active_id):
        """Run a single Auto Transfer rule (source → destinations)."""
        from auto_transfer import (
            update_rule, cache_dir,
            MEDIA_CHOICES, now_str,
        )
        from utils.file_utils import sanitize_filename
        from pdf_utils import remove_pdf_watermark

        # Cross-account: download from one account, upload via another (if configured)
        dl_account = rule.get("download_account_id") or active_id
        ul_account = rule.get("upload_account_id") or dl_account
        rule_label = rule.get("name") or rule.get("source_channel_id") or "Rule"

        src_client, src_ok = await self._ensure_client_authorized(dl_account)
        if not src_ok:
            self.signals.auto_transfer_log.emit(
                f"[{rule_label}] download account '{dl_account}' is not logged in / reachable; skipping."
            )
            return

        if ul_account == dl_account:
            dst_client = src_client
        else:
            dst_client, dst_ok = await self._ensure_client_authorized(ul_account)
            if not dst_ok:
                self.signals.auto_transfer_log.emit(
                    f"[{rule_label}] upload account '{ul_account}' is not logged in / reachable; skipping."
                )
                return

        src_client_label = f"download: {dl_account}" + (f"  ·  upload: {ul_account}" if ul_account != dl_account else "")
        self.signals.auto_transfer_log.emit(f"[{rule_label}] starting ({src_client_label})")
        self.signals.auto_transfer_status.emit(f"{rule_label}: resolving source channel…")

        state = rule

        src = state.get("source_channel_id", "")
        dests = state.get("destination_ids", [])
        if not src or not dests:
            self.signals.auto_transfer_log.emit(f"[{rule_label}] no source channel or destination groups configured; skipping.")
            return

        media_type = state["media_type"]
        now = now_str()

        try:
            src_clean, src_topic = parse_channel_input(str(src))
            source = await fetch_channel(src_client, src_clean)
        except Exception as e:
            self.signals.auto_transfer_log.emit(f"[{rule_label}] cannot resolve source channel: {e}")
            update_rule(state["id"], last_run=now)
            return

        src_title = getattr(source, "title", str(src))

        # Resolve destination entities via the UPLOAD client (skip unreachable ones)
        dest_entities = []
        for d in dests:
            try:
                d_clean, _ = parse_channel_input(str(d))
                dest_entities.append(await fetch_channel(dst_client, d_clean))
            except Exception as de:
                self.signals.auto_transfer_log.emit(f"[{rule_label}] cannot resolve destination {d}: {de}")
        if not dest_entities:
            self.signals.auto_transfer_log.emit(f"[{rule_label}] no reachable destination groups; skipping.")
            return

        self.signals.auto_transfer_status.emit(f"{rule_label}: transferring to {len(dest_entities)} destination(s)…")

        # Text/Chat mode: re-post message texts, no file download/upload
        if media_type == "text":
            try:
                messages = await src_client.get_messages(source, reply_to=src_topic, limit=20)
                messages = [m for m in messages if (m.message or "").strip() and not getattr(m, "media", None)]
                last_seen = int(state["last_seen_msg_id"])
                if last_seen == 0 and not state["include_existing"]:
                    newest = max((m.id for m in messages), default=0)
                    update_rule(state["id"], last_seen_msg_id=newest, last_run=now)
                    self.signals.auto_transfer_log.emit(
                        f"Auto Transfer: initialized for {src_title} — watching for NEW text posts."
                    )
                    return
                new_msgs = sorted(
                    [m for m in messages if m.id > last_seen] if not state["include_existing"] else messages,
                    key=lambda m: m.id,
                )
                if not new_msgs:
                    update_rule(state["id"], last_run=now)
                    self.signals.auto_transfer_log.emit(f"Auto Transfer: {src_title} — no new text posts.")
                    return
                max_seen = last_seen
                for m in new_msgs:
                    caption = (m.message or "").strip()
                    for dent in dest_entities:
                        try:
                            await dst_client.send_message(dent, caption)
                        except Exception as de:
                            self.signals.auto_transfer_log.emit(f"✗ text → {getattr(dent, 'title', 'dest')}: {de}")
                    max_seen = max(max_seen, m.id)
                    self.signals.auto_transfer_log.emit(f"✓ text post #{m.id} sent to {len(dest_entities)} group(s)")
                update_rule(state["id"], last_seen_msg_id=max_seen, last_run=now)
            except Exception as e:
                self.signals.auto_transfer_log.emit(f"Auto Transfer (text) error: {e}")
            self.signals.auto_transfer_finished.emit()
            return

        # Media mode: download to the isolated cache, re-upload, then delete
        try:
            messages = await get_messages_by_type(
                src_client, source, MEDIA_CHOICES.get(media_type, 6),
                limit=20, topic_id=src_topic,
            )
        except Exception as e:
            self.signals.auto_transfer_log.emit(f"Auto Transfer: failed to fetch media from {src_title}: {e}")
            self.signals.auto_transfer_finished.emit()
            return

        last_seen = int(state["last_seen_msg_id"])

        # First-ever run: do NOT dump the whole backlog — seed last_seen and wait for new posts
        if last_seen == 0 and not state["include_existing"]:
            newest = max((m.id for m in messages), default=0)
            update_rule(state["id"], last_seen_msg_id=newest, last_run=now)
            self.signals.auto_transfer_log.emit(
                f"Auto Transfer: initialized for {src_title} — watching for NEW posts "
                f"(backlog untouched, last_seen={newest})."
            )
            self.signals.auto_transfer_finished.emit()
            return

        if state["include_existing"]:
            new_msgs = sorted(messages, key=lambda m: m.id)
        else:
            new_msgs = sorted([m for m in messages if m.id > last_seen], key=lambda m: m.id)

        if not new_msgs:
            update_rule(state["id"], last_run=now)
            self.signals.auto_transfer_log.emit(f"Auto Transfer: {src_title} — no new media.")
            self.signals.auto_transfer_finished.emit()
            return

        out_dir = cache_dir()
        max_seen = last_seen
        for m in new_msgs:
            sent_all = True
            fname = ""
            if getattr(m, "file", None) and m.file.name:
                fname = sanitize_filename(m.file.name)
            else:
                ext = getattr(getattr(m, "file", None), "ext", "") or ""
                fname = f"{media_type}_{m.id}{ext}"

            dest_path = os.path.join(out_dir, fname)
            # Avoid overwriting a partially downloaded duplicate in cache
            base, ext = os.path.splitext(fname)
            counter = 1
            while os.path.exists(dest_path):
                counter += 1
                dest_path = os.path.join(out_dir, f"{base} ({counter}){ext}")

            try:
                total_size = 0
                try:
                    total_size = int(getattr(getattr(m, "file", None), "size", 0) or 0)
                except Exception:
                    total_size = 0

                # Prefer the parallel (multi-connection) downloader for max throughput;
                # fall back to Telethon's single-connection download_media if it can't
                # handle this media or the file is small.
                used_fast = False
                if total_size > 0:
                    try:
                        from utils.fast_telethon import fast_download_file
                        last_dl = {"t": 0.0}
                        def dl_progress(current, total):
                            t = time.time()
                            tot = total or total_size
                            if tot and (t - last_dl["t"] >= 0.1 or current == tot or current == 0):
                                last_dl["t"] = t
                                self.signals.auto_transfer_download_progress.emit(fname, int(current), int(tot))
                        ok = await fast_download_file(
                            src_client, m, dest_path, total_size,
                            progress_callback=dl_progress, workers=8,
                        )
                        if ok and os.path.exists(dest_path):
                            used_fast = True
                    except Exception as fe:
                        self.signals.auto_transfer_log.emit(f"  (fast download fallback: {fe})")
                if not used_fast:
                    last_dl = {"t": 0.0}
                    def dl_progress2(current, total):
                        t = time.time()
                        tot = total or total_size
                        if tot and (t - last_dl["t"] >= 0.1 or current == tot or current == 0):
                            last_dl["t"] = t
                            self.signals.auto_transfer_download_progress.emit(fname, int(current), int(tot))
                    download_result = await m.download_media(file=dest_path, progress_callback=dl_progress2)
                    if not download_result or not os.path.exists(dest_path):
                        download_result = dest_path
                    dest_path = str(download_result)
                else:
                    download_result = dest_path
                    dest_path = str(dest_path)
            except Exception as e:
                self.signals.auto_transfer_download_progress.emit(fname, 0, 0)
                self.signals.auto_transfer_log.emit(f"✗ download {fname}: {e}")
                max_seen = max(max_seen, m.id)
                continue

            # PDFs: strip text/stamp watermarks before re-uploading
            watermark_removed = False
            if dest_path.lower().endswith(".pdf"):
                cleaned_path = remove_pdf_watermark(dest_path, dest_path)
                watermark_removed = bool(cleaned_path and os.path.exists(cleaned_path))
                dest_path = cleaned_path or dest_path

            ul_total = 0
            try:
                ul_total = os.path.getsize(dest_path)
            except Exception:
                ul_total = 0
            async def _upload_one(dent):
                try:
                    caption = (m.message or "").strip() or None
                    last_ul = {"t": 0.0}
                    def ul_progress(current, total):
                        t = time.time()
                        tot = total or ul_total
                        if tot and (t - last_ul["t"] >= 0.1 or current == tot or current == 0):
                            last_ul["t"] = t
                            self.signals.auto_transfer_upload_progress.emit(fname, getattr(dent, "title", "dest"), int(current), int(tot))
                    await dst_client.send_file(dent, dest_path, caption=caption, progress_callback=ul_progress)
                    return True, None
                except Exception as de:
                    self.signals.auto_transfer_upload_progress.emit(fname, getattr(dent, "title", "dest"), 0, 0)
                    return False, de

            results = await asyncio.gather(*[_upload_one(d) for d in dest_entities], return_exceptions=True)
            for dent, res in zip(dest_entities, results):
                if isinstance(res, Exception):
                    sent_all = False
                    self.signals.auto_transfer_log.emit(f"✗ send {fname} → {getattr(dent, 'title', 'dest')}: {res}")
                elif isinstance(res, tuple):
                    ok, err = res
                    if not ok:
                        sent_all = False
                        self.signals.auto_transfer_log.emit(f"✗ send {fname} → {getattr(dent, 'title', 'dest')}: {err}")

            if sent_all:
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
                wm_note = "  ·  watermark removed" if watermark_removed else ""
                self.signals.auto_transfer_log.emit(
                    f"✓ {fname}{wm_note} → {len(dest_entities)} group(s); removed from cache"
                )
            else:
                # Keep the file in the cache for inspection; skip retrying to avoid re-sending
                self.signals.auto_transfer_log.emit(f"✗ {fname}: kept in cache (not all destinations received it)")

            max_seen = max(max_seen, m.id)

        update_rule(state["id"], last_seen_msg_id=max_seen, last_run=now)

    # -------------------------------------------------------------------------
    # Multi-account support
    # -------------------------------------------------------------------------
    async def _get_or_create_client(self, account_id):
        account_id = str(account_id)
        if account_id in self.clients:
            return self.clients[account_id]
        from accounts import get_account_credentials, account_session_path
        api_id, api_hash = get_account_credentials(account_id)
        if not api_id or not api_hash:
            return None
        session_full_path = account_session_path(account_id)
        try:
            client = TelegramClient(session_full_path, api_id, api_hash, loop=self.loop,
                                    proxy=build_proxy_dict())
            await client.connect()
        except Exception:
            return None
        self.clients[account_id] = client
        return client

    async def _ensure_client_authorized(self, account_id):
        account_id = str(account_id)
        client = await self._get_or_create_client(account_id)
        if client is None:
            return None, False
        try:
            return client, await client.is_user_authorized()
        except Exception:
            return client, False

    def switch_account(self, account_id):
        if not self.loop:
            return
        asyncio.run_coroutine_threadsafe(self._switch_account_coro(str(account_id)), self.loop)

    async def _switch_account_coro(self, account_id):
        from accounts import set_active_account_id
        client, authorized = await self._ensure_client_authorized(account_id)
        if client is None:
            self.signals.account_event.emit(f"error:{account_id}:failed to connect")
            return
        set_active_account_id(account_id)
        self.client = client
        self.signals.account_event.emit(f"switched:{account_id}")
        if authorized:
            try:
                self.fetch_user_dialogs()
            except Exception:
                pass
        else:
            self.signals.auth_needed.emit()

    def start_account_login(self, account_id, phone):
        if not self.loop:
            return
        asyncio.run_coroutine_threadsafe(self._start_account_login_coro(str(account_id), str(phone)), self.loop)

    async def _start_account_login_coro(self, account_id, phone):
        client, authorized = await self._ensure_client_authorized(account_id)
        if client is None:
            self.signals.account_event.emit(f"error:{account_id}:failed to connect or missing API credentials")
            return
        # Persist the phone the user entered so Settings can show it immediately
        try:
            from accounts import update_account, _normalize_phone
            update_account(account_id, phone=_normalize_phone(str(phone).strip()))
        except Exception:
            pass
        if authorized:
            await self._store_account_identity(client, account_id)
            self.signals.account_event.emit(f"success:{account_id}")
            return
        try:
            await client.send_code_request(phone)
            self._pending_login[account_id] = phone
            self.signals.account_event.emit(f"code_sent:{account_id}:{phone}")
        except Exception as e:
            self.signals.account_event.emit(f"error:{account_id}:{e}")

    async def _store_account_identity(self, client, account_id):
        """Fetch get_me() and persist phone/username/user_id for the account."""
        try:
            me = await client.get_me()
            phone = getattr(me, "phone", None) or ""
            if phone and not str(phone).startswith("+"):
                phone = "+" + str(phone)
            from accounts import update_account
            update_account(
                account_id,
                phone=phone,
                username=getattr(me, "username", None) or "",
                user_id=getattr(me, "id", 0) or 0,
                first_name=getattr(me, "first_name", None) or "",
            )
        except Exception:
            pass

    def submit_account_code(self, account_id, code):
        if not self.loop:
            return
        asyncio.run_coroutine_threadsafe(self._submit_account_code_coro(str(account_id), str(code)), self.loop)

    async def _submit_account_code_coro(self, account_id, code):
        client = self.clients.get(account_id)
        phone = self._pending_login.get(account_id)
        if not client or not phone:
            self.signals.account_event.emit(f"error:{account_id}:no pending login")
            return
        from telethon.errors import SessionPasswordNeededError
        try:
            await client.sign_in(phone, code)
            await self._store_account_identity(client, account_id)
            self.signals.account_event.emit(f"success:{account_id}")
        except SessionPasswordNeededError:
            self.signals.account_event.emit(f"password_needed:{account_id}")
        except Exception as e:
            self.signals.account_event.emit(f"error:{account_id}:{e}")

    def submit_account_password(self, account_id, password):
        if not self.loop:
            return
        asyncio.run_coroutine_threadsafe(self._submit_account_password_coro(str(account_id), str(password)), self.loop)

    async def _submit_account_password_coro(self, account_id, password):
        client = self.clients.get(account_id)
        if not client:
            self.signals.account_event.emit(f"error:{account_id}:no client")
            return
        try:
            await client.sign_in(password=password)
            await self._store_account_identity(client, account_id)
            self.signals.account_event.emit(f"success:{account_id}")
        except Exception as e:
            self.signals.account_event.emit(f"error:{account_id}:{e}")

    def check_all_accounts(self):
        if not self.loop:
            return
        asyncio.run_coroutine_threadsafe(self._check_all_accounts_coro(), self.loop)

    async def _check_all_accounts_coro(self):
        from accounts import get_accounts
        for acc in get_accounts():
            acc_id = str(acc.get("id"))
            client, authorized = await self._ensure_client_authorized(acc_id)
            if authorized and client is not None:
                await self._store_account_identity(client, acc_id)
            self.signals.account_event.emit(f"status:{acc_id}:{'1' if authorized else '0'}")

    # -------------------------------------------------------------------------
    # Backup & Clone — dump a channel/group to a folder or re-publish it elsewhere
    # -------------------------------------------------------------------------
    def run_backup(self, source_id, dest_id, mode, include_media=True, include_text=True, limit=None):
        """mode: 'backup' (download to folder) or 'clone' (re-publish to dest channel/group)."""
        if not self.loop or not self.client:
            self.signals.backup_log.emit("Telegram client not ready.")
            self.signals.backup_finished.emit()
            return
        asyncio.run_coroutine_threadsafe(
            self._backup_coro(str(source_id), str(dest_id or ""), str(mode),
                              bool(include_media), bool(include_text), limit),
            self.loop,
        )

    async def _backup_coro(self, source_id, dest_id, mode, include_media, include_text, limit):
        import os as _os
        from backup import backup_folder_for, write_backup_index, sanitize_name
        from utils.file_utils import sanitize_filename

        try:
            src_clean, src_topic = parse_channel_input(str(source_id))
            source = await fetch_channel(self.client, src_clean)
        except Exception as e:
            self.signals.backup_log.emit(f"Backup: cannot resolve source channel: {e}")
            self.signals.backup_finished.emit()
            return

        src_title = getattr(source, 'title', str(source_id))
        self.signals.backup_log.emit(f"Backup started: {src_title} (mode={mode})")

        dest = None
        if mode == "clone":
            if not dest_id:
                self.signals.backup_log.emit("Clone: no destination channel/group selected.")
                self.signals.backup_finished.emit()
                return
            try:
                d_clean, _ = parse_channel_input(str(dest_id))
                dest = await fetch_channel(self.client, d_clean)
            except Exception as e:
                self.signals.backup_log.emit(f"Clone: cannot resolve destination: {e}")
                self.signals.backup_finished.emit()
                return

        # Iterate ALL messages (media + text posts) in one pass, oldest first
        backfill = []
        try:
            async for m in self.client.iter_messages(source, reply_to=src_topic, reverse=True):
                backfill.append(m)
                if limit and len(backfill) >= int(limit):
                    break
        except Exception as e:
            self.signals.backup_log.emit(f"Backup: cannot read messages: {e}")
            self.signals.backup_finished.emit()
            return

        self.signals.backup_log.emit(f"Exporting {len(backfill)} message(s)...")
        out_dir = backup_folder_for(src_title) if mode == "backup" else None
        if out_dir:
            _os.makedirs(out_dir, exist_ok=True)
            self.signals.backup_log.emit(f"Saving to: {out_dir}")

        rows = []
        media_count = 0
        for i, m in enumerate(backfill, 1):
            text = (m.message or "").strip()
            has_media = bool(getattr(m, 'media', None))
            media_type = "text"
            if getattr(m, 'photo', None):
                media_type = "image"
            elif getattr(m, 'video', None) or getattr(m, 'video_note', None):
                media_type = "video"
            elif getattr(m, 'audio', None) or getattr(m, 'voice', None):
                media_type = "audio"
            elif getattr(m, 'document', None):
                media_type = "document"

            fname = ""
            if getattr(m, 'file', None) and m.file.name:
                fname = sanitize_filename(m.file.name)
            elif has_media:
                ext = getattr(getattr(m, 'file', None), 'ext', '') or ''
                fname = f"{media_type}_{m.id}{ext}"
            else:
                fname = f"text_{m.id}.txt"

            if mode == "backup":
                row_path = None
                if has_media and include_media:
                    try:
                        row_path = await m.download_media(file=_os.path.join(out_dir, fname))
                        media_count += 1
                    except Exception as e:
                        self.signals.backup_log.emit(f"✗ media #{m.id}: {e}")
                elif not has_media and include_text:
                    try:
                        with open(_os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
                            f.write(text)
                    except Exception:
                        pass
                rows.append({
                    "id": m.id,
                    "date": m.date.strftime("%Y-%m-%d %H:%M:%S") if getattr(m, 'date', None) else "",
                    "media_type": media_type,
                    "file": fname if row_path else ("" if not has_media else fname),
                    "media_saved": bool(row_path) if has_media else include_text,
                    "text": text if include_text else "",
                    "reply_to": getattr(getattr(m, 'reply_to', None), 'reply_to_msg_id', None) or "",
                })
            else:  # clone
                try:
                    if has_media and include_media:
                        tmp_path = await m.download_media(file=cache_dir_for_clone())
                        caption = text or None
                        await self.client.send_file(dest, tmp_path, caption=caption)
                        try:
                            if tmp_path and _os.path.exists(tmp_path):
                                _os.remove(tmp_path)
                        except OSError:
                            pass
                        media_count += 1
                    elif not has_media and include_text:
                        await self.client.send_message(dest, text)
                    rows.append({
                        "id": m.id,
                        "date": m.date.strftime("%Y-%m-%d %H:%M:%S") if getattr(m, 'date', None) else "",
                        "media_type": media_type,
                        "cloned": True,
                        "text": text[:200],
                    })
                except Exception as e:
                    self.signals.backup_log.emit(f"✗ post #{m.id}: {e}")

            if i % 25 == 0:
                self.signals.backup_log.emit(f"… {i}/{len(backfill)} processed ({media_count} media)")

        if mode == "backup":
            json_path = write_backup_index(rows, out_dir)
            self.signals.backup_log.emit(f"✓ Backup complete: {len(rows)} message(s), {media_count} media file(s) → {out_dir}")
            self.signals.backup_log.emit(f"Index: {_os.path.basename(json_path)}")
        else:
            self.signals.backup_log.emit(f"✓ Clone complete: {media_count} media + text re-published to {getattr(dest, 'title', 'dest')}")
        self.signals.backup_finished.emit()


def cache_dir_for_clone():
    """Temp path for media while re-publishing (clone mode)."""
    import os
    from resource_utils import get_project_root
    d = os.path.join(get_project_root(), "auto_transfer_cache")
    os.makedirs(d, exist_ok=True)
    import time
    return os.path.join(d, f"clone_{int(time.time()*1000)}")
