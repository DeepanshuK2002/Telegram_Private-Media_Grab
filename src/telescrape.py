"""
Telescrape — member scraper for public Telegram groups and channels.

Adapted from https://github.com/ephell/Telescrape (MIT License, © ephell).
Stripped of the standalone app, its own auth flow and settings — it runs as
part of TG Private Grab using the app's logged-in Telethon client.
"""
import csv
import os
import re
from datetime import datetime, timedelta, timezone

from telethon.errors import ChatAdminRequiredError
from telethon.tl.types import (
    ChannelParticipantsAdmins,
    UserStatusOnline,
    UserStatusRecently,
    UserStatusEmpty,
    UserStatusOffline,
    UserStatusLastWeek,
    UserStatusLastMonth,
)


def scrape_options_from(mapping):
    """Build a flat scrape options dict from either a dict or Qt checkbox state."""
    opts = dict(mapping or {})
    opts.setdefault("exclude_yourself", True)
    opts.setdefault("exclude_admins", True)
    opts.setdefault("exclude_bots", True)
    opts.setdefault("exclude_deleted_users", True)
    opts.setdefault("exclude_restricted_users", True)
    opts.setdefault("exclude_scam_flagged_users", True)
    opts.setdefault("exclude_fake_flagged_users", True)
    opts.setdefault("exclude_users_in_contacts", True)
    opts.setdefault("exclude_users_with_hidden_last_seen_online", False)
    opts.setdefault("user_active_in_last_days", 0)
    opts.setdefault("only_premium", False)
    return opts


async def scrape_members(client, entity, options):
    """
    Fetch and filter members of `entity`.

    Returns the list of User objects, or None if admin privileges are required
    to list participants.
    """
    exclude_admins = options.get("exclude_admins", True)
    try:
        all_participants = [p async for p in client.iter_participants(entity)]
        if exclude_admins:
            admin_participants = [
                p async for p in client.iter_participants(entity, filter=ChannelParticipantsAdmins)
            ]
            all_participants = [p for p in all_participants if p not in admin_participants]
    except ChatAdminRequiredError:
        return None

    exclude_yourself = options.get("exclude_yourself", True)
    exclude_bots = options.get("exclude_bots", True)
    exclude_deleted_users = options.get("exclude_deleted_users", True)
    exclude_restricted_users = options.get("exclude_restricted_users", True)
    exclude_scam_flagged_users = options.get("exclude_scam_flagged_users", True)
    exclude_fake_flagged_users = options.get("exclude_fake_flagged_users", True)
    exclude_users_in_contacts = options.get("exclude_users_in_contacts", True)
    exclude_users_with_hidden_last_seen_online = options.get("exclude_users_with_hidden_last_seen_online", False)
    user_active_in_last_days = options.get("user_active_in_last_days", 0)
    only_premium = options.get("only_premium", False)

    all_users = []
    for participant in all_participants:
        if (
            (exclude_yourself and participant.is_self)
            or (exclude_bots and participant.bot)
            or (exclude_deleted_users and participant.deleted)
            or (exclude_restricted_users and participant.restricted)
            or (exclude_scam_flagged_users and participant.scam)
            or (exclude_fake_flagged_users and participant.fake)
            or (exclude_users_in_contacts and participant.contact)
        ):
            continue
        if only_premium and not getattr(participant, "premium", False):
            continue

        if isinstance(participant.status, UserStatusOffline):
            if user_active_in_last_days <= 0:
                all_users.append(participant)
            else:
                last_online = participant.status.was_online.replace(tzinfo=timezone.utc)
                day_offset = datetime.now(timezone.utc) - timedelta(days=user_active_in_last_days)
                if last_online >= day_offset:
                    all_users.append(participant)
        else:
            statuses = [UserStatusOnline, UserStatusRecently]
            if not exclude_users_with_hidden_last_seen_online:
                statuses.extend([UserStatusEmpty, type(None)])

            if user_active_in_last_days <= 0:
                statuses.extend([UserStatusLastWeek, UserStatusLastMonth])
            else:
                if user_active_in_last_days >= 2:
                    statuses.append(UserStatusLastWeek)
                if user_active_in_last_days >= 6:
                    statuses.append(UserStatusLastMonth)

            if any(isinstance(participant.status, status) for status in statuses):
                all_users.append(participant)

    return all_users


def extract_users_data(users):
    users_data = []
    for user in users:
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        name = (first_name + " " + last_name).strip()
        users_data.append({
            "id": user.id,
            "access_hash": user.access_hash,
            "full_name": name,
            "username": user.username or "",
            "phone": user.phone or "Hidden",
        })
    return users_data


def write_csv(users_data, entity_title, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    title_clean = re.sub(r'[<>:"/\\|?*]', "_", entity_title or "members").strip() or "members"
    full_path = os.path.join(out_dir, title_clean + ".csv")
    with open(full_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if users_data:
            writer.writerow(users_data[0].keys())
            for row in users_data:
                writer.writerow(row.values())
        else:
            writer.writerow(["id", "access_hash", "full_name", "username", "phone"])
    return full_path


def scrape_output_dir():
    from resource_utils import get_project_root
    return os.path.join(get_project_root(), "scraped_members")


async def scrape_messages(client, entity, limit=1000, topic_id=None):
    """Export a channel/group's message history (text + metadata)."""
    rows = []
    kwargs = {"limit": int(limit) if limit else None}
    if topic_id is not None:
        kwargs["reply_to"] = topic_id
    async for m in client.iter_messages(entity, **kwargs):
        sender = getattr(m, "sender", None)
        first = getattr(sender, "first_name", "") or ""
        last = getattr(sender, "last_name", "") or ""
        sender_name = (first + " " + last).strip()
        username = getattr(sender, "username", "") or ""

        media_type = "text"
        if getattr(m, "photo", None):
            media_type = "image"
        elif getattr(m, "video", None) or getattr(m, "video_note", None):
            media_type = "video"
        elif getattr(m, "audio", None) or getattr(m, "voice", None):
            media_type = "audio"
        elif getattr(m, "document", None):
            media_type = "document"
        elif getattr(m, "sticker", None):
            media_type = "sticker"
        elif getattr(m, "poll", None):
            media_type = "poll"
        elif getattr(m, "contact", None):
            media_type = "contact"
        elif getattr(m, "geo", None) or getattr(m, "venue", None):
            media_type = "location"

        rows.append({
            "id": m.id,
            "date": m.date.strftime("%Y-%m-%d %H:%M:%S") if getattr(m, "date", None) else "",
            "sender_id": getattr(sender, "id", "") or "",
            "sender": sender_name,
            "username": username,
            "media_type": media_type,
            "text": (m.message or "").strip(),
            "reply_to": getattr(getattr(m, "reply_to", None), "reply_to_msg_id", None) or "",
        })
    return rows


def write_messages_csv(rows, title, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    title_clean = re.sub(r'[<>:"/\\|?*]', "_", title or "messages").strip() or "messages"
    full_path = os.path.join(out_dir, title_clean + ".csv")
    with open(full_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        cols = ["id", "date", "sender_id", "sender", "username", "media_type", "text", "reply_to"]
        writer.writerow(cols)
        for row in rows:
            writer.writerow([row.get(c, "") for c in cols])
    return full_path


def export_channels_csv(channels, out_dir):
    """Export the app's cached channel/group list to CSV ('scrape channel list')."""
    os.makedirs(out_dir, exist_ok=True)
    full_path = os.path.join(out_dir, "channel_list.csv")
    with open(full_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["channel_id", "title", "username", "is_channel", "is_group", "unread_count", "pinned"])
        for ch in channels:
            writer.writerow([
                ch.get("channel_id") or ch.get("id") or "",
                ch.get("title") or "",
                ch.get("username") or "",
                ch.get("is_channel", 0),
                ch.get("is_group", 0),
                ch.get("unread_count", 0),
                ch.get("pinned", 0),
            ])
    return full_path
