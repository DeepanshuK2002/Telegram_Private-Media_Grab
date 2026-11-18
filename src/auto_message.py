"""
Auto Message — write multiple messages (text + optional emoji + optional image)
and re-send them to selected Telegram groups on a fixed interval.

Settings are stored in config.json under the "auto_message" key.
Images are NOT deleted (unlike Auto Transfer) — they are part of your message library.
"""
from datetime import datetime
from ui.views.settings_view import load_config, save_config

CONFIG_KEY = "auto_message"

DEFAULT_INTERVAL_MINUTES = 60


def get_auto_message() -> dict:
    cfg = load_config()
    d = cfg.get(CONFIG_KEY, {}) or {}
    messages = d.get("messages") or []
    # Normalize message entries
    norm_messages = []
    for i, m in enumerate(messages):
        if not isinstance(m, dict):
            continue
        norm_messages.append({
            "id": str(m.get("id") or f"msg_{i}"),
            "text": str(m.get("text") or ""),
            "image_path": str(m.get("image_path") or ""),
        })
    return {
        "enabled": bool(d.get("enabled", False)),
        "interval_minutes": int(d.get("interval_minutes") or DEFAULT_INTERVAL_MINUTES),
        "rotation": str(d.get("rotation") or "roundrobin"),
        "destination_ids": list(d.get("destination_ids") or []),
        "messages": norm_messages,
        "next_index": int(d.get("next_index") or 0),
        "last_run": str(d.get("last_run") or ""),
        "send_count": int(d.get("send_count") or 0),
        "auto_reply_enabled": bool(d.get("auto_reply_enabled", False)),
        "auto_reply_text": str(d.get("auto_reply_text") or ""),
        "auto_reply_cooldown_hours": int(d.get("auto_reply_cooldown_hours") or 24),
        "auto_reply_last_replied": dict(d.get("auto_reply_last_replied") or {}),
    }


def save_auto_message(**kwargs) -> dict:
    cfg = load_config()
    d = get_auto_message()
    d.update(kwargs)
    cfg[CONFIG_KEY] = d
    save_config(cfg)
    return d


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
