"""
Multi-account support for TG Private Grab.

Accounts are stored in config.json under the "accounts" key:
    [{ "id": "default", "name": "Main", "session": "default_session",
        "api_id": 0, "api_hash": "" }, ...]
and the currently active one under "active_account_id".

The legacy app uses a single hardcoded session ("default_session") with API_ID/API_HASH
from .env — that account is migrated automatically as account id "default".
"""
import os
from resource_utils import get_project_root


def get_accounts() -> list:
    from ui.views.settings_view import load_config
    cfg = load_config()
    accounts = cfg.get("accounts")
    if not accounts:
        accounts = [_default_account()]
        _write_accounts(accounts)
    changed = False
    for acc in accounts:
        if not acc.get("session"):
            acc["session"] = f"session_{acc.get('id', 'acc')}"
            changed = True
        if not acc.get("id"):
            acc["id"] = acc["session"]
            changed = True
        # Backfill newer fields so the UI can show phone / login identity
        for key in ("phone", "username", "user_id", "first_name"):
            if key not in acc:
                acc[key] = "" if key != "user_id" else 0
                changed = True
    if changed:
        _write_accounts(accounts)
    return accounts


def _default_account() -> dict:
    api_id, api_hash = _legacy_credentials()
    return {
        "id": "default",
        "name": "Main Account",
        "session": "default_session",
        "api_id": api_id,
        "api_hash": api_hash,
    }


def _normalize_phone(phone: str) -> str:
    phone = (phone or "").strip()
    if phone and phone.replace(" ", "").replace("-", "").isdigit() and not phone.startswith("+"):
        phone = "+" + phone
    return phone
    """Built-in Telegram Desktop API credentials (publicly available, used by open-source
    Telegram clients). Lets users log in with just a phone number — no .env setup required."""
    return 2040, "b18441a1ff607e10a989891a5462e627"


def _legacy_credentials():
    api_id, api_hash = 0, ""
    try:
        cfg = load_config()
        api_id = cfg.get("api_id") or 0
        api_hash = cfg.get("api_hash") or ""
    except Exception:
        cfg = {}
    if not api_id or not api_hash:
        env_path = os.path.join(get_project_root(), ".env")
        try:
            with open(env_path, "r") as f:
                env = {}
                for line in f:
                    if "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() == "API_ID":
                            v = v.strip().strip("'").strip('"')
                            api_id = int(v) if v.isdigit() else 0
                        elif k.strip() == "API_HASH":
                            api_hash = v.strip().strip("'").strip('"')
        except Exception:
            pass
    if not api_id or not api_hash:
        api_id, api_hash = get_builtin_credentials()
    return api_id, api_hash


def _write_accounts(accounts: list):
    from ui.views.settings_view import load_config, save_config
    cfg = load_config()
    cfg["accounts"] = accounts
    save_config(cfg)


def get_active_account_id() -> str:
    from ui.views.settings_view import load_config
    cfg = load_config()
    active = cfg.get("active_account_id")
    accounts = get_accounts()
    if not active or all(a.get("id") != active for a in accounts):
        active = accounts[0]["id"] if accounts else "default"
        set_active_account_id(active)
    return active


def set_active_account_id(account_id: str):
    from ui.views.settings_view import load_config, save_config
    cfg = load_config()
    cfg["active_account_id"] = str(account_id)
    save_config(cfg)


def get_account(account_id: str) -> dict:
    for acc in get_accounts():
        if acc.get("id") == str(account_id):
            return dict(acc)
    return _default_account()


def get_active_account() -> dict:
    return get_account(get_active_account_id())


def get_account_credentials(account_id: str):
    """Resolve (api_id, api_hash) for an account, falling back to the legacy .env credentials."""
    acc = get_account(account_id)
    api_id = acc.get("api_id") or 0
    api_hash = acc.get("api_hash") or ""
    if not api_id or not api_hash:
        env_id, env_hash = _legacy_credentials()
        if not api_id:
            api_id = env_id
        if not api_hash:
            api_hash = env_hash
    return int(api_id or 0), api_hash


def account_session_path(account_id: str) -> str:
    session = get_account(account_id).get("session") or f"session_{account_id}"
    return os.path.join(get_project_root(), session)


def add_account(name: str, phone: str = "", account_id: str = None) -> dict:
    from ui.views.settings_view import load_config, save_config
    name = (name or "New Account").strip() or "New Account"
    if not account_id:
        account_id = "acc_" + os.urandom(4).hex()
    session = f"session_{account_id}"
    api_id, api_hash = _legacy_credentials()
    acc = {
        "id": account_id,
        "name": name,
        "session": session,
        "api_id": api_id,
        "api_hash": api_hash,
        "phone": _normalize_phone(phone),
        "username": "",
        "user_id": 0,
        "first_name": "",
    }
    accounts = get_accounts()
    accounts.append(acc)
    cfg = load_config()
    cfg["accounts"] = accounts
    save_config(cfg)
    return dict(acc)


def update_account(account_id: str, **fields) -> bool:
    """Update fields of an existing account in config.json. Returns True if found."""
    from ui.views.settings_view import load_config, save_config
    account_id = str(account_id)
    accounts = get_accounts()
    found = False
    for acc in accounts:
        if str(acc.get("id")) == account_id:
            for k, v in fields.items():
                if v is not None:
                    acc[k] = v
            found = True
            break
    if not found:
        return False
    cfg = load_config()
    cfg["accounts"] = accounts
    save_config(cfg)
    return True


def remove_account(account_id: str) -> bool:
    account_id = str(account_id)
    accounts = get_accounts()
    new_accounts = [a for a in accounts if a.get("id") != account_id]
    if len(new_accounts) == len(accounts):
        return False
    if account_id == "default":
        # Keep a legacy default account if it was the only one
        if not new_accounts:
            new_accounts = [_default_account()]
    _write_accounts(new_accounts)

    # Delete the session file(s) for this account
    acc = get_account(account_id)
    for suffix in (".session", ".session-journal"):
        path = os.path.join(get_project_root(), str(acc.get("session", "")) + suffix)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    active = get_active_account_id()
    if active == account_id:
        set_active_account_id(new_accounts[0]["id"])
    return True
