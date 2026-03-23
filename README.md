# Claw Researcher

AI Agent for academic research — with multi-channel interactive messaging (Telegram, Discord, Email, Messenger, Zalo).

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [CLI Usage](#cli-usage)
- [Multi-Channel Server](#multi-channel-server)
- [Channel Setup Guides](#channel-setup-guides)
- [Docker](#docker)
- [Architecture](#architecture)
- [Development](#development)

---

## Requirements

- Python **3.11+**
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- An **Anthropic API key** (or any LiteLLM-compatible provider)

---

## Installation

### 1. Clone the repo

```bash
git clone <repo-url>
cd claw_researcher
```

### 2. Create virtual environment

```bash
uv venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 3. Install core package

```bash
uv pip install -e .
```

### 4. Install channel dependencies (for `claw serve`)

```bash
uv pip install -e ".[channels]"
```

This adds:
- `websockets` — Discord Gateway WebSocket
- `python-telegram-bot` — Telegram long-polling
- `aiohttp` — Webhook server (Messenger & Zalo)

### 5. Set up environment variables

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

Minimum required:

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-your-key-here
CLAW_WORKSPACE=./workspace
```

---

## Configuration

All settings use the `CLAW_` prefix and are loaded from `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Anthropic API key (required) |
| `CLAW_WORKSPACE` | `./workspace` | Directory for memory, skills, reports |
| `CLAW_DEFAULT_MODEL` | `anthropic/claude-sonnet-4-20250514` | LLM model |
| `CLAW_MAX_ITERATIONS` | `40` | Max agent tool-use iterations per message |
| `CLAW_LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`) |
| `GROQ_API_KEY` | — | Optional: Groq key for audio transcription (Whisper) |

---

## CLI Usage

### `claw chat` — Interactive Research REPL

```bash
claw chat
claw chat --model anthropic/claude-opus-4-20250514
claw chat --workspace ./my-project
```

Starts an interactive terminal session. Type your research question and the agent will use its tools (web search, paper search, code execution, file system) to respond.

**In-session commands:**

| Command | Action |
|---------|--------|
| `/quit` or `/exit` | Exit the session |

---

### `claw onboard` — Initialize Workspace

```bash
claw onboard
claw onboard --workspace ./my-project
```

Sets up the workspace directory with:
- Built-in skills (survey, brainstorm, report, gap-analysis, reproduce, memory)
- Memory store (`memory/MEMORY.md`, `memory/HISTORY.md`)

Run this once before your first `claw chat`.

---

### `claw status` — Check Configuration

```bash
claw status
```

Verifies API keys are set and required packages are importable.

---

### `claw serve` — Multi-Channel Server

```bash
claw serve
claw serve --workspace ./workspace
claw serve --webhook-port 8080
```

See [Multi-Channel Server](#multi-channel-server) below.

---

## Multi-Channel Server

`claw serve` starts the interactive gateway that connects Telegram, Discord, Email, Messenger, and Zalo to the agent.

### First run — generate config template

```bash
claw serve --workspace ./workspace
```

On first run (no `channels.json` found), this creates `workspace/channels.json` with a template and exits:

```
⚙️  First-time Setup
channels.json template created at: ./workspace/channels.json
Edit it with your tokens then run: claw serve --workspace ./workspace
```

### channels.json format

```json
{
  "telegram": {
    "enabled": true,
    "token": "YOUR_BOT_TOKEN",
    "allow_from": ["*"],
    "group_policy": "mention"
  },
  "discord": {
    "enabled": false,
    "token": "",
    "allow_from": ["*"],
    "group_policy": "mention"
  },
  "email": {
    "enabled": false,
    "consent_granted": false,
    "imap_host": "imap.gmail.com",
    "imap_port": 993,
    "imap_username": "",
    "imap_password": "",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_username": "",
    "smtp_password": "",
    "from_address": "",
    "allow_from": []
  },
  "messenger": {
    "enabled": false,
    "page_access_token": "",
    "verify_token": "",
    "app_secret": "",
    "allow_from": ["*"],
    "webhook_path": "/messenger/webhook"
  },
  "zalo": {
    "enabled": false,
    "oa_access_token": "",
    "app_secret": "",
    "allow_from": ["*"],
    "webhook_path": "/zalo/webhook"
  }
}
```

**`allow_from`**: list of user IDs allowed to interact. Use `["*"]` to allow everyone, or list specific IDs (e.g. Telegram user IDs, Discord user IDs, email addresses).

### Start the server

```bash
claw serve --workspace ./workspace
```

Output:

```
🐾 Claw Serve
Claw multi-channel server starting...
Workspace: /path/to/workspace
Channels: telegram, discord
Webhook: http://0.0.0.0:8080
Press Ctrl+C to stop.
```

---

## Channel Setup Guides

### Telegram

1. Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot`
2. Copy the token into `channels.json`:
   ```json
   { "telegram": { "enabled": true, "token": "123456:ABC-DEF..." } }
   ```
3. No public URL needed — uses long-polling.

**Group policy:**
- `"mention"` (default) — bot only responds when @mentioned in groups
- `"open"` — bot responds to all messages in groups

---

### Discord

1. Go to [discord.com/developers](https://discord.com/developers/applications) → New Application → Bot
2. Under **Bot**, copy the token
3. Under **OAuth2 → URL Generator**, select scopes: `bot` + permissions: `Send Messages`, `Read Message History`
4. Invite the bot to your server via the generated URL
5. Add token to `channels.json`:
   ```json
   { "discord": { "enabled": true, "token": "YOUR_BOT_TOKEN" } }
   ```
6. To get your user ID: enable Developer Mode in Discord settings → right-click your name → Copy ID. Add it to `allow_from`.

---

### Email (IMAP + SMTP)

> ⚠️ Requires explicit opt-in: set `"consent_granted": true` in config.

**Gmail setup:**
1. Enable 2FA on your Google account
2. Generate an [App Password](https://myaccount.google.com/apppasswords) (16 characters)
3. Fill in config:
   ```json
   {
     "email": {
       "enabled": true,
       "consent_granted": true,
       "imap_host": "imap.gmail.com",
       "imap_username": "you@gmail.com",
       "imap_password": "your-app-password",
       "smtp_host": "smtp.gmail.com",
       "smtp_username": "you@gmail.com",
       "smtp_password": "your-app-password",
       "from_address": "you@gmail.com",
       "allow_from": ["trusted@example.com"]
     }
   }
   ```

---

### Messenger (Facebook)

> Requires a public HTTPS URL. Use [ngrok](https://ngrok.com/) for local development.

1. Go to [developers.facebook.com](https://developers.facebook.com) → Create App → Business
2. Add **Messenger** product
3. Generate a **Page Access Token** for your Facebook Page
4. Set a custom **Verify Token** (any string you choose)
5. In your app's Webhook settings, point to: `https://your-domain.com/messenger/webhook`
6. Start ngrok: `ngrok http 8080` → use the HTTPS URL as your webhook
7. Add to `channels.json`:
   ```json
   {
     "messenger": {
       "enabled": true,
       "page_access_token": "EAABxxx...",
       "verify_token": "my-secret-verify-token",
       "app_secret": "your-app-secret"
     }
   }
   ```

---

### Zalo Official Account

> Requires a public HTTPS URL. Use [ngrok](https://ngrok.com/) for local development.

1. Register at [developers.zalo.me](https://developers.zalo.me)
2. Create an Official Account app
3. Get your **OA Access Token**
4. Set webhook URL to: `https://your-domain.com/zalo/webhook`
5. Add to `channels.json`:
   ```json
   {
     "zalo": {
       "enabled": true,
       "oa_access_token": "your_oa_access_token",
       "app_secret": "your_app_secret"
     }
   }
   ```

### Using ngrok for local webhook testing

```bash
# Terminal 1 — start the server
claw serve --workspace ./workspace

# Terminal 2 — expose it publicly
ngrok http 8080
# Copy the https://xxxx.ngrok-free.app URL
# Use it as your webhook base URL in Facebook / Zalo settings
```

---

## Docker

### Build the image

```bash
docker compose build
# or: make docker-build
```

### Run interactive chat (TTY)

```bash
docker compose --profile chat up claw
# or: make docker-chat
```

### Run multi-channel server (background)

```bash
# 1. Make sure workspace/channels.json exists with your tokens
# 2. Start the server
docker compose --profile serve up -d claw-serve
# or: make docker-serve

# View logs
docker compose logs -f claw-serve
# or: make docker-logs

# Stop
docker compose down
# or: make docker-down
```

### Environment variables in Docker

All settings are loaded from `.env` via `env_file`. Minimum required:

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-your-key-here
WEBHOOK_PORT=8080          # host port exposed for Messenger/Zalo webhooks
```

Workspace is bind-mounted from `./workspace` on the host to `/workspace` inside the container — so `channels.json`, memory, skills, and reports all persist across container restarts.

### Services overview

| Service | Profile | Description |
|---------|---------|-------------|
| `claw` | `chat` | Interactive research REPL (requires TTY) |
| `claw-serve` | `serve` | Multi-channel server, exposes `:8080` for webhooks |

---

## Architecture

```
┌─────────────────────────────────────────┐
│  Channels                                │
│  Telegram · Discord · Email             │  long-poll / WebSocket
│  Messenger · Zalo                       │  webhook (aiohttp :8080)
└────────────────┬────────────────────────┘
                 │ InboundMessage
                 ▼
        ┌────────────────┐
        │  MessageBus    │  asyncio.Queue (inbound + outbound)
        └───────┬────────┘
                │
                ▼
     ┌──────────────────────┐
     │  InteractiveGateway  │
     │  _agent_consumer     │──► AgentLoop.chat(session_key)
     │  _outbound_dispatcher│◄── OutboundMessage
     └──────────────────────┘
                │
                ▼
        channel.send(msg)
```

**Session isolation**: every `{channel}:{chat_id}` pair gets its own conversation history. Multiple users are handled concurrently via `asyncio.create_task()`.

---

## Development

### Run tests

```bash
# All tests
.venv/Scripts/python.exe -m pytest tests/ -v          # Windows
python -m pytest tests/ -v                            # macOS/Linux

# Interactive module smoke tests only
python -m pytest tests/test_interactive_smoke.py -v
```

### Install dev dependencies

```bash
uv pip install -e ".[dev]"
```

### Lint

```bash
.venv/Scripts/python.exe -m ruff check claw/
.venv/Scripts/python.exe -m ruff format claw/
```

### Project structure

```
claw_researcher/
├── claw/
│   ├── agent/          # AgentLoop, LLM providers, tools, memory
│   ├── interactive/    # Multi-channel messaging (channels, bus, gateway)
│   ├── providers/      # Groq transcription
│   ├── security/       # SSRF protection
│   ├── core/           # FastAPI REST gateway
│   ├── tools/          # Research API clients
│   ├── utils/          # Helpers (split_message, token counting, …)
│   ├── skills/         # Built-in agent skills
│   ├── config.py       # Pydantic settings
│   └── cli.py          # typer CLI entry point
├── tests/
├── workspace/          # Created at runtime (memory, skills, reports)
├── pyproject.toml
├── .env.example
└── CLAUDE.md
```

### Adding a new channel

1. Create `claw/interactive/channels/yourchannel.py`:
   ```python
   class YourConfig(Base):
       enabled: bool = False
       token: str = ""
       allow_from: list[str] = []

   class YourChannel(BaseChannel):
       name = "yourchannel"
       async def start(self): ...
       async def stop(self): ...
       async def send(self, msg: OutboundMessage): ...
   ```
2. Export from `claw/interactive/channels/__init__.py`
3. Register in `InteractiveGateway._build_channels()` in `gateway.py`
4. Add template entry to `_write_channels_template()` in `gateway.py`
5. Add env vars to `.env.example`

---

## License

MIT
