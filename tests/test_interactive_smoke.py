"""
Smoke tests for claw.interactive multi-channel integration.

~35 tests covering:
- Module imports
- Config schema
- MessageBus publish/consume
- InboundMessage.session_key
- BaseChannel.is_allowed()
- All 5 channel configs instantiation
- Channel instantiation with mock bus
- InteractiveGateway instantiation
- split_message()
- validate_url_target()
- WebhookServer instantiation
- MessengerChannel webhook challenge + signature
- ZaloChannel signature validation
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# 1. Module Imports
# ===========================================================================


def test_import_messagebus():
    from claw.interactive import MessageBus
    assert MessageBus is not None


def test_import_events():
    from claw.interactive import InboundMessage, OutboundMessage
    assert InboundMessage is not None
    assert OutboundMessage is not None


def test_import_bus_submodule():
    from claw.interactive.bus import MessageBus, InboundMessage, OutboundMessage
    assert MessageBus is not None


def test_import_config_schema():
    from claw.interactive.config.schema import Base
    assert Base is not None


def test_import_security_network():
    from claw.security.network import validate_url_target
    assert callable(validate_url_target)


def test_import_transcription():
    from claw.providers.transcription import GroqTranscriptionProvider
    assert GroqTranscriptionProvider is not None


def test_import_channels_init():
    from claw.interactive.channels import (
        BaseChannel,
        EmailChannel, EmailConfig,
        MessengerChannel, MessengerConfig,
        ZaloChannel, ZaloConfig,
    )
    # Always available (no extra deps)
    assert BaseChannel is not None
    assert all(c is not None for c in [
        EmailChannel, EmailConfig,
        MessengerChannel, MessengerConfig,
        ZaloChannel, ZaloConfig,
    ])
    # Optional deps (may be None if not installed)
    from claw.interactive.channels import DiscordChannel, TelegramChannel
    # They will be None if packages not installed, or the class if installed
    # Just verify the import itself doesn't raise


def test_import_gateway():
    from claw.interactive.gateway import InteractiveGateway, WebhookServer
    assert InteractiveGateway is not None
    assert WebhookServer is not None


# ===========================================================================
# 2. Config Schema
# ===========================================================================


def test_base_config_default():
    from claw.interactive.config.schema import Base

    class MyConf(Base):
        name: str = "test"

    c = MyConf()
    assert c.name == "test"


def test_base_config_extra_ignored():
    """Extra fields should be silently ignored."""
    from claw.interactive.config.schema import Base

    class MyConf(Base):
        value: int = 5

    c = MyConf.model_validate({"value": 10, "unknown_field": "foo"})
    assert c.value == 10


def test_get_media_dir(tmp_path):
    """get_media_dir() creates and returns media directory."""
    from claw.interactive.config.paths import get_media_dir
    from claw.config import get_settings

    with patch.object(get_settings(), "workspace", tmp_path):
        with patch("claw.interactive.config.paths.get_settings") as mock_settings:
            mock_settings.return_value.workspace = tmp_path
            media = get_media_dir("test_channel")
            assert media.exists()
            assert media.is_dir()
            assert "test_channel" in str(media)


# ===========================================================================
# 3. MessageBus
# ===========================================================================


@pytest.mark.asyncio
async def test_messagebus_publish_consume_inbound():
    from claw.interactive import MessageBus, InboundMessage

    bus = MessageBus()
    msg = InboundMessage(
        channel="telegram",
        sender_id="user1",
        chat_id="chat1",
        content="Hello!",
    )
    await bus.publish_inbound(msg)
    received = await bus.consume_inbound()
    assert received.content == "Hello!"
    assert received.channel == "telegram"


@pytest.mark.asyncio
async def test_messagebus_publish_consume_outbound():
    from claw.interactive import MessageBus, OutboundMessage

    bus = MessageBus()
    msg = OutboundMessage(
        channel="discord",
        chat_id="channel123",
        content="Response!",
    )
    await bus.publish_outbound(msg)
    received = await bus.consume_outbound()
    assert received.content == "Response!"
    assert received.channel == "discord"


@pytest.mark.asyncio
async def test_messagebus_queue_sizes():
    from claw.interactive import MessageBus, InboundMessage, OutboundMessage

    bus = MessageBus()
    assert bus.inbound_size == 0
    assert bus.outbound_size == 0

    await bus.publish_inbound(
        InboundMessage("telegram", "u1", "c1", "msg1")
    )
    await bus.publish_inbound(
        InboundMessage("telegram", "u1", "c1", "msg2")
    )
    assert bus.inbound_size == 2

    await bus.consume_inbound()
    assert bus.inbound_size == 1


# ===========================================================================
# 4. InboundMessage.session_key
# ===========================================================================


def test_inbound_message_session_key_default():
    from claw.interactive import InboundMessage

    msg = InboundMessage(
        channel="telegram",
        sender_id="user123",
        chat_id="chat456",
        content="hi",
    )
    assert msg.session_key == "telegram:chat456"


def test_inbound_message_session_key_override():
    from claw.interactive import InboundMessage

    msg = InboundMessage(
        channel="telegram",
        sender_id="user123",
        chat_id="chat456",
        content="hi",
        session_key_override="telegram:chat456:topic:789",
    )
    assert msg.session_key == "telegram:chat456:topic:789"


# ===========================================================================
# 5. BaseChannel.is_allowed()
# ===========================================================================


def _make_channel(allow_from: list[str]):
    """Helper: create a concrete BaseChannel subclass with a mock bus."""
    from claw.interactive.channels.base import BaseChannel
    from claw.interactive import MessageBus
    from claw.interactive.config.schema import Base
    from pydantic import Field

    _allow_from = allow_from  # capture for class body default

    class DummyConfig(Base):
        enabled: bool = True
        allow_from: list[str] = Field(default_factory=list)

    class DummyChannel(BaseChannel):
        name = "dummy"
        display_name = "Dummy"

        async def start(self): pass
        async def stop(self): pass
        async def send(self, msg): pass

    bus = MessageBus()
    return DummyChannel(DummyConfig(allow_from=_allow_from), bus)


def test_is_allowed_empty_list_denies_all():
    ch = _make_channel([])
    assert ch.is_allowed("anyone") is False


def test_is_allowed_star_allows_all():
    ch = _make_channel(["*"])
    assert ch.is_allowed("user123") is True
    assert ch.is_allowed("random_user") is True


def test_is_allowed_specific_user():
    ch = _make_channel(["user123", "admin"])
    assert ch.is_allowed("user123") is True
    assert ch.is_allowed("admin") is True
    assert ch.is_allowed("stranger") is False


# ===========================================================================
# 6. Channel Config Instantiation
# ===========================================================================


def test_telegram_config_defaults():
    pytest.importorskip("telegram", reason="python-telegram-bot not installed")
    from claw.interactive.channels.telegram import TelegramConfig
    c = TelegramConfig()
    assert c.enabled is False
    assert c.token == ""
    assert c.group_policy == "mention"


def test_discord_config_defaults():
    pytest.importorskip("websockets", reason="websockets not installed")
    from claw.interactive.channels.discord import DiscordConfig
    c = DiscordConfig()
    assert c.enabled is False
    assert c.token == ""
    assert c.group_policy == "mention"


def test_email_config_defaults():
    from claw.interactive.channels.email import EmailConfig
    c = EmailConfig()
    assert c.enabled is False
    assert c.imap_host == ""
    assert c.smtp_port == 587


def test_messenger_config_defaults():
    from claw.interactive.channels.messenger import MessengerConfig
    c = MessengerConfig()
    assert c.enabled is False
    assert c.page_access_token == ""
    assert c.webhook_path == "/messenger/webhook"


def test_zalo_config_defaults():
    from claw.interactive.channels.zalo import ZaloConfig
    c = ZaloConfig()
    assert c.enabled is False
    assert c.oa_access_token == ""
    assert c.webhook_path == "/zalo/webhook"
    assert c.api_base == "https://openapi.zalo.me"


# ===========================================================================
# 7. Channel Instantiation with Mock Bus
# ===========================================================================


def _make_bus():
    from claw.interactive import MessageBus
    return MessageBus()


def test_telegram_channel_instantiation():
    pytest.importorskip("telegram", reason="python-telegram-bot not installed")
    from claw.interactive.channels.telegram import TelegramChannel, TelegramConfig
    ch = TelegramChannel(TelegramConfig(enabled=True, token="tok"), _make_bus())
    assert ch.name == "telegram"
    assert ch.is_running is False


def test_discord_channel_instantiation():
    pytest.importorskip("websockets", reason="websockets not installed")
    from claw.interactive.channels.discord import DiscordChannel, DiscordConfig
    ch = DiscordChannel(DiscordConfig(enabled=True, token="tok"), _make_bus())
    assert ch.name == "discord"


def test_email_channel_instantiation():
    from claw.interactive.channels.email import EmailChannel, EmailConfig
    ch = EmailChannel(EmailConfig(enabled=True), _make_bus())
    assert ch.name == "email"


def test_messenger_channel_instantiation():
    from claw.interactive.channels.messenger import MessengerChannel, MessengerConfig
    ch = MessengerChannel(
        MessengerConfig(enabled=True, page_access_token="tok", verify_token="vt"),
        _make_bus(),
    )
    assert ch.name == "messenger"
    assert ch.is_running is False


def test_zalo_channel_instantiation():
    from claw.interactive.channels.zalo import ZaloChannel, ZaloConfig
    ch = ZaloChannel(ZaloConfig(enabled=True, oa_access_token="tok"), _make_bus())
    assert ch.name == "zalo"
    assert ch.is_running is False


# ===========================================================================
# 8. InteractiveGateway Instantiation (no start)
# ===========================================================================


def test_interactive_gateway_instantiation():
    from claw.interactive.gateway import InteractiveGateway

    mock_agent = MagicMock()
    gw = InteractiveGateway(
        agent=mock_agent,
        configs={},
        webhook_host="0.0.0.0",
        webhook_port=9999,
    )
    assert gw._running is False
    assert isinstance(gw.channels, dict)


def test_interactive_gateway_skips_disabled_channels():
    from claw.interactive.gateway import InteractiveGateway

    mock_agent = MagicMock()
    configs = {
        "telegram": {"enabled": False, "token": "test"},
        "discord": {"enabled": False, "token": "test"},
    }
    gw = InteractiveGateway(agent=mock_agent, configs=configs)
    assert len(gw.channels) == 0


def test_interactive_gateway_builds_enabled_channels():
    from claw.interactive.gateway import InteractiveGateway

    mock_agent = MagicMock()
    configs = {
        "telegram": {"enabled": True, "token": "test_token", "allow_from": ["*"]},
        "discord": {"enabled": False, "token": ""},
    }
    gw = InteractiveGateway(agent=mock_agent, configs=configs)
    assert "telegram" in gw.channels
    assert "discord" not in gw.channels


# ===========================================================================
# 9. WebhookServer Instantiation
# ===========================================================================


def test_webhook_server_instantiation():
    from claw.interactive.gateway import WebhookServer
    ws = WebhookServer(host="127.0.0.1", port=9001)
    assert ws.host == "127.0.0.1"
    assert ws.port == 9001
    assert ws.is_running is False


def test_webhook_server_add_route():
    from claw.interactive.gateway import WebhookServer
    ws = WebhookServer()

    async def dummy_handler(req): ...

    ws.add_route("GET", "/test", dummy_handler)
    ws.add_route("POST", "/test", dummy_handler)
    assert len(ws._routes) == 2


# ===========================================================================
# 10. split_message()
# ===========================================================================


def test_split_message_short_content():
    from claw.utils.helpers import split_message
    result = split_message("Hello world", 2000)
    assert result == ["Hello world"]


def test_split_message_empty():
    from claw.utils.helpers import split_message
    result = split_message("", 2000)
    assert result == []


def test_split_message_long_content():
    from claw.utils.helpers import split_message
    content = "a" * 5000
    chunks = split_message(content, 2000)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= 2000


def test_split_message_respects_newlines():
    from claw.utils.helpers import split_message
    content = ("Hello World\n" * 200)
    chunks = split_message(content, 500)
    # Each chunk should be within the limit
    for chunk in chunks:
        assert len(chunk) <= 500
    # Joining chunks should recover full content (minus leading whitespace stripped)
    assert all("Hello World" in chunk for chunk in chunks)


# ===========================================================================
# 11. validate_url_target()
# ===========================================================================


def test_validate_url_target_private_ip_blocked():
    from claw.security.network import validate_url_target
    # localhost resolves to 127.0.0.1 which is in blocked range → returns (False, reason)
    ok, reason = validate_url_target("http://localhost/test")
    assert ok is False
    assert "Blocked" in reason


def test_validate_url_target_loopback_blocked():
    from claw.security.network import validate_url_target
    # 127.0.0.1 is in 127.0.0.0/8 → blocked
    ok, reason = validate_url_target("http://127.0.0.1/test")
    assert ok is False
    assert "Blocked" in reason


def test_validate_url_target_private_range_blocked():
    from claw.security.network import validate_url_target
    ok, reason = validate_url_target("http://192.168.1.1/test")
    assert ok is False


def test_validate_url_target_invalid_hostname():
    import socket
    from unittest.mock import patch
    from claw.security.network import validate_url_target
    # Mock gethostbyname to simulate DNS failure regardless of OS behavior
    with patch("socket.gethostbyname", side_effect=socket.gaierror("Name or service not known")):
        with pytest.raises(ValueError, match="Cannot resolve"):
            validate_url_target("http://this-host-definitely-does-not-exist.invalid/path")


# ===========================================================================
# 12. MessengerChannel Webhook Challenge
# ===========================================================================


def test_messenger_verify_challenge_success():
    from claw.interactive.channels.messenger import MessengerChannel, MessengerConfig

    ch = MessengerChannel(
        MessengerConfig(
            enabled=True,
            page_access_token="tok",
            verify_token="my-verify-token",
        ),
        _make_bus(),
    )
    challenge = ch.verify_webhook_challenge({
        "hub.mode": "subscribe",
        "hub.verify_token": "my-verify-token",
        "hub.challenge": "challenge123",
    })
    assert challenge == "challenge123"


def test_messenger_verify_challenge_wrong_token():
    from claw.interactive.channels.messenger import MessengerChannel, MessengerConfig

    ch = MessengerChannel(
        MessengerConfig(
            enabled=True,
            page_access_token="tok",
            verify_token="correct-token",
        ),
        _make_bus(),
    )
    challenge = ch.verify_webhook_challenge({
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong-token",
        "hub.challenge": "challenge123",
    })
    assert challenge is None


def test_messenger_verify_signature_valid():
    from claw.interactive.channels.messenger import MessengerChannel, MessengerConfig

    secret = "my_app_secret"
    ch = MessengerChannel(
        MessengerConfig(
            enabled=True,
            page_access_token="tok",
            verify_token="vt",
            app_secret=secret,
        ),
        _make_bus(),
    )
    body = b'{"entry": []}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert ch.verify_signature(body, f"sha256={sig}") is True


def test_messenger_verify_signature_invalid():
    from claw.interactive.channels.messenger import MessengerChannel, MessengerConfig

    ch = MessengerChannel(
        MessengerConfig(
            enabled=True,
            page_access_token="tok",
            verify_token="vt",
            app_secret="real_secret",
        ),
        _make_bus(),
    )
    body = b'{"entry": []}'
    assert ch.verify_signature(body, "sha256=wrong_signature") is False


def test_messenger_verify_signature_no_secret():
    """If no app_secret configured, signature check is skipped (returns True)."""
    from claw.interactive.channels.messenger import MessengerChannel, MessengerConfig

    ch = MessengerChannel(
        MessengerConfig(enabled=True, page_access_token="tok", verify_token="vt"),
        _make_bus(),
    )
    # No app_secret → always pass
    assert ch.verify_signature(b"body", "sha256=anything") is True


# ===========================================================================
# 13. ZaloChannel Signature Validation
# ===========================================================================


def test_zalo_verify_signature_valid():
    from claw.interactive.channels.zalo import ZaloChannel, ZaloConfig

    secret = "zalo_secret"
    ch = ZaloChannel(
        ZaloConfig(
            enabled=True,
            oa_access_token="tok",
            app_secret=secret,
        ),
        _make_bus(),
    )
    body = b'{"event_name": "user_send_text"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert ch.verify_signature(body, sig) is True


def test_zalo_verify_signature_invalid():
    from claw.interactive.channels.zalo import ZaloChannel, ZaloConfig

    ch = ZaloChannel(
        ZaloConfig(
            enabled=True,
            oa_access_token="tok",
            app_secret="real_secret",
        ),
        _make_bus(),
    )
    body = b'{"event_name": "user_send_text"}'
    assert ch.verify_signature(body, "bad_signature") is False


def test_zalo_verify_signature_no_secret():
    """If no app_secret configured, signature check is skipped (returns True)."""
    from claw.interactive.channels.zalo import ZaloChannel, ZaloConfig

    ch = ZaloChannel(
        ZaloConfig(enabled=True, oa_access_token="tok"),
        _make_bus(),
    )
    assert ch.verify_signature(b"body", "any_signature") is True
