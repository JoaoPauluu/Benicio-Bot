"""What every command / listener receives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from neonize.utils.jid import build_jid

if TYPE_CHECKING:
    from .bot import Bot
    from .incoming import Incoming


def jid_from_str(jid: str):
    user, _, server = jid.partition("@")
    return build_jid(user, server or "s.whatsapp.net")


@dataclass
class Context:
    bot: "Bot"
    chat: str
    text: str = ""                 # message text with the bot mention removed
    args: list[str] = field(default_factory=list)
    command: str | None = None
    is_owner: bool = False
    is_group: bool = False
    triggered: bool = False        # bot was mentioned (group) or DM'd
    incoming: "Incoming | None" = None
    event: Any = None              # raw neonize MessageEv (None for scheduled runs)

    @property
    def store(self):
        return self.bot.store

    @property
    def ai(self):
        return self.bot.ai

    @property
    def settings(self):
        return self.bot.settings

    @property
    def sender_name(self) -> str:
        return self.incoming.sender_name if self.incoming else "dono"

    async def reply(self, text: str) -> None:
        """Answer using WhatsApp's native reply (quotes the triggering message)."""
        if self.event is None:
            await self.send(text)
        else:
            await self.bot.client.reply_message(text, quoted=self.event)

    async def send(self, text: str) -> None:
        """Plain message to this chat, no quote."""
        await self.bot.client.send_message(jid_from_str(self.chat), text)
