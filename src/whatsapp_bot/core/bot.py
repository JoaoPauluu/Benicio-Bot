"""The router: decides what to do with each incoming message."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from neonize.utils.jid import build_jid

from whatsapp_bot.config import Settings
from whatsapp_bot.core.context import Context
from whatsapp_bot.core.registry import Registry, load_commands
from whatsapp_bot.core.roles import Role, allowed, denied_message, expand, from_values
from whatsapp_bot.core.store import Store
from whatsapp_bot.services.ai import AI
from whatsapp_bot.services.aio import AIO
from whatsapp_bot.services.conversation import AI_FEATURE, chat_with_ai
from whatsapp_bot.services.history import MessageLog
from whatsapp_bot.services.klipy import Klipy
from whatsapp_bot.whatsapp.identity import Identity, phone_variants, sender_ids
from whatsapp_bot.whatsapp.incoming import Incoming, parse_event
from whatsapp_bot.whatsapp.jid import is_group_jid

if TYPE_CHECKING:
    from whatsapp_bot.core.scheduler import Scheduler

log = logging.getLogger(__name__)

STALE_SECONDS = 60  # ignore messages older than this when (re)connecting


class Bot:
    def __init__(self, settings: Settings, client: Any, ai: AI | None = None, store: Store | None = None,
                 registry: Registry | None = None, aio: AIO | None = None, klipy: Klipy | None = None):
        self.settings = settings
        self.client = client
        self.ai = ai or AI(settings)
        self.store = store or Store(settings.data_dir / "state.json")
        self.registry = registry or load_commands()
        self.aio = aio or AIO(settings.aio_base_url, settings.baixar_timeout)
        self.klipy = klipy or Klipy(settings.klipy_api_key, settings.klipy_locale, settings.klipy_content_filter)
        self.identity = Identity(settings.owner_number)
        self.history = MessageLog()
        self.started_at = time.time()
        self.scheduler: Scheduler | None = None  # set by main
        self._tasks: set[asyncio.Task] = set()

    # ---- lifecycle -----------------------------------------------------
    async def on_connected(self) -> None:
        me = await self.client.get_me()
        self.identity.set_bot(me.JID.User, me.LID.User)
        log.info("connected as %s (lid %s)", me.JID.User, me.LID.User or "?")
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
        """Wait for every background task (used by tests)."""
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
        self.history.record(inc.chat, inc.id, inc.sender_name, inc.text, inc.quoted_id)
        roles = self.user_roles(inc)

        if inc.is_group:
            triggered = self.identity.mentions_bot(inc)
        else:
            triggered = bool(roles) or self.settings.allow_dms_from_others
        log.info("  -> roles=%s triggered=%s (bot ids %s, owner ids %s)", sorted(roles), triggered,
                 sorted(self.identity.bot_ids), sorted(self.identity.owner_ids))
        body = self.identity.strip_mentions(inc.text) if triggered else inc.text

        ctx = Context(self, inc.chat, text=body, roles=roles, is_group=inc.is_group, incoming=inc, event=ev)

        for lst in self.registry.listeners:
            if not allowed(roles, lst.roles):
                continue
            try:
                await lst.func(ctx)
            except Exception:
                log.exception("listener %s failed", lst.name)

        if triggered and not ctx.handled:
            await self.dispatch(ctx)

    def user_roles(self, inc: Incoming) -> frozenset[Role]:
        ids = sender_ids(inc)
        roles = from_values(self.store.roles_of(ids))
        if self.identity.is_owner(inc):
            roles.add(Role.OWNER)
        else:
            self.store.link_ids(ids)  # remember LID <-> phone for people with roles
        return expand(roles)

    async def dispatch(self, ctx: Context) -> None:
        cmd, args = self.registry.match(ctx.text)
        if cmd is not None:
            if not allowed(ctx.roles, cmd.roles):
                await ctx.reply(denied_message(cmd.name, cmd.roles))
                return
            if cmd.group_only and not ctx.is_group:
                await ctx.reply("Esse comando só funciona em grupos.")
                return
            ctx.args = args
            await cmd.func(ctx)
            return
        if not ctx.text:
            await ctx.reply("Oi! Me mande *ajuda* para ver os comandos.")
            return
        if self.store.get_flag(ctx.chat, AI_FEATURE.name, AI_FEATURE.default):
            await chat_with_ai(ctx)

    # ---- scheduled payloads --------------------------------------------
    async def run_payload(self, chat: str, payload: str) -> None:
        """A scheduled payload is a command (e.g. 'bomdia') or plain text. Runs with owner rights."""
        ctx = Context(self, chat, text=payload, roles=expand({Role.OWNER}), is_group=is_group_jid(chat))
        cmd, _ = self.registry.match(payload)
        if cmd is not None:
            await self.dispatch(ctx)
        else:
            await ctx.send(payload)
