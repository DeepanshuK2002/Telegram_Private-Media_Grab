import asyncio
import os
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


class TelegramWorker(QThread):
    def __init__(self, session_name, api_id, api_hash, parent=None):
        super().__init__(parent)
        self.session_name = session_name
        self.api_id = api_id
        self.api_hash = api_hash
        self.signals = WorkerSignals()
        self.loop = None
        self.client = None
        self.task_cancel_events = {}
        self.running_tasks = {} # task_id -> future or task

    def get_client(self):
        return self.client

    def run(self):
        """Thread entry point. Starts the asyncio event loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            session_full_path = os.path.join(get_project_root(), self.session_name)
            self.client = TelegramClient(session_full_path, self.api_id, self.api_hash, loop=self.loop)
            self.loop.run_until_complete(self.check_auth())
        except ValueError:
            # API ID / Hash missing or invalid
            self.signals.auth_needed.emit()
        
        # Run forever processing asyncio tasks
        self.loop.run_forever()

    def set_credentials(self, api_id, api_hash):
        self.api_id = int(api_id)
        self.api_hash = api_hash
        
        async def _reinit():
            if self.client:
                await self.client.disconnect()
            session_full_path = os.path.join(get_project_root(), self.session_name)
            self.client = TelegramClient(session_full_path, self.api_id, self.api_hash, loop=self.loop)
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
            
            # Cache in SQLite for instant reload next time
            from database import cache_channels_list
            try:
                cache_channels_list(result)
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
        """Fetches video messages for a specific channel/chat."""
        if not self.loop or not self.client:
            return
        asyncio.run_coroutine_threadsafe(self._fetch_channel_videos_coro(channel_id, limit), self.loop)

    async def _fetch_channel_videos_coro(self, channel_id, limit=300):
        try:
            self.signals.explore_loading.emit(True, "Fetching videos...")
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
            
            from telethon.tl.types import InputMessagesFilterVideo, InputMessagesFilterDocument
            
            kwargs = {}
            if topic_id is not None:
                kwargs['reply_to'] = topic_id
                
            # 🚀 Fire both message requests in parallel — halves channel load time
            native_vids_coro = self.client.get_messages(channel, limit=limit, filter=InputMessagesFilterVideo(), **kwargs)
            doc_msgs_coro = self.client.get_messages(channel, limit=min(limit, 100), filter=InputMessagesFilterDocument(), **kwargs)
            native_vids, doc_msgs = await asyncio.gather(native_vids_coro, doc_msgs_coro)
            doc_vids = [
                m for m in doc_msgs 
                if m.document and (
                    (getattr(m.document, 'mime_type', '') or '').startswith('video/') or 
                    any(attr for attr in getattr(m.document, 'attributes', []) if hasattr(attr, 'duration'))
                )
            ]
            
            # Combine and deduplicate by message id
            all_msgs_map = {}
            for m in list(native_vids) + doc_vids:
                if m and m.id and m.id not in all_msgs_map:
                    all_msgs_map[m.id] = m
                    
            sorted_msgs = sorted(all_msgs_map.values(), key=lambda m: m.id, reverse=True)
            
            videos_list = []
            ch_title = getattr(channel, 'title', getattr(channel, 'first_name', str(channel_id)))
            
            for m in sorted_msgs:
                fname = ""
                if m.file and m.file.name:
                    fname = m.file.name
                elif m.file and m.file.ext:
                    fname = f"video_{m.id}{m.file.ext}"
                else:
                    fname = f"video_{m.id}.mp4"
                
                fsize = 0
                if m.file and m.file.size:
                    fsize = m.file.size
                elif m.document and m.document.size:
                    fsize = m.document.size
                    
                duration_sec = 0
                width = 0
                height = 0
                if m.document and hasattr(m.document, 'attributes'):
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
                
                videos_list.append({
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
                })
                
            self.signals.channel_videos_fetched.emit(str(channel_id), videos_list)
            self.signals.explore_loading.emit(False, "")

            # Schedule background thumbnail download for these videos on the worker loop
            real_msgs = [v.get("msg_obj") for v in videos_list if v.get("msg_obj")]
            if real_msgs:
                asyncio.create_task(self._fetch_channel_thumbnails_coro(clean_id, real_msgs))
        except Exception as e:
            print(f"DEBUG: fetch_channel_videos error: {e}")
            self.signals.explore_error.emit(f"Error fetching videos: {str(e)}")
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
