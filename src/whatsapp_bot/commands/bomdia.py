"""Daily good-morning quote scraped from a Portuguese site (BOMDIA_URL)."""

import hashlib
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from whatsapp_bot.core.context import Context
from whatsapp_bot.core.registry import command
from whatsapp_bot.services.fallback import send_ai_error

log = logging.getLogger(__name__)

# pensador.com markup: each quote is
#   <div class="thought-card"><p class="frase">..</p>..<span class="author-name">..</span>
CARD_SELECTOR = ".thought-card"
TEXT_SELECTOR = "p.frase"
AUTHOR_SELECTOR = ".author-name"
MAX_CHARS = 600
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/130.0 Safari/537.36"}


def parse_quotes(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    quotes = []
    for card in soup.select(CARD_SELECTOR):
        text_el = card.select_one(TEXT_SELECTOR)
        if not text_el:
            continue
        text = text_el.get_text(" ", strip=True)
        if not text or len(text) > MAX_CHARS:
            continue
        author_el = card.select_one(AUTHOR_SELECTOR)
        quotes.append((text, author_el.get_text(strip=True) if author_el else ""))
    return quotes


def pick_for_day(quotes: list[tuple[str, str]], day: str) -> tuple[str, str]:
    """Same quote for the whole day, different one each day."""
    idx = int(hashlib.sha256(day.encode()).hexdigest(), 16) % len(quotes)
    return quotes[idx]


async def fetch_bomdia(url: str, day: str) -> str | None:
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as http:
            resp = await http.get(url)
            resp.raise_for_status()
        quotes = parse_quotes(resp.text)
    except Exception:
        log.exception("bomdia fetch failed")
        return None
    if not quotes:
        return None
    text, author = pick_for_day(quotes, day)
    return f"☀️ *Bom dia!*\n\n{text}" + (f"\n\n— _{author}_" if author else "")


@command("bomdia", help="mensagem de bom dia do dia", aliases=("goodmorning",))
async def bomdia(ctx: Context):
    day = datetime.now(ZoneInfo(ctx.settings.timezone)).date().isoformat()
    msg = await fetch_bomdia(ctx.settings.bomdia_url, day)
    if msg is None:  # site down / layout changed: never send nothing
        text = await ctx.ai.ask("Escreva uma mensagem curta e calorosa de bom dia para um grupo de amigos.")
        if text is None:
            await send_ai_error(ctx, prefix="☀️ ")
            return
        msg = "☀️ " + text
    await ctx.reply(msg)
