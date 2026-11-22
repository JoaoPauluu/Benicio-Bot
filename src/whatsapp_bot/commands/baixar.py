"""Download media links via the AIO Toolkit (yt-dlp) and send them to the chat.

    @bot baixar [qualidade] link1, link2 ...
    @bot baixar cookies          (owner) then reply to the bot's message with cookies.txt
"""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from whatsapp_bot.core.context import Context
from whatsapp_bot.core.registry import command, listener
from whatsapp_bot.core.roles import Role, denied_message
from whatsapp_bot.core.store import atomic_write
from whatsapp_bot.services.aio import AIO, AIOError
from whatsapp_bot.whatsapp.incoming import media_message
from whatsapp_bot.whatsapp.jid import jid_from_str

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Preset:
    label: str
    format: str = "mp4"
    quality: str | None = None
    bitrate: str | None = None


LOW = Preset("baixa (360p)", quality="360")
MEDIUM = Preset("média (480p)", quality="480")
HIGH = Preset("alta (720p)", quality="720")
MAX = Preset("máxima (1080p)", quality="1080")
AUDIO = Preset("áudio (MP3)", format="mp3", bitrate="192K")
DEFAULT = MEDIUM

PRESETS: dict[str, Preset] = {
    "baixa": LOW, "low": LOW,
    "media": MEDIUM, "média": MEDIUM, "medio": MEDIUM, "médio": MEDIUM, "medium": MEDIUM,
    "alta": HIGH, "high": HIGH,
    "max": MAX, "maxima": MAX, "máxima": MAX,
    "audio": AUDIO, "áudio": AUDIO, "mp3": AUDIO,
}
QUALITIES = {"144", "240", "360", "480", "720", "1080", "1440", "2160", "4320"}
COOKIE_WORDS = {"cookies", "cookie"}
COOKIES_PROMPT = "🍪 Responda essa mensagem com o arquivo cookies.txt."
USAGE = "[baixa|media|alta|max|audio] link1, link2 …"

_URL_RE = re.compile(r"^(https?://)?([\w-]+\.)+[a-z]{2,}(/\S*)?$", re.IGNORECASE)


def parse_request(args: list[str]) -> tuple[Preset, list[str]]:
    """['alta', 'youtube.com/a,', 'instagram.com/b'] -> (HIGH, ['https://youtube.com/a', 'https://instagram.com/b'])."""
    preset = DEFAULT
    if args:
        first = args[0].lower().rstrip(",").removesuffix("p")
        if first in PRESETS:
            preset, args = PRESETS[first], args[1:]
        elif first in QUALITIES:
            preset, args = Preset(f"{first}p", quality=first), args[1:]
    urls = []
    for token in re.split(r"[,\s]+", " ".join(args)):
        token = token.strip("<>()[]\"'")
        if token and _URL_RE.match(token):
            urls.append(token if token.lower().startswith(("http://", "https://")) else f"https://{token}")
    return preset, list(dict.fromkeys(urls))  # dedupe, keep order


def cookies_path(ctx: Context) -> Path:
    return ctx.settings.data_dir / "cookies.txt"


@command("baixar", help="baixa vídeos/áudios de links e manda aqui", usage=USAGE, role=Role.MEDIA,
         aliases=("download", "baixe"))
async def baixar(ctx: Context):
    if ctx.args and ctx.args[0].lower() in COOKIE_WORDS:
        if not ctx.is_owner:
            await ctx.reply(denied_message("baixar cookies", {Role.OWNER}))
            return
        await ctx.reply(COOKIES_PROMPT)
        return

    preset, urls = parse_request(ctx.args)
    if not urls:
        await ctx.reply(f"Uso: baixar {USAGE}\nPadrão: {DEFAULT.label}. Separe vários links por vírgula.")
        return
    await ctx.reply(f"⏳ Baixando {len(urls)} link{'s' if len(urls) > 1 else ''} em {preset.label}…")
    for url in urls:  # one job per link: a failure doesn't block the others
        ctx.bot.spawn(_download_and_send(ctx, url, preset))


async def _download_and_send(ctx: Context, url: str, preset: Preset) -> None:
    aio = ctx.bot.aio
    tmp_root = ctx.settings.data_dir / "tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=tmp_root))
    job = None
    try:
        job = await aio.run_ytdlp([url], preset.format, preset.quality, preset.bitrate, cookies_path(ctx))
        if not job.get("files"):
            await ctx.reply(f"❌ Nada foi baixado de {url}.")
            return
        for f in job["files"]:
            path = await aio.download(f["url"], tmp / Path(f["name"]).name)
            await _send_file(ctx, aio, path, url)
    except AIOError as e:
        log.warning("baixar failed for %s: %s\n%s", url, e, "\n".join(e.logs[-20:]))
        await ctx.reply(f"❌ Não consegui baixar {url}: {_short(str(e))}")
    except Exception as e:
        log.exception("baixar failed for %s", url)
        await ctx.reply(f"❌ Erro ao baixar {url}: {_short(str(e)) or type(e).__name__}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if job and job.get("id"):
            await aio.delete_job(job["id"])


async def _send_file(ctx: Context, aio: AIO, path: Path, url: str) -> None:
    size_mb = path.stat().st_size / (1 << 20)
    if size_mb > ctx.settings.baixar_max_mb:
        expires = ctx.settings.baixar_share_expires
        link = await aio.share(path, expires, note=f"WhatsApp: {url}")
        await ctx.reply(f"📦 Arquivo grande demais para o WhatsApp ({size_mb:.0f} MB).\n{link}\n(expira em {expires})")
        return
    client, to, quoted = ctx.bot.client, jid_from_str(ctx.chat), ctx.event
    ext = path.suffix.lower()
    if ext in (".mp4", ".mov", ".m4v"):
        await client.send_video(to, str(path), quoted=quoted)
    elif ext in (".mp3", ".m4a", ".opus", ".ogg", ".aac"):
        await client.send_audio(to, str(path), quoted=quoted)
    else:
        await client.send_document(to, str(path), filename=path.name, quoted=quoted)


def _short(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ---- cookies upload (owner replies to COOKIES_PROMPT with the file) ----------

def looks_like_cookies(data: bytes) -> bool:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    if "Netscape HTTP Cookie File" in text[:200]:
        return True
    lines = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    return bool(lines) and all(len(line.split("\t")) >= 7 for line in lines[:20])


@listener(role=Role.OWNER)
async def receive_cookies(ctx: Context):
    inc = ctx.incoming
    if inc is None or not inc.has_document or ctx.event is None:
        return
    if not ctx.bot.identity.is_bot(inc.quoted_participant) or not inc.quoted_text.startswith(COOKIES_PROMPT):
        return
    ctx.handled = True
    try:
        data = await ctx.bot.client.download_any(media_message(ctx.event.Message))
    except Exception:
        log.exception("could not download cookies file")
        await ctx.reply("❌ Não consegui baixar o arquivo. Tente de novo.")
        return
    if not data or not looks_like_cookies(data):
        await ctx.reply("❌ Isso não parece um cookies.txt (formato Netscape). Nada foi alterado.")
        return
    atomic_write(cookies_path(ctx), data, mode=0o600)
    await ctx.reply("✅ Cookies salvos. Todos os próximos *baixar* vão usar esse arquivo.")
