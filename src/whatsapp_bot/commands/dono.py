"""Owner hooks: special actions that run on *every* message the owner sends.

Template — nothing is registered by default. Runs in DMs and groups, mentioned
or not. Uncomment and adapt, e.g.:

    from whatsapp_bot.core.context import Context
    from whatsapp_bot.core.registry import listener
    from whatsapp_bot.core.roles import Role

    @listener(role=Role.OWNER)
    async def owner_seen(ctx: Context):
        if ctx.incoming and ctx.incoming.text == "!ping":
            await ctx.reply("pong")
            ctx.handled = True   # skip command dispatch / AI for this message
"""
