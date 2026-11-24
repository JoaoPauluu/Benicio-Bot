"""In-memory log of recent messages per chat, so reply chains can be rebuilt for the AI.

WhatsApp only ships the message being quoted, not what that one quoted; walking the chain needs
the bot to remember messages (incoming and its own). Lost on restart, which is fine: callers fall
back to the quoted text WhatsApp sends.
"""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from dataclasses import dataclass

PER_CHAT = 500


@dataclass(frozen=True)
class Entry:
    name: str
    text: str
    parent_id: str = ""


class MessageLog:
    def __init__(self, per_chat: int = PER_CHAT):
        self.per_chat = per_chat
        self._chats: dict[str, OrderedDict[str, Entry]] = defaultdict(OrderedDict)

    def record(self, chat: str, msg_id: str, name: str, text: str, parent_id: str = "") -> None:
        if not msg_id or not text:
            return
        log = self._chats[chat]
        log[msg_id] = Entry(name, text, parent_id)
        log.move_to_end(msg_id)
        while len(log) > self.per_chat:
            log.popitem(last=False)

    def chain(self, chat: str, msg_id: str, limit: int = 6) -> list[Entry]:
        """``msg_id`` and the messages it (transitively) replied to, oldest first, at most ``limit``."""
        log = self._chats.get(chat, {})
        out: list[Entry] = []
        seen: set[str] = set()
        while msg_id and msg_id in log and msg_id not in seen and len(out) < limit:
            seen.add(msg_id)
            entry = log[msg_id]
            out.append(entry)
            msg_id = entry.parent_id
        return out[::-1]
