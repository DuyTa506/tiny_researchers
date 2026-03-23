"""
Subagent manager for background research tasks.

Spawns lightweight agent processes for heavy operations:
  - Literature surveys (many papers to read)
  - Paper reproduction (build sandbox, generate code)
  - Deep analysis (gap finding, trend analysis)

Each subagent gets its own ToolRegistry and limited iterations.
Results are announced back to the main agent via callback.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger

from claw.agent.tools.base import Tool
from claw.agent.tools.registry import ToolRegistry
from claw.agent.providers import LLMProvider


class SubagentManager:
    """Manages background subagent execution for heavy research tasks."""

    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        on_result: Callable[[str, str, str], Awaitable[None]] | None = None,
    ):
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.default_model
        self.on_result = on_result  # callback(task_id, label, result)
        self._running_tasks: dict[str, asyncio.Task[None]] = {}

    async def spawn(
        self,
        task: str,
        label: str | None = None,
        extra_tools: list[Tool] | None = None,
        max_iterations: int = 20,
    ) -> str:
        """Spawn a subagent to execute a research task in the background."""
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:40] + ("..." if len(task) > 40 else "")

        bg_task = asyncio.create_task(
            self._run_subagent(task_id, task, display_label, extra_tools, max_iterations)
        )
        self._running_tasks[task_id] = bg_task

        def _cleanup(_: asyncio.Task) -> None:
            self._running_tasks.pop(task_id, None)

        bg_task.add_done_callback(_cleanup)

        logger.info("Spawned subagent [{}]: {}", task_id, display_label)
        return f"Subagent [{display_label}] started (id: {task_id}). I'll report back when done."

    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        extra_tools: list[Tool] | None,
        max_iterations: int,
    ) -> None:
        """Execute the subagent task."""
        logger.info("Subagent [{}] starting: {}", task_id, label)

        try:
            tools = self._build_subagent_tools(extra_tools)
            system_prompt = self._build_subagent_prompt()

            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ]

            iteration = 0
            final_result: str | None = None

            while iteration < max_iterations:
                iteration += 1

                response = await self.provider.chat(
                    messages=messages,
                    tools=tools.get_definitions(),
                    model=self.model,
                )

                if response.get("tool_calls"):
                    # Add assistant message with tool calls
                    messages.append({
                        "role": "assistant",
                        "content": response.get("content") or "",
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"]) if isinstance(tc["arguments"], dict) else tc["arguments"]},
                            }
                            for tc in response["tool_calls"]
                        ],
                    })

                    # Execute tools
                    for tc in response["tool_calls"]:
                        logger.debug("Subagent [{}] tool: {}({})", task_id, tc["name"], str(tc["arguments"])[:100])
                        result = await tools.execute(tc["name"], tc["arguments"])
                        content = result if isinstance(result, str) else json.dumps(result, default=str)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": tc["name"],
                            "content": content[:16000],  # truncate large results
                        })
                else:
                    final_result = response.get("content")
                    break

            if final_result is None:
                final_result = f"Subagent reached max iterations ({max_iterations}) without final answer."

            logger.info("Subagent [{}] completed", task_id)
            if self.on_result:
                await self.on_result(task_id, label, final_result)

        except asyncio.CancelledError:
            logger.info("Subagent [{}] cancelled", task_id)
            raise
        except Exception as e:
            error_msg = f"Subagent error: {str(e)}"
            logger.error("Subagent [{}] failed: {}", task_id, e)
            if self.on_result:
                await self.on_result(task_id, label, error_msg)

    def _build_subagent_tools(self, extra_tools: list[Tool] | None) -> ToolRegistry:
        """Build tool registry for a subagent (shared tools + extras)."""
        from claw.agent.tools.filesystem import ReadFileTool, WriteFileTool, ListDirTool
        from claw.agent.tools.exec_tool import ExecTool
        from claw.agent.tools.web import WebSearchTool, WebFetchTool
        from claw.agent.tools.paper_search import PaperSearchTool
        from claw.agent.tools.paper_read import PaperReadTool

        registry = ToolRegistry()

        # Filesystem tools
        registry.register(ReadFileTool(workspace=self.workspace))
        registry.register(WriteFileTool(workspace=self.workspace))
        registry.register(ListDirTool(workspace=self.workspace))

        # Shell
        registry.register(ExecTool(working_dir=str(self.workspace)))

        # Web
        registry.register(WebSearchTool())
        registry.register(WebFetchTool())

        # Research tools
        registry.register(PaperSearchTool())
        registry.register(PaperReadTool())

        # Extra tools for specific tasks
        if extra_tools:
            for tool in extra_tools:
                registry.register(tool)

        return registry

    def _build_subagent_prompt(self) -> str:
        """Build system prompt for subagent."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return f"""# Claw Researcher — Subagent

Current Time: {now}

You are a research subagent spawned to complete a specific task.
Stay focused on the assigned task. Your final text response will be reported back.

## Guidelines
- Use paper_search to find papers before making claims about literature.
- Use paper_read to get details about specific papers (arXiv IDs or S2 paper IDs).
- Use dataset_search to find datasets on HuggingFace.
- Use web_search and web_fetch for general information.
- Use read_file, write_file, list_dir for workspace files.
- Use exec for shell commands (pip install, git clone, python scripts).
- Always cite paper titles and arXiv IDs when referencing papers.
- Be thorough but concise in your final response.

## Workspace
{self.workspace}"""

    async def cancel_all(self) -> int:
        """Cancel all running subagents."""
        tasks = [t for t in self._running_tasks.values() if not t.done()]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return len(tasks)

    @property
    def running_count(self) -> int:
        return len(self._running_tasks)
