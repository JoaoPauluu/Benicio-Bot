"""Helpers for WhatsApp JID strings ('5511999@s.whatsapp.net', '1234:5@lid', '1203...@g.us')."""

from __future__ import annotations

from neonize.utils.jid import build_jid

GROUP_SERVER = "g.us"
USER_SERVER = "s.whatsapp.net"


def user_of(jid: str) -> str:
    """'5511999@s.whatsapp.net' / '1234:5@lid' -> '5511999' / '1234'."""
    return jid.split("@", 1)[0].split(":", 1)[0].split(".", 1)[0]


def jid_from_str(jid: str):
    """'5511999@s.whatsapp.net' -> neonize JID protobuf (server defaults to a user chat)."""
    user, _, server = jid.partition("@")
    return build_jid(user, server or USER_SERVER)


def is_group_jid(jid: str) -> bool:
    return jid.endswith(f"@{GROUP_SERVER}")
