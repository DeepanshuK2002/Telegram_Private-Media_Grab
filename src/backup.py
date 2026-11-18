"""
Backups & channel cloning.

- Backup mode: export a channel/group's media + message history into a dated
  folder under backups/.
- Clone mode: re-publish (media + text) from a source channel/group into a
  destination channel/group, message-by-message.
"""
import os
import json
from datetime import datetime

from resource_utils import get_project_root

BACKUP_ROOT = os.path.join(get_project_root(), "backups")


def backup_root() -> str:
    os.makedirs(BACKUP_ROOT, exist_ok=True)
    return BACKUP_ROOT


def sanitize_name(name: str) -> str:
    import re
    return re.sub(r'[<>:"/\\|?*]', "_", str(name or "backup")).strip() or "backup"


def backup_folder_for(title: str) -> str:
    return os.path.join(backup_root(), f"{sanitize_name(title)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")


def write_backup_index(rows: list, folder: str) -> str:
    """Write backup_index.json (metadata for every exported message)."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "backup_index.json")
    payload = {
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(rows),
        "messages": rows,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path
