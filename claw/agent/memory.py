"""
Memory system for Claw Researcher.

Two-layer memory stored as plain .md files:
  - MEMORY.md  → Long-term facts (always loaded into LLM context)
  - HISTORY.md → Append-only research log (grep-searchable, NOT in context)

Auto-consolidation: when context grows too large, LLM summarizes old messages
into HISTORY.md and extracts key facts into MEMORY.md.
"""

from __future__ import annotations

import asyncio
import json
import weakref
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from loguru import logger

if TYPE_CHECKING:
    from claw.agent.providers import LLMProvider


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save the memory consolidation result to persistent storage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": (
                            "A paragraph summarizing key research events/decisions/findings. "
                            "Start with [YYYY-MM-DD HH:MM]. Include paper titles, methods, "
                            "and decisions for grep search."
                        ),
                    },
                    "memory_update": {
                        "type": "string",
                        "description": (
                            "Full updated long-term memory as markdown. Include all existing "
                            "facts plus new ones. Return unchanged if nothing new."
                        ),
                    },
                },
                "required": ["history_entry", "memory_update"],
            },
        },
    }
]


class MemoryStore:
    """Two-layer memory: MEMORY.md (long-term facts) + HISTORY.md (research log)."""

    _MAX_FAILURES_BEFORE_RAW_ARCHIVE = 3

    def __init__(self, workspace: Path):
        self.memory_dir = _ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.history_file = self.memory_dir / "HISTORY.md"
        self._consecutive_failures = 0

        # Initialize from template if empty
        if not self.memory_file.exists():
            self._init_memory_template()

    def _init_memory_template(self) -> None:
        """Create initial MEMORY.md from template."""
        template = """# Research Memory

## Current Research Topic

(Topic being researched)

## Key Papers

(Important papers discovered during research)

## Research Gaps Found

(Gaps identified in the literature)

## Decisions & Preferences

(Research decisions made, user preferences)

## Dataset & Code Sources

(Datasets used, code repositories found)

## Important Notes

(Other facts to remember across sessions)

---

*Auto-updated by Claw Researcher during research sessions.*
"""
        self.memory_file.write_text(template, encoding="utf-8")

    def read_long_term(self) -> str:
        """Read MEMORY.md contents."""
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def write_long_term(self, content: str) -> None:
        """Overwrite MEMORY.md with updated content."""
        self.memory_file.write_text(content, encoding="utf-8")

    def append_history(self, entry: str) -> None:
        """Append an entry to HISTORY.md."""
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(entry.rstrip() + "\n\n")

    def get_memory_context(self) -> str:
        """Get MEMORY.md content for inclusion in system prompt."""
        long_term = self.read_long_term()
        return f"## Long-term Memory\n{long_term}" if long_term else ""

    @staticmethod
    def _format_messages(messages: list[dict]) -> str:
        lines = []
        for message in messages:
            if not message.get("content"):
                continue
            content = message["content"]
            if isinstance(content, list):
                content = " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
                )
            tools = ""
            if message.get("tools_used"):
                tools = f" [tools: {', '.join(message['tools_used'])}]"
            ts = message.get("timestamp", "?")[:16]
            lines.append(f"[{ts}] {message['role'].upper()}{tools}: {content}")
        return "\n".join(lines)

    async def consolidate(
        self,
        messages: list[dict],
        provider: LLMProvider,
        model: str,
    ) -> bool:
        """Consolidate messages into MEMORY.md + HISTORY.md via LLM."""
        if not messages:
            return True

        current_memory = self.read_long_term()
        prompt = f"""Process this research conversation and call the save_memory tool.

## Current Long-term Memory
{current_memory or "(empty)"}

## Conversation to Process
{self._format_messages(messages)}

Instructions:
- history_entry: Summarize key research activities, papers found, decisions made. Start with [YYYY-MM-DD HH:MM].
- memory_update: Update the long-term memory markdown. Add new papers, gaps, decisions. Keep existing facts unless contradicted."""

        chat_messages = [
            {"role": "system", "content": "You are a research memory consolidation agent. Call the save_memory tool."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await provider.chat(
                messages=chat_messages,
                tools=_SAVE_MEMORY_TOOL,
                model=model,
                tool_choice={"type": "function", "function": {"name": "save_memory"}},
            )

            if not response.get("tool_calls"):
                logger.warning("Memory consolidation: LLM did not call save_memory")
                return self._fail_or_raw_archive(messages)

            args = response["tool_calls"][0].get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args)

            entry = _ensure_text(args.get("history_entry", "")).strip()
            update = _ensure_text(args.get("memory_update", ""))

            if not entry:
                return self._fail_or_raw_archive(messages)

            self.append_history(entry)
            if update and update != current_memory:
                self.write_long_term(update)

            self._consecutive_failures = 0
            logger.info("Memory consolidation done for {} messages", len(messages))
            return True
        except Exception:
            logger.exception("Memory consolidation failed")
            return self._fail_or_raw_archive(messages)

    def _fail_or_raw_archive(self, messages: list[dict]) -> bool:
        self._consecutive_failures += 1
        if self._consecutive_failures < self._MAX_FAILURES_BEFORE_RAW_ARCHIVE:
            return False
        self._raw_archive(messages)
        self._consecutive_failures = 0
        return True

    def _raw_archive(self, messages: list[dict]) -> None:
        """Fallback: dump raw messages to HISTORY.md without LLM summarization."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.append_history(
            f"[{ts}] [RAW] {len(messages)} messages\n"
            f"{self._format_messages(messages)}"
        )
        logger.warning("Memory consolidation degraded: raw-archived {} messages", len(messages))


class MemoryConsolidator:
    """Owns consolidation policy: when context is too large, archive old messages."""

    _MAX_CONSOLIDATION_ROUNDS = 5

    def __init__(
        self,
        workspace: Path,
        provider: LLMProvider,
        model: str,
        context_window_tokens: int,
        build_messages_fn: Callable[..., list[dict[str, Any]]],
    ):
        self.store = MemoryStore(workspace)
        self.provider = provider
        self.model = model
        self.context_window_tokens = context_window_tokens
        self._build_messages = build_messages_fn
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()

    def get_lock(self, session_key: str) -> asyncio.Lock:
        return self._locks.setdefault(session_key, asyncio.Lock())

    async def maybe_consolidate(self, session: dict) -> None:
        """Archive old messages if context exceeds half the window."""
        messages = session.get("messages", [])
        if not messages or self.context_window_tokens <= 0:
            return

        session_key = session.get("key", "default")
        lock = self.get_lock(session_key)
        async with lock:
            # Estimate current context size
            total_text = json.dumps(messages, default=str)
            estimated_tokens = _estimate_tokens(total_text)

            if estimated_tokens < self.context_window_tokens:
                return

            target = self.context_window_tokens // 2
            last_consolidated = session.get("last_consolidated", 0)

            for _ in range(self._MAX_CONSOLIDATION_ROUNDS):
                if estimated_tokens <= target:
                    return

                # Find boundary at a user message
                chunk_end = last_consolidated
                removed_tokens = 0
                for idx in range(last_consolidated, len(messages)):
                    msg = messages[idx]
                    removed_tokens += _estimate_tokens(json.dumps(msg, default=str))
                    if idx > last_consolidated and msg.get("role") == "user":
                        chunk_end = idx
                        if removed_tokens >= estimated_tokens - target:
                            break

                if chunk_end <= last_consolidated:
                    return

                chunk = messages[last_consolidated:chunk_end]
                if not chunk:
                    return

                logger.info("Consolidating {} messages (tokens: {}/{})", len(chunk), estimated_tokens, self.context_window_tokens)
                ok = await self.store.consolidate(chunk, self.provider, self.model)
                if not ok:
                    return

                session["last_consolidated"] = chunk_end
                last_consolidated = chunk_end
                total_text = json.dumps(messages[last_consolidated:], default=str)
                estimated_tokens = _estimate_tokens(total_text)
