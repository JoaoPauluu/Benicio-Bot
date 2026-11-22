"""Free-form chat with the AI: what happens when the bot is addressed without a command."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from whatsapp_bot.core.registry import feature
from whatsapp_bot.services.stickers import AI_STICKER_CHANCE, contextual_sticker

if TYPE_CHECKING:
    from whatsapp_bot.core.context import Context

AI_FEATURE = feature("ia", help="responde com IA quando mencionado sem comando", default=True)


async def chat_with_ai(ctx: Context) -> None:
    """Answer ``ctx.text`` with the AI (and sometimes a matching sticker)."""
    where = "um grupo do WhatsApp" if ctx.is_group else "uma conversa privada no WhatsApp"
    parts = []
    if ctx.incoming and ctx.incoming.quoted_text:
        parts.append(f"(Em resposta a: \"{ctx.incoming.quoted_text}\")")
    parts.append(f"{ctx.sender_name}: {ctx.text}")
    extra = [f"Você está em {where}.", *ctx.chat_instructions()]
    contents = "\n".join(parts)
    await ctx.reply(await ctx.ai.ask(contents, *extra))
    if random.random() < AI_STICKER_CHANCE:
        await contextual_sticker(ctx, contents, *extra)
