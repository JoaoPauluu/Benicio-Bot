"""Generic per-chat on/off switches for any registered feature."""

from whatsapp_bot.core.context import Context
from whatsapp_bot.core.registry import command
from whatsapp_bot.core.roles import Role

ON = {"on", "ligar", "liga", "sim", "1"}
OFF = {"off", "desligar", "desliga", "nao", "não", "0"}


@command("recurso", help="liga/desliga recursos neste chat", usage="[nome on|off]", role=Role.ADMIN,
         aliases=("recursos", "feature", "features"))
async def recurso(ctx: Context):
    feats = ctx.bot.registry.features
    if not ctx.args:
        lines = ["⚙️ *Recursos neste chat*"]
        for f in feats.values():
            state = "✅" if ctx.store.get_flag(ctx.chat, f.name, f.default) else "⛔"
            lines.append(f"{state} *{f.name}* — {f.help}")
        await ctx.reply("\n".join(lines))
        return
    name = ctx.args[0].lower()
    if name not in feats:
        await ctx.reply(f"Recurso desconhecido. Disponíveis: {', '.join(feats)}")
        return
    if len(ctx.args) > 1 and ctx.args[1].lower() in ON | OFF:
        value = ctx.args[1].lower() in ON
    else:
        value = not ctx.store.get_flag(ctx.chat, name, feats[name].default)
    ctx.store.set_flag(ctx.chat, name, value)
    await ctx.reply(f"⚙️ {name}: {'ligado' if value else 'desligado'}")
