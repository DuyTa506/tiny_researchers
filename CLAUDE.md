# Project Instructions
## Project: Claw Researcher

AI Agent system for academic research with multi-channel interactive messaging.

### Package Layout

```
claw/
├── agent/               # Core AgentLoop, LLM providers, tools, memory
│   ├── loop.py          # AgentLoop — main chat/session engine
│   ├── providers.py     # LLMProvider (litellm / Anthropic)
│   ├── memory.py        # MemoryStore + MemoryConsolidator
│   ├── skills.py        # SkillsLoader
│   ├── context.py       # ContextBuilder (system prompt, history, memory)
│   ├── subagent.py      # SubagentManager
│   └── tools/           # ReadFile, WriteFile, Exec, Web, PaperSearch, …
├── interactive/         # Multi-channel messaging integration
│   ├── __init__.py      # exports: MessageBus, InboundMessage, OutboundMessage
│   ├── gateway.py       # InteractiveGateway + WebhookServer (aiohttp)
│   ├── bus/
│   │   ├── events.py    # InboundMessage, OutboundMessage dataclasses
│   │   └── queue.py     # MessageBus (asyncio.Queue wrapper)
│   ├── channels/
│   │   ├── base.py      # BaseChannel ABC (is_allowed, _handle_message, transcribe_audio)
│   │   ├── telegram.py  # Long-polling, markdown→HTML, group policy, topic sessions
│   │   ├── discord.py   # Gateway WebSocket, REST API, rate-limiting
│   │   ├── email.py     # IMAP poll + SMTP reply
│   │   ├── messenger.py # Facebook Messenger webhook + HMAC-SHA256 verification
│   │   └── zalo.py      # Zalo OA webhook + HMAC-SHA256 verification
│   └── config/
│       ├── schema.py    # Base pydantic model (extra=ignore, populate_by_name)
│       └── paths.py     # get_media_dir(channel) → workspace/media/<channel>/
├── providers/
│   └── transcription.py # GroqTranscriptionProvider (Whisper via Groq API)
├── security/
│   └── network.py       # validate_url_target() — SSRF protection
├── core/                # FastAPI gateway (api_gateway.py, models.py)
├── tools/               # Research API clients (Arxiv, OpenAlex, PwC, S2)
├── utils/
│   └── helpers.py       # split_message, build_image_content_blocks, token utils
├── config.py            # Settings (pydantic-settings, CLAW_ prefix, .env)
├── cli.py               # typer CLI: chat | onboard | status | serve
└── skills/              # Builtin skills (survey, brainstorm, report, …)
```

### Architecture: Multi-Channel Flow

```
Telegram (long-poll)  ─┐
Discord (WebSocket)   ─┤  InboundMessage
Email (IMAP poll)     ─┼──────────────► MessageBus.inbound
Messenger (webhook)   ─┤               │
Zalo (webhook)        ─┘               ▼
                        WebhookServer  InteractiveGateway._agent_consumer
                        (aiohttp 8080) │
                                       ▼
                                  AgentLoop.chat(session_key)
                                       │
                                       ▼ OutboundMessage
                                  MessageBus.outbound
                                       │
                                  InteractiveGateway._outbound_dispatcher
                                       │
                                  channel.send(OutboundMessage)
```

### Key Design Decisions

- **Session isolation**: `session_key = "{channel}:{chat_id}"` — each chat gets its own history
- **Concurrency**: `asyncio.create_task()` per message — multiple users never block each other
- **Graceful degradation**: channels that fail to start don't block others
- **Optional deps**: `websockets` (Discord) and `python-telegram-bot` (Telegram) are optional; channels fall back gracefully if not installed
- **SSRF protection**: `validate_url_target()` blocks private/loopback IPs before any outbound fetch
- **Signature verification**: Messenger uses `X-Hub-Signature-256` (HMAC-SHA256); Zalo uses `X-ZaloOA-Signature`

### CLI Commands

```bash
claw chat      [--model MODEL] [--workspace PATH]   # Interactive research REPL
claw onboard   [--workspace PATH]                   # Init workspace (skills + memory)
claw status                                         # Check API keys and imports
claw serve     [--workspace PATH]                   # Multi-channel interactive server
               [--config-file channels.json]
               [--webhook-host 0.0.0.0]
               [--webhook-port 8080]
```

### Configuration

All settings use `CLAW_` prefix in `.env`:

```bash
CLAW_WORKSPACE=./workspace
CLAW_DEFAULT_MODEL=anthropic/claude-sonnet-4-20250514
CLAW_MAX_ITERATIONS=40
ANTHROPIC_API_KEY=sk-ant-...
```

Channel config lives in `workspace/channels.json` (auto-generated template on first `claw serve`).

### Testing

```bash
# All tests
.venv/Scripts/python.exe -m pytest tests/ -v

# Smoke tests only (interactive module)
.venv/Scripts/python.exe -m pytest tests/test_interactive_smoke.py -v
```

### Dependencies

| Group | Install | Key packages |
|-------|---------|--------------|
| Core | `uv pip install -e .` | litellm, httpx, pydantic, typer, rich, loguru |
| Channels | `uv pip install -e ".[channels]"` | websockets, python-telegram-bot, aiohttp |
| Dev | `uv pip install -e ".[dev]"` | pytest, pytest-asyncio, ruff |

### Adding a New Channel

1. Create `claw/interactive/channels/yourchannel.py` with `YourConfig(Base)` and `YourChannel(BaseChannel)`
2. Implement `start()`, `stop()`, `send()`
3. Export from `claw/interactive/channels/__init__.py`
4. Register in `InteractiveGateway._build_channels()` in `gateway.py`
5. Add config section to `_write_channels_template()` in `gateway.py`
6. Add env vars to `.env.example`
