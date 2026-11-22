from whatsapp_bot.registry import command


@command("prompt", help="mostra/define/limpa o prompt extra da IA neste chat", usage="[texto|limpar]",
         owner_only=True)
async def prompt(ctx):
    if not ctx.args:
        current = ctx.store.get_prompt(ctx.chat)
        await ctx.reply(f"📝 Prompt deste chat:\n{current}" if current else "Este chat usa só o prompt base.")
        return
    if ctx.args == ["limpar"]:
        ctx.store.set_prompt(ctx.chat, "")
        await ctx.reply("📝 Prompt do chat removido.")
        return
    text = ctx.text.split(None, 1)[1]  # keep original spacing/case
    ctx.store.set_prompt(ctx.chat, text)
    await ctx.reply("📝 Prompt do chat atualizado.")
