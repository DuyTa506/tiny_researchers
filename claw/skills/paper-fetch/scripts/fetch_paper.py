#!/usr/bin/env python3
"""
Fetch the full text of an arXiv paper via ar5iv.org (with arXiv fallback).

Usage:
    python fetch_paper.py "<paper_id>"

paper_id accepts:
    - Bare arXiv ID:      1706.03762
    - Prefixed arXiv ID:  arxiv:1706.03762
    - arXiv URL:          https://arxiv.org/abs/1706.03762
    - ar5iv URL:          https://ar5iv.org/abs/1706.03762
"""

import argparse
import re
import sys

import httpx

_AR5IV_URL = "https://ar5iv.org/abs/{arxiv_id}"
_ARXIV_ABS_URL = "https://arxiv.org/abs/{arxiv_id}"
_MAX_CHARS = 50_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    """Remove HTML markup and return clean plain text."""
    # Drop script/style blocks entirely
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Collapse whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _normalize_arxiv_id(raw: str) -> str:
    """Return a bare arXiv ID from any supported input format."""
    raw = raw.strip()

    # Full URL: https://arxiv.org/abs/1706.03762  or  /pdf/1706.03762
    url_match = re.search(r'arxiv\.org/(?:abs|pdf)/([^\s/?#]+)', raw, re.IGNORECASE)
    if url_match:
        return url_match.group(1).removesuffix('.pdf').rstrip('/')

    # ar5iv URL: https://ar5iv.org/abs/1706.03762
    ar5iv_match = re.search(r'ar5iv\.org/(?:abs|html)/([^\s/?#]+)', raw, re.IGNORECASE)
    if ar5iv_match:
        return ar5iv_match.group(1).rstrip('/')

    # "arxiv:1706.03762" or "arXiv: 1706.03762"
    raw = re.sub(r'^arxiv\s*:\s*', '', raw, flags=re.IGNORECASE)

    return raw


def _extract_arxiv_title_abstract(html: str) -> tuple[str, str]:
    """Pull title and abstract out of an arXiv abstract page."""
    title = ""
    abstract = ""

    title_match = re.search(
        r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h1>',
        html, re.DOTALL | re.IGNORECASE,
    )
    if title_match:
        title = _strip_html(title_match.group(1))
        title = re.sub(r'^Title:\s*', '', title, flags=re.IGNORECASE).strip()

    abstract_match = re.search(
        r'<blockquote[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</blockquote>',
        html, re.DOTALL | re.IGNORECASE,
    )
    if abstract_match:
        abstract = _strip_html(abstract_match.group(1))
        abstract = re.sub(r'^Abstract:\s*', '', abstract, flags=re.IGNORECASE).strip()

    return title, abstract


# ---------------------------------------------------------------------------
# Fetch logic
# ---------------------------------------------------------------------------

def _fetch_ar5iv(client: httpx.Client, arxiv_id: str) -> str | None:
    """Try ar5iv.org for full rendered text. Returns plain text or None."""
    url = _AR5IV_URL.format(arxiv_id=arxiv_id)
    try:
        resp = client.get(url)
    except httpx.RequestError as exc:
        print(f"[paper-fetch] ar5iv request error: {exc}", file=sys.stderr)
        return None

    if resp.status_code != 200:
        print(f"[paper-fetch] ar5iv returned HTTP {resp.status_code}", file=sys.stderr)
        return None

    text = _strip_html(resp.text)
    # ar5iv pages sometimes return a "conversion failed" page — detect it
    if "ar5iv.org" in text and len(text) < 500:
        return None

    return text


def _fetch_arxiv_fallback(client: httpx.Client, arxiv_id: str) -> tuple[str, str, str]:
    """Fetch title + abstract from the arXiv abstract page.

    Returns (title, abstract, error). error is empty string on success.
    """
    url = _ARXIV_ABS_URL.format(arxiv_id=arxiv_id)
    try:
        resp = client.get(url)
    except httpx.RequestError as exc:
        return "", "", f"Error: could not reach arXiv — {exc}"

    if resp.status_code != 200:
        return "", "", f"Error: arXiv returned HTTP {resp.status_code} for {url}"

    title, abstract = _extract_arxiv_title_abstract(resp.text)
    return title, abstract, ""


def fetch_paper(paper_id: str) -> str:
    arxiv_id = _normalize_arxiv_id(paper_id)

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        # Primary: ar5iv — full rendered LaTeX text
        full_text = _fetch_ar5iv(client, arxiv_id)
        if full_text:
            result = (
                f"## Source\nar5iv.org (full rendered LaTeX text)\n\n"
                f"## Full Text\n{full_text}"
            )
            return result[:_MAX_CHARS]

        # Fallback: arXiv abstract page
        title, abstract, error = _fetch_arxiv_fallback(client, arxiv_id)
        if error:
            return error

    parts: list[str] = []
    if title:
        parts.append(f"## Title\n{title}")
    if abstract:
        parts.append(f"## Abstract\n{abstract}")

    if not parts:
        return f"Error: could not extract content for arXiv:{arxiv_id}"

    parts.append(
        "## Full Text\n"
        "_Full text unavailable — ar5iv.org did not return content for this paper. "
        "The abstract above was retrieved from the arXiv abstract page. "
        "Try again in a few hours as ar5iv may still be processing this paper._"
    )

    return "\n\n".join(parts)[:_MAX_CHARS]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch full text of an arXiv paper via ar5iv.org."
    )
    parser.add_argument(
        "paper_id",
        help="arXiv ID (e.g. 1706.03762), arXiv URL, or ar5iv URL",
    )
    args = parser.parse_args()
    print(fetch_paper(args.paper_id))


if __name__ == "__main__":
    main()
