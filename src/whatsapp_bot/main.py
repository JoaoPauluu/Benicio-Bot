"""Entry point: `uv run whatsapp-bot` (or `uv run python -m whatsapp_bot.main`)."""

from __future__ import annotations

import asyncio
import logging

from neonize.aioze.client import NewAClient
from neonize.aioze.events import ConnectedEv, MessageEv, PairStatusEv
from neonize.events import UndecryptableMessageEv  # not re-exported by aioze; same event registry

from .bot import Bot
from .config import load_settings
from .scheduler import Scheduler

log = logging.getLogger("whatsapp_bot")


async def amain() -> None:
    settings = load_settings()
    if not settings.owner_number:
        log.warning("OWNER_NUMBER not set: owner-only commands will never run")

    client = NewAClient(str(settings.data_dir / "session.db"))
    bot = Bot(settings, client)
    bot.scheduler = Scheduler(bot)

    @client.event(ConnectedEv)
    async def _on_connected(_c: NewAClient, _ev: ConnectedEv) -> None:
        await bot.on_connected()

    @client.event(PairStatusEv)
    async def _on_pair(_c: NewAClient, ev: PairStatusEv) -> None:
        log.info("paired as %s", ev.ID.User)

    @client.event(UndecryptableMessageEv)
    async def _on_undecryptable(_c: NewAClient, ev: UndecryptableMessageEv) -> None:
        src = ev.Info.MessageSource
        log.warning(
            "could not read message %s in %s from %s (unavailable=%s). The sender's phone did not encrypt "
            "it for this linked device; this usually stops a few minutes after pairing.",
            ev.Info.ID, src.Chat.User, src.Sender.User, ev.IsUnavailable,
        )

    @client.event(MessageEv)
    async def _on_message(_c: NewAClient, ev: MessageEv) -> None:
        await bot.on_message(ev)

    bot.scheduler.start()
    await client.connect()  # prints a QR code in the terminal on first run
    await client.idle()


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
