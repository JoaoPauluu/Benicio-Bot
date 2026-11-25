from types import SimpleNamespace

import pytest
from google.genai import errors

from whatsapp_bot.services import ai as ai_mod
from whatsapp_bot.services.ai import AI

OK = SimpleNamespace(text="resposta ok 👍")


def server_error(code=503):
    return errors.ServerError(code, {"error": {"code": code, "message": "overloaded", "status": "UNAVAILABLE"}})


class FakeModels:
    """``generate_content`` plays back ``script``: exceptions are raised, anything else is returned."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = 0

    async def generate_content(self, **kw):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def make_ai(bot, monkeypatch):
    slept = []

    async def fake_sleep(s):
        slept.append(s)
    monkeypatch.setattr(ai_mod.asyncio, "sleep", fake_sleep)

    def make(*script):
        ai = AI(bot.settings)
        models = FakeModels(*script)
        ai._client = SimpleNamespace(aio=SimpleNamespace(models=models))
        return ai, models, slept
    return make


@pytest.mark.parametrize("script,expected,sleeps", [
    ((server_error(), OK), "resposta ok 👍", [1]),
    ((server_error(), server_error(), OK), "resposta ok 👍", [1, 4]),
    ((server_error(), server_error(), server_error()), None, [1, 4]),
])
async def test_retries_on_503(make_ai, script, expected, sleeps):
    ai, models, slept = make_ai(*script)
    assert await ai.ask("oi") == expected
    assert slept == sleeps and models.calls == len(script)


@pytest.mark.parametrize("error", [
    errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}),
    server_error(500),
    RuntimeError("boom"),
])
async def test_other_errors_do_not_retry(make_ai, error):
    ai, models, slept = make_ai(error, OK)
    assert await ai.ask("oi") is None
    assert slept == [] and models.calls == 1
