"""Turn neonize MessageEv protobufs into a plain, testable dataclass."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from neonize.utils.jid import Jid2String, JIDToNonAD
from neonize.utils.message import extract_text

from .jid import user_of

# Message types that carry a contextInfo (mentions / quoted message).
_CTX_FIELDS = (
    "extendedTextMessage", "imageMessage", "videoMessage", "documentMessage", "audioMessage", "stickerMessage",
)


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
    id: str = ""                   # WhatsApp message id
    quoted_id: str = ""            # id of the quoted message (replies)
    has_document: bool = False
    document_name: str = ""
    timestamp: float = field(default_factory=time.time)


def _timestamp(raw: int) -> float:
    if raw <= 0:
        return time.time()
    return raw / 1000 if raw > 10**11 else float(raw)  # ms or s


def media_message(msg):
    """Documents with a caption arrive wrapped in documentWithCaptionMessage; unwrap them."""
    if msg.HasField("documentWithCaptionMessage"):
        return msg.documentWithCaptionMessage.message
    return msg


def parse_event(ev) -> Incoming:
    src = ev.Info.MessageSource
    outer = ev.Message
    msg = media_message(outer)
    mentioned: set[str] = set()
    quoted_participant = quoted_text = quoted_id = ""
    for name in _CTX_FIELDS:
        if msg.HasField(name):
            info = getattr(msg, name).contextInfo
            mentioned = {user_of(j) for j in info.mentionedJID}
            quoted_participant = user_of(info.participant) if info.participant else ""
            quoted_id = info.stanzaID
            if info.HasField("quotedMessage"):
                quoted_text = extract_text(info.quotedMessage) or ""
            break
    has_document = msg.HasField("documentMessage")
    return Incoming(
        chat=Jid2String(JIDToNonAD(src.Chat)),
        sender=src.Sender.User,
        sender_alt=src.SenderAlt.User if src.HasField("SenderAlt") else "",
        sender_name=ev.Info.Pushname or src.Sender.User,
        is_group=src.IsGroup,
        from_me=src.IsFromMe,
        text=(extract_text(outer) or extract_text(msg) or msg.documentMessage.caption or "").strip(),
        mentioned=mentioned,
        quoted_participant=quoted_participant,
        quoted_text=quoted_text.strip(),
        id=ev.Info.ID,
        quoted_id=quoted_id,
        has_document=has_document,
        document_name=msg.documentMessage.fileName if has_document else "",
        timestamp=_timestamp(ev.Info.Timestamp),
    )
