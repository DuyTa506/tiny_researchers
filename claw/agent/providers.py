"""
LLM Provider abstraction.

Supports any OpenAI-compatible API via litellm:
  - Anthropic Claude
  - OpenAI GPT
  - DeepSeek, Qwen, etc.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from loguru import logger


class LLMProvider:
    """Unified LLM provider using litellm for multi-provider support."""

    def __init__(self, model: str = "anthropic/claude-sonnet-4-20250514", api_key: str | None = None):
        self.default_model = model
        self.api_key = api_key

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tools: list[dict] | None = None,
        tool_choice: Any = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Send a chat completion request. Returns normalized response dict."""
        try:
            from litellm import acompletion

            kwargs: dict[str, Any] = {
                "model": model or self.default_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if tools:
                kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice
            if self.api_key:
                kwargs["api_key"] = self.api_key

            response = await acompletion(**kwargs)
            return self._normalize_response(response)

        except ImportError:
            logger.warning("litellm not installed, falling back to direct Anthropic API")
            return await self._chat_anthropic_direct(messages, model, tools, max_tokens)
        except Exception as e:
            logger.error("LLM chat failed: {}", e)
            return {
                "content": f"Error: {str(e)}",
                "tool_calls": [],
                "finish_reason": "error",
                "usage": {},
            }

    async def chat_with_retry(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tools: list[dict] | None = None,
        tool_choice: Any = None,
        max_retries: int = 2,
        **kwargs,
    ) -> dict[str, Any]:
        """Chat with automatic retry on transient errors."""
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return await self.chat(messages, model=model, tools=tools, tool_choice=tool_choice, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning("LLM call failed (attempt {}), retrying: {}", attempt + 1, e)
                    import asyncio
                    await asyncio.sleep(1 * (attempt + 1))

        return {
            "content": f"Error after {max_retries + 1} attempts: {last_error}",
            "tool_calls": [],
            "finish_reason": "error",
            "usage": {},
        }

    def _normalize_response(self, response: Any) -> dict[str, Any]:
        """Normalize litellm response to a simple dict."""
        choice = response.choices[0] if response.choices else None
        if not choice:
            return {"content": None, "tool_calls": [], "finish_reason": "error", "usage": {}}

        message = choice.message
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        pass
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args,
                })

        return {
            "content": message.content,
            "tool_calls": tool_calls,
            "finish_reason": choice.finish_reason,
            "usage": dict(response.usage) if response.usage else {},
        }

    async def _chat_anthropic_direct(
        self,
        messages: list[dict],
        model: str | None,
        tools: list[dict] | None,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Direct Anthropic API fallback (no litellm needed)."""
        import os

        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return {"content": "Error: No ANTHROPIC_API_KEY set", "tool_calls": [], "finish_reason": "error", "usage": {}}

        # Convert messages to Anthropic format
        system_msg = ""
        api_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"] if isinstance(m["content"], str) else str(m["content"])
            else:
                api_messages.append(m)

        body: dict[str, Any] = {
            "model": (model or self.default_model).replace("anthropic/", ""),
            "messages": api_messages,
            "max_tokens": max_tokens,
        }
        if system_msg:
            body["system"] = system_msg
        if tools:
            # Convert OpenAI tool format to Anthropic format
            body["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"]["description"],
                    "input_schema": t["function"]["parameters"],
                }
                for t in tools
            ]

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
            )
            data = resp.json()

        if resp.status_code != 200:
            return {"content": f"API Error: {data}", "tool_calls": [], "finish_reason": "error", "usage": {}}

        content_text = ""
        tool_calls = []
        for block in data.get("content", []):
            if block["type"] == "text":
                content_text += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "name": block["name"],
                    "arguments": block["input"],
                })

        return {
            "content": content_text or None,
            "tool_calls": tool_calls,
            "finish_reason": data.get("stop_reason", "end_turn"),
            "usage": data.get("usage", {}),
        }
