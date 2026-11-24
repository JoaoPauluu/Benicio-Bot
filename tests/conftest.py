import time
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from whatsapp_bot.config import Settings
from whatsapp_bot.core.bot import Bot
from whatsapp_bot.core.store import Store
from whatsapp_bot.whatsapp.incoming import Incoming

OWNER = "5511900000001"
OWNER_LID = "99001"
BOT = "5511900000002"
BOT_LID = "99002"
GROUP = "120363000000000001@g.us"


@dataclass
class FakeClient:
    sent: list = field(default_factory=list)
    sent_ids: list = field(default_factory=list)   # ids "BOT1", "BOT2"... of sent texts, like SendResponse.ID

    def _response(self):
        self.sent_ids.append(f"BOT{len(self.sent_ids) + 1}")
        return SimpleNamespace(ID=self.sent_ids[-1])

    async def reply_message(self, text, quoted):
        self.sent.append(("reply", text, quoted))
        return self._response()

    async def send_message(self, to, text):
        self.sent.append(("send", text, f"{to.User}@{to.Server}"))
        return self._response()

    async def send_video(self, to, file, caption=None, quoted=None, **kw):
        self.sent.append(("video", file, quoted))

    async def send_audio(self, to, file, ptt=False, quoted=None, **kw):
        self.sent.append(("audio", file, quoted))

    async def send_document(self, to, file, caption=None, title=None, filename=None, quoted=None, **kw):
        self.sent.append(("document", file, quoted))

    async def send_sticker(self, to, file, quoted=None, **kw):
        self.sent.append(("sticker", file, quoted))

    downloads: dict = field(default_factory=dict)   # message -> bytes, for download_any

    async def download_any(self, message, path=None):
        return self.downloads.get(id(message), b"")


class FakeAI:
    model = "fake-model"

    def __init__(self):
        self.calls = []
        self.gif_queries = []
        self.gif_answer = "cat bruh meme"

    async def gif_query(self, contents, *extra):
        self.gif_queries.append((contents, extra))
        return self.gif_answer

    def read_prompt(self, name):
        return f"<{name}>"

    async def ask(self, contents, *extra):
        self.calls.append((contents, extra))
        return f"AI:{contents.splitlines()[-1]}"


@pytest.fixture
def bot(tmp_path):
    settings = Settings(
        gemini_api_key="", gemini_model="fake-model", owner_number=OWNER, timezone="America/Sao_Paulo",
        bomdia_url="http://invalid.localhost/", comentarista_interval=3, allow_dms_from_others=False,
        data_dir=tmp_path, prompts_dir=tmp_path,
    )
    b = Bot(settings, FakeClient(), ai=FakeAI(), store=Store(tmp_path / "state.json"))
    b.identity.set_bot(BOT, BOT_LID)
    return b


def group_msg(text, sender=OWNER, mention=True, name="Ana", lid=None, chat=GROUP, **kw):
    mentioned = {BOT_LID} if mention else set()
    if mention:
        text = f"@{BOT_LID} {text}"
    return Incoming(chat=chat, sender=lid or sender, sender_alt=sender if lid else "", sender_name=name,
                    is_group=True, text=text, mentioned=mentioned, timestamp=time.time(), **kw)


def dm(text, sender=OWNER):
    return Incoming(chat=f"{sender}@s.whatsapp.net", sender=sender, sender_name="Dono", text=text,
                    timestamp=time.time())
