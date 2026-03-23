"""Paper search tool — searches Semantic Scholar and arXiv for academic papers."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from claw.agent.tools.base import Tool

_S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_S2_FIELDS = "title,abstract,year,citationCount,authors,externalIds,url"


class PaperSearchTool(Tool):
    """Search for academic papers across Semantic Scholar."""

    @property
    def name(self) -> str:
        return "paper_search"

    @property
    def description(self) -> str:
        return (
            "Search for academic papers by keyword query using Semantic Scholar. "
            "Returns titles, years, citation counts, authors, and arXiv IDs. "
            "Use this to discover relevant literature on a research topic."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for finding papers (e.g. 'transformer attention mechanism').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-100).",
                },
                "year_from": {
                    "type": ["integer", "null"],
                    "description": "Only include papers published in or after this year.",
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> str:
        query: str = kwargs["query"]
        max_results: int = min(kwargs.get("max_results", 10), 100)
        year_from: int | None = kwargs.get("year_from")

        logger.info("paper_search: query={!r} max_results={} year_from={}", query, max_results, year_from)

        params: dict[str, Any] = {
            "query": query,
            "limit": max_results,
            "fields": _S2_FIELDS,
        }
        if year_from is not None:
            params["year"] = f"{year_from}-"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(_S2_SEARCH_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Semantic Scholar HTTP error: {}", exc)
            return f"Error: Semantic Scholar API returned status {exc.response.status_code}."
        except httpx.RequestError as exc:
            logger.error("Semantic Scholar request error: {}", exc)
            return f"Error: Could not reach Semantic Scholar API — {exc}"
        except Exception as exc:
            logger.error("paper_search unexpected error: {}", exc)
            return f"Error: Unexpected failure during paper search — {exc}"

        papers = data.get("data") or []
        total = data.get("total", len(papers))

        if not papers:
            return f"No papers found for query: '{query}'."

        lines: list[str] = [f"Found {total} papers (showing top {len(papers)}):\n"]
        for i, p in enumerate(papers, 1):
            title = p.get("title", "Untitled")
            year = p.get("year", "N/A")
            cites = p.get("citationCount", 0)
            authors = p.get("authors") or []
            author_str = ", ".join(a.get("name", "") for a in authors[:3])
            if len(authors) > 3:
                author_str += " et al."

            ext_ids = p.get("externalIds") or {}
            arxiv_id = ext_ids.get("ArXiv", "")
            s2_id = p.get("paperId", "")
            url = p.get("url", "")

            lines.append(
                f"{i}. **{title}** ({year})\n"
                f"   Authors: {author_str}\n"
                f"   Citations: {cites} | S2 ID: {s2_id}"
                + (f" | arXiv: {arxiv_id}" if arxiv_id else "")
                + (f"\n   URL: {url}" if url else "")
            )

        return "\n".join(lines)
