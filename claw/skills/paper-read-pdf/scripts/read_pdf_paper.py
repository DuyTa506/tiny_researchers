#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract and structure text from a local research paper PDF.

Usage:
    python read_pdf_paper.py <pdf_path> [--sections SECTION ...] [--pages N-M]

Examples:
    python read_pdf_paper.py paper.pdf
    python read_pdf_paper.py paper.pdf --sections abstract method results
    python read_pdf_paper.py paper.pdf --pages 1-8
    python read_pdf_paper.py paper.pdf --sections conclusion references

Requires (one of):
    pip install pymupdf        # preferred — better multi-column handling
    pip install pypdf           # fallback
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_MAX_CHARS = 80_000

# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

# Maps canonical section names → regex patterns that match common headings
_SECTION_PATTERNS: dict[str, list[str]] = {
    "abstract": [
        r"^abstract$",
    ],
    "introduction": [
        r"^introduction$",
        r"^motivation$",
        r"^overview$",
        r"^\d[\d.]* +introduction",
        r"^\d[\d.]* +motivation",
    ],
    "related": [
        r"^related work",
        r"^related works",
        r"^background",
        r"^prior work",
        r"^literature review",
        r"^\d[\d.]* +related",
        r"^\d[\d.]* +background",
    ],
    "method": [
        r"^method(?:ology)?$",
        r"^approach$",
        r"^model$",
        r"^architecture$",
        r"^framework$",
        r"^proposed method",
        r"^our method",
        r"^our approach",
        r"^\d[\d.]* +method",
        r"^\d[\d.]* +approach",
        r"^\d[\d.]* +model",
        r"^\d[\d.]* +architecture",
        r"^\d[\d.]* +framework",
    ],
    "experiments": [
        r"^experiment",
        r"^experimental setup",
        r"^experimental results",
        r"^evaluation",
        r"^benchmark",
        r"^empirical",
        r"^\d[\d.]* +experiment",
        r"^\d[\d.]* +evaluation",
    ],
    "results": [
        r"^results?$",
        r"^analysis$",
        r"^discussion$",
        r"^findings$",
        r"^quantitative",
        r"^qualitative",
        r"^\d[\d.]* +results?",
        r"^\d[\d.]* +analysis",
        r"^\d[\d.]* +discussion",
    ],
    "conclusion": [
        r"^conclusion",
        r"^summary$",
        r"^future work",
        r"^limitations",
        r"^concluding remarks",
        r"^\d[\d.]* +conclusion",
        r"^\d[\d.]* +summary",
        r"^\d[\d.]* +limitation",
    ],
    "references": [
        r"^references?$",
        r"^bibliography$",
    ],
}


def _classify_heading(line: str) -> str | None:
    """Return section canonical name if line looks like a section heading, else None."""
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return None
    normalized = stripped.lower()
    for section, patterns in _SECTION_PATTERNS.items():
        for pat in patterns:
            if re.match(pat, normalized):
                return section
    return None


def _is_heading_like(line: str) -> bool:
    """Heuristic: short line, mostly title-case or uppercase, not ending with period."""
    s = line.strip()
    if not s or len(s) > 100 or s.endswith('.'):
        return False
    words = s.split()
    if len(words) > 12:
        return False
    # Must be mostly title-case or all-caps
    cap_words = sum(1 for w in words if w and (w[0].isupper() or w.isupper()))
    return cap_words / len(words) >= 0.6


# ---------------------------------------------------------------------------
# PDF extraction — pymupdf primary, pypdf fallback
# ---------------------------------------------------------------------------

def _extract_with_pymupdf(pdf_path: str, page_range: tuple[int, int] | None) -> tuple[list[str], int]:
    """Extract text per-page using pymupdf (fitz). Returns (pages_text, total_pages)."""
    import fitz  # pymupdf

    doc = fitz.open(pdf_path)
    total = len(doc)
    start, end = (0, total) if page_range is None else (page_range[0] - 1, page_range[1])
    pages_text: list[str] = []
    for i in range(start, min(end, total)):
        page = doc[i]
        # sort=True preserves reading order (important for multi-column papers)
        text = page.get_text("text", sort=True)
        pages_text.append(text)
    doc.close()
    return pages_text, total


def _extract_with_pypdf(pdf_path: str, page_range: tuple[int, int] | None) -> tuple[list[str], int]:
    """Extract text per-page using pypdf. Returns (pages_text, total_pages)."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    total = len(reader.pages)
    start, end = (0, total) if page_range is None else (page_range[0] - 1, page_range[1])
    pages_text: list[str] = []
    for i in range(start, min(end, total)):
        text = reader.pages[i].extract_text() or ""
        pages_text.append(text)
    return pages_text, total


def _extract_text(pdf_path: str, page_range: tuple[int, int] | None) -> tuple[list[str], int, str]:
    """Try pymupdf → pypdf → error. Returns (pages_text, total_pages, library_used)."""
    try:
        pages, total = _extract_with_pymupdf(pdf_path, page_range)
        return pages, total, "pymupdf"
    except ImportError:
        pass

    try:
        pages, total = _extract_with_pypdf(pdf_path, page_range)
        return pages, total, "pypdf"
    except ImportError:
        pass

    print(
        "Error: no PDF library found.\n"
        "Install one of:\n"
        "  uv pip install -e '.[pdf]'   # installs pymupdf\n"
        "  uv pip install pypdf          # lightweight fallback",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------

def _split_into_sections(pages_text: list[str]) -> dict[str, str]:
    """
    Walk all text lines and group into detected sections.
    Lines before the first recognized heading go into 'preamble'.
    """
    full_text = "\n".join(pages_text)
    lines = full_text.splitlines()

    sections: dict[str, list[str]] = {"preamble": []}
    current_section = "preamble"
    current_canonical: str | None = None

    for line in lines:
        canonical = _classify_heading(line)
        if canonical:
            # Start a new section bucket; deduplicate (e.g. two "results" blocks → append)
            if canonical in sections:
                key = f"{canonical}_2" if f"{canonical}_2" not in sections else f"{canonical}_3"
            else:
                key = canonical
            sections[key] = [line]
            current_section = key
            current_canonical = canonical
        else:
            sections[current_section].append(line)

    # Clean up: join lines, strip excessive blank lines
    cleaned: dict[str, str] = {}
    for name, lines_list in sections.items():
        text = "\n".join(lines_list)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        if text:
            cleaned[name] = text

    return cleaned


def _filter_sections(sections: dict[str, str], wanted: list[str]) -> dict[str, str]:
    """Keep only sections whose canonical name is in `wanted`."""
    result: dict[str, str] = {}
    for key, text in sections.items():
        # key may be "results" or "results_2" — match the base name
        base = re.sub(r'_\d+$', '', key)
        if base in wanted:
            result[key] = text
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _parse_page_range(s: str) -> tuple[int, int]:
    """Parse '1-5' or '3' → (start, end) 1-indexed inclusive."""
    s = s.strip()
    if '-' in s:
        parts = s.split('-', 1)
        return int(parts[0]), int(parts[1])
    n = int(s)
    return n, n


def read_pdf_paper(
    pdf_path: str,
    sections_filter: list[str] | None = None,
    page_range: tuple[int, int] | None = None,
) -> str:
    path = Path(pdf_path)
    if not path.exists():
        return f"Error: file not found — {pdf_path}"
    if path.suffix.lower() != ".pdf":
        return f"Error: expected a .pdf file, got {path.suffix}"

    pages_text, total_pages, library = _extract_text(str(path), page_range)

    if not any(p.strip() for p in pages_text):
        return (
            f"Error: no text extracted from '{path.name}'. "
            "This may be a scanned (image-only) PDF. "
            "Try an OCR tool (e.g. ocrmypdf) to add a text layer first."
        )

    page_info = f"pages {page_range[0]}–{page_range[1]}" if page_range else f"all {total_pages} pages"
    header = (
        f"## File: {path.name}\n"
        f"**Total pages:** {total_pages} | **Extracted:** {page_info} | **Library:** {library}\n"
    )

    sections = _split_into_sections(pages_text)
    has_sections = any(k != "preamble" for k in sections)

    if sections_filter:
        wanted = [s.lower() for s in sections_filter]
        filtered = _filter_sections(sections, wanted)
        if not filtered:
            # Fall back to raw output with a note
            raw = "\n\n".join(pages_text)
            return (
                f"{header}\n"
                f"_No sections matching {wanted} were auto-detected in this PDF. "
                f"Showing raw extracted text:_\n\n{raw}"
            )[:_MAX_CHARS]
        body_parts = [f"### [{name.upper()}]\n{text}" for name, text in filtered.items()]
    elif has_sections:
        body_parts = [f"### [{name.upper()}]\n{text}" for name, text in sections.items()
                      if name != "preamble" or sections.get("preamble", "").strip()]
    else:
        # No sections detected — return raw page-by-page text
        body_parts = [f"### [PAGE {i + 1}]\n{t}" for i, t in enumerate(pages_text) if t.strip()]

    body = "\n\n---\n\n".join(body_parts)
    return f"{header}\n{body}"[:_MAX_CHARS]


def main() -> None:
    # Force UTF-8 output on Windows terminals
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Extract and structure text from a research paper PDF."
    )
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument(
        "--sections", nargs="+", metavar="SECTION",
        help="Sections to extract: abstract introduction related method experiments results conclusion references",
    )
    parser.add_argument(
        "--pages", metavar="N-M",
        help="Page range to read, e.g. '1-10' or '5' (1-indexed)",
    )
    args = parser.parse_args()

    page_range = _parse_page_range(args.pages) if args.pages else None
    result = read_pdf_paper(args.pdf_path, sections_filter=args.sections, page_range=page_range)
    print(result)


if __name__ == "__main__":
    main()
