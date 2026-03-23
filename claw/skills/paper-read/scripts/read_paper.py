#!/usr/bin/env python3
"""
Fetch full details for a single academic paper from Semantic Scholar.

Usage:
    python read_paper.py "<paper_id>"

paper_id formats:
    - Semantic Scholar ID: alphanumeric hash (e.g. 204e3073870fae3d05bcbc2f6a8e263d9b72e776)
    - arXiv ID:            arXiv:YYMM.NNNNN  (e.g. arXiv:1706.03762)
"""

import argparse
import os
import sys

import httpx

_S2_PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper"
_S2_FIELDS = (
    "title,abstract,year,authors,references,citationCount,"
    "externalIds,tldr,url"
)


def format_paper(p: dict) -> str:
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

    tldr_obj = p.get("tldr") or {}
    tldr = tldr_obj.get("text", "")
    abstract = p.get("abstract") or ""

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


def read_paper(paper_id: str) -> str:
    url = f"{_S2_PAPER_URL}/{paper_id}"
    params = {"fields": _S2_FIELDS}

    headers = {}
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
    if api_key:
        headers["x-api-key"] = api_key

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            paper = resp.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 404:
            return f"Error: Paper '{paper_id}' not found on Semantic Scholar."
        return f"Error: Semantic Scholar API returned status {status}."
    except httpx.RequestError as exc:
        return f"Error: Could not reach Semantic Scholar API — {exc}"
    except Exception as exc:
        return f"Error: Unexpected failure — {exc}"

    return format_paper(paper)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch full paper details from Semantic Scholar.")
    parser.add_argument("paper_id",
                        help="Semantic Scholar ID or arXiv ID prefixed with 'arXiv:' (e.g. arXiv:1706.03762)")
    args = parser.parse_args()

    result = read_paper(args.paper_id)
    print(result)


if __name__ == "__main__":
    main()
