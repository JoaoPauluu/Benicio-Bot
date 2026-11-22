"""Owner-only role management: give/take global roles (admin, mídia, …)."""

import re

from whatsapp_bot.incoming import phone_variants
from whatsapp_bot.registry import command
from whatsapp_bot.roles import GRANTABLE, LABELS, Role, describe, from_values, parse_role

USAGE = "[dar|tirar <cargo> <@pessoa|número>]"
GIVE = {"dar", "add", "adicionar"}
TAKE = {"tirar", "remover", "rm"}


def _target(ctx, extra_args: list[str]) -> set[str]:
    """Who the command is about: a mention, a typed number, or the author of the quoted message."""
    inc = ctx.incoming
    if inc is not None:
        mentioned = inc.mentioned - ctx.bot.identity.bot_ids
        if mentioned:
            return set(mentioned)
    for arg in extra_args:
        digits = re.sub(r"\D", "", arg)
        if len(digits) >= 8:
            return phone_variants(digits)
    if inc is not None and inc.quoted_participant and inc.quoted_participant not in ctx.bot.identity.bot_ids:
        return {inc.quoted_participant}
    return set()


def _choices() -> str:
    return ", ".join(LABELS[r] for r in sorted(GRANTABLE, key=list(Role).index))


@command("cargo", help="lista/dá/tira cargos (globais)", usage=USAGE, role=Role.OWNER, aliases=("cargos",))
async def cargo(ctx):
    if not ctx.args:
        holders = ctx.store.role_holders()
        if not holders:
            await ctx.reply(f"Ninguém tem cargo ainda. Cargos: {_choices()}.")
            return
        lines = ["👥 *Cargos*"] + [
            f"• {'/'.join(p['ids'])}: {describe(from_values(p['roles']))}"
            for p in holders
        ]
        await ctx.reply("\n".join(lines))
        return

    action = ctx.args[0].lower()
    if action not in GIVE | TAKE or len(ctx.args) < 2:
        await ctx.reply(f"Uso: cargo {USAGE}\nCargos: {_choices()}")
        return
    role = parse_role(ctx.args[1])
    if role not in GRANTABLE:
        await ctx.reply(f"Cargo desconhecido. Disponíveis: {_choices()}")
        return
    ids = _target(ctx, ctx.args[2:])
    if not ids:
        await ctx.reply("Diga quem: mencione a pessoa, escreva o número ou responda a uma mensagem dela.")
        return

    who = "/".join(sorted(ids))
    if action in GIVE:
        ctx.store.grant_role(ids, role.value)
        await ctx.reply(f"✅ {who} agora é *{LABELS[role]}*.")
    elif ctx.store.revoke_role(ids, role.value):
        await ctx.reply(f"🗑️ {who} não é mais *{LABELS[role]}*.")
    else:
        await ctx.reply(f"{who} não tinha o cargo *{LABELS[role]}*.")
