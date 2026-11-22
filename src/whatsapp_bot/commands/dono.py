"""Owner hooks: special actions that run on *every* message the owner sends.

Template — add your own reactions here. Runs in DMs and groups, mentioned or not.
"""

import logging

from whatsapp_bot.registry import command, listener
from whatsapp_bot.roles import Role

log = logging.getLogger(__name__)


@listener(role=Role.OWNER)
async def owner_seen(ctx):
    # Example hook point. e.g.:
    # if ctx.incoming.text == "!ping": await ctx.reply("pong")
    log.debug("owner message in %s: %s", ctx.chat, ctx.incoming.text if ctx.incoming else "")


@command("ping", help="testa se o bot está vivo", role=Role.ADMIN)
async def ping(ctx):
    await ctx.reply("pong 🏓")
