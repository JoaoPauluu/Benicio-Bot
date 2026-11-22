import dataclasses
import json
import time

import httpx
import pytest
from conftest import BOT_LID, GROUP, OWNER, group_msg

from whatsapp_bot.commands.baixar import AUDIO, COOKIES_PROMPT, DEFAULT, HIGH, looks_like_cookies, parse_request
from whatsapp_bot.core.registry import REGISTRY
from whatsapp_bot.services.aio import AIO, AIOError
from whatsapp_bot.whatsapp.incoming import Incoming

STRANGER = "5511900000009"
COOKIES = b"# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tabc\n"


class FakeAIO:
    """In-memory AIO Toolkit server for httpx.MockTransport."""

    def __init__(self, size=1000, fail=False, pending=0):
        self.size, self.fail, self.pending = size, fail, pending
        self.runs: list[httpx.Request] = []
        self.deleted: list[str] = []
        self.shares = 0

    def __call__(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == "/api/plugins/ytdlp/run":
            self.runs.append(req)
            if self.fail:
                return httpx.Response(422, json={"id": "j1", "state": "failed", "error": "Unsupported URL",
                                                 "logs": ["ERROR: nope"]})
            if self.pending:
                return httpx.Response(202, json={"id": "j1", "state": "running"})
            return httpx.Response(200, json=self._done())
        if path == "/api/jobs/j1" and req.method == "GET":
            self.pending -= 1
            if self.pending > 0:
                return httpx.Response(202, json={"id": "j1", "state": "running"})
            return httpx.Response(200, json=self._done())
        if path == "/api/jobs/j1" and req.method == "DELETE":
            self.deleted.append("j1")
            return httpx.Response(200, json={"ok": True})
        if path == "/api/jobs/j1/files/video.mp4":
            return httpx.Response(200, content=b"x" * self.size)
        if path == "/api/shares":
            self.shares += 1
            return httpx.Response(201, json={"id": "S1", "files": [], "size": self.size})
        if path == "/api/config":
            return httpx.Response(200, json={"public_url": "https://aio.example/"})
        return httpx.Response(404, json={"error": "unknown"})

    def _done(self):
        return {"id": "j1", "state": "done", "files": [{"name": "video.mp4", "size": self.size,
                                                        "url": "/api/jobs/j1/files/video.mp4"}]}

    def fields(self, i=-1) -> dict:
        req = self.runs[i]
        if req.headers["content-type"].startswith("application/json"):
            return json.loads(req.content)
        return {"__multipart__": req.content}


@pytest.fixture
def aio_server(bot):
    server = FakeAIO()
    bot.aio = AIO("http://aio.test", 60, transport=httpx.MockTransport(server))
    return server


# ---- parsing ----------------------------------------------------------------

def test_parse_request_presets_and_urls():
    preset, urls = parse_request(["alta", "youtube.com/watch?v=a,", "instagram.com/reel/b"])
    assert preset is HIGH
    assert urls == ["https://youtube.com/watch?v=a", "https://instagram.com/reel/b"]
    preset, urls = parse_request(["https://youtu.be/x,https://youtu.be/y"])
    assert preset is DEFAULT and DEFAULT.quality == "480" and len(urls) == 2
    assert parse_request(["audio", "youtu.be/x"])[0] is AUDIO
    assert parse_request(["720p", "youtu.be/x"])[0].quality == "720"
    assert parse_request(["olá", "mundo"])[1] == []


def test_every_command_has_an_english_alias():
    for pt, en in [("ajuda", "help"), ("bomdia", "goodmorning"), ("ia", "ai"), ("comentarista", "commentator"),
                   ("agendar", "schedule"), ("agendamentos", "schedules"), ("desagendar", "unschedule"),
                   ("recurso", "feature"), ("cargo", "role"), ("baixar", "download")]:
        assert REGISTRY.find(pt) is REGISTRY.find(en), (pt, en)


async def test_ajuda_shows_aliases(bot):
    await bot.handle(group_msg("help"))
    assert "*baixar* (download, baixe)" in bot.client.sent[-1][1]


def test_cookie_validation():
    assert looks_like_cookies(COOKIES)
    assert looks_like_cookies(b".x.com\tTRUE\t/\tFALSE\t0\tk\tv\n")
    assert not looks_like_cookies(b"hello world")
    assert not looks_like_cookies(b"\xff\xfe\x00")


# ---- AIO client -------------------------------------------------------------

async def test_aio_waits_for_202_jobs():
    server = FakeAIO(pending=2)
    aio = AIO("http://aio.test", 60, transport=httpx.MockTransport(server))
    job = await aio.run_ytdlp(["https://youtu.be/x"], quality="480")
    assert job["state"] == "done" and server.pending == 0
    fields = server.fields()
    assert fields["urls"] == "https://youtu.be/x" and fields["quality"] == "480" and fields["library"] is False


async def test_aio_failure_raises_with_logs():
    aio = AIO("http://aio.test", 60, transport=httpx.MockTransport(FakeAIO(fail=True)))
    with pytest.raises(AIOError) as e:
        await aio.run_ytdlp(["https://youtu.be/x"])
    assert "Unsupported URL" in str(e.value) and e.value.logs == ["ERROR: nope"]


async def test_aio_share_link_uses_public_url(tmp_path):
    f = tmp_path / "a.mp4"
    f.write_bytes(b"1")
    aio = AIO("http://aio.test", 60, transport=httpx.MockTransport(FakeAIO()))
    assert await aio.share(f) == "https://aio.example/files/S1"


# ---- command ----------------------------------------------------------------

async def test_baixar_sends_video_and_cleans_up(bot, aio_server):
    ev = object()
    await bot.handle(group_msg("baixar youtube.com/a, instagram.com/b"), ev)
    await bot.drain()
    assert "⏳ Baixando 2 links em média (480p)" in bot.client.sent[0][1]
    videos = [s for s in bot.client.sent if s[0] == "video"]
    assert len(videos) == 2 and all(v[2] is ev for v in videos)  # quoted reply to the request
    assert aio_server.deleted == ["j1", "j1"]
    assert not any((bot.settings.data_dir / "tmp").iterdir())


async def test_baixar_big_file_goes_to_share_link(bot, aio_server):
    bot.settings = dataclasses.replace(bot.settings, baixar_max_mb=0.0001)
    await bot.handle(group_msg("download alta youtu.be/a"))
    await bot.drain()
    assert aio_server.shares == 1
    assert "https://aio.example/files/S1" in bot.client.sent[-1][1]
    assert not [s for s in bot.client.sent if s[0] == "video"]


async def test_baixar_reports_failures(bot, aio_server):
    aio_server.fail = True
    await bot.handle(group_msg("baixar youtu.be/a"))
    await bot.drain()
    assert "❌" in bot.client.sent[-1][1] and "Unsupported URL" in bot.client.sent[-1][1]


async def test_baixar_requires_media_role(bot, aio_server):
    await bot.handle(group_msg("baixar youtu.be/a", sender=STRANGER))
    assert "🚫" in bot.client.sent[-1][1]
    bot.store.grant_role({STRANGER}, "media")
    await bot.handle(group_msg("baixar youtu.be/a", sender=STRANGER))
    await bot.drain()
    assert bot.client.sent[-1][0] == "video"


async def test_baixar_without_links_shows_usage(bot, aio_server):
    await bot.handle(group_msg("baixar"))
    assert "Uso:" in bot.client.sent[-1][1] and not aio_server.runs


# ---- cookies ----------------------------------------------------------------

class FakeMessage:
    def HasField(self, name):
        return False


class FakeEvent:
    def __init__(self):
        self.Message = FakeMessage()


def cookies_reply(sender=OWNER):
    return Incoming(chat=GROUP, sender=sender, sender_name="Ana", is_group=True, text="", has_document=True,
                    quoted_participant=BOT_LID, quoted_text=COOKIES_PROMPT, timestamp=time.time())


async def test_cookies_flow(bot, aio_server):
    await bot.handle(group_msg("baixar cookies"))
    assert bot.client.sent[-1][1] == COOKIES_PROMPT

    ev = FakeEvent()
    bot.client.downloads[id(ev.Message)] = COOKIES
    await bot.handle(cookies_reply(), ev)
    assert "✅ Cookies salvos" in bot.client.sent[-1][1]
    assert len(bot.client.sent) == 2  # handled: no "Oi! Me mande ajuda" afterwards
    path = bot.settings.data_dir / "cookies.txt"
    assert path.read_bytes() == COOKIES

    await bot.handle(group_msg("baixar youtu.be/a"))
    await bot.drain()
    body = aio_server.fields()["__multipart__"]
    assert b'name="cookies"' in body and b"SID\tabc" in body and b'name="quality"' in body

    newer = COOKIES.replace(b"abc", b"xyz")  # a new file replaces the old one
    ev2 = FakeEvent()
    bot.client.downloads[id(ev2.Message)] = newer
    await bot.handle(cookies_reply(), ev2)
    assert path.read_bytes() == newer


async def test_cookies_rejected_for_non_owner_and_bad_files(bot, aio_server):
    bot.store.grant_role({STRANGER}, "admin")
    await bot.handle(group_msg("baixar cookies", sender=STRANGER))
    assert "🚫" in bot.client.sent[-1][1]

    ev = FakeEvent()
    bot.client.downloads[id(ev.Message)] = COOKIES
    await bot.handle(cookies_reply(sender=STRANGER), ev)  # not the owner: listener ignores it
    assert not (bot.settings.data_dir / "cookies.txt").exists()

    bot.client.downloads[id(ev.Message)] = b"not cookies"
    await bot.handle(cookies_reply(), ev)
    assert "não parece um cookies.txt" in bot.client.sent[-1][1]
    assert not (bot.settings.data_dir / "cookies.txt").exists()


def test_english_schedule_rules():
    from whatsapp_bot.core.scheduler import parse_rule

    assert parse_rule("daily").day_of_week == "*"
    assert parse_rule("weekdays").day_of_week == "mon-fri"
    assert parse_rule("mon,wed").day_of_week == "mon,wed"


def test_parse_captioned_document_reply():
    from neonize.proto import Neonize_pb2 as p
    from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import ContextInfo, DocumentMessage, FutureProofMessage, Message

    from whatsapp_bot.whatsapp.incoming import parse_event

    quoted = Message(conversation=COOKIES_PROMPT)
    doc = DocumentMessage(fileName="cookies.txt", caption="aqui",
                          contextInfo=ContextInfo(participant=f"{BOT_LID}@lid", quotedMessage=quoted))
    ev = p.Message(
        Info=p.MessageInfo(MessageSource=p.MessageSource(Chat=p.JID(User=OWNER, Server="s.whatsapp.net"),
                                                         Sender=p.JID(User=OWNER, Server="s.whatsapp.net")),
                           Timestamp=int(time.time())),
        Message=Message(documentWithCaptionMessage=FutureProofMessage(message=Message(documentMessage=doc))),
    )
    inc = parse_event(ev)
    assert inc.has_document and inc.document_name == "cookies.txt"
    assert inc.quoted_participant == BOT_LID and inc.quoted_text == COOKIES_PROMPT
