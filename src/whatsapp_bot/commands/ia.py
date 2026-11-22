from whatsapp_bot.registry import command


@command("ia", help="pergunta direto para a IA (útil em agendamentos)", usage="<texto>", aliases=("ai",))
async def ia(ctx):
    if not ctx.args:
        await ctx.reply("Uso: ia <pergunta>")
        return
    ctx.text = ctx.text.split(None, 1)[1]
    await ctx.bot.chat_with_ai(ctx)
