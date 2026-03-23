"""Paper fetch tool — fetches the full text of an arXiv paper via ar5iv.org or arXiv."""

from __future__ import annotations

import re
from typing import Any

import httpx
from loguru import logger

from claw.agent.tools.base import Tool

_AR5IV_URL = "https://ar5iv.org/abs/{arxiv_id}"
_ARXIV_ABS_URL = "https://arxiv.org/abs/{arxiv_id}"
_MAX_CHARS = 50_000


def _strip_html(html: str) -> str:
    """Remove HTML markup and return plain text."""
    # Remove script/style blocks entirely
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _normalize_arxiv_id(paper_id: str) -> str:
    """Return a bare arXiv ID given a raw input string."""
    paper_id = paper_id.strip()

    # Strip "arxiv:" prefix (case-insensitive)
    paper_id = re.sub(r'^arxiv\s*:\s*', '', paper_id, flags=re.IGNORECASE)

    # Handle full URLs: https://arxiv.org/abs/1706.03762  or  https://ar5iv.org/abs/1706.03762
    url_match = re.search(r'arxiv\.org/(?:abs|pdf)/([^\s/?#]+)', paper_id, re.IGNORECASE)
    if url_match:
        return url_match.group(1).rstrip('.pdf').rstrip('/')

    ar5iv_match = re.search(r'ar5iv\.org/(?:abs|html)/([^\s/?#]+)', paper_id, re.IGNORECASE)
    if ar5iv_match:
        return ar5iv_match.group(1).rstrip('/')

    # What remains should already be a bare ID such as "1706.03762" or "cs.LG/0601001"
    return paper_id


def _extract_arxiv_title_abstract(html: str) -> tuple[str, str]:
    """Extract title and abstract from an arXiv abstract-page HTML snippet."""
    title = ""
    abstract = ""

    # Title lives inside <h1 class="title ...">Title:<span ...>Actual Title</span></h1>
    title_match = re.search(
        r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h1>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if title_match:
        title = _strip_html(title_match.group(1))
        # arXiv prepends "Title:" as visible text — remove it
        title = re.sub(r'^Title:\s*', '', title, flags=re.IGNORECASE).strip()

    # Abstract lives inside <blockquote class="abstract ...">Abstract:<span...>…</span></blockquote>
    abstract_match = re.search(
        r'<blockquote[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</blockquote>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if abstract_match:
        abstract = _strip_html(abstract_match.group(1))
        abstract = re.sub(r'^Abstract:\s*', '', abstract, flags=re.IGNORECASE).strip()

    return title, abstract


class PaperFetchTool(Tool):
    """Fetch the full text of an arXiv paper via ar5iv.org with arXiv fallback."""

    @property
    def name(self) -> str:
        return "paper_fetch"

    @property
    def description(self) -> str:
        return (
            "Fetch the full text of a paper from arXiv. "
            "Provide an arXiv ID (e.g. '1706.03762' or 'arxiv:1706.03762') or a direct URL. "
            "Returns structured text with title, abstract, and main sections."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "paper_id": {
                    "type": "string",
                    "description": (
                        "arXiv ID (e.g. '1706.03762', '2301.00001', or 'arxiv:1706.03762') "
                        "or full URL"
                    ),
                },
                "sections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Sections to extract: abstract, introduction, method, experiments, "
                        "results, conclusion, appendix. Default: all."
                    ),
                },
            },
            "required": ["paper_id"],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_ar5iv(self, client: httpx.AsyncClient, arxiv_id: str) -> str | None:
        """Attempt to fetch rendered HTML from ar5iv.org. Returns plain text or None."""
        url = _AR5IV_URL.format(arxiv_id=arxiv_id)
        logger.info("paper_fetch: trying ar5iv at {}", url)
        try:
            resp = await client.get(url)
        except httpx.RequestError as exc:
            logger.error("paper_fetch: ar5iv request error — {}", exc)
            return None

        if resp.status_code != 200:
            logger.info("paper_fetch: ar5iv returned HTTP {} for {}", resp.status_code, url)
            return None

        return _strip_html(resp.text)

    async def _fetch_arxiv_fallback(
        self, client: httpx.AsyncClient, arxiv_id: str
    ) -> tuple[str, str, str]:
        """Fetch title and abstract from the arXiv abstract page.

        Returns (title, abstract, error_message).  error_message is empty on success.
        """
        url = _ARXIV_ABS_URL.format(arxiv_id=arxiv_id)
        logger.info("paper_fetch: falling back to arXiv abstract page at {}", url)
        try:
            resp = await client.get(url)
        except httpx.RequestError as exc:
            logger.error("paper_fetch: arXiv request error — {}", exc)
            return "", "", f"Error: could not fetch paper {arxiv_id}: {exc}"

        if resp.status_code != 200:
            logger.error("paper_fetch: arXiv returned HTTP {} for {}", resp.status_code, url)
            return "", "", f"Error: HTTP {resp.status_code} for {url}"

        title, abstract = _extract_arxiv_title_abstract(resp.text)
        return title, abstract, ""

    # ------------------------------------------------------------------
    # Public execute
    # ------------------------------------------------------------------

    async def execute(self, **kwargs: Any) -> str:
        raw_id: str = kwargs["paper_id"]
        sections: list[str] | None = kwargs.get("sections")

        arxiv_id = _normalize_arxiv_id(raw_id)
        logger.info("paper_fetch: paper_id={!r} → arxiv_id={!r} sections={}", raw_id, arxiv_id, sections)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # ── Primary: ar5iv.org ──────────────────────────────────────
            full_text = await self._fetch_ar5iv(client, arxiv_id)

            if full_text:
                # ar5iv gives us everything; build result directly
                result = (
                    f"## Source\nar5iv.org (rendered LaTeX)\n\n"
                    f"## Full Text\n{full_text}"
                )
                return result[:_MAX_CHARS]

            # ── Fallback: arXiv abstract page ───────────────────────────
            title, abstract, error = await self._fetch_arxiv_fallback(client, arxiv_id)
            if error:
                return error

        # Build a structured markdown response from whatever we recovered
        parts: list[str] = []

        if title:
            parts.append(f"## Title\n{title}")

        if abstract:
            parts.append(f"## Abstract\n{abstract}")

        if not parts:
            return f"Error: could not fetch paper {arxiv_id}: no content extracted."

        parts.append(
            "## Full Text\n"
            "_Full text unavailable — ar5iv.org did not return content for this paper. "
            "The abstract above was retrieved from the arXiv abstract page._"
        )

        result = "\n\n".join(parts)
        return result[:_MAX_CHARS]
