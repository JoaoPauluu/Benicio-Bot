"""Turn neonize MessageEv protobufs into a plain, testable dataclass."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from neonize.utils.jid import Jid2String, JIDToNonAD
from neonize.utils.message import extract_text

_CTX_FIELDS = ("extendedTextMessage", "imageMessage", "videoMessage", "documentMessage", "audioMessage", "stickerMessage")


def user_of(jid: str) -> str:
    """'5511999@s.whatsapp.net' / '1234:5@lid' -> '5511999' / '1234'."""
    return jid.split("@", 1)[0].split(":", 1)[0].split(".", 1)[0]


@dataclass
class Incoming:
    chat: str
    sender: str
    sender_alt: str = ""
    sender_name: str = ""
    is_group: bool = False
    from_me: bool = False
    text: str = ""
    mentioned: set[str] = field(default_factory=set)
    quoted_participant: str = ""
    quoted_text: str = ""
    timestamp: float = field(default_factory=time.time)


def _timestamp(raw: int) -> float:
    if raw <= 0:
        return time.time()
    return raw / 1000 if raw > 10**11 else float(raw)  # ms or s


def parse_event(ev) -> Incoming:
    src = ev.Info.MessageSource
    msg = ev.Message
    mentioned: set[str] = set()
    quoted_participant = quoted_text = ""
    for name in _CTX_FIELDS:
        if msg.HasField(name):
            ctx = getattr(msg, name).contextInfo
            mentioned = {user_of(j) for j in ctx.mentionedJID}
            quoted_participant = user_of(ctx.participant) if ctx.participant else ""
            if ctx.HasField("quotedMessage"):
                quoted_text = extract_text(ctx.quotedMessage) or ""
            break
    return Incoming(
        chat=Jid2String(JIDToNonAD(src.Chat)),
        sender=src.Sender.User,
        sender_alt=src.SenderAlt.User if src.HasField("SenderAlt") else "",
        sender_name=ev.Info.Pushname or src.Sender.User,
        is_group=src.IsGroup,
        from_me=src.IsFromMe,
        text=(extract_text(msg) or "").strip(),
        mentioned=mentioned,
        quoted_participant=quoted_participant,
        quoted_text=quoted_text.strip(),
        timestamp=_timestamp(ev.Info.Timestamp),
    )


def phone_variants(number: str) -> set[str]:
    """Brazilian mobiles may appear with or without the extra 9 after the area code.

    WhatsApp keeps the legacy 12-digit form (55 + DDD + 8 digits) as the JID for accounts
    registered before the 9-digit change, while people usually write the 13-digit form.
    """
    if not number:
        return set()
    variants = {number}
    if number.startswith("55"):
        if len(number) == 13 and number[4] == "9":
            variants.add(number[:4] + number[5:])
        elif len(number) == 12:
            variants.add(number[:4] + "9" + number[4:])
    return variants


class Identity:
    """Knows who the bot is and who the owner is (phone numbers *and* LIDs)."""

    def __init__(self, owner_number: str):
        self.owner_number = owner_number
        self.owner_ids: set[str] = phone_variants(owner_number)
        self.bot_ids: set[str] = set()

    def set_bot(self, *ids: str) -> None:
        self.bot_ids = {i for i in ids if i}

    def learn(self, inc: Incoming) -> None:
        """Groups often address users by LID; learn the owner's LID when seen."""
        if inc.sender_alt and inc.sender_alt in self.owner_ids:
            self.owner_ids.add(inc.sender)
        elif inc.sender in self.owner_ids and inc.sender_alt:
            self.owner_ids.add(inc.sender_alt)

    def is_owner(self, inc: Incoming) -> bool:
        return inc.sender in self.owner_ids or (bool(inc.sender_alt) and inc.sender_alt in self.owner_ids)

    def mentions_bot(self, inc: Incoming) -> bool:
        return bool(inc.mentioned & self.bot_ids) or (inc.quoted_participant in self.bot_ids)

    def strip_mentions(self, text: str) -> str:
        for bid in self.bot_ids:
            text = re.sub(rf"@{re.escape(bid)}\b", " ", text)
        return re.sub(r"\s+", " ", text).strip()
