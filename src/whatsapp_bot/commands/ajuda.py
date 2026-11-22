from whatsapp_bot.registry import REGISTRY, command
from whatsapp_bot.roles import allowed, describe


@command("ajuda", help="lista os comandos", aliases=("help", "comandos"))
async def ajuda(ctx):
    lines = ["*Comandos*" + (" (mencione o bot: @bot <comando>)" if ctx.is_group else "")]
    for cmd in REGISTRY.unique_commands():
        if not allowed(ctx.roles, cmd.roles):
            continue
        usage = f" {cmd.usage}" if cmd.usage else ""
        lock = f" 🔒 {describe(cmd.roles)}" if cmd.roles else ""
        lines.append(f"• *{cmd.name}*{usage} — {cmd.help}{lock}")
    lines.append("\nQualquer outra mensagem depois da menção vai para a IA.")
    await ctx.reply("\n".join(lines))
