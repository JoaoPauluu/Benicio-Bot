# Benício Bot

Benício is a personal WhatsApp bot that runs on a normal account as a linked device. It does not use the Meta API.
Built with [neonize](https://github.com/krypton-byte/neonize) (whatsmeow) and Gemini.

## Setup

```bash
uv sync
cp .env.example .env    # fill GEMINI_API_KEY, GEMINI_MODEL, OWNER_NUMBER
uv run whatsapp-bot
```

On the first run a QR code prints in the terminal. Scan it with the **bot's** phone: WhatsApp → Linked devices.
The session is saved in `data/session.db`, so later runs log in automatically.

## Docker (run it all the time)

Every push to `main` builds `ghcr.io/joaopauluu/benicio-bot:latest` (amd64 + arm64).
On the server, put [`compose.yaml`](compose.yaml) and your `.env` in one folder, then start it:

```bash
docker compose up -d
docker compose logs -f        # first run: scan the QR shown here with the bot's phone
```

- The WhatsApp session and schedules live in the `benicio-data` volume, so restarts and image updates keep you logged in.
- If the QR code expires before you scan it, run `docker compose restart` to get a new one.
- To update: `docker compose pull && docker compose up -d`, or let Watchtower do it.
- To edit prompts without rebuilding, uncomment the `./prompts` mount in `compose.yaml`.

Build locally instead: `docker build -t benicio-bot .`

## Usage

- **Groups:** @mention the bot, or reply to one of its messages, followed by a command. Anything else after the mention goes to Gemini.
- **DMs:** no mention needed. Only people with a role (owner, admin, mídia) get answers unless `ALLOW_DMS_FROM_OTHERS=true`.
- **Replies:** every answer is a native WhatsApp reply. Scheduled sends are plain messages.

Every command also has an English alias (shown in `ajuda`), e.g. `help`, `schedule`, `download`.

| Command | Who | What |
|---|---|---|
| `ajuda` | all | list the commands you are allowed to run (🔒 marks the required role) |
| `bomdia` | all | quote of the day from pensador.com, with Gemini as fallback |
| `ia <texto>` | all | ask Gemini explicitly (handy inside schedules) |
| `figurinha <termo>` | all | animated sticker from a KLIPY GIF search (aliases `sticker`, `fig`) |
| `status` | admin | uptime, model, schedules |
| `comentarista` | admin | toggle commentator mode in this group (every `COMENTARISTA_INTERVAL` msgs) |
| `agendar HH:MM [diario\|uteis\|fds\|seg,qua\|AAAA-MM-DD] <comando ou texto>` | admin | schedule in this chat |
| `agendamentos` / `desagendar <id>` | admin | list / remove schedules |
| `prompt [texto\|limpar]` | admin | extra Gemini instructions for this chat |
| `recurso [nome on\|off]` | admin | per-chat switches (`ia`, `comentarista`, …) |
| `ping` | admin | liveness check |
| `baixar [baixa\|media\|alta\|max\|audio] link1, link2` | media | download links via AIO Toolkit (yt-dlp) and send them here |
| `baixar cookies` | owner | set the `cookies.txt` used by every download |
| `cargo` / `cargos` | owner | list roles |
| `cargo dar\|tirar <admin\|media> <@pessoa\|número>` | owner | give / take a role (you can also reply to the person's message) |

### Downloads (`baixar` / `download`)

`@bot baixar alta youtube.com/watch?v=…, instagram.com/reel/…` downloads each link through the
AIO Toolkit `ytdlp` plugin at `AIO_BASE_URL` and replies with the video.

| Preset | Result |
|---|---|
| `baixa` / `low` | 360p |
| `media` / `medium` (default) | 480p, small enough for WhatsApp |
| `alta` / `high` | 720p |
| `max` | 1080p |
| `audio` / `mp3` | MP3 audio |

A number such as `720` also works. Files over `BAIXAR_MAX_MB` (100 MB by default) are uploaded to an
AIO share instead, and the bot sends the link (expires after `BAIXAR_SHARE_EXPIRES`).

**Cookies** (for age-restricted or members-only videos): the owner sends `baixar cookies`, and the bot
answers "🍪 Responda essa mensagem com o arquivo cookies.txt.". Reply to *that* message with the
Netscape-format `cookies.txt` as a document. It is stored in `data/cookies.txt` and used by every
`baixar` until you send a new one, which replaces it.

### Stickers (`figurinha` / `sticker`)

Needs `KLIPY_API_KEY` (from https://partner.klipy.com/api-keys; test keys allow 100 calls/hour).
`@bot figurinha gato` searches KLIPY, picks a random GIF and sends it as an animated sticker, or answers
that nothing was found. `KLIPY_LOCALE` and `KLIPY_CONTENT_FILTER` tune the search.

The bot also sends stickers on its own. Gemini picks a meme-style GIF query from the conversation using
`prompts/figurinha.md`:

- **AI replies** (`ia` or a plain mention): a 1 in 8 chance of a sticker after the text.
- **Commentator mode:** a 1 in 10 chance of text plus a sticker, and a 1 in 5 chance of a sticker instead
  of the text. If no GIF is found, it sends the text.

The chances are constants in `src/whatsapp_bot/services/stickers.py`.

### Roles

Roles are global (they apply in every chat) and are saved in `data/state.json`.

- **dono (owner):** the `OWNER_NUMBER` from `.env`. Holds every role, and is the only one who can manage roles.
- **admin:** can run everything except owner-only commands.
- **mídia (`media`):** reserved for media commands. None need it yet.

Anyone who tries a command without the required role is told they are not allowed.

## Prompts

- `prompts/base.md` is the system prompt for **every** Gemini call.
- `prompts/comentarista.md` is added on top of it in commentator mode.
- `prompts/figurinha.md` is added when Gemini picks a GIF search query for a random sticker.
- Files are re-read on each call, so edits apply without a restart.

## Adding a command

Create `src/whatsapp_bot/commands/<anything>.py`. It is auto-discovered:

```python
from whatsapp_bot.core.registry import command, feature, listener
from whatsapp_bot.core.roles import Role

@command("dado", help="rola um dado", usage="[lados]")
async def dado(ctx):
    import random
    await ctx.reply(str(random.randint(1, int(ctx.args[0]) if ctx.args else 6)))

meu = feature("meurecurso", help="...", default=False)   # togglable via `recurso meurecurso on`

@command("figurinha", help="...", role=Role.MEDIA)   # restrict to a role (admin/owner pass too)
async def figurinha(ctx):
    ...

@listener()                  # runs on every message; role=Role.OWNER for owner hooks
async def watcher(ctx):
    if ctx.store.get_flag(ctx.chat, "meurecurso"):
        ...
```

`ctx` gives you:

- `reply()` (native quoted reply) and `send()`
- `args`, `rest` (text after the command, original case), `text`, `roles` / `is_owner`, `is_group`, `chat`, `incoming`
- `store` (flags, prompts, schedules), `ai.ask()`, `chat_instructions()`, `settings`, `bot`

Owner-only special actions on every owner message go in `commands/dono.py` (a commented template).

## Layout

```
src/whatsapp_bot/
  main.py, config.py   entry point and .env settings
  core/                router (bot), context, registry, roles, store, scheduler
  whatsapp/            neonize message parsing, JIDs, bot/owner identity
  services/            Gemini (ai), free-form AI chat (conversation), AIO Toolkit, KLIPY, stickers
  commands/            one module per chat command, auto-discovered
```

To add a new role, add it to `Role` and `LABELS` in `src/whatsapp_bot/core/roles.py`. The owner and admins get it automatically, and `cargo` can grant it.

## Tests

```bash
uv run pytest
```
