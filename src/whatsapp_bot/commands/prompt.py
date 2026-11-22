"""Per-chat extra instructions for the AI."""

from whatsapp_bot.core.context import Context
from whatsapp_bot.core.registry import command
from whatsapp_bot.core.roles import Role

CLEAR = {"limpar", "clear"}


@command("prompt", help="mostra/define/limpa o prompt extra da IA neste chat", usage="[texto|limpar]",
         role=Role.ADMIN)
async def prompt(ctx: Context):
    if not ctx.args:
        current = ctx.store.get_prompt(ctx.chat)
        await ctx.reply(f"📝 Prompt deste chat:\n{current}" if current else "Este chat usa só o prompt base.")
        return
    if len(ctx.args) == 1 and ctx.args[0].lower() in CLEAR:
        ctx.store.set_prompt(ctx.chat, "")
        await ctx.reply("📝 Prompt do chat removido.")
        return
    ctx.store.set_prompt(ctx.chat, ctx.rest)  # keep original spacing/case
    await ctx.reply("📝 Prompt do chat atualizado.")
