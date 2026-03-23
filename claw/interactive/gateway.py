"""
InteractiveGateway — orchestrates all channels with the AgentLoop.

Architecture:
    Channels → MessageBus.inbound → InteractiveGateway._agent_consumer
                                  → AgentLoop.chat()
                                  → MessageBus.outbound
                                  → InteractiveGateway._outbound_dispatcher
                                  → channel.send()

Webhook channels (Messenger, Zalo) are served by the embedded WebhookServer.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger


class WebhookServer:
    """
    Embedded aiohttp HTTP server for Messenger & Zalo webhooks.

    Usage:
        server = WebhookServer(host="0.0.0.0", port=8080)
        server.add_route("GET", "/messenger/webhook", handler)
        server.add_route("POST", "/messenger/webhook", handler)
        await server.start()
        # ... serve ...
        await server.stop()
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self._routes: list[tuple[str, str, Any]] = []  # (method, path, handler)
        self._runner: Any = None
        self._site: Any = None

    def add_route(self, method: str, path: str, handler: Any) -> None:
        """Register a route handler (called before start())."""
        self._routes.append((method.upper(), path, handler))
        logger.debug("WebhookServer: route registered {} {}", method.upper(), path)

    async def start(self) -> None:
        """Start the aiohttp web server."""
        try:
            from aiohttp import web
        except ImportError:
            logger.error(
                "aiohttp not installed. Install with: pip install aiohttp>=3.9.0"
            )
            return

        app = web.Application()
        for method, path, handler in self._routes:
            app.router.add_route(method, path, handler)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        logger.info(
            "WebhookServer started on http://{}:{}", self.host, self.port
        )

    async def stop(self) -> None:
        """Stop the aiohttp web server."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            self._site = None
            logger.info("WebhookServer stopped")

    @property
    def is_running(self) -> bool:
        return self._runner is not None


class InteractiveGateway:
    """
    Orchestrates all channels with the AgentLoop via the MessageBus.

    - Starts all enabled channels (long-poll, websocket, or webhook-based)
    - Consumes inbound messages and routes them to the agent
    - Dispatches outbound messages back to the correct channel
    """

    def __init__(
        self,
        agent: Any,
        configs: dict[str, Any],
        webhook_host: str = "0.0.0.0",
        webhook_port: int = 8080,
    ):
        """
        Args:
            agent: AgentLoop instance.
            configs: Dict of channel name → config dict or config object.
                     e.g. {"telegram": TelegramConfig(...), "discord": {...}}
            webhook_host: Host for the embedded webhook server.
            webhook_port: Port for the embedded webhook server.
        """
        from claw.interactive.bus.queue import MessageBus

        self.bus = MessageBus()
        self.agent = agent
        self._channels: dict[str, Any] = {}
        self._webhook_server = WebhookServer(webhook_host, webhook_port)
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._build_channels(configs)

    def _build_channels(self, configs: dict[str, Any]) -> None:
        """Instantiate enabled channel objects from configs."""
        from claw.interactive.channels.telegram import TelegramChannel, TelegramConfig
        from claw.interactive.channels.discord import DiscordChannel, DiscordConfig
        from claw.interactive.channels.email import EmailChannel, EmailConfig
        from claw.interactive.channels.messenger import MessengerChannel, MessengerConfig
        from claw.interactive.channels.zalo import ZaloChannel, ZaloConfig

        channel_map = {
            "telegram": (TelegramChannel, TelegramConfig),
            "discord": (DiscordChannel, DiscordConfig),
            "email": (EmailChannel, EmailConfig),
            "messenger": (MessengerChannel, MessengerConfig),
            "zalo": (ZaloChannel, ZaloConfig),
        }

        for name, (channel_cls, config_cls) in channel_map.items():
            raw = configs.get(name)
            if raw is None:
                continue

            # Accept raw dict or already-typed config object
            if isinstance(raw, dict):
                try:
                    config = config_cls.model_validate(raw)
                except Exception as e:
                    logger.error("Gateway: invalid config for channel {}: {}", name, e)
                    continue
            else:
                config = raw

            if not getattr(config, "enabled", False):
                logger.debug("Gateway: channel {} is disabled, skipping", name)
                continue

            try:
                channel = channel_cls(config=config, bus=self.bus)
                self._channels[name] = channel
                logger.info("Gateway: channel {} created", name)
            except Exception as e:
                logger.error("Gateway: failed to create channel {}: {}", name, e)

    async def start(self) -> None:
        """
        Start all channels, the webhook server (if needed), and the
        agent consumer + outbound dispatcher loops.
        """
        self._running = True
        tasks: list[asyncio.Task] = []

        # Determine which channels need the webhook server
        from claw.interactive.channels.messenger import MessengerChannel
        from claw.interactive.channels.zalo import ZaloChannel
        webhook_channels = {
            k: v for k, v in self._channels.items()
            if isinstance(v, (MessengerChannel, ZaloChannel))
        }
        poll_channels = {
            k: v for k, v in self._channels.items()
            if k not in webhook_channels
        }

        # Register webhook routes before starting channels
        for name, ch in webhook_channels.items():
            try:
                ch.register_routes(self._webhook_server)
                await ch.start()
            except Exception as e:
                logger.error("Gateway: error starting webhook channel {}: {}", name, e)

        # Start webhook server if any webhook channels exist
        if webhook_channels:
            tasks.append(asyncio.create_task(
                self._webhook_server.start(), name="webhook_server"
            ))

        # Start long-poll / websocket channels
        for name, ch in poll_channels.items():
            tasks.append(asyncio.create_task(ch.start(), name=f"channel_{name}"))

        # Agent consumer: inbound → agent → outbound
        tasks.append(asyncio.create_task(
            self._agent_consumer(), name="agent_consumer"
        ))

        # Outbound dispatcher: outbound queue → channel.send()
        tasks.append(asyncio.create_task(
            self._outbound_dispatcher(), name="outbound_dispatcher"
        ))

        self._tasks = tasks
        logger.info(
            "InteractiveGateway started with {} channel(s): {}",
            len(self._channels),
            list(self._channels.keys()),
        )

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _agent_consumer(self) -> None:
        """
        Consume inbound messages from the bus and dispatch to the agent.
        Each message is processed concurrently via asyncio.create_task().
        """
        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(), timeout=1.0
                )
                # Fire-and-forget to allow concurrent message handling
                asyncio.create_task(
                    self._process_message(msg), name=f"msg_{msg.session_key}"
                )
            except asyncio.TimeoutError:
                continue  # Check _running flag
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Gateway: agent_consumer error: {}", e)

    async def _process_message(self, msg: Any) -> None:
        """Process one inbound message through the agent and publish the response."""
        from claw.interactive.bus.events import OutboundMessage

        try:
            async def on_progress(text: str) -> None:
                """Send typing indicator back to the originating channel."""
                try:
                    await self.bus.publish_outbound(
                        OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content="",
                            metadata={"typing": True, "_progress": True},
                        )
                    )
                except Exception:
                    pass

            response = await self.agent.chat(
                message=msg.content,
                session_key=msg.session_key,
                on_progress=on_progress,
            )

            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=response or "",
                    reply_to=msg.metadata.get("message_id"),
                    metadata={"message_thread_id": msg.metadata.get("message_thread_id")},
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(
                "Gateway: error processing message from {}/{}: {}",
                msg.channel, msg.session_key, e,
            )
            # Send error message back to user
            try:
                from claw.interactive.bus.events import OutboundMessage
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content="Sorry, I encountered an error. Please try again.",
                    )
                )
            except Exception:
                pass

    async def _outbound_dispatcher(self) -> None:
        """
        Consume outbound messages and route each to the correct channel.send().
        """
        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(), timeout=1.0
                )
                channel = self._channels.get(msg.channel)
                if channel:
                    asyncio.create_task(
                        channel.send(msg), name=f"send_{msg.channel}_{msg.chat_id}"
                    )
                else:
                    logger.warning(
                        "Gateway: no channel found for outbound message to: {}",
                        msg.channel,
                    )
            except asyncio.TimeoutError:
                continue  # Check _running flag
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Gateway: outbound_dispatcher error: {}", e)

    async def stop(self) -> None:
        """Gracefully stop the gateway and all channels."""
        logger.info("InteractiveGateway shutting down...")
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Stop all channels
        for name, ch in self._channels.items():
            try:
                await ch.stop()
                logger.debug("Gateway: channel {} stopped", name)
            except Exception as e:
                logger.error("Gateway: error stopping channel {}: {}", name, e)

        # Stop webhook server
        await self._webhook_server.stop()

        logger.info("InteractiveGateway stopped")

    @property
    def channels(self) -> dict[str, Any]:
        """Return read-only view of active channels."""
        return dict(self._channels)


def _write_channels_template(config_path: Path) -> None:
    """Write a channels.json template to the given path."""
    template = {
        "telegram": {
            "enabled": False,
            "token": "",
            "allow_from": ["*"],
            "group_policy": "mention",
        },
        "discord": {
            "enabled": False,
            "token": "",
            "allow_from": ["*"],
            "group_policy": "mention",
        },
        "email": {
            "enabled": False,
            "consent_granted": False,
            "imap_host": "imap.gmail.com",
            "imap_port": 993,
            "imap_username": "",
            "imap_password": "",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_username": "",
            "smtp_password": "",
            "from_address": "",
            "allow_from": [],
        },
        "messenger": {
            "enabled": False,
            "page_access_token": "",
            "verify_token": "",
            "app_secret": "",
            "allow_from": ["*"],
            "webhook_path": "/messenger/webhook",
        },
        "zalo": {
            "enabled": False,
            "oa_access_token": "",
            "app_secret": "",
            "allow_from": ["*"],
            "webhook_path": "/zalo/webhook",
        },
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(template, indent=2, ensure_ascii=False), encoding="utf-8")
