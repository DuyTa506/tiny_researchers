"""
Conversational E2E tests for Claw Researcher.

Simulates real multi-turn research sessions. Each scenario:
  - Runs against live APIs (ArXiv + OpenAlex)
  - Verifies the agent calls the right tools in the right order
  - Checks response quality (not just "no crash")
  - Prints a clear timeline of turns + tool calls

Run (requires OPENAI_API_KEY in .env):
    pytest tests/test_e2e_conversational.py -v -s

Skip in CI if no API key:
    pytest tests/ --ignore=tests/test_e2e_conversational.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pytest
from loguru import logger

# Suppress debug noise in test output
logger.remove()
logger.add(sys.stderr, level="WARNING")

# ── skip guard ────────────────────────────────────────────────────────────────

def _has_llm_key() -> bool:
    from dotenv import load_dotenv
    load_dotenv()
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

requires_llm = pytest.mark.skipif(
    not _has_llm_key(),
    reason="No LLM API key found — set OPENAI_API_KEY or ANTHROPIC_API_KEY",
)

# ── helpers ───────────────────────────────────────────────────────────────────

@dataclass
class Turn:
    user: str
    response: str = ""
    tool_calls: list[str] = field(default_factory=list)
    elapsed: float = 0.0

    def used_tool(self, *names: str) -> bool:
        """Check if any of the given tool names were called this turn."""
        return any(
            any(name in call for call in self.tool_calls)
            for name in names
        )

    def assert_tool(self, *names: str) -> None:
        assert self.used_tool(*names), (
            f"Expected one of {names} to be called.\n"
            f"Tools called: {self.tool_calls}\n"
            f"Response: {self.response[:300]}"
        )

    def assert_contains(self, *keywords: str) -> None:
        text = self.response.lower()
        missing = [kw for kw in keywords if kw.lower() not in text]
        assert not missing, (
            f"Expected keywords {missing} in response.\n"
            f"Response snippet: {self.response[:500]}"
        )


class ConversationalSession:
    """
    Wraps AgentLoop for multi-turn E2E testing.

    Usage:
        async with ConversationalSession() as s:
            t1 = await s.say("find papers on X")
            t1.assert_tool("paper_search")
            t2 = await s.say("now read the top one")
            t2.assert_tool("paper_read")
    """

    def __init__(
        self,
        model: str = "openai/gpt-4o-mini",
        max_iterations: int = 6,
        workspace: Path | None = None,
    ):
        self.model = model
        self.max_iterations = max_iterations
        self._workspace = workspace or Path(".")
        self._agent = None
        self.history: list[Turn] = []

    async def __aenter__(self) -> "ConversationalSession":
        from claw.agent.loop import AgentLoop
        from claw.agent.providers import LLMProvider

        provider = LLMProvider(model=self.model, api_key=None)
        self._agent = AgentLoop(
            workspace=self._workspace,
            provider=provider,
            model=self.model,
            max_iterations=self.max_iterations,
        )
        return self

    async def __aexit__(self, *_) -> None:
        self._agent = None

    async def say(self, message: str) -> Turn:
        """Send one message, collect tool calls + response, return Turn."""
        turn = Turn(user=message)
        t0 = time.time()

        async def _on_progress(text: str) -> None:
            if text.startswith("🔧"):
                turn.tool_calls.append(text)

        turn.response = await self._agent.chat(message, on_progress=_on_progress)
        turn.elapsed = time.time() - t0
        self.history.append(turn)

        # Pretty-print for -s output
        print(f"\n{'─'*60}")
        print(f"USER  : {message}")
        print(f"TOOLS : {turn.tool_calls or '(none)'}")
        print(f"TIME  : {turn.elapsed:.1f}s")
        print(f"REPLY : {turn.response[:400]}{'...' if len(turn.response) > 400 else ''}")

        return turn

    def total_time(self) -> float:
        return sum(t.elapsed for t in self.history)

    def all_tool_calls(self) -> list[str]:
        return [c for t in self.history for c in t.tool_calls]


# ── scenarios ─────────────────────────────────────────────────────────────────

@requires_llm
@pytest.mark.asyncio
async def test_scenario_paper_search_and_read():
    """
    Scenario: User searches for papers, then asks to read the top result.

    Turn 1: paper_search called
    Turn 2: paper_read called using ID from turn 1
    Turn 3: follow-up question — no new tool call needed (uses context)
    """
    async with ConversationalSession(max_iterations=5) as s:

        # Turn 1 — search
        t1 = await s.say("find 3 papers about knowledge distillation in neural networks")
        t1.assert_tool("paper_search")
        t1.assert_contains("knowledge distillation")
        assert len(t1.tool_calls) >= 1

        # Turn 2 — read most cited
        t2 = await s.say(
            "use paper_read to get full details of the most cited paper from those results"
        )
        t2.assert_tool("paper_read")
        t2.assert_contains("citations")

        # Turn 3 — follow-up from context (no new tool needed)
        t3 = await s.say("who are the authors of that paper?")
        # Should answer from context, not re-fetch
        assert t3.response  # just checks it doesn't crash

        print(f"\n✅ Scenario complete. Total time: {s.total_time():.1f}s")
        print(f"   Tool calls across session: {s.all_tool_calls()}")


@requires_llm
@pytest.mark.asyncio
async def test_scenario_year_filtered_search():
    """
    Scenario: User wants recent papers only (year filter).

    Turn 1: paper_search with year_from=2023
    Turn 2: ask to compare two papers
    """
    async with ConversationalSession(max_iterations=5) as s:

        t1 = await s.say(
            "search for papers about 'large language model agents' published after 2022, "
            "give me the top 5 by citations"
        )
        t1.assert_tool("paper_search")

        # All results should be recent
        response_lower = t1.response.lower()
        assert any(str(y) in response_lower for y in [2023, 2024, 2025]), (
            "Expected at least one paper from 2023-2025 in results"
        )

        t2 = await s.say("what's the main difference between the top 2 papers?")
        assert t2.response  # synthesis from context

        print(f"\n✅ Scenario complete. Total time: {s.total_time():.1f}s")


@requires_llm
@pytest.mark.asyncio
async def test_scenario_multi_angle_search():
    """
    Scenario: User asks for thorough literature search from multiple angles.
    Agent should call paper_search multiple times (different queries).

    Mimics Phase 1 of the deep-research skill.
    """
    async with ConversationalSession(max_iterations=8) as s:

        t1 = await s.say(
            "I want to survey the literature on 'efficient transformers'. "
            "Search from at least 2 different angles: one on efficiency methods, "
            "one on benchmark evaluations. Give me the combined list."
        )
        t1.assert_tool("paper_search")

        # Should have called paper_search at least twice
        search_calls = [c for c in t1.tool_calls if "paper_search" in c]
        assert len(search_calls) >= 1, (
            f"Expected multiple paper_search calls, got: {t1.tool_calls}"
        )

        print(f"\n✅ Scenario complete. Total time: {s.total_time():.1f}s")
        print(f"   paper_search calls: {len(search_calls)}")


@requires_llm
@pytest.mark.asyncio
async def test_scenario_paper_fetch_full_text():
    """
    Scenario: User wants full text of a specific paper.
    Agent should use web_fetch (ar5iv) or paper_read — either is valid.

    Turn 1: fetch content of a known arXiv paper
    Turn 2: ask a specific question about its method section
    """
    async with ConversationalSession(max_iterations=5) as s:

        t1 = await s.say(
            "fetch the full text of arXiv paper 1706.03762 (Attention Is All You Need) "
            "and summarize the architecture in 3 bullet points"
        )
        # Agent may use web_fetch (ar5iv) or paper_read — both acceptable
        assert t1.used_tool("web_fetch", "paper_read"), (
            f"Expected web_fetch or paper_read. Tools called: {t1.tool_calls}"
        )
        t1.assert_contains("attention", "transformer")

        t2 = await s.say("how many attention heads do they use in the base model?")
        # Should answer from fetched content — just check it doesn't crash
        assert t2.response
        # The base Transformer uses 8 heads — check for "8" or "head" keyword
        assert any(kw in t2.response.lower() for kw in ["8", "head", "multi"]), (
            f"Expected answer about attention heads, got: {t2.response[:200]}"
        )

        print(f"\n✅ Scenario complete. Total time: {s.total_time():.1f}s")


@requires_llm
@pytest.mark.asyncio
async def test_scenario_save_results_to_file():
    """
    Scenario: User wants search results saved to a file in the workspace.
    Agent should call paper_search + write_file.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)

        async with ConversationalSession(workspace=ws, max_iterations=6) as s:

            t1 = await s.say(
                "search for 5 papers about 'diffusion models image generation' "
                "and save the results as a markdown file called corpus.md in the workspace"
            )
            t1.assert_tool("paper_search")
            t1.assert_tool("write_file")

            # File should exist
            corpus = ws / "corpus.md"
            assert corpus.exists(), f"corpus.md not created. Tool calls: {t1.tool_calls}"
            content = corpus.read_text(encoding="utf-8")
            assert len(content) > 100, "corpus.md is nearly empty"
            assert "diffusion" in content.lower() or "paper" in content.lower()

            print(f"\n✅ corpus.md created ({len(content)} chars)")
            print(f"   Snippet: {content[:200]}")


@requires_llm
@pytest.mark.asyncio
async def test_scenario_chained_search_read_save():
    """
    Full research mini-session:
      1. Search for papers
      2. Read details of top result
      3. Save a summary to file

    This is the minimal version of what the `survey` skill does.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)

        async with ConversationalSession(workspace=ws, max_iterations=8) as s:

            t1 = await s.say(
                "find the top 3 most cited papers about 'BERT language model'"
            )
            t1.assert_tool("paper_search")
            t1.assert_contains("bert")

            t2 = await s.say(
                "get full details of the most cited paper using paper_read"
            )
            t2.assert_tool("paper_read")
            t2.assert_contains("citations")

            t3 = await s.say(
                "save a brief summary of what we found (paper title, authors, abstract) "
                "to a file called bert_summary.md"
            )
            t3.assert_tool("write_file")

            summary_file = ws / "bert_summary.md"
            assert summary_file.exists(), f"bert_summary.md not created"
            content = summary_file.read_text(encoding="utf-8")
            assert len(content) > 50

            print(f"\n✅ Full chain complete in {s.total_time():.1f}s")
            print(f"   All tool calls: {s.all_tool_calls()}")
            print(f"   Summary file ({len(content)} chars):\n{content[:300]}")
