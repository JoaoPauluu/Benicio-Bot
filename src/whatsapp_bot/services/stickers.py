"""GIF stickers from KLIPY: on demand (``figurinha``) or picked by Gemini from the conversation."""

from __future__ import annotations

import logging
import random
import re
from typing import TYPE_CHECKING

from whatsapp_bot.services.klipy import KlipyError

if TYPE_CHECKING:
    from whatsapp_bot.core.context import Context

log = logging.getLogger(__name__)

AI_STICKER_CHANCE = 1 / 8      # ia command / plain mention: sticker together with the text
COMMENT_BOTH = 1 / 10          # commentator: text + sticker
COMMENT_STICKER_ONLY = 1 / 5   # commentator: sticker instead of text

MEME_TERMS = ("meme", "shitpost", "reaction", "cursed", "bruh")
_MEME_RE = re.compile(r"\b(" + "|".join(MEME_TERMS) + r")\b", re.IGNORECASE)


def without_meme_terms(query: str) -> str:
    return " ".join(_MEME_RE.sub(" ", query).split())


async def send_gif_sticker(ctx: Context, query: str) -> bool:
    """Search ``query`` on KLIPY, send a random result as a sticker. False if nothing found or on error."""
    klipy = ctx.bot.klipy
    if not klipy.enabled or not query.strip():
        return False
    try:
        urls = await klipy.search(query)
        if not urls and (plain := without_meme_terms(query)) and plain != query:
            urls = await klipy.search(plain)
        if not urls:
            log.info("no gif found for %r", query)
            return False
        data = await klipy.download(random.choice(urls))
        await ctx.send_sticker(data)
        return True
    except KlipyError as e:
        log.warning("klipy failed for %r: %s", query, e)
    except Exception:
        log.exception("could not send sticker for %r", query)
    return False


async def contextual_sticker(ctx: Context, contents: str, *extra: str) -> bool:
    """Let Gemini pick a GIF query for ``contents`` and send it as a sticker. Silent on failure."""
    if not ctx.bot.klipy.enabled:
        return False
    query = await ctx.ai.gif_query(contents, *extra)
    if not query:
        return False
    log.info("sticker query: %r", query)
    return await send_gif_sticker(ctx, query)
