"""What the bot sends when Gemini fails (high demand, rate limit, ...): a random funny text and/or sticker."""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

from whatsapp_bot.services.stickers import send_gif_sticker

if TYPE_CHECKING:
    from whatsapp_bot.core.context import Context

log = logging.getLogger(__name__)

PROMPT_NAME = "erro"  # prompts/erro.md, re-read on every failure so edits apply live
DEFAULT_MESSAGE = "deu tela azul na minha cabesa aq amigo tenta dnv daqui a pouco ok 👍"
# Fixed queries: Gemini can't choose a sticker while it is down.
STICKER_QUERIES = ("shitpost", "confused dog", "this is fine")

TEXT_ONLY, STICKER_ONLY, BOTH = "text", "sticker", "both"
MODES = (TEXT_ONLY, STICKER_ONLY, BOTH)


def parse_messages(text: str) -> list[str]:
    """Messages of the prompt file: each "- " bullet, plus the indented lines right below it."""
    messages: list[list[str]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("- "):
            current = [line[2:].strip()]
            messages.append(current)
        elif current is not None and line[:1].isspace() and line.strip():
            current.append(line.strip())
        else:
            current = None  # anything else ends the current message
    return [msg for lines in messages if (msg := "\n".join(ln for ln in lines if ln))]


def pick_message(ctx: Context) -> str:
    return random.choice(parse_messages(ctx.ai.read_prompt(PROMPT_NAME)) or [DEFAULT_MESSAGE])


async def send_ai_error(ctx: Context, prefix: str = "") -> None:
    """Reply with a random error text, a random sticker, or both. Never sends nothing."""
    mode = random.choice(MODES) if ctx.bot.klipy.enabled else TEXT_ONLY
    if mode != TEXT_ONLY:
        sent = await send_gif_sticker(ctx, random.choice(STICKER_QUERIES))
        if mode == STICKER_ONLY and sent:
            return
    await ctx.reply(prefix + pick_message(ctx))
