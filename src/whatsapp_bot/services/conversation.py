"""Free-form chat with the AI: what happens when the bot is addressed without a command."""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

from whatsapp_bot.core.registry import feature
from whatsapp_bot.services.fallback import send_ai_error
from whatsapp_bot.services.stickers import AI_STICKER_CHANCE, contextual_sticker

if TYPE_CHECKING:
    from whatsapp_bot.core.context import Context

log = logging.getLogger(__name__)

AI_FEATURE = feature("ia", help="responde com IA quando mencionado sem comando", default=True)
CHAIN_LIMIT = 6  # earlier messages of the reply chain passed to the AI


def reply_context(ctx: Context) -> list[str]:
    """Lines describing what the message replies to: the reply chain, or just the quoted text."""
    inc = ctx.incoming
    if inc is None or not (inc.quoted_id or inc.quoted_text):
        return []
    chain = ctx.bot.history.chain(ctx.chat, inc.quoted_id, CHAIN_LIMIT)
    if chain:
        return ["(Conversa anterior, respondendo em cadeia:)", *(f"{e.name}: {e.text}" for e in chain)]
    if inc.quoted_text:  # chain unknown (e.g. after a restart): only what WhatsApp sent
        return [f"(Em resposta a: \"{inc.quoted_text}\")"]
    return []


async def chat_with_ai(ctx: Context) -> None:
    """Answer ``ctx.text`` with the AI (and sometimes a matching sticker)."""
    where = "um grupo do WhatsApp" if ctx.is_group else "uma conversa privada no WhatsApp"
    parts = reply_context(ctx)
    parts.append(f"{ctx.sender_name}: {ctx.text}")
    extra = [f"Você está em {where}.", *ctx.chat_instructions()]
    contents = "\n".join(parts)
    log.debug("ai contents: %r", contents)
    text = await ctx.ai.ask(contents, *extra)
    if text is None:
        await send_ai_error(ctx)
        return
    await ctx.reply(text)
    if random.random() < AI_STICKER_CHANCE:
        await contextual_sticker(ctx, contents, *extra)
