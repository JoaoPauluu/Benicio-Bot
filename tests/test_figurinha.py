import httpx
import pytest
from conftest import group_msg

from whatsapp_bot.commands import comentarista
from whatsapp_bot.services import conversation
from whatsapp_bot.services.ai import clean_query
from whatsapp_bot.services.klipy import Klipy, media_url
from whatsapp_bot.services.stickers import without_meme_terms

GIF = b"GIF89a-fake"


def item(slug, sizes=("sm",), fmt="gif"):
    return {"id": 1, "slug": slug, "type": "gif",
            "file": {s: {fmt: {"url": f"https://static.test/{slug}-{s}.{fmt}", "width": 1, "height": 1, "size": 1}}
                     for s in sizes}}


class FakeKlipy:
    """In-memory KLIPY API for httpx.MockTransport. ``results`` maps query -> items."""

    def __init__(self, results=None):
        self.results = results if results is not None else {}
        self.queries: list[str] = []
        self.downloads: list[str] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if req.url.host == "static.test":
            self.downloads.append(str(req.url))
            return httpx.Response(200, content=GIF)
        if req.url.path == "/api/v1/KEY/gifs/search":
            q = req.url.params["q"]
            self.queries.append(q)
            return httpx.Response(200, json={"result": True, "data": {"data": self.results.get(q, []),
                                                                      "has_next": False}})
        return httpx.Response(404, json={"result": False})


@pytest.fixture
def klipy(bot):
    server = FakeKlipy({"gato": [item("gato-1"), item("gato-2")]})
    bot.klipy = Klipy("KEY", transport=httpx.MockTransport(server))
    return server


def stickers(bot):
    return [s for s in bot.client.sent if s[0] == "sticker"]


def texts(bot):
    return [s[1] for s in bot.client.sent if s[0] in ("reply", "send")]


# ---- client / helpers -------------------------------------------------------

def test_media_url_prefers_small_and_skips_ads():
    assert media_url(item("a", sizes=("hd", "md"))) == "https://static.test/a-md.gif"
    assert media_url(item("b", fmt="mp4")) == "https://static.test/b-sm.mp4"
    assert media_url({"type": "ad", "content": "<html>"}) is None


async def test_search_parses_results_and_skips_ads():
    server = FakeKlipy({"x": [item("x1"), {"type": "ad"}, item("x2")]})
    k = Klipy("KEY", locale="br", content_filter="low", transport=httpx.MockTransport(server))
    assert await k.search("x") == ["https://static.test/x1-sm.gif", "https://static.test/x2-sm.gif"]
    assert await k.search("nada") == []


def test_clean_query_and_meme_terms():
    assert clean_query('Query: "cat bruh meme".\nexplanation') == "cat bruh meme"
    assert clean_query("   \n") is None
    assert without_meme_terms("dog panic reaction meme") == "dog panic"


# ---- figurinha command ------------------------------------------------------

async def test_figurinha_sends_sticker(bot, klipy):
    await bot.handle(group_msg("figurinha gato"))
    assert stickers(bot) == [("sticker", GIF, None)]
    assert klipy.queries == ["gato"] and len(klipy.downloads) == 1


async def test_figurinha_not_found(bot, klipy):
    await bot.handle(group_msg("sticker asdkjhqwe"))
    assert not stickers(bot)
    assert texts(bot) == ['❌ Nenhum gif encontrado para "asdkjhqwe".']


async def test_figurinha_usage_and_missing_key(bot):
    await bot.handle(group_msg("figurinha"))
    await bot.handle(group_msg("fig gato"))
    assert texts(bot) == ["Uso: figurinha <termo>", "KLIPY_API_KEY não configurada no .env."]


async def test_meme_terms_dropped_when_nothing_found(bot, klipy):
    bot.ai.gif_answer = "gato bruh meme"
    from whatsapp_bot.core.context import Context
    from whatsapp_bot.services.stickers import contextual_sticker
    assert await contextual_sticker(Context(bot, "x@g.us"), "oi")
    assert klipy.queries == ["gato bruh meme", "gato"]


# ---- random stickers on AI replies -----------------------------------------

async def test_ai_reply_sometimes_adds_sticker(bot, klipy, monkeypatch):
    bot.ai.gif_answer = "gato"
    monkeypatch.setattr(conversation.random, "random", lambda: 0.0)
    await bot.handle(group_msg("ia qual a boa"))
    assert texts(bot) == ["AI:Ana: qual a boa"] and len(stickers(bot)) == 1
    assert bot.ai.gif_queries[0][0] == "Ana: qual a boa"


async def test_ai_reply_usually_text_only(bot, klipy, monkeypatch):
    monkeypatch.setattr(conversation.random, "random", lambda: 0.99)
    await bot.handle(group_msg("qual a boa"))
    assert texts(bot) == ["AI:Ana: qual a boa"] and not stickers(bot) and not bot.ai.gif_queries


# ---- commentator ------------------------------------------------------------

async def run_comment(bot, monkeypatch, roll):
    monkeypatch.setattr(comentarista.random, "random", lambda: roll)
    await bot.handle(group_msg("comentarista"))
    bot.client.sent.clear()
    for i in range(bot.settings.comentarista_interval):
        await bot.handle(group_msg(f"msg {i}", mention=False))
    await bot.drain()


@pytest.mark.parametrize("roll, n_text, n_sticker", [(0.05, 1, 1), (0.2, 0, 1), (0.5, 1, 0)])
async def test_comentarista_sticker_chances(bot, klipy, monkeypatch, roll, n_text, n_sticker):
    bot.ai.gif_answer = "gato"
    await run_comment(bot, monkeypatch, roll)
    assert len(texts(bot)) == n_text and len(stickers(bot)) == n_sticker


async def test_comentarista_sticker_only_falls_back_to_text(bot, klipy, monkeypatch):
    bot.ai.gif_answer = "nada encontrado"
    await run_comment(bot, monkeypatch, 0.2)
    assert len(texts(bot)) == 1 and not stickers(bot)
