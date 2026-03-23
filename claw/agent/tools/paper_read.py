"""
PaperReadTool — fetch full metadata for a specific paper via OpenAlex.

Accepts: OpenAlex work ID (W...), arXiv ID (1706.03762 or arXiv:1706.03762), DOI.
Returns: title, abstract, authors, venue, year, citation count, references, PDF URL.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
from loguru import logger

from claw.agent.tools.base import Tool

_USER_AGENT = (
    "claw-researcher/1.0 (academic research agent; "
    "https://github.com/DuyTa506/tiny_researchers)"
)
_TIMEOUT = 20.0
_MAX_RETRIES = 3

_OA_FIELDS = (
    "id,title,publication_year,publication_date,authorships,cited_by_count,"
    "referenced_works_count,ids,abstract_inverted_index,primary_location,"
    "open_access,biblio,type,referenced_works"
)


async def _oa_get_raw(raw_url: str) -> dict | None:
    """GET OpenAlex using a pre-built URL string (avoids httpx encoding filter colons)."""
    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT, follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                resp = await client.get(httpx.URL(raw_url))
                if resp.status_code == 429:
                    wait = min(int(resp.headers.get("Retry-After", 10 * (2 ** attempt))), 60)
                    await asyncio.sleep(wait)
                    continue
                if resp.status_code == 404:
                    return None
                if resp.status_code >= 500:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                if not resp.is_success:
                    logger.warning("OpenAlex {} for {}", resp.status_code, raw_url[:100])
                    return None
                return resp.json()
        except Exception as exc:
            logger.warning("_oa_get_raw error (attempt {}): {}", attempt + 1, exc)
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(3 * (attempt + 1))
    return None


async def _oa_get(url: str, params: dict | None = None) -> dict | None:
    """GET a single OpenAlex work with retry + backoff."""
    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT, follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                # Build request manually to avoid double URL-encoding of filter values
                req = client.build_request("GET", url, params=params or {})
                resp = await client.send(req)

                if resp.status_code == 429:
                    wait = min(int(resp.headers.get("Retry-After", 10 * (2 ** attempt))), 60)
                    logger.warning("OpenAlex 429 — waiting {}s", wait)
                    await asyncio.sleep(wait)
                    continue

                if resp.status_code == 404:
                    return None

                if resp.status_code >= 500:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue

                if not resp.is_success:
                    logger.warning("OpenAlex {} for {}", resp.status_code, str(req.url)[:120])
                    return None

                return resp.json()

        except Exception as exc:
            logger.warning("paper_read error (attempt {}): {}", attempt + 1, exc)
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(3 * (attempt + 1))

    return None


def _normalize_id(raw: str) -> str | None:
    """
    Convert various ID formats to an OpenAlex-resolvable identifier.

    OpenAlex /works/{id} accepts:
      - https://openalex.org/W2741809807
      - W2741809807
      - doi:10.48550/arXiv.1706.03762
      - https://doi.org/10.48550/...
      - arxiv:1706.03762  (via filter, handled separately)
    """
    s = raw.strip()

    # Already an OpenAlex ID
    if re.match(r"^W\d+$", s, re.IGNORECASE):
        return s

    # DOI variants  →  doi:10.xxx/...
    if re.match(r"(?i)^doi:", s):
        return s
    if re.match(r"^10\.", s):
        return f"doi:{s}"
    if "doi.org/" in s:
        doi = re.search(r"doi\.org/(.+)", s)
        return f"doi:{doi.group(1)}" if doi else None

    # arXiv variants → we handle via filter endpoint (returned as None → use filter path)
    if re.match(r"(?i)^arxiv:", s):
        return None  # signal: use filter
    if re.match(r"^\d{4}\.\d{4,5}", s):
        return None  # bare arXiv ID

    return s  # pass through as-is


def _extract_arxiv_id(raw: str) -> str | None:
    """Pull out a bare arXiv ID from various formats."""
    s = raw.strip()
    # arXiv:1706.03762v3 or 1706.03762
    m = re.search(r"(\d{4}\.\d{4,5})", s)
    return m.group(1).split("v")[0] if m else None


def _reconstruct_abstract(inv: dict) -> str:
    if not inv:
        return ""
    positions: dict[int, str] = {}
    for word, pos_list in inv.items():
        for pos in pos_list:
            positions[pos] = word
    return " ".join(v for _, v in sorted(positions.items()))


async def _fetch_by_arxiv_id(arxiv_id: str) -> dict | None:
    """Look up a preprint by arXiv ID via its canonical DOI (10.48550/arxiv.XXXX)."""
    # ArXiv preprints in OpenAlex have DOI = https://doi.org/10.48550/arxiv.{id}
    doi = f"10.48550/arxiv.{arxiv_id}"
    data = await _oa_get(
        f"https://api.openalex.org/works/doi:{doi}",
        {"select": _OA_FIELDS, "mailto": "research@claw"},
    )
    if data and data.get("id"):
        return data

    # Fallback: full-text search by arXiv ID as a query term
    select_enc = _OA_FIELDS.replace(",", "%2C")
    raw_url = (
        f"https://api.openalex.org/works"
        f"?search={arxiv_id}"
        f"&per-page=1"
        f"&select={select_enc}"
        f"&mailto=research@claw"
    )
    data = await _oa_get_raw(raw_url)
    if data and data.get("results"):
        return data["results"][0]

    return None
    if data and data.get("results"):
        return data["results"][0]
    return None


async def _fetch_work(raw_id: str) -> dict | None:
    """Fetch a work from OpenAlex, handling all ID formats."""
    # Check if it's an arXiv ID first
    arxiv_id = _extract_arxiv_id(raw_id)
    oa_id = _normalize_id(raw_id)

    if oa_id is None and arxiv_id:
        # arXiv ID path → use filter
        return await _fetch_by_arxiv_id(arxiv_id)

    if oa_id:
        # Direct lookup
        data = await _oa_get(
            f"https://api.openalex.org/works/{oa_id}",
            {"select": _OA_FIELDS, "mailto": "research@claw"},
        )
        if data:
            return data

    # Fallback: if we have an arXiv ID, try filter path
    if arxiv_id:
        return await _fetch_by_arxiv_id(arxiv_id)

    return None


def _format_work(w: dict) -> str:
    """Format an OpenAlex work dict into readable markdown."""
    title = w.get("title") or "Unknown Title"
    year = w.get("publication_year") or "?"
    pub_date = w.get("publication_date") or ""

    # Authors
    authors = [
        a["author"]["display_name"]
        for a in (w.get("authorships") or [])[:15]
        if a.get("author") and a["author"].get("display_name")
    ]
    author_str = ", ".join(authors[:5]) + (" et al." if len(authors) > 5 else "")

    # Venue
    loc = w.get("primary_location") or {}
    venue = (loc.get("source") or {}).get("display_name") or ""

    # Counts
    citations = w.get("cited_by_count", 0)
    ref_count = w.get("referenced_works_count", 0)

    # IDs
    ids = w.get("ids") or {}
    arxiv_raw = ids.get("arxiv") or ""
    arxiv_match = re.search(r"(\d{4}\.\d{4,5})", arxiv_raw)
    arxiv_id = arxiv_match.group(1) if arxiv_match else ""
    doi = (w.get("doi") or "").replace("https://doi.org/", "")
    oa_id = (w.get("id") or "").replace("https://openalex.org/", "")

    # Open access
    oa_info = w.get("open_access") or {}
    pdf_url = oa_info.get("oa_url") or ""
    if not pdf_url and arxiv_id:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

    # Abstract
    abstract = _reconstruct_abstract(w.get("abstract_inverted_index") or {})

    # Top references (OpenAlex IDs only — agent can call paper_read on any of them)
    ref_ids = (w.get("referenced_works") or [])[:10]
    ref_short = [r.replace("https://openalex.org/", "") for r in ref_ids]

    lines = [
        f"## {title} ({year})",
        f"**Authors**: {author_str}",
    ]
    if venue:
        lines.append(f"**Venue**: {venue}" + (f" | Published: {pub_date}" if pub_date else ""))
    lines.append(f"**Citations**: {citations} | **References**: {ref_count}")
    if arxiv_id:
        lines.append(f"**arXiv**: {arxiv_id} → https://arxiv.org/abs/{arxiv_id}")
    if doi:
        lines.append(f"**DOI**: {doi}")
    if oa_id:
        lines.append(f"**OpenAlex ID**: {oa_id}")
    if pdf_url:
        lines.append(f"**PDF**: {pdf_url}")

    lines.append("")
    lines.append("**Abstract**:")
    lines.append(abstract or "*(no abstract available)*")

    if ref_short:
        lines.append("")
        lines.append(f"**Top {len(ref_short)} Referenced Works** (OpenAlex IDs — use paper_read to look up any):")
        lines.append(", ".join(ref_short))

    return "\n".join(lines)


class PaperReadTool(Tool):
    """Fetch full metadata for a specific paper from OpenAlex."""

    @property
    def name(self) -> str:
        return "paper_read"

    @property
    def description(self) -> str:
        return (
            "Fetch full details of a specific academic paper: abstract, authors, "
            "citation count, references, venue, and PDF link. "
            "Accepts arXiv IDs (e.g. '1706.03762'), OpenAlex IDs (e.g. 'W2741809807'), "
            "or DOIs. Use after paper_search to read a specific paper in depth."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "paper_id": {
                    "type": "string",
                    "description": (
                        "Paper identifier. Accepted formats: "
                        "arXiv ID ('1706.03762'), "
                        "OpenAlex ID ('W2741809807'), "
                        "DOI ('10.18653/v1/2020.acl-main.463')"
                    ),
                },
            },
            "required": ["paper_id"],
        }

    async def execute(self, **kwargs: Any) -> str:
        raw_id: str = kwargs["paper_id"]
        logger.info("paper_read: id={!r}", raw_id)

        work = await _fetch_work(raw_id)

        if work is None:
            return (
                f"Paper not found for ID: '{raw_id}'. "
                "Try paper_search to find the correct arXiv ID or OpenAlex ID."
            )

        return _format_work(work)
