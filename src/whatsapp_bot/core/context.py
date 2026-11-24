"""What every command / listener receives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from whatsapp_bot.core.roles import Role
from whatsapp_bot.whatsapp.jid import jid_from_str

BOT_NAME = "Benício"

if TYPE_CHECKING:
    from whatsapp_bot.config import Settings
    from whatsapp_bot.core.bot import Bot
    from whatsapp_bot.core.store import Store
    from whatsapp_bot.services.ai import AI
    from whatsapp_bot.whatsapp.incoming import Incoming


@dataclass
class Context:
    bot: Bot
    chat: str
    text: str = ""                 # message text with the bot mention removed
    args: list[str] = field(default_factory=list)   # words after the command name
    roles: frozenset[Role] = frozenset()   # already expanded (owner/admin include the others)
    is_group: bool = False
    incoming: Incoming | None = None
    event: Any = None              # raw neonize MessageEv (None for scheduled runs)
    handled: bool = False          # a listener set this: skip command dispatch / AI

    @property
    def is_owner(self) -> bool:
        return Role.OWNER in self.roles

    @property
    def store(self) -> Store:
        return self.bot.store

    @property
    def ai(self) -> AI:
        return self.bot.ai

    @property
    def settings(self) -> Settings:
        return self.bot.settings

    @property
    def sender_name(self) -> str:
        return self.incoming.sender_name if self.incoming else "dono"

    @property
    def rest(self) -> str:
        """Everything after the command name, with the original spacing and case."""
        parts = self.text.split(None, 1)
        return parts[1] if len(parts) > 1 else ""

    def chat_instructions(self) -> list[str]:
        """Extra system instructions set for this chat with the ``prompt`` command (may be empty)."""
        prompt = self.store.get_prompt(self.chat)
        return [f"Instruções específicas deste chat:\n{prompt}"] if prompt else []

    async def reply(self, text: str) -> None:
        """Answer using WhatsApp's native reply (quotes the triggering message)."""
        if self.event is None:
            await self.send(text)
        else:
            resp = await self.bot.client.reply_message(text, quoted=self.event)
            self._remember_sent(resp, text, self.incoming.id if self.incoming else "")

    async def send(self, text: str) -> None:
        """Plain message to this chat, no quote."""
        resp = await self.bot.client.send_message(jid_from_str(self.chat), text)
        self._remember_sent(resp, text)

    def _remember_sent(self, resp: Any, text: str, parent_id: str = "") -> None:
        """Log the bot's own message so replies to it can rebuild the chain."""
        msg_id = getattr(resp, "ID", "")
        if isinstance(msg_id, str) and msg_id:
            self.bot.history.record(self.chat, msg_id, BOT_NAME, text, parent_id)

    async def send_sticker(self, data: bytes) -> None:
        """Convert ``data`` (GIF/MP4/WebP/image) to a WhatsApp sticker and send it, quoting the trigger."""
        await self.bot.client.send_sticker(jid_from_str(self.chat), data, quoted=self.event,
                                           packname=self.settings.sticker_pack, enforce_not_broken=True)
