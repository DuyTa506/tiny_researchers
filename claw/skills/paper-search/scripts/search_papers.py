#!/usr/bin/env python3
"""
Search academic papers via Semantic Scholar API.

Usage:
    python search_papers.py "<query>" [--max N] [--year-from YYYY]
"""

import argparse
import os
import sys

import httpx

_S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_S2_FIELDS = "title,abstract,year,citationCount,authors,externalIds,url"


def search_papers(query: str, max_results: int = 10, year_from: int | None = None) -> str:
    params: dict = {
        "query": query,
        "limit": min(max_results, 100),
        "fields": _S2_FIELDS,
    }
    if year_from is not None:
        params["year"] = f"{year_from}-"

    headers = {}
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
    if api_key:
        headers["x-api-key"] = api_key

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(_S2_SEARCH_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        return f"Error: Semantic Scholar API returned status {exc.response.status_code}."
    except httpx.RequestError as exc:
        return f"Error: Could not reach Semantic Scholar API — {exc}"
    except Exception as exc:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Search academic papers via Semantic Scholar.")
    parser.add_argument("query", help="Search query string")
    parser.add_argument("--max", type=int, default=10, dest="max_results",
                        help="Maximum results to return (default: 10, max: 100)")
    parser.add_argument("--year-from", type=int, default=None, dest="year_from",
                        help="Only include papers from this year onwards")
    args = parser.parse_args()

    result = search_papers(args.query, max_results=args.max_results, year_from=args.year_from)
    print(result)


if __name__ == "__main__":
    main()
