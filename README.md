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
- **DMs:** no mention needed. Only the owner gets answers unless `ALLOW_DMS_FROM_OTHERS=true`.
- **Replies:** every answer is a native WhatsApp reply. Scheduled sends are plain messages.

| Command | Who | What |
|---|---|---|
| `ajuda` | all | list commands (owner sees 🔒 ones too) |
| `bomdia` | all | quote of the day from pensador.com, with Gemini as fallback |
| `ia <texto>` | all | ask Gemini explicitly (handy inside schedules) |
| `status` | owner | uptime, model, schedules |
| `comentarista` | owner | toggle commentator mode in this group (every `COMENTARISTA_INTERVAL` msgs) |
| `agendar HH:MM [diario\|uteis\|fds\|seg,qua\|AAAA-MM-DD] <comando ou texto>` | owner | schedule in this chat |
| `agendamentos` / `desagendar <id>` | owner | list / remove schedules |
| `prompt [texto\|limpar]` | owner | extra Gemini instructions for this chat |
| `recurso [nome on\|off]` | owner | per-chat switches (`ia`, `comentarista`, …) |
| `ping` | owner | liveness check |

Non-owners who use owner-only commands get no response.

## Prompts

- `prompts/base.md` is the system prompt for **every** Gemini call.
- `prompts/comentarista.md` is added on top of it in commentator mode.
- Files are re-read on each call, so edits apply without a restart.

## Adding a command

Create `src/whatsapp_bot/commands/<anything>.py`. It is auto-discovered:

```python
from whatsapp_bot.registry import command, feature, listener

@command("dado", help="rola um dado", usage="[lados]")
async def dado(ctx):
    import random
    await ctx.reply(str(random.randint(1, int(ctx.args[0]) if ctx.args else 6)))

meu = feature("meurecurso", help="...", default=False)   # togglable via `recurso meurecurso on`

@listener()                  # runs on every message; owner_only=True for owner hooks
async def watcher(ctx):
    if ctx.store.get_flag(ctx.chat, "meurecurso"):
        ...
```

`ctx` gives you:

- `reply()` (native quoted reply) and `send()`
- `args`, `text`, `is_owner`, `is_group`, `chat`, `incoming`
- `store` (flags, prompts, schedules), `ai.ask()`, `settings`, `bot`

Owner-only special actions on every owner message go in `commands/dono.py`.

## Tests

```bash
uv run pytest
```
