import time
from dataclasses import dataclass, field

import pytest

from whatsapp_bot.bot import Bot
from whatsapp_bot.config import Settings
from whatsapp_bot.incoming import Incoming
from whatsapp_bot.store import Store

OWNER = "5511900000001"
OWNER_LID = "99001"
BOT = "5511900000002"
BOT_LID = "99002"
GROUP = "120363000000000001@g.us"


@dataclass
class FakeClient:
    sent: list = field(default_factory=list)

    async def reply_message(self, text, quoted):
        self.sent.append(("reply", text, quoted))

    async def send_message(self, to, text):
        self.sent.append(("send", text, f"{to.User}@{to.Server}"))


class FakeAI:
    model = "fake-model"

    def __init__(self):
        self.calls = []

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


def group_msg(text, sender=OWNER, mention=True, name="Ana", lid=None):
    mentioned = {BOT_LID} if mention else set()
    if mention:
        text = f"@{BOT_LID} {text}"
    return Incoming(chat=GROUP, sender=lid or sender, sender_alt=sender if lid else "", sender_name=name,
                    is_group=True, text=text, mentioned=mentioned, timestamp=time.time())


def dm(text, sender=OWNER):
    return Incoming(chat=f"{sender}@s.whatsapp.net", sender=sender, sender_name="Dono", text=text,
                    timestamp=time.time())
