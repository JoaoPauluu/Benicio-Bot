import time

from whatsapp_bot.registry import command
from whatsapp_bot.roles import Role


def format_uptime(seconds: float) -> str:
    seconds = int(seconds)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = [f"{d}d"] if d else []
    parts += [f"{h}h"] if h or d else []
    parts += [f"{m}min", f"{s}s"]
    return " ".join(parts)


@command("status", help="tempo online do bot", role=Role.ADMIN)
async def status(ctx):
    store = ctx.store
    await ctx.reply(
        "🤖 *Status*\n"
        f"• Online há: {format_uptime(time.time() - ctx.bot.started_at)}\n"
        f"• Modelo: {ctx.ai.model}\n"
        f"• Agendamentos: {len(store.schedules())}\n"
        f"• Grupos com comentarista: {len(store.chats_with_flag('comentarista'))}"
    )
