from whatsapp_bot.registry import command
from whatsapp_bot.roles import Role
from whatsapp_bot.scheduler import describe, parse_agendar

USAGE = "HH:MM [diario|uteis|fds|seg,qua,..|AAAA-MM-DD|DD/MM/AAAA] <comando ou texto>"


@command("agendar", help="agenda uma mensagem/comando neste chat", usage=USAGE, role=Role.ADMIN)
async def agendar(ctx):
    try:
        hhmm, rule, payload = parse_agendar(ctx.args)
    except ValueError as e:
        await ctx.reply(f"❌ {e}\nUso: agendar {USAGE}")
        return
    item = ctx.bot.scheduler.add(ctx.chat, hhmm, rule, payload)
    if item is None:
        await ctx.reply("❌ Data/regra inválida ou já passou.")
        return
    await ctx.reply(f"⏰ Agendado: {describe(item)}")


@command("agendamentos", help="lista os agendamentos deste chat", role=Role.ADMIN)
async def agendamentos(ctx):
    items = ctx.store.schedules(ctx.chat)
    if not items:
        await ctx.reply("Nenhum agendamento neste chat.")
        return
    await ctx.reply("⏰ *Agendamentos*\n" + "\n".join(describe(i) for i in items))


@command("desagendar", help="remove um agendamento", usage="<id>", role=Role.ADMIN)
async def desagendar(ctx):
    if not ctx.args:
        await ctx.reply("Uso: desagendar <id> (veja os ids em *agendamentos*)")
        return
    ok = ctx.bot.scheduler.remove(ctx.args[0], ctx.chat)
    await ctx.reply("🗑️ Removido." if ok else "Não achei esse id neste chat.")
