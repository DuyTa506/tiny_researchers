"""Facebook Messenger channel — webhook-based integration."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx
from loguru import logger
from pydantic import Field

from claw.interactive.bus.events import OutboundMessage
from claw.interactive.bus.queue import MessageBus
from claw.interactive.channels.base import BaseChannel
from claw.interactive.config.schema import Base
from claw.utils.helpers import split_message

MESSENGER_API_BASE = "https://graph.facebook.com/v18.0"
MESSENGER_MAX_MESSAGE_LEN = 2000  # Facebook Messenger character limit


class MessengerConfig(Base):
    """Facebook Messenger channel configuration."""

    enabled: bool = False
    page_access_token: str = ""       # From Facebook App → Page token
    verify_token: str = ""            # Custom string for webhook verification
    app_secret: str = ""              # For X-Hub-Signature-256 verification
    allow_from: list[str] = Field(default_factory=list)  # Sender PSIDs, or ["*"]
    webhook_path: str = "/messenger/webhook"


class MessengerChannel(BaseChannel):
    """
    Facebook Messenger channel using webhook.

    Receive: POST /messenger/webhook (Facebook sends events here)
    Send:    POST https://graph.facebook.com/v18.0/me/messages

    Requires a public HTTPS URL (use ngrok for local testing).
    """

    name = "messenger"
    display_name = "Messenger"

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        return MessengerConfig().model_dump(by_alias=True)

    def __init__(self, config: Any, bus: MessageBus):
        if isinstance(config, dict):
            config = MessengerConfig.model_validate(config)
        super().__init__(config, bus)
        self.config: MessengerConfig = config
        self._webhook_server: Any = None  # Set by gateway when registering routes

    async def start(self) -> None:
        """
        Register webhook routes with the WebhookServer.

        MessengerChannel has no polling loop — it relies on the
        WebhookServer to call _handle_webhook_get and _handle_webhook_post.
        Routes are registered by the gateway via register_routes().
        """
        if not self.config.enabled:
            logger.info("Messenger channel disabled")
            return

        if not self.config.page_access_token:
            logger.error("Messenger page_access_token not configured")
            return

        if not self.config.verify_token:
            logger.error("Messenger verify_token not configured")
            return

        self._running = True
        logger.info(
            "Messenger channel ready on webhook path: {}", self.config.webhook_path
        )

    def register_routes(self, webhook_server: Any) -> None:
        """Register GET and POST handlers with the webhook server."""
        self._webhook_server = webhook_server
        webhook_server.add_route(
            "GET", self.config.webhook_path, self._handle_webhook_get
        )
        webhook_server.add_route(
            "POST", self.config.webhook_path, self._handle_webhook_post
        )
        logger.info(
            "Messenger webhook routes registered at {}", self.config.webhook_path
        )

    async def stop(self) -> None:
        """Stop the Messenger channel."""
        self._running = False
        logger.info("Messenger channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message to a Messenger user via the Send API."""
        if not self.config.page_access_token:
            logger.warning("Messenger: page_access_token not configured")
            return

        recipient_id = msg.chat_id
        if not recipient_id:
            logger.warning("Messenger: missing recipient chat_id")
            return

        url = f"{MESSENGER_API_BASE}/me/messages"
        params = {"access_token": self.config.page_access_token}

        async with httpx.AsyncClient(timeout=30.0) as client:
            for chunk in split_message(msg.content or "", MESSENGER_MAX_MESSAGE_LEN):
                payload = {
                    "recipient": {"id": recipient_id},
                    "message": {"text": chunk},
                }
                try:
                    r = await client.post(url, params=params, json=payload)
                    r.raise_for_status()
                    logger.debug("Messenger: sent message to {}", recipient_id)
                except httpx.HTTPStatusError as e:
                    logger.error(
                        "Messenger send error {} to {}: {}",
                        e.response.status_code, recipient_id, e.response.text,
                    )
                    break
                except Exception as e:
                    logger.error("Messenger send failed to {}: {}", recipient_id, e)
                    break

    def verify_webhook_challenge(self, query_params: dict[str, str]) -> str | None:
        """
        Verify Facebook webhook subscription challenge.

        Returns hub.challenge string if verification passes, else None.
        """
        mode = query_params.get("hub.mode", "")
        token = query_params.get("hub.verify_token", "")
        challenge = query_params.get("hub.challenge", "")

        if mode == "subscribe" and token == self.config.verify_token:
            logger.info("Messenger webhook verification successful")
            return challenge

        logger.warning(
            "Messenger webhook verification failed (mode={}, token_match={})",
            mode, token == self.config.verify_token,
        )
        return None

    def verify_signature(self, body: bytes, signature_header: str) -> bool:
        """
        Verify X-Hub-Signature-256 header from Facebook.

        Returns True if signature is valid (or if app_secret is not configured).
        """
        if not self.config.app_secret:
            # If no app_secret configured, skip verification (development mode)
            logger.debug("Messenger: app_secret not set, skipping signature check")
            return True

        if not signature_header.startswith("sha256="):
            logger.warning("Messenger: invalid signature header format")
            return False

        expected_sig = signature_header[len("sha256="):]
        actual_sig = hmac.new(
            self.config.app_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, actual_sig):
            logger.warning("Messenger: signature verification failed")
            return False

        return True

    async def _handle_webhook_get(self, request: Any) -> Any:
        """
        Handle GET /messenger/webhook — Facebook subscription verification.

        Works with aiohttp.web.Request.
        """
        from aiohttp import web

        query = dict(request.rel_url.query)
        challenge = self.verify_webhook_challenge(query)
        if challenge is not None:
            return web.Response(text=challenge, status=200)
        return web.Response(text="Forbidden", status=403)

    async def _handle_webhook_post(self, request: Any) -> Any:
        """
        Handle POST /messenger/webhook — incoming Facebook messages.

        Verifies signature, extracts messages, publishes to bus.
        """
        from aiohttp import web
        import json

        body = await request.read()

        # Verify X-Hub-Signature-256
        sig_header = request.headers.get("X-Hub-Signature-256", "")
        if not self.verify_signature(body, sig_header):
            return web.Response(text="Unauthorized", status=401)

        try:
            data = json.loads(body)
        except Exception as e:
            logger.warning("Messenger: invalid JSON body: {}", e)
            return web.Response(text="Bad Request", status=400)

        # Process each entry
        for entry in data.get("entry", []):
            for messaging in entry.get("messaging", []):
                sender_id = (messaging.get("sender") or {}).get("id", "")
                message = messaging.get("message", {})
                text = message.get("text", "")

                if not sender_id:
                    continue

                # Skip echo messages (sent by the page itself)
                if message.get("is_echo"):
                    continue

                # Skip non-text (attachments, stickers, etc.)
                if not text:
                    attachment_types = [
                        a.get("type", "") for a in message.get("attachments", [])
                    ]
                    if attachment_types:
                        logger.debug(
                            "Messenger: non-text message from {} ({}), skipping",
                            sender_id, attachment_types,
                        )
                    continue

                if not self.is_allowed(sender_id):
                    logger.warning(
                        "Messenger: access denied for sender {}", sender_id
                    )
                    continue

                logger.debug(
                    "Messenger: message from {}: {}...", sender_id, text[:50]
                )

                await self._handle_message(
                    sender_id=sender_id,
                    chat_id=sender_id,  # In Messenger, PSID is both sender and "chat"
                    content=text,
                    metadata={
                        "message_id": message.get("mid", ""),
                        "sender_psid": sender_id,
                    },
                )

        # Facebook requires a 200 OK response quickly
        return web.Response(text="EVENT_RECEIVED", status=200)
