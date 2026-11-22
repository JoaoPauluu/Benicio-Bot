"""Send a sticker made from a KLIPY GIF: ``figurinha <termo>``."""

from whatsapp_bot.core.context import Context
from whatsapp_bot.core.registry import command
from whatsapp_bot.services.stickers import send_gif_sticker


@command("figurinha", help="manda uma figurinha animada de um gif", usage="<termo>", aliases=("sticker", "fig"))
async def figurinha(ctx: Context):
    if not ctx.args:
        await ctx.reply("Uso: figurinha <termo>")
        return
    if not ctx.bot.klipy.enabled:
        await ctx.reply("KLIPY_API_KEY não configurada no .env.")
        return
    query = " ".join(ctx.args)
    if not await send_gif_sticker(ctx, query):
        await ctx.reply(f"❌ Nenhum gif encontrado para \"{query}\".")
