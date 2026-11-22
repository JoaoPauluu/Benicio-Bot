from whatsapp_bot.registry import REGISTRY, command
from whatsapp_bot.roles import allowed, describe


@command("ajuda", help="lista os comandos", aliases=("help", "comandos", "commands"))
async def ajuda(ctx):
    lines = ["*Comandos*" + (" (mencione o bot: @bot <comando>)" if ctx.is_group else "")]
    for cmd in REGISTRY.unique_commands():
        if not allowed(ctx.roles, cmd.roles):
            continue
        usage = f" {cmd.usage}" if cmd.usage else ""
        lock = f" 🔒 {describe(cmd.roles)}" if cmd.roles else ""
        aka = f" ({', '.join(cmd.aliases)})" if cmd.aliases else ""
        lines.append(f"• *{cmd.name}*{aka}{usage} — {cmd.help}{lock}")
    lines.append("\nQualquer outra mensagem depois da menção vai para a IA.")
    await ctx.reply("\n".join(lines))
