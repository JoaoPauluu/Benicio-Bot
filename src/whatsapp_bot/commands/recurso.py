"""Generic per-chat on/off switches for any registered feature."""

from whatsapp_bot.registry import REGISTRY, command, feature
from whatsapp_bot.roles import Role

feature("ia", help="responde com IA quando mencionado sem comando", default=True)

ON = {"on", "ligar", "liga", "sim", "1"}
OFF = {"off", "desligar", "desliga", "nao", "não", "0"}


@command("recurso", help="liga/desliga recursos neste chat", usage="[nome on|off]", role=Role.ADMIN,
         aliases=("recursos", "feature", "features"))
async def recurso(ctx):
    feats = REGISTRY.features
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
