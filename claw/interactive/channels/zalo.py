"""Zalo Official Account channel — webhook-based integration."""

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

ZALO_MAX_MESSAGE_LEN = 2000  # Zalo character limit per message

# Zalo event names that carry text content
_TEXT_EVENT = "user_send_text"
_IMAGE_EVENT = "user_send_image"
_STICKER_EVENT = "user_send_sticker"


class ZaloConfig(Base):
    """Zalo Official Account channel configuration."""

    enabled: bool = False
    oa_access_token: str = ""         # OA API access token
    app_secret: str = ""              # For X-ZaloOA-Signature verification
    allow_from: list[str] = Field(default_factory=list)
    webhook_path: str = "/zalo/webhook"
    api_base: str = "https://openapi.zalo.me"


class ZaloChannel(BaseChannel):
    """
    Zalo Official Account channel using webhook.

    Receive: POST /zalo/webhook (Zalo sends events here)
    Send:    POST https://openapi.zalo.me/v3.0/oa/message/cs

    Requires a public HTTPS URL (use ngrok for local testing).
    """

    name = "zalo"
    display_name = "Zalo"

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        return ZaloConfig().model_dump(by_alias=True)

    def __init__(self, config: Any, bus: MessageBus):
        if isinstance(config, dict):
            config = ZaloConfig.model_validate(config)
        super().__init__(config, bus)
        self.config: ZaloConfig = config
        self._webhook_server: Any = None  # Set by gateway when registering routes

    async def start(self) -> None:
        """
        Register webhook routes with the WebhookServer.

        ZaloChannel has no polling loop — it relies on the
        WebhookServer to call _handle_webhook_post.
        Routes are registered by the gateway via register_routes().
        """
        if not self.config.enabled:
            logger.info("Zalo channel disabled")
            return

        if not self.config.oa_access_token:
            logger.error("Zalo oa_access_token not configured")
            return

        self._running = True
        logger.info(
            "Zalo OA channel ready on webhook path: {}", self.config.webhook_path
        )

    def register_routes(self, webhook_server: Any) -> None:
        """Register POST handler with the webhook server."""
        self._webhook_server = webhook_server
        webhook_server.add_route(
            "POST", self.config.webhook_path, self._handle_webhook_post
        )
        logger.info(
            "Zalo webhook route registered at {}", self.config.webhook_path
        )

    async def stop(self) -> None:
        """Stop the Zalo channel."""
        self._running = False
        logger.info("Zalo channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message to a Zalo user via the OA API."""
        if not self.config.oa_access_token:
            logger.warning("Zalo: oa_access_token not configured")
            return

        recipient_id = msg.chat_id
        if not recipient_id:
            logger.warning("Zalo: missing recipient chat_id")
            return

        url = f"{self.config.api_base}/v3.0/oa/message/cs"
        headers = {
            "access_token": self.config.oa_access_token,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            for chunk in split_message(msg.content or "", ZALO_MAX_MESSAGE_LEN):
                payload = {
                    "recipient": {"user_id": recipient_id},
                    "message": {"text": chunk},
                }
                try:
                    r = await client.post(url, headers=headers, json=payload)
                    r.raise_for_status()
                    resp_data = r.json()
                    if resp_data.get("error") not in (0, None):
                        logger.error(
                            "Zalo API error sending to {}: {}",
                            recipient_id, resp_data,
                        )
                    else:
                        logger.debug("Zalo: sent message to {}", recipient_id)
                except httpx.HTTPStatusError as e:
                    logger.error(
                        "Zalo send HTTP error {} to {}: {}",
                        e.response.status_code, recipient_id, e.response.text,
                    )
                    break
                except Exception as e:
                    logger.error("Zalo send failed to {}: {}", recipient_id, e)
                    break

    def verify_signature(self, body: bytes, signature_header: str) -> bool:
        """
        Verify X-ZaloOA-Signature header.

        Expected: HMAC-SHA256(app_secret, raw_body) as hex string.
        Returns True if signature is valid (or app_secret is not set).
        """
        if not self.config.app_secret:
            logger.debug("Zalo: app_secret not set, skipping signature check")
            return True

        actual_sig = hmac.new(
            self.config.app_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(actual_sig, signature_header):
            logger.warning("Zalo: signature verification failed")
            return False

        return True

    async def _handle_webhook_post(self, request: Any) -> Any:
        """
        Handle POST /zalo/webhook — incoming Zalo OA messages.

        Verifies signature, extracts text messages, publishes to bus.
        """
        from aiohttp import web
        import json

        body = await request.read()

        # Verify X-ZaloOA-Signature
        sig_header = request.headers.get("X-ZaloOA-Signature", "")
        if not self.verify_signature(body, sig_header):
            return web.Response(text="Unauthorized", status=401)

        try:
            data = json.loads(body)
        except Exception as e:
            logger.warning("Zalo: invalid JSON body: {}", e)
            return web.Response(text="Bad Request", status=400)

        event_name = data.get("event_name", "")
        sender_id = str(data.get("user_id_by_app", "") or data.get("sender", {}).get("id", ""))
        message_data = data.get("message", {})
        text = message_data.get("text", "")

        if not sender_id:
            return web.Response(text="OK", status=200)

        if event_name == _TEXT_EVENT:
            if not text:
                logger.debug("Zalo: empty text message from {}, skipping", sender_id)
                return web.Response(text="OK", status=200)

            if not self.is_allowed(sender_id):
                logger.warning("Zalo: access denied for sender {}", sender_id)
                return web.Response(text="OK", status=200)

            logger.debug("Zalo: message from {}: {}...", sender_id, text[:50])

            await self._handle_message(
                sender_id=sender_id,
                chat_id=sender_id,  # Zalo: user_id_by_app is both sender and "chat"
                content=text,
                metadata={
                    "message_id": message_data.get("msg_id", ""),
                    "event_name": event_name,
                    "app_id": data.get("app_id", ""),
                },
            )
        elif event_name in (_IMAGE_EVENT, _STICKER_EVENT):
            # Non-text events: log and skip (no text content to process)
            logger.debug(
                "Zalo: non-text event '{}' from {}, skipping", event_name, sender_id
            )
        else:
            logger.debug("Zalo: unhandled event '{}', ignoring", event_name)

        return web.Response(text="OK", status=200)
