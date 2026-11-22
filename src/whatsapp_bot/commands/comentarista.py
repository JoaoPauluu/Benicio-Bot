"""Commentator mode: every N messages in a group, the AI comments on them."""

import random
from collections import defaultdict, deque

from whatsapp_bot.core.context import Context
from whatsapp_bot.core.registry import command, feature, listener
from whatsapp_bot.core.roles import Role
from whatsapp_bot.services.stickers import COMMENT_BOTH, COMMENT_STICKER_ONLY, contextual_sticker

FEATURE = feature("comentarista", help="comenta a conversa a cada N mensagens")

_buffers: dict[str, deque] = defaultdict(deque)


@command("comentarista", help="liga/desliga o modo comentarista neste grupo", role=Role.ADMIN, group_only=True,
         aliases=("commentator",))
async def toggle(ctx: Context):
    on = not ctx.store.get_flag(ctx.chat, FEATURE.name)
    ctx.store.set_flag(ctx.chat, FEATURE.name, on)
    _buffers.pop(ctx.chat, None)
    n = ctx.settings.comentarista_interval
    await ctx.reply(f"🎙️ Comentarista {'ligado' if on else 'desligado'}" + (f" (a cada {n} mensagens)." if on else "."))


@listener()
async def count_messages(ctx: Context):
    inc = ctx.incoming
    if not ctx.is_group or inc is None or not inc.text:
        return
    if not ctx.store.get_flag(ctx.chat, FEATURE.name):
        return
    cmd, _ = ctx.bot.registry.match(ctx.text)
    if cmd is not None and cmd.func is toggle:
        return  # the toggle command itself (any alias) doesn't count as conversation
    buf = _buffers[ctx.chat]
    buf.append(f"{inc.sender_name}: {inc.text}")
    n = ctx.settings.comentarista_interval
    if len(buf) < n:
        return
    transcript = "\n".join(buf)
    buf.clear()
    ctx.bot.spawn(_comment(ctx, transcript))


async def _comment(ctx: Context, transcript: str) -> None:
    extra = [ctx.ai.read_prompt("comentarista"), *ctx.chat_instructions()]
    contents = f"Últimas mensagens do grupo:\n{transcript}"
    roll = random.random()
    sticker_only = COMMENT_BOTH <= roll < COMMENT_BOTH + COMMENT_STICKER_ONLY
    if sticker_only and await contextual_sticker(ctx, contents, *extra):
        return  # sticker instead of text; no gif found -> fall back to the text comment
    text = await ctx.ai.ask(contents, *extra)
    await ctx.reply(text)  # quotes the message that completed the batch
    if roll < COMMENT_BOTH:
        await contextual_sticker(ctx, contents, *extra)
