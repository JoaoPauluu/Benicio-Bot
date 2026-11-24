from pathlib import Path

import httpx
import pytest
from conftest import group_msg
from test_figurinha import FakeKlipy, item, stickers, texts

from whatsapp_bot.services import fallback
from whatsapp_bot.services.klipy import Klipy

ERRO_MD = """# Mensagens de erro

Texto explicativo com - traço no meio.

- primeira ok 👍
- opa
  ok 👍
  beleza ok 👍

- terceira
"""


def test_parse_messages_supports_multiline():
    assert fallback.parse_messages(ERRO_MD) == ["primeira ok 👍", "opa\nok 👍\nbeleza ok 👍", "terceira"]
    assert fallback.parse_messages("sem bullets") == []


def test_real_prompt_file_has_messages():
    path = Path(__file__).parents[1] / "prompts" / f"{fallback.PROMPT_NAME}.md"
    messages = fallback.parse_messages(path.read_text(encoding="utf-8"))
    assert len(messages) >= 10 and {"opa", "ok 👍", "beleza ok 👍"} <= set(messages)


@pytest.fixture
def failing_ai(bot, tmp_path):
    (tmp_path / "erro.md").write_text("- caiu ok 👍\n", encoding="utf-8")
    bot.ai.read_prompt = lambda name: (tmp_path / f"{name}.md").read_text(encoding="utf-8")

    async def ask(contents, *extra):
        bot.ai.calls.append((contents, extra))
        return None
    bot.ai.ask = ask
    return bot


@pytest.fixture
def error_klipy(bot):
    server = FakeKlipy({q: [item(q.replace(" ", "-"))] for q in fallback.STICKER_QUERIES})
    bot.klipy = Klipy("KEY", transport=httpx.MockTransport(server))
    return server


def force_mode(monkeypatch, mode):
    monkeypatch.setattr(fallback.random, "choice", lambda seq: mode if seq is fallback.MODES else seq[0])


@pytest.mark.parametrize("mode,n_text,n_sticker", [
    (fallback.TEXT_ONLY, 1, 0), (fallback.STICKER_ONLY, 0, 1), (fallback.BOTH, 1, 1),
])
async def test_ai_error_modes(failing_ai, error_klipy, monkeypatch, mode, n_text, n_sticker):
    force_mode(monkeypatch, mode)
    await failing_ai.handle(group_msg("ia qual a boa"))
    assert texts(failing_ai) == ["caiu ok 👍"] * n_text and len(stickers(failing_ai)) == n_sticker
    assert not failing_ai.ai.gif_queries  # never asks the failing Gemini for a sticker query
    if n_sticker:
        assert error_klipy.queries == [fallback.STICKER_QUERIES[0]]


async def test_sticker_only_falls_back_to_text(failing_ai, monkeypatch):
    failing_ai.klipy = Klipy("KEY", transport=httpx.MockTransport(FakeKlipy({})))  # no gifs found
    force_mode(monkeypatch, fallback.STICKER_ONLY)
    await failing_ai.handle(group_msg("ia qual a boa"))
    assert texts(failing_ai) == ["caiu ok 👍"] and not stickers(failing_ai)


async def test_without_klipy_always_text(failing_ai):
    await failing_ai.handle(group_msg("ia qual a boa"))
    assert texts(failing_ai) == ["caiu ok 👍"]


async def test_empty_prompt_file_uses_default(failing_ai, tmp_path):
    (tmp_path / "erro.md").write_text("", encoding="utf-8")
    await failing_ai.handle(group_msg("ia qual a boa"))
    assert texts(failing_ai) == [fallback.DEFAULT_MESSAGE]
