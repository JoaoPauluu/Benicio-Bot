"""The router: decides what to do with each incoming message."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Coroutine
from typing import Any

from .ai import AI
from .aio import AIO
from .config import Settings
from .context import Context
from .incoming import Identity, Incoming, parse_event, phone_variants
from .registry import REGISTRY, Registry, load_commands
from .roles import Role, allowed, describe, expand, from_values
from .store import Store

log = logging.getLogger(__name__)

STALE_SECONDS = 60  # ignore messages older than this when (re)connecting


class Bot:
    def __init__(self, settings: Settings, client: Any, ai: AI | None = None, store: Store | None = None,
                 registry: Registry | None = None, aio: AIO | None = None):
        self.settings = settings
        self.client = client
        self.ai = ai or AI(settings)
        self.store = store or Store(settings.data_dir / "state.json")
        self.registry = registry or load_commands()
        self.aio = aio or AIO(settings.aio_base_url, settings.baixar_timeout)
        self.identity = Identity(settings.owner_number)
        self.started_at = time.time()
        self.scheduler = None  # set by main
        self._tasks: set[asyncio.Task] = set()

    # ---- lifecycle -----------------------------------------------------
    async def on_connected(self) -> None:
        me = await self.client.get_me()
        self.identity.set_bot(me.JID.User, me.LID.User)
        log.info("connected as %s (lid %s)", me.JID.User, me.LID.User or "?")
        from neonize.utils.jid import build_jid

        for number in phone_variants(self.settings.owner_number):
            try:
                lid = await self.client.get_lid_from_pn(build_jid(number))
                if lid.User:
                    self.identity.owner_ids.add(lid.User)
            except Exception:
                log.debug("could not resolve owner LID for %s yet", number, exc_info=True)
        log.info("owner ids: %s", sorted(self.identity.owner_ids))

    def spawn(self, coro: Coroutine) -> asyncio.Task:
        """Run work in the background without blocking message handling."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._task_done)
        return task

    def _task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception():
            log.error("background task failed", exc_info=task.exception())

    async def drain(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    # ---- incoming messages ---------------------------------------------
    async def on_message(self, ev: Any) -> None:
        try:
            await self.handle(parse_event(ev), ev)
        except Exception:
            log.exception("error handling message")

    async def handle(self, inc: Incoming, ev: Any = None) -> None:
        log.info("msg chat=%s from=%s alt=%s name=%r group=%s mentioned=%s text=%r",
                 inc.chat, inc.sender, inc.sender_alt or "-", inc.sender_name, inc.is_group,
                 sorted(inc.mentioned), inc.text[:80])
        if inc.from_me:
            log.info("  -> ignored: sent by the bot account itself")
            return
        if inc.timestamp < self.started_at - STALE_SECONDS:
            log.info("  -> ignored: stale (sent before the bot started)")
            return
        self.identity.learn(inc)
        roles = self.user_roles(inc)

        if inc.is_group:
            triggered = self.identity.mentions_bot(inc)
        else:
            triggered = bool(roles) or self.settings.allow_dms_from_others
        log.info("  -> roles=%s triggered=%s (bot ids %s, owner ids %s)", sorted(roles), triggered,
                 sorted(self.identity.bot_ids), sorted(self.identity.owner_ids))
        body = self.identity.strip_mentions(inc.text) if triggered else inc.text

        ctx = Context(self, inc.chat, text=body, roles=roles, is_group=inc.is_group,
                      triggered=triggered, incoming=inc, event=ev)

        for lst in self.registry.listeners:
            if not allowed(roles, lst.roles):
                continue
            try:
                await lst.func(ctx)
            except Exception:
                log.exception("listener %s failed", lst.name)

        if triggered and not ctx.handled:
            await self.dispatch(ctx)

    @staticmethod
    def ids_of(inc: Incoming) -> set[str]:
        """Every id the sender may be stored under (LID, phone and its 9th-digit variant)."""
        ids = {inc.sender, inc.sender_alt} - {""}
        for i in list(ids):
            ids |= phone_variants(i)
        return ids

    def user_roles(self, inc: Incoming) -> frozenset[Role]:
        ids = self.ids_of(inc)
        roles = from_values(self.store.roles_of(ids))
        if self.identity.is_owner(inc):
            roles.add(Role.OWNER)
        else:
            self.store.link_ids(ids)  # remember LID <-> phone for people with roles
        return expand(roles)

    async def dispatch(self, ctx: Context) -> None:
        words = ctx.text.split()
        cmd = self.registry.find(words[0].lstrip("/!")) if words else None
        if cmd is not None:
            if not allowed(ctx.roles, cmd.roles):
                await ctx.reply(f"🚫 Você não tem permissão para usar *{cmd.name}* (requer: {describe(cmd.roles)}).")
                return
            if cmd.group_only and not ctx.is_group:
                await ctx.reply("Esse comando só funciona em grupos.")
                return
            ctx.command, ctx.args = cmd.name, words[1:]
            await cmd.func(ctx)
            return
        if not ctx.text:
            await ctx.reply("Oi! Me mande *ajuda* para ver os comandos.")
            return
        if not self.store.get_flag(ctx.chat, "ia", default=True):
            return
        await self.chat_with_ai(ctx)

    async def chat_with_ai(self, ctx: Context) -> None:
        where = "um grupo do WhatsApp" if ctx.is_group else "uma conversa privada no WhatsApp"
        parts = []
        if ctx.incoming and ctx.incoming.quoted_text:
            parts.append(f"(Em resposta a: \"{ctx.incoming.quoted_text}\")")
        parts.append(f"{ctx.sender_name}: {ctx.text}")
        extra = [f"Você está em {where}."]
        if prompt := self.store.get_prompt(ctx.chat):
            extra.append(f"Instruções específicas deste chat:\n{prompt}")
        await ctx.reply(await self.ai.ask("\n".join(parts), *extra))

    # ---- scheduled payloads --------------------------------------------
    async def run_payload(self, chat: str, payload: str) -> None:
        """A scheduled payload is a command (e.g. 'bomdia') or plain text."""
        ctx = Context(self, chat, text=payload, roles=expand({Role.OWNER}),
                      is_group=chat.endswith("@g.us"), triggered=True)
        words = payload.split()
        if words and self.registry.find(words[0].lstrip("/!")):
            await self.dispatch(ctx)
        else:
            await ctx.send(payload)
