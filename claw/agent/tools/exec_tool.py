"""Exec tool — run shell commands with safety constraints."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from claw.agent.tools.base import Tool

_MAX_OUTPUT_CHARS = 16_000
_DEFAULT_TIMEOUT = 30


class ExecTool(Tool):
    """Execute shell commands with timeout and output limits."""

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command and return its output. Useful for running "
            "scripts, installing packages, processing data, or any system task. "
            "Commands are subject to a timeout and output size limit."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds (default 30, max 300).",
                },
            },
            "required": ["command"],
        }

    async def execute(self, **kwargs: Any) -> str:
        command: str = kwargs["command"]
        timeout: int = min(kwargs.get("timeout", _DEFAULT_TIMEOUT), 300)

        logger.info("exec: command={!r} timeout={}s", command, timeout)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as exc:
            logger.error("exec: failed to start process: {}", exc)
            return f"Error: Could not start process — {exc}"

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            # Drain any remaining output
            try:
                await asyncio.wait_for(proc.communicate(), timeout=5)
            except Exception:
                pass
            return f"Error: Command timed out after {timeout}s.\nCommand: {command}"
        except Exception as exc:
            logger.error("exec: error during execution: {}", exc)
            return f"Error: Command execution failed — {exc}"

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        exit_code = proc.returncode

        # Build output
        parts: list[str] = []

        if stdout:
            parts.append(f"STDOUT:\n{stdout}")
        if stderr:
            parts.append(f"STDERR:\n{stderr}")
        if not parts:
            parts.append("(no output)")

        parts.append(f"\nExit code: {exit_code}")
        output = "\n".join(parts)

        # Truncate if necessary
        if len(output) > _MAX_OUTPUT_CHARS:
            output = output[:_MAX_OUTPUT_CHARS] + f"\n\n... [truncated at {_MAX_OUTPUT_CHARS} chars]"

        return output
