#!/usr/bin/env python3
"""
Search HuggingFace Hub for datasets.

Usage:
    python search_datasets.py "<query>" [--max N]
"""

import argparse
import sys

import httpx

_HF_DATASETS_URL = "https://huggingface.co/api/datasets"


def search_datasets(query: str, max_results: int = 5) -> str:
    params: dict = {
        "search": query,
        "limit": min(max_results, 50),
        "sort": "downloads",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(_HF_DATASETS_URL, params=params)
            resp.raise_for_status()
            datasets = resp.json()
    except httpx.HTTPStatusError as exc:
        return f"Error: HuggingFace API returned status {exc.response.status_code}."
    except httpx.RequestError as exc:
        return f"Error: Could not reach HuggingFace API — {exc}"
    except Exception as exc:
        return f"Error: Unexpected failure during dataset search — {exc}"

    if not datasets:
        return f"No datasets found for query: '{query}'."

    lines: list[str] = [f"Found {len(datasets)} datasets for '{query}':\n"]
    for i, ds in enumerate(datasets, 1):
        ds_id = ds.get("id", "unknown")
        description = ds.get("description") or ""
        if len(description) > 200:
            description = description[:200].rstrip() + "..."

        downloads = ds.get("downloads", 0)
        likes = ds.get("likes", 0)
        tags = ds.get("tags") or []
        tag_str = ", ".join(tags[:5]) if tags else "N/A"

        lines.append(
            f"{i}. **{ds_id}**\n"
            f"   Downloads: {downloads:,} | Likes: {likes}\n"
            f"   Tags: {tag_str}"
            + (f"\n   Description: {description}" if description else "")
        )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search HuggingFace Hub for datasets.")
    parser.add_argument("query", help="Search query string")
    parser.add_argument("--max", type=int, default=5, dest="max_results",
                        help="Maximum results to return (default: 5, max: 50)")
    args = parser.parse_args()

    result = search_datasets(args.query, max_results=args.max_results)
    print(result)


if __name__ == "__main__":
    main()
