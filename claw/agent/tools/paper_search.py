"""
PaperSearchTool — search academic papers via ArXiv and OpenAlex.

Sources:
  - ArXiv    : export.arxiv.org/api/query (Atom XML, official API)
  - OpenAlex : api.openalex.org/works (JSON, CC0, 100k req/day free)

Rate limiting follows ArXiv policy: max 1 request / 3 seconds.
"""
from __future__ import annotations

import asyncio
import re
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from loguru import logger

from claw.agent.tools.base import Tool

# ---------------------------------------------------------------------------
# ArXiv rate limiting (policy: max 1 req / 3 sec)
# ---------------------------------------------------------------------------
_arxiv_semaphore = asyncio.Semaphore(1)
_arxiv_last_request: float = 0.0
_ARXIV_MIN_INTERVAL = 3.5  # seconds

_USER_AGENT = (
    "claw-researcher/1.0 (academic research agent; "
    "https://github.com/DuyTa506/tiny_researchers)"
)
_TIMEOUT = 20.0
_MAX_RETRIES = 3


async def _arxiv_request(url: str, params: dict) -> httpx.Response | None:
    """Execute a rate-limited, retried GET to the ArXiv API."""
    global _arxiv_last_request

    async with _arxiv_semaphore:
        elapsed = time.time() - _arxiv_last_request
        if elapsed < _ARXIV_MIN_INTERVAL:
            await asyncio.sleep(_ARXIV_MIN_INTERVAL - elapsed)

        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                    timeout=_TIMEOUT, follow_redirects=True,
                    headers={"User-Agent": _USER_AGENT},
                ) as client:
                    resp = await client.get(url, params=params)
                    _arxiv_last_request = time.time()

                    if resp.status_code == 429:
                        wait = int(resp.headers.get("Retry-After", 10 * (2 ** attempt)))
                        wait = min(wait, 60)
                        logger.warning("ArXiv 429 — waiting {}s", wait)
                        await asyncio.sleep(wait)
                        continue

                    if resp.status_code >= 500:
                        wait = 5 * (attempt + 1)
                        logger.warning("ArXiv {} — waiting {}s", resp.status_code, wait)
                        await asyncio.sleep(wait)
                        continue

                    resp.raise_for_status()
                    return resp

            except Exception as exc:
                logger.warning("ArXiv request error (attempt {}): {}", attempt + 1, exc)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(3 * (attempt + 1))

    return None


async def _http_get_json(url: str, params: dict | None = None) -> dict | list | None:
    """Generic retried GET that returns parsed JSON."""
    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT, follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                resp = await client.get(url, params=params or {})

                if resp.status_code == 429:
                    wait = min(int(resp.headers.get("Retry-After", 10 * (2 ** attempt))), 60)
                    logger.warning("HTTP 429 on {} — waiting {}s", url, wait)
                    await asyncio.sleep(wait)
                    continue

                if resp.status_code >= 500:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue

                resp.raise_for_status()
                return resp.json()

        except Exception as exc:
            logger.warning("HTTP GET error (attempt {}): {}", attempt + 1, exc)
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(3 * (attempt + 1))

    return None


# ---------------------------------------------------------------------------
# ArXiv search
# ---------------------------------------------------------------------------

def _parse_arxiv_xml(xml_text: str) -> list[dict]:
    """Parse ArXiv Atom XML response into paper dicts."""
    papers: list[dict] = []
    try:
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        root = ET.fromstring(xml_text)
        for entry in root.findall("atom:entry", ns):
            def _text(tag: str) -> str:
                el = entry.find(tag, ns)
                return el.text.strip() if el is not None and el.text else ""

            arxiv_id_raw = _text("atom:id")
            arxiv_id = re.search(r"abs/([^\s/]+)", arxiv_id_raw)
            arxiv_id = arxiv_id.group(1).split("v")[0] if arxiv_id else ""

            authors = [
                a.find("atom:name", ns).text.strip()
                for a in entry.findall("atom:author", ns)
                if a.find("atom:name", ns) is not None
            ]

            year_str = _text("atom:published")[:4]
            year = int(year_str) if year_str.isdigit() else None

            papers.append({
                "title": _text("atom:title").replace("\n", " ").strip(),
                "abstract": _text("atom:summary").replace("\n", " ").strip(),
                "authors": authors,
                "year": year,
                "arxiv_id": arxiv_id,
                "doi": None,
                "openalex_id": None,
                "citations": None,
                "venue": None,
                "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
                "source": "arxiv",
            })
    except Exception as exc:
        logger.warning("ArXiv XML parse error: {}", exc)

    return papers


async def _search_arxiv(query: str, max_results: int, year_from: int | None) -> list[dict]:
    search_query = f"all:{query}"
    if year_from:
        search_query += f" AND submittedDate:[{year_from}0101 TO 99991231]"

    resp = await _arxiv_request(
        "https://export.arxiv.org/api/query",
        {"search_query": search_query, "max_results": max_results, "sortBy": "relevance"},
    )
    if resp is None:
        return []
    return _parse_arxiv_xml(resp.text)


# ---------------------------------------------------------------------------
# OpenAlex search
# ---------------------------------------------------------------------------

def _condense_for_openalex(query: str, max_words: int = 4) -> str:
    """
    OpenAlex requires ALL terms to match — condense to 3-4 significant words
    to avoid zero results from over-specificity.
    """
    stopwords = {
        "a", "an", "the", "and", "or", "of", "in", "for", "to", "with",
        "using", "based", "on", "via", "from", "by", "is", "are", "be",
    }
    words = [w for w in query.lower().split() if len(w) > 2 and w not in stopwords]
    return " ".join(words[:max_words])


def _reconstruct_abstract(inv: dict) -> str:
    """Reconstruct abstract text from OpenAlex inverted index format."""
    if not inv:
        return ""
    positions: dict[int, str] = {}
    for word, pos_list in inv.items():
        for pos in pos_list:
            positions[pos] = word
    return " ".join(v for _, v in sorted(positions.items()))


async def _search_openalex(query: str, max_results: int, year_from: int | None) -> list[dict]:
    condensed = _condense_for_openalex(query)
    filter_str = f"title_and_abstract.search:{condensed}"
    if year_from:
        filter_str += f",publication_year:>{year_from - 1}"

    params: dict = {
        "filter": filter_str,
        "per-page": max_results,
        "select": "id,title,publication_year,authorships,cited_by_count,doi,ids,abstract_inverted_index,primary_location",
        "mailto": "research@claw",
    }

    data = await _http_get_json("https://api.openalex.org/works", params)
    if not data or "results" not in data:
        return []

    papers: list[dict] = []
    for w in data["results"]:
        abstract = _reconstruct_abstract(w.get("abstract_inverted_index") or {})

        authors = [
            a["author"]["display_name"]
            for a in (w.get("authorships") or [])[:10]
            if a.get("author") and a["author"].get("display_name")
        ]

        ids = w.get("ids") or {}
        arxiv_raw = ids.get("arxiv", "")
        arxiv_match = re.search(r"(\d{4}\.\d{4,5})", arxiv_raw)
        arxiv_id = arxiv_match.group(1) if arxiv_match else ""

        loc = w.get("primary_location") or {}
        venue = (loc.get("source") or {}).get("display_name", "")

        # OpenAlex ID is a URL like https://openalex.org/W2741809807 → extract short ID
        oa_id = (w.get("id") or "").replace("https://openalex.org/", "")

        papers.append({
            "title": w.get("title") or "",
            "abstract": abstract[:800],
            "authors": authors,
            "year": w.get("publication_year"),
            "arxiv_id": arxiv_id,
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "openalex_id": oa_id,
            "citations": w.get("cited_by_count"),
            "venue": venue,
            "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else (w.get("id") or ""),
            "source": "openalex",
        })

    return papers


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _dedup(papers: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []

    for p in papers:
        keys: list[str] = []

        arxiv = (p.get("arxiv_id") or "").strip()
        if arxiv:
            keys.append(f"arxiv:{arxiv}")

        doi = (p.get("doi") or "").strip().lower()
        if doi:
            keys.append(f"doi:{doi}")

        title = re.sub(r"\W+", " ", (p.get("title") or "").lower()).strip()[:50]
        first_author = (p.get("authors") or [""])[0].split()[-1].lower() if p.get("authors") else ""
        if title:
            keys.append(f"fp:{title}|{first_author}")

        if any(k in seen for k in keys):
            continue

        for k in keys:
            seen.add(k)
        unique.append(p)

    return unique


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _format_results(papers: list[dict], query: str) -> str:
    if not papers:
        return f"No papers found for query: '{query}'"

    lines = [f"Found {len(papers)} papers for '{query}':\n"]
    for i, p in enumerate(papers, 1):
        authors = p.get("authors") or []
        author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
        year = p.get("year") or "?"
        citations = p.get("citations")
        cite_str = f"{citations} citations" if citations is not None else ""
        venue = p.get("venue") or ""
        arxiv = f"arXiv:{p['arxiv_id']}" if p.get("arxiv_id") else ""
        oa_id = f"OA:{p['openalex_id']}" if p.get("openalex_id") else ""

        meta = " | ".join(x for x in [cite_str, arxiv, oa_id] if x)
        abstract = (p.get("abstract") or "")[:200]
        if len(p.get("abstract") or "") > 200:
            abstract += "..."

        lines.append(
            f"{i}. **{p.get('title', 'Untitled')}** ({year})"
            + (f" — {venue}" if venue else "") + "\n"
            f"   {author_str}\n"
            + (f"   {meta}\n" if meta else "")
            + f"   {abstract}\n"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool class
# ---------------------------------------------------------------------------

class PaperSearchTool(Tool):
    """Search academic papers via ArXiv and OpenAlex."""

    @property
    def name(self) -> str:
        return "paper_search"

    @property
    def description(self) -> str:
        return (
            "Search for academic papers by keyword across ArXiv and OpenAlex. "
            "Returns titles, authors, abstracts, citation counts, arXiv IDs, "
            "and OpenAlex IDs. Use for finding relevant research papers on a topic."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keywords, e.g. 'attention mechanism transformers'",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max papers per source (default 10, max 50)",
                    "default": 10,
                },
                "year_from": {
                    "type": "integer",
                    "description": "Only papers published from this year onwards, e.g. 2022",
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> str:
        query: str = kwargs["query"]
        max_results: int = min(int(kwargs.get("max_results", 10)), 50)
        year_from: int | None = kwargs.get("year_from")

        logger.info("paper_search: query={!r} max={} year_from={}", query, max_results, year_from)

        arxiv_task = asyncio.create_task(_search_arxiv(query, max_results, year_from))
        openalex_task = asyncio.create_task(_search_openalex(query, max_results, year_from))

        results = await asyncio.gather(arxiv_task, openalex_task, return_exceptions=True)

        all_papers: list[dict] = []
        for name, res in zip(["ArXiv", "OpenAlex"], results):
            if isinstance(res, Exception):
                logger.warning("paper_search {} failed: {}", name, res)
            elif res:
                all_papers.extend(res)
                logger.debug("paper_search {}: {} results", name, len(res))

        unique = _dedup(all_papers)
        unique.sort(key=lambda p: p.get("citations") or -1, reverse=True)

        top = unique[:max_results]
        return _format_results(top, query)
