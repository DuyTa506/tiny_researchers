"""Interactive channel implementations — all 5 channels exported."""

from claw.interactive.channels.base import BaseChannel
from claw.interactive.channels.email import EmailChannel, EmailConfig
from claw.interactive.channels.messenger import MessengerChannel, MessengerConfig
from claw.interactive.channels.zalo import ZaloChannel, ZaloConfig

# Discord requires `websockets` (optional dep: pip install "claw-researcher[channels]")
try:
    from claw.interactive.channels.discord import DiscordChannel, DiscordConfig
except ImportError:
    DiscordChannel = None  # type: ignore[assignment,misc]
    DiscordConfig = None   # type: ignore[assignment,misc]

# Telegram requires `python-telegram-bot` (optional dep: pip install "claw-researcher[channels]")
try:
    from claw.interactive.channels.telegram import TelegramChannel, TelegramConfig
except ImportError:
    TelegramChannel = None  # type: ignore[assignment,misc]
    TelegramConfig = None   # type: ignore[assignment,misc]

__all__ = [
    "BaseChannel",
    "DiscordChannel",
    "DiscordConfig",
    "TelegramChannel",
    "TelegramConfig",
    "EmailChannel",
    "EmailConfig",
    "MessengerChannel",
    "MessengerConfig",
    "ZaloChannel",
    "ZaloConfig",
]
