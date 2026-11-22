"""Who is who: the bot's and the owner's ids (phone numbers *and* LIDs)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .incoming import Incoming


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


def sender_ids(inc: Incoming) -> set[str]:
    """Every id the sender may be stored under (LID, phone and its 9th-digit variant)."""
    ids = {inc.sender, inc.sender_alt} - {""}
    for i in list(ids):
        ids |= phone_variants(i)
    return ids


class Identity:
    """Knows who the bot is and who the owner is."""

    def __init__(self, owner_number: str):
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

    def is_bot(self, user: str) -> bool:
        return user in self.bot_ids

    def mentions_bot(self, inc: Incoming) -> bool:
        return bool(inc.mentioned & self.bot_ids) or self.is_bot(inc.quoted_participant)

    def strip_mentions(self, text: str) -> str:
        for bid in self.bot_ids:
            text = re.sub(rf"@{re.escape(bid)}\b", " ", text)
        return re.sub(r"\s+", " ", text).strip()
