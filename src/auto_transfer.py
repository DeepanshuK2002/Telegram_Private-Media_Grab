"""
Auto Transfer — watch a source channel and re-upload new media to selected groups.

Settings are stored in config.json under the "auto_transfer" key.

Files are downloaded to a dedicated `auto_transfer_cache/` folder (separate from the
user's normal download folders) and are deleted automatically after they have been
successfully sent to every selected destination group.
"""
import os
import time
from datetime import datetime

from resource_utils import get_project_root
from ui.views.settings_view import load_config, save_config

CONFIG_KEY = "auto_transfer"

MEDIA_CHOICES = {
    "all": 6,
    "videos": 2,
    "images": 1,
    "documents": 3,
    "audio": 5,
    # "text" is handled specially by the worker (plain message re-post)
}

LEGACY_KEY = "auto_transfer"
RULES_KEY = "auto_transfer_rules"
_RULE_ID_COUNTER = [0]


def _get_cfg():
    return load_config()


def _save_cfg(cfg):
    save_config(cfg)


def _migrate_legacy_if_needed():
    """One-time migration: single-source auto_transfer config → multiple rules."""
    cfg = _get_cfg()
    legacy = cfg.get(LEGACY_KEY)
    if not legacy:
        return
    rules = list(cfg.get(RULES_KEY, {}).get("rules", []) if isinstance(cfg.get(RULES_KEY), dict) else [])
    if rules:
        cfg.pop(LEGACY_KEY, None)
        _save_cfg(cfg)
        return
    if not (legacy.get("source_channel_id") or legacy.get("destination_ids")):
        cfg.pop(LEGACY_KEY, None)
        _save_cfg(cfg)
        return
    rule = {
        "id": "rule_migrated",
        "name": "Main rule",
        "enabled": bool(legacy.get("enabled", False)),
        "source_channel_id": str(legacy.get("source_channel_id") or ""),
        "destination_ids": list(legacy.get("destination_ids") or []),
        "media_type": str(legacy.get("media_type") or "videos"),
        "include_existing": bool(legacy.get("include_existing", False)),
        "last_seen_msg_id": int(legacy.get("last_seen_msg_id") or 0),
        "last_run": str(legacy.get("last_run") or ""),
        "download_account_id": str(legacy.get("download_account_id") or ""),
        "upload_account_id": str(legacy.get("upload_account_id") or ""),
    }
    cfg[RULES_KEY] = {"rules": [rule]}
    cfg.pop(LEGACY_KEY, None)
    _save_cfg(cfg)


def get_auto_transfer() -> dict:
    """Legacy shim kept for backwards compatibility: returns the first rule's state."""
    _migrate_legacy_if_needed()
    rules = get_rules()
    if rules:
        return dict(rules[0])
    # Empty default when no rules configured yet
    return {
        "id": "",
        "name": "Rule 1",
        "enabled": False,
        "source_channel_id": "",
        "destination_ids": [],
        "media_type": "videos",
        "include_existing": False,
        "last_seen_msg_id": 0,
        "last_run": "",
        "download_account_id": "",
        "upload_account_id": "",
    }


def save_auto_transfer(**kwargs) -> dict:
    """Legacy shim: updates the first rule. Prefer get_rules/save_rules instead."""
    _migrate_legacy_if_needed()
    rules = get_rules()
    if not rules:
        rules = [{
            "id": _new_rule_id(),
            "name": "Rule 1",
            "enabled": False,
            "source_channel_id": "",
            "destination_ids": [],
            "media_type": "videos",
            "include_existing": False,
            "last_seen_msg_id": 0,
            "last_run": "",
            "download_account_id": "",
            "upload_account_id": "",
        }]
    merged = dict(rules[0])
    merged.update(kwargs)
    rules[0] = _normalize_rule(merged)
    save_rules(rules)
    return dict(rules[0])


def _new_rule_id() -> str:
    _RULE_ID_COUNTER[0] += 1
    import time as _t
    return f"rule_{int(_t.time() * 1000)}_{_RULE_ID_COUNTER[0]}"


def _normalize_rule(rule: dict, index: int = 0) -> dict:
    return {
        "id": str(rule.get("id") or f"rule_{index + 1}"),
        "name": str(rule.get("name") or f"Rule {index + 1}"),
        "enabled": bool(rule.get("enabled", False)),
        "source_channel_id": str(rule.get("source_channel_id") or ""),
        "destination_ids": list(rule.get("destination_ids") or []),
        "media_type": str(rule.get("media_type") or "videos"),
        "include_existing": bool(rule.get("include_existing", False)),
        "last_seen_msg_id": int(rule.get("last_seen_msg_id") or 0),
        "last_run": str(rule.get("last_run") or ""),
        "download_account_id": str(rule.get("download_account_id") or ""),
        "upload_account_id": str(rule.get("upload_account_id") or ""),
    }


def get_rules() -> list:
    """Return the list of Auto Transfer rules (enabled and disabled)."""
    _migrate_legacy_if_needed()
    cfg = _get_cfg()
    data = cfg.get(RULES_KEY) if isinstance(cfg.get(RULES_KEY), dict) else {}
    raw = data.get("rules", []) if isinstance(data, dict) else []
    rules = []
    for i, r in enumerate(raw):
        if isinstance(r, dict):
            rules.append(_normalize_rule(r, i))
    return rules


def save_rules(rules: list) -> list:
    cfg = _get_cfg()
    norm = [_normalize_rule(r, i) for i, r in enumerate(rules or [])]
    cfg[RULES_KEY] = {"rules": norm}
    _save_cfg(cfg)
    return norm


def add_rule(name: str = None) -> dict:
    rules = get_rules()
    rule = _normalize_rule({
        "id": _new_rule_id(),
        "name": name or f"Rule {len(rules) + 1}",
    })
    rules.append(rule)
    save_rules(rules)
    return rule


def update_rule(rule_id: str, **kwargs) -> dict:
    rules = get_rules()
    out = None
    for i, r in enumerate(rules):
        if str(r.get("id")) == str(rule_id):
            merged = dict(r)
            merged.update(kwargs)
            rules[i] = _normalize_rule(merged, i)
            out = dict(rules[i])
            break
    save_rules(rules)
    return out


def remove_rule(rule_id: str) -> bool:
    rules = get_rules()
    new_rules = [r for r in rules if str(r.get("id")) != str(rule_id)]
    if len(new_rules) == len(rules):
        return False
    save_rules(new_rules)
    return True


def cache_dir() -> str:
    path = os.path.join(get_project_root(), "auto_transfer_cache")
    os.makedirs(path, exist_ok=True)
    return path


def clean_cache(max_age_seconds: int = 7 * 24 * 3600) -> int:
    """Remove stale files from the transfer cache (e.g. after a crash)."""
    d = cache_dir()
    now = time.time()
    removed = 0
    for fname in os.listdir(d):
        fp = os.path.join(d, fname)
        try:
            if os.path.isfile(fp) and (now - os.path.getmtime(fp)) > max_age_seconds:
                os.remove(fp)
                removed += 1
        except OSError:
            pass
    return removed


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
