"""
Smoke tests for Claw Researcher.

Run with:  pytest tests/ -v
Or:        uv run pytest tests/ -v

Covers all layers without requiring an API key:
  - Imports
  - Tool instantiation & schema
  - Filesystem + exec tools (no network)
  - Memory + Skills + ContextBuilder (file-based)
  - AgentLoop instantiation (no LLM call)
  - CLI --help (no LLM call)

Cross-platform: Windows, macOS, Linux.
"""

from __future__ import annotations

import sys
import shutil
import tempfile
from pathlib import Path

import pytest

# ── helpers ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def ws(tmp_path: Path) -> Path:
    """Temporary workspace for each test."""
    return tmp_path


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Imports
# ══════════════════════════════════════════════════════════════════════════════

class TestImports:

    def test_claw_package(self):
        import claw
        assert claw.__version__

    def test_config(self):
        from claw.config import get_settings
        s = get_settings()
        assert s.workspace is not None

    def test_tool_base(self):
        from claw.agent.tools.base import Tool
        assert Tool

    def test_tool_registry(self):
        from claw.agent.tools.registry import ToolRegistry
        assert ToolRegistry

    def test_memory(self):
        from claw.agent.memory import MemoryStore
        assert MemoryStore

    def test_providers(self):
        from claw.agent.providers import LLMProvider
        assert LLMProvider

    def test_skills(self):
        from claw.agent.skills import SkillsLoader
        assert SkillsLoader

    def test_subagent(self):
        from claw.agent.subagent import SubagentManager
        assert SubagentManager

    def test_loop(self):
        from claw.agent.loop import AgentLoop
        assert AgentLoop

    def test_context(self):
        from claw.agent.context import ContextBuilder
        assert ContextBuilder

    def test_research_tools(self):
        from claw.agent.tools.paper_search import PaperSearchTool
        from claw.agent.tools.paper_read import PaperReadTool
        from claw.agent.tools.dataset_search import DatasetSearchTool
        from claw.agent.tools.web import WebSearchTool, WebFetchTool
        from claw.agent.tools.filesystem import ReadFileTool, WriteFileTool, ListDirTool
        from claw.agent.tools.exec_tool import ExecTool
        assert all([PaperSearchTool, PaperReadTool, DatasetSearchTool,
                    WebSearchTool, WebFetchTool, ReadFileTool, WriteFileTool,
                    ListDirTool, ExecTool])


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Tool instantiation & registry
# ══════════════════════════════════════════════════════════════════════════════

class TestToolRegistry:

    def _make_registry(self):
        from claw.agent.tools.registry import ToolRegistry
        from claw.agent.tools.paper_search import PaperSearchTool
        from claw.agent.tools.paper_read import PaperReadTool
        from claw.agent.tools.dataset_search import DatasetSearchTool
        from claw.agent.tools.web import WebSearchTool, WebFetchTool
        from claw.agent.tools.filesystem import ReadFileTool, WriteFileTool, ListDirTool
        from claw.agent.tools.exec_tool import ExecTool

        reg = ToolRegistry()
        for t in [PaperSearchTool(), PaperReadTool(), DatasetSearchTool(),
                  WebSearchTool(), WebFetchTool(), ReadFileTool(),
                  WriteFileTool(), ListDirTool(), ExecTool()]:
            reg.register(t)
        return reg

    def test_register_all(self):
        reg = self._make_registry()
        assert len(reg) == 9

    def test_expected_names(self):
        reg = self._make_registry()
        expected = {
            "paper_search", "paper_read", "dataset_search",
            "web_search", "web_fetch",
            "read_file", "write_file", "list_dir", "exec",
        }
        assert set(reg.tool_names) == expected

    def test_schemas_valid(self):
        reg = self._make_registry()
        for defn in reg.get_definitions():
            assert defn["type"] == "function"
            fn = defn["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn
            assert fn["parameters"]["type"] == "object"

    def test_param_validation_pass(self):
        from claw.agent.tools.paper_search import PaperSearchTool
        errs = PaperSearchTool().validate_params({"query": "transformers"})
        assert errs == []

    def test_param_validation_fail_missing_required(self):
        from claw.agent.tools.paper_search import PaperSearchTool
        errs = PaperSearchTool().validate_params({})
        assert len(errs) > 0

    def test_duplicate_register_raises(self):
        from claw.agent.tools.registry import ToolRegistry
        from claw.agent.tools.paper_search import PaperSearchTool
        reg = ToolRegistry()
        reg.register(PaperSearchTool())
        with pytest.raises(Exception):
            reg.register(PaperSearchTool())


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Filesystem tools (no network, cross-platform)
# ══════════════════════════════════════════════════════════════════════════════

class TestFilesystemTools:

    @pytest.mark.asyncio
    async def test_write_and_read(self, ws):
        from claw.agent.tools.filesystem import WriteFileTool, ReadFileTool
        write = WriteFileTool()
        read = ReadFileTool()

        path = str(ws / "note.txt")
        r = await write.execute(path=path, content="Hello Claw!")
        assert "error" not in r.lower(), f"write failed: {r}"

        r = await read.execute(path=path)
        assert "Hello Claw!" in r

    @pytest.mark.asyncio
    async def test_read_missing_file(self, ws):
        from claw.agent.tools.filesystem import ReadFileTool
        r = await ReadFileTool().execute(path=str(ws / "nope.txt"))
        # Should return error string, not raise
        assert "error" in r.lower() or "not found" in r.lower() or "no such" in r.lower()

    @pytest.mark.asyncio
    async def test_list_dir(self, ws):
        from claw.agent.tools.filesystem import WriteFileTool, ListDirTool
        await WriteFileTool().execute(path=str(ws / "a.txt"), content="a")
        await WriteFileTool().execute(path=str(ws / "b.txt"), content="b")
        r = await ListDirTool().execute(path=str(ws))
        assert "a.txt" in r
        assert "b.txt" in r

    @pytest.mark.asyncio
    async def test_list_missing_dir(self, ws):
        from claw.agent.tools.filesystem import ListDirTool
        r = await ListDirTool().execute(path=str(ws / "nonexistent"))
        assert "error" in r.lower() or "not found" in r.lower()

    @pytest.mark.asyncio
    async def test_write_creates_subdirs(self, ws):
        from claw.agent.tools.filesystem import WriteFileTool, ReadFileTool
        deep = str(ws / "a" / "b" / "c.txt")
        r = await WriteFileTool().execute(path=deep, content="deep")
        assert "error" not in r.lower()
        r = await ReadFileTool().execute(path=deep)
        assert "deep" in r


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — ExecTool (cross-platform using `python -c`)
# ══════════════════════════════════════════════════════════════════════════════

class TestExecTool:

    @pytest.mark.asyncio
    async def test_simple_python(self):
        from claw.agent.tools.exec_tool import ExecTool
        r = await ExecTool().execute(command="python -c \"print('smoke ok')\"")
        assert "smoke ok" in r

    @pytest.mark.asyncio
    async def test_arithmetic(self):
        from claw.agent.tools.exec_tool import ExecTool
        r = await ExecTool().execute(command="python -c \"print(2 + 2)\"")
        assert "4" in r

    @pytest.mark.asyncio
    async def test_stderr_captured(self):
        from claw.agent.tools.exec_tool import ExecTool
        r = await ExecTool().execute(command="python -c \"import sys; sys.stderr.write('err_msg')\"")
        assert "err_msg" in r

    @pytest.mark.asyncio
    async def test_error_exit_code_captured(self):
        from claw.agent.tools.exec_tool import ExecTool
        r = await ExecTool().execute(command="python -c \"raise ValueError('boom')\"")
        # Should return error info, not raise
        assert "ValueError" in r or "boom" in r or "Exit code" in r

    @pytest.mark.asyncio
    async def test_timeout(self):
        from claw.agent.tools.exec_tool import ExecTool
        r = await ExecTool().execute(
            command="python -c \"import time; time.sleep(60)\"",
            timeout=2,
        )
        assert "timeout" in r.lower() or "timed out" in r.lower() or "error" in r.lower()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Memory (file-based, no DB)
# ══════════════════════════════════════════════════════════════════════════════

class TestMemory:

    def test_memory_file_created(self, ws):
        from claw.agent.memory import MemoryStore
        store = MemoryStore(ws)
        assert store.memory_file.exists()

    def test_read_long_term(self, ws):
        from claw.agent.memory import MemoryStore
        content = MemoryStore(ws).read_long_term()
        assert isinstance(content, str)
        assert len(content) > 0

    def test_append_history(self, ws):
        from claw.agent.memory import MemoryStore
        store = MemoryStore(ws)
        store.append_history("[2025-01-01] Test entry.")
        text = store.history_file.read_text(encoding="utf-8")
        assert "Test entry" in text

    def test_history_is_append_only(self, ws):
        from claw.agent.memory import MemoryStore
        store = MemoryStore(ws)
        store.append_history("Entry A")
        store.append_history("Entry B")
        text = store.history_file.read_text(encoding="utf-8")
        assert "Entry A" in text
        assert "Entry B" in text

    def test_get_memory_context(self, ws):
        from claw.agent.memory import MemoryStore
        ctx = MemoryStore(ws).get_memory_context()
        assert isinstance(ctx, str)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — SkillsLoader
# ══════════════════════════════════════════════════════════════════════════════

class TestSkillsLoader:

    def test_lists_builtin_skills(self, ws):
        from claw.agent.skills import SkillsLoader
        skills = SkillsLoader(ws).list_skills()
        assert len(skills) >= 5  # memory, survey, brainstorm, gap-analysis, report, reproduce

    def test_expected_skill_names(self, ws):
        from claw.agent.skills import SkillsLoader
        names = {s["name"] for s in SkillsLoader(ws).list_skills()}
        assert "memory" in names
        assert "survey" in names
        assert "brainstorm" in names

    def test_build_skills_summary(self, ws):
        from claw.agent.skills import SkillsLoader
        summary = SkillsLoader(ws).build_skills_summary()
        assert isinstance(summary, str)
        assert len(summary) > 50

    def test_load_skill_content(self, ws):
        from claw.agent.skills import SkillsLoader
        loader = SkillsLoader(ws)
        content = loader.load_skills_for_context(["survey"])
        assert isinstance(content, str)
        assert len(content) > 0

    def test_workspace_skill_overrides_builtin(self, ws):
        """A SKILL.md in workspace/skills/ should override builtin."""
        from claw.agent.skills import SkillsLoader
        override = ws / "skills" / "survey" / "SKILL.md"
        override.parent.mkdir(parents=True, exist_ok=True)
        override.write_text("---\nname: survey\n---\n# Custom Survey\nCustom content.", encoding="utf-8")
        content = SkillsLoader(ws).load_skills_for_context(["survey"])
        assert "Custom content" in content


# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — ContextBuilder
# ══════════════════════════════════════════════════════════════════════════════

class TestContextBuilder:

    def test_build_system_prompt(self, ws):
        from claw.agent.context import ContextBuilder
        prompt = ContextBuilder(ws).build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 500  # must have real content

    def test_build_messages_structure(self, ws):
        from claw.agent.context import ContextBuilder
        msgs = ContextBuilder(ws).build_messages(history=[], current_message="Hello")
        assert msgs[0]["role"] == "system"
        assert msgs[-1]["role"] == "user"
        assert "Hello" in msgs[-1]["content"]

    def test_build_messages_with_history(self, ws):
        from claw.agent.context import ContextBuilder
        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]
        msgs = ContextBuilder(ws).build_messages(history=history, current_message="Follow-up")
        roles = [m["role"] for m in msgs]
        assert roles[0] == "system"
        assert "user" in roles
        assert "assistant" in roles
        assert roles[-1] == "user"


# ══════════════════════════════════════════════════════════════════════════════
# STEP 8 — AgentLoop instantiation (no LLM call)
# ══════════════════════════════════════════════════════════════════════════════

class TestAgentLoopInstantiation:

    def test_create_agent_loop(self, ws):
        from claw.agent.loop import AgentLoop
        agent = AgentLoop(workspace=ws)
        assert agent is not None
        assert len(agent.tools) >= 9

    def test_tools_registered(self, ws):
        from claw.agent.loop import AgentLoop
        agent = AgentLoop(workspace=ws)
        names = set(agent.tools.tool_names)
        assert "paper_search" in names
        assert "exec" in names
        assert "read_file" in names
        assert "spawn" in names

    def test_status_command(self, ws):
        from claw.agent.loop import AgentLoop
        agent = AgentLoop(workspace=ws)
        status = agent._build_status()
        assert "Model" in status
        assert "Tools" in status

    def test_help_command(self, ws):
        from claw.agent.loop import AgentLoop
        agent = AgentLoop(workspace=ws)
        help_text = agent._build_help()
        assert "paper" in help_text.lower() or "research" in help_text.lower()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 9 — CLI smoke test (no LLM call)
# ══════════════════════════════════════════════════════════════════════════════

class TestCLI:

    def test_cli_help(self):
        from typer.testing import CliRunner
        from claw.cli import app
        result = CliRunner().invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "chat" in result.output.lower() or "claw" in result.output.lower()

    def test_cli_status(self):
        from typer.testing import CliRunner
        from claw.cli import app
        result = CliRunner().invoke(app, ["status"])
        assert result.exit_code == 0
        assert "Model" in result.output or "model" in result.output

    def test_cli_onboard(self, ws):
        from typer.testing import CliRunner
        from claw.cli import app
        result = CliRunner().invoke(app, ["onboard", "--workspace", str(ws)])
        assert result.exit_code == 0
        assert (ws / "memory").exists()
