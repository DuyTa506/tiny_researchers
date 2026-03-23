"""
Agent loop: the core processing engine.

Flow:
  1. Receive message (from CLI or channel)
  2. Build context (system prompt + history + memory + skills)
  3. Call LLM
  4. Execute tool calls
  5. Repeat until final text response
  6. Auto-consolidate memory if context grows too large
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger

from claw.agent.context import ContextBuilder
from claw.agent.memory import MemoryConsolidator, MemoryStore
from claw.agent.providers import LLMProvider
from claw.agent.skills import SkillsLoader
from claw.agent.subagent import SubagentManager
from claw.agent.tools.registry import ToolRegistry

# Default tools
from claw.agent.tools.filesystem import ReadFileTool, WriteFileTool, ListDirTool
from claw.agent.tools.exec_tool import ExecTool
from claw.agent.tools.web import WebSearchTool, WebFetchTool

# Phase 2 — Reproduction tools (imported lazily to avoid hard dependency)
try:
    from claw.agent.tools.env_builder import EnvBuilderTool
    from claw.agent.tools.dataset_download import DatasetDownloadTool
    from claw.agent.tools.code_gen import CodeGenTool
    _PHASE2_TOOLS_AVAILABLE = True
except ImportError:
    _PHASE2_TOOLS_AVAILABLE = False


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives user messages
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    6. Auto-consolidates memory when context grows
    """

    _TOOL_RESULT_MAX_CHARS = 16_000

    def __init__(
        self,
        workspace: Path,
        provider: LLMProvider | None = None,
        model: str | None = None,
        max_iterations: int = 40,
        context_window_tokens: int = 128_000,
    ):
        self.workspace = workspace
        self.provider = provider or LLMProvider()
        self.model = model or self.provider.default_model
        self.max_iterations = max_iterations
        self.context_window_tokens = context_window_tokens
        self._start_time = time.time()

        # Core components
        self.context = ContextBuilder(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=self.provider,
            workspace=workspace,
            model=self.model,
            on_result=self._on_subagent_result,
        )

        # Session history (in-memory, simple list of messages)
        self._sessions: dict[str, dict] = {}

        # Memory consolidator
        self.memory_consolidator = MemoryConsolidator(
            workspace=workspace,
            provider=self.provider,
            model=self.model,
            context_window_tokens=context_window_tokens,
            build_messages_fn=self.context.build_messages,
        )

        # Register tools
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # Filesystem — no workspace arg (tools use absolute paths)
        self.tools.register(ReadFileTool())
        self.tools.register(WriteFileTool())
        self.tools.register(ListDirTool())

        # Shell execution
        self.tools.register(ExecTool())

        # Web tools
        self.tools.register(WebSearchTool())
        self.tools.register(WebFetchTool())

        # Phase 2 — Reproduction tools
        if _PHASE2_TOOLS_AVAILABLE:
            self.tools.register(EnvBuilderTool())
            self.tools.register(DatasetDownloadTool())
            self.tools.register(CodeGenTool())
            logger.debug("Phase 2 reproduction tools registered")

        # Spawn tool (for subagents)
        self.tools.register(_SpawnTool(self.subagents))

    def _get_session(self, key: str = "default") -> dict:
        """Get or create a session."""
        if key not in self._sessions:
            self._sessions[key] = {
                "key": key,
                "messages": [],
                "last_consolidated": 0,
                "created_at": datetime.now().isoformat(),
            }
        return self._sessions[key]

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think>…</think> blocks from model output."""
        if not text:
            return None
        return re.sub(r"<think>[\s\S]*?</think>", "", text).strip() or None

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> tuple[str | None, list[str], list[dict]]:
        """Run the agent iteration loop. Returns (final_content, tools_used, all_messages)."""
        messages = initial_messages
        iteration = 0
        final_content = None
        tools_used: list[str] = []

        while iteration < self.max_iterations:
            iteration += 1

            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model,
            )

            if response.get("tool_calls"):
                # Show progress
                if on_progress:
                    thought = self._strip_think(response.get("content"))
                    if thought:
                        await on_progress(thought)
                    tool_names = [tc["name"] for tc in response["tool_calls"]]
                    await on_progress(f"🔧 {', '.join(tool_names)}")

                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": response.get("content") or "",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["arguments"]) if isinstance(tc["arguments"], dict) else tc["arguments"],
                            },
                        }
                        for tc in response["tool_calls"]
                    ],
                })

                # Execute each tool
                for tc in response["tool_calls"]:
                    tools_used.append(tc["name"])
                    logger.info("Tool call: {}({})", tc["name"], str(tc["arguments"])[:200])
                    result = await self.tools.execute(tc["name"], tc["arguments"])
                    content = result if isinstance(result, str) else json.dumps(result, default=str)
                    # Truncate large results
                    if len(content) > self._TOOL_RESULT_MAX_CHARS:
                        content = content[:self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tc["name"],
                        "content": content,
                    })
            else:
                # Final text response
                clean = self._strip_think(response.get("content"))
                if response.get("finish_reason") == "error":
                    logger.error("LLM error: {}", (clean or "")[:200])
                    final_content = clean or "Sorry, I encountered an error."
                    break
                messages.append({"role": "assistant", "content": clean or ""})
                final_content = clean
                break

        if final_content is None and iteration >= self.max_iterations:
            logger.warning("Max iterations ({}) reached", self.max_iterations)
            final_content = (
                f"I reached the maximum iterations ({self.max_iterations}). "
                "Try breaking the task into smaller steps."
            )

        return final_content, tools_used, messages

    async def chat(
        self,
        message: str,
        session_key: str = "default",
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """Process a user message and return the response. Main entry point."""
        session = self._get_session(session_key)

        # Slash commands
        cmd = message.strip().lower()
        if cmd == "/new":
            session["messages"] = []
            session["last_consolidated"] = 0
            return "🔄 New research session started."
        if cmd == "/status":
            return self._build_status()
        if cmd == "/help":
            return self._build_help()

        # Auto-consolidate if context is large
        await self.memory_consolidator.maybe_consolidate(session)

        # Build messages with full context
        history = session["messages"][session.get("last_consolidated", 0):]
        initial_messages = self.context.build_messages(
            history=history,
            current_message=message,
        )

        # Run agent loop
        final_content, tools_used, all_msgs = await self._run_agent_loop(
            initial_messages, on_progress=on_progress,
        )

        if final_content is None:
            final_content = "Processing complete but no response generated."

        # Save new messages to session history
        skip = 1 + len(history)  # skip system + old history
        for m in all_msgs[skip:]:
            entry = dict(m)
            entry.setdefault("timestamp", datetime.now().isoformat())
            if entry.get("role") == "tool" and isinstance(entry.get("content"), str):
                if len(entry["content"]) > self._TOOL_RESULT_MAX_CHARS:
                    entry["content"] = entry["content"][:self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
            session["messages"].append(entry)

        return final_content

    async def _on_subagent_result(self, task_id: str, label: str, result: str) -> None:
        """Handle subagent completion — inject result into default session."""
        logger.info("Subagent [{}] result received", task_id)
        session = self._get_session("default")
        session["messages"].append({
            "role": "assistant",
            "content": f"[Subagent '{label}' completed]\n\n{result}",
            "timestamp": datetime.now().isoformat(),
        })

    def _build_status(self) -> str:
        session = self._get_session("default")
        uptime = int(time.time() - self._start_time)
        return (
            f"🧠 **Claw Researcher Status**\n"
            f"- Model: {self.model}\n"
            f"- Uptime: {uptime}s\n"
            f"- Session messages: {len(session['messages'])}\n"
            f"- Tools available: {len(self.tools)}\n"
            f"- Subagents running: {self.subagents.running_count}\n"
            f"- Memory: {self.workspace / 'memory' / 'MEMORY.md'}"
        )

    def _build_help(self) -> str:
        skills = SkillsLoader(self.workspace)
        skill_list = skills.list_skills(filter_unavailable=False)
        skill_names = [s["name"] for s in skill_list]

        return (
            "🧠 **Claw Researcher — Commands**\n\n"
            "**Slash Commands:**\n"
            "- `/new` — Start a new research session\n"
            "- `/status` — Show system status\n"
            "- `/help` — Show this help\n\n"
            "**What I Can Do:**\n"
            "- 🔍 Search academic papers (Semantic Scholar, arXiv)\n"
            "- 📚 Read paper details, abstracts, references\n"
            "- 📊 Search datasets (HuggingFace Hub)\n"
            "- 🧠 Brainstorm research ideas\n"
            "- 📋 Conduct literature surveys\n"
            "- 🔬 Find research gaps\n"
            "- 📝 Write research reports\n"
            "- 🔧 Reproduce experiments from papers\n"
            "- 🌐 Search the web and fetch pages\n"
            "- 💻 Execute code and shell commands\n\n"
            f"**Available Skills:** {', '.join(skill_names) if skill_names else 'None'}\n"
            "(Ask me to read a skill for detailed instructions)"
        )


class _SpawnTool:
    """Tool wrapper for spawning subagents — registered in ToolRegistry."""

    def __init__(self, manager: SubagentManager):
        self._manager = manager

    @property
    def name(self) -> str:
        return "spawn"

    @property
    def description(self) -> str:
        return (
            "Spawn a background subagent for heavy research tasks "
            "(surveys, reproductions, deep analysis). "
            "The subagent runs independently and reports back when done."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Detailed description of the research task to perform.",
                },
                "label": {
                    "type": "string",
                    "description": "Short label for the task (e.g., 'Survey: Transformers').",
                },
            },
            "required": ["task"],
        }

    async def execute(self, **kwargs: Any) -> str:
        return await self._manager.spawn(
            task=kwargs["task"],
            label=kwargs.get("label"),
        )

    def cast_params(self, params: dict) -> dict:
        return params

    def validate_params(self, params: dict) -> list[str]:
        if "task" not in params:
            return ["missing required task"]
        return []

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
