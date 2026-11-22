"""Ask the AI directly (handy in schedules, where a plain mention isn't possible)."""

from whatsapp_bot.core.context import Context
from whatsapp_bot.core.registry import command
from whatsapp_bot.services.conversation import chat_with_ai


@command("ia", help="pergunta direto para a IA (útil em agendamentos)", usage="<texto>", aliases=("ai",))
async def ia(ctx: Context):
    if not ctx.args:
        await ctx.reply("Uso: ia <pergunta>")
        return
    ctx.text = ctx.rest
    await chat_with_ai(ctx)
