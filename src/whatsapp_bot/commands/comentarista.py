"""Commentator mode: every N messages in a group, the AI comments on them."""

from collections import defaultdict, deque

from whatsapp_bot.registry import command, feature, listener
from whatsapp_bot.roles import Role

FEATURE = feature("comentarista", help="comenta a conversa a cada N mensagens")

_buffers: dict[str, deque] = defaultdict(deque)


@command("comentarista", help="liga/desliga o modo comentarista neste grupo", role=Role.ADMIN, group_only=True)
async def toggle(ctx):
    on = not ctx.store.get_flag(ctx.chat, FEATURE.name)
    ctx.store.set_flag(ctx.chat, FEATURE.name, on)
    _buffers.pop(ctx.chat, None)
    n = ctx.settings.comentarista_interval
    await ctx.reply(f"🎙️ Comentarista {'ligado' if on else 'desligado'}" + (f" (a cada {n} mensagens)." if on else "."))


@listener()
async def count_messages(ctx):
    inc = ctx.incoming
    if not ctx.is_group or inc is None or not inc.text:
        return
    if not ctx.store.get_flag(ctx.chat, FEATURE.name):
        return
    if ctx.command == "comentarista" or ctx.text.split()[:1] == ["comentarista"]:
        return
    buf = _buffers[ctx.chat]
    buf.append(f"{inc.sender_name}: {inc.text}")
    n = ctx.settings.comentarista_interval
    if len(buf) < n:
        return
    transcript = "\n".join(buf)
    buf.clear()
    ctx.bot.spawn(_comment(ctx, transcript))


async def _comment(ctx, transcript: str) -> None:
    extra = [ctx.ai.read_prompt("comentarista")]
    if prompt := ctx.store.get_prompt(ctx.chat):
        extra.append(f"Instruções específicas deste chat:\n{prompt}")
    text = await ctx.ai.ask(f"Últimas mensagens do grupo:\n{transcript}", *extra)
    await ctx.reply(text)  # quotes the message that completed the batch
