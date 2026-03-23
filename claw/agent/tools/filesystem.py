"""Filesystem tools — read, write, and list directory contents."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from loguru import logger

from claw.agent.tools.base import Tool

_MAX_READ_CHARS = 128_000  # ~128 KB max for file reads


class ReadFileTool(Tool):
    """Read a file and return its contents."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read the contents of a file at the given path. Returns the text "
            "content of the file. Useful for reading research notes, code, data "
            "files, and configuration."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read.",
                },
            },
            "required": ["path"],
        }

    async def execute(self, **kwargs: Any) -> str:
        path_str: str = kwargs["path"]
        path = Path(path_str).expanduser().resolve()
        logger.info("read_file: {}", path)

        if not path.exists():
            return f"Error: File not found: {path}"
        if not path.is_file():
            return f"Error: Path is not a file: {path}"

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except PermissionError:
            return f"Error: Permission denied reading: {path}"
        except Exception as exc:
            logger.error("read_file error: {}", exc)
            return f"Error: Could not read file — {exc}"

        if len(content) > _MAX_READ_CHARS:
            content = content[:_MAX_READ_CHARS] + f"\n\n... [truncated at {_MAX_READ_CHARS} chars]"

        return content


class WriteFileTool(Tool):
    """Write content to a file."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "Write text content to a file at the given path. Creates parent "
            "directories if they don't exist. Overwrites existing files. "
            "Use for saving research notes, results, generated reports, etc."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write.",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write to the file.",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(self, **kwargs: Any) -> str:
        path_str: str = kwargs["path"]
        content: str = kwargs["content"]
        path = Path(path_str).expanduser().resolve()
        logger.info("write_file: {} ({} chars)", path, len(content))

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except PermissionError:
            return f"Error: Permission denied writing: {path}"
        except Exception as exc:
            logger.error("write_file error: {}", exc)
            return f"Error: Could not write file — {exc}"

        return f"Successfully wrote {len(content)} chars to {path}"


class ListDirTool(Tool):
    """List the contents of a directory."""

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return (
            "List the contents of a directory. Returns file and subdirectory "
            "names with size info. Useful for exploring project structure "
            "and finding files."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the directory to list. Defaults to current directory.",
                },
            },
            "required": [],
        }

    async def execute(self, **kwargs: Any) -> str:
        path_str: str = kwargs.get("path", ".")
        path = Path(path_str).expanduser().resolve()
        logger.info("list_dir: {}", path)

        if not path.exists():
            return f"Error: Directory not found: {path}"
        if not path.is_dir():
            return f"Error: Path is not a directory: {path}"

        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return f"Error: Permission denied listing: {path}"
        except Exception as exc:
            logger.error("list_dir error: {}", exc)
            return f"Error: Could not list directory — {exc}"

        if not entries:
            return f"Directory is empty: {path}"

        lines: list[str] = [f"Contents of {path}:\n"]
        for entry in entries[:200]:  # Cap at 200 entries
            if entry.is_dir():
                lines.append(f"  📁 {entry.name}/")
            else:
                try:
                    size = entry.stat().st_size
                    size_str = _human_size(size)
                except OSError:
                    size_str = "?"
                lines.append(f"  📄 {entry.name}  ({size_str})")

        if len(entries) > 200:
            lines.append(f"\n  ... and {len(entries) - 200} more entries")

        return "\n".join(lines)


def _human_size(size: int) -> str:
    """Convert bytes to human-readable size string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024  # type: ignore[assignment]
    return f"{size:.1f} TB"
