"""Paper read tool — fetches full details for a single academic paper."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from claw.agent.tools.base import Tool

_S2_PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper"
_S2_FIELDS = (
    "title,abstract,year,authors,references,citationCount,"
    "externalIds,tldr,url"
)


class PaperReadTool(Tool):
    """Fetch and read a paper's full details from Semantic Scholar."""

    @property
    def name(self) -> str:
        return "paper_read"

    @property
    def description(self) -> str:
        return (
            "Retrieve full details for a specific academic paper by its Semantic Scholar "
            "paper ID or arXiv ID (e.g. 'arXiv:2401.12345'). Returns the title, TLDR, "
            "abstract, authors, citation count, and top references."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "paper_id": {
                    "type": "string",
                    "description": (
                        "Semantic Scholar paper ID, or an arXiv ID prefixed with 'arXiv:' "
                        "(e.g. 'arXiv:2401.01234')."
                    ),
                },
            },
            "required": ["paper_id"],
        }

    async def execute(self, **kwargs: Any) -> str:
        paper_id: str = kwargs["paper_id"]
        logger.info("paper_read: paper_id={!r}", paper_id)

        url = f"{_S2_PAPER_URL}/{paper_id}"
        params = {"fields": _S2_FIELDS}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                paper = resp.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 404:
                return f"Error: Paper '{paper_id}' not found on Semantic Scholar."
            logger.error("Semantic Scholar HTTP error: {}", exc)
            return f"Error: Semantic Scholar API returned status {status}."
        except httpx.RequestError as exc:
            logger.error("Semantic Scholar request error: {}", exc)
            return f"Error: Could not reach Semantic Scholar API — {exc}"
        except Exception as exc:
            logger.error("paper_read unexpected error: {}", exc)
            return f"Error: Unexpected failure — {exc}"

        return self._format_paper(paper)

    @staticmethod
    def _format_paper(p: dict[str, Any]) -> str:
        title = p.get("title", "Untitled")
        year = p.get("year", "N/A")
        cites = p.get("citationCount", 0)
        url = p.get("url", "")

        authors = p.get("authors") or []
        author_str = ", ".join(a.get("name", "") for a in authors[:10])
        if len(authors) > 10:
            author_str += f" et al. ({len(authors)} total)"

        ext_ids = p.get("externalIds") or {}
        arxiv_id = ext_ids.get("ArXiv", "")
        doi = ext_ids.get("DOI", "")

        # TLDR
        tldr_obj = p.get("tldr") or {}
        tldr = tldr_obj.get("text", "")

        abstract = p.get("abstract") or ""

        # Top references
        refs = p.get("references") or []
        ref_lines: list[str] = []
        for r in refs[:10]:
            ref_title = r.get("title", "Untitled")
            ref_year = r.get("year", "")
            ref_id = r.get("paperId", "")
            ref_lines.append(f"  - {ref_title} ({ref_year}) [ID: {ref_id}]")

        sections: list[str] = [
            f"# {title}",
            f"**Year:** {year} | **Citations:** {cites}",
            f"**Authors:** {author_str}",
        ]
        if arxiv_id:
            sections.append(f"**arXiv:** {arxiv_id}")
        if doi:
            sections.append(f"**DOI:** {doi}")
        if url:
            sections.append(f"**URL:** {url}")
        if tldr:
            sections.append(f"\n## TLDR\n{tldr}")
        if abstract:
            sections.append(f"\n## Abstract\n{abstract}")
        if ref_lines:
            sections.append(f"\n## Top References ({len(refs)} total)\n" + "\n".join(ref_lines))

        return "\n".join(sections)
