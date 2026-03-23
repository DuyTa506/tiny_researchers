---
name: paper-fetch
description: Fetch the FULL TEXT of an arXiv paper (all sections — introduction, method, results, conclusion). Use when you need to read beyond the abstract into the paper's actual content. Only works for arXiv papers. For metadata/abstract only, use paper-read. For local PDFs, use paper-read-pdf.
always: false
---

# Paper Fetch — Full Text

Fetch the complete text of an arXiv paper using `web_fetch` via ar5iv.org (LaTeX → clean HTML),
with automatic fallback to the arXiv abstract page.

## Strategy

```
Primary:  https://ar5iv.org/abs/<arxiv_id>     — full rendered text (all sections)
Fallback: https://arxiv.org/abs/<arxiv_id>     — abstract page only
```

ar5iv renders LaTeX source to HTML, giving clean readable text including equations,
tables, and all sections. It is the best way to read arXiv papers as plain text.

## Accepted ID Formats

| Input | Example |
|-------|---------|
| Bare arXiv ID | `1706.03762` |
| arXiv ID with prefix | `arxiv:1706.03762` → strip prefix, use `1706.03762` |
| arXiv abstract URL | `https://arxiv.org/abs/1706.03762` → extract ID `1706.03762` |
| arXiv PDF URL | `https://arxiv.org/pdf/1706.03762` → extract ID `1706.03762` |
| ar5iv URL | `https://ar5iv.org/abs/1706.03762` → use as-is |

**Always normalize to bare ID before constructing URL.**

## How to Use

### Step 1 — Extract the bare arXiv ID

From whatever format you receive, extract just the numeric ID:
- `arxiv:1706.03762` → `1706.03762`
- `https://arxiv.org/abs/2303.08774v2` → `2303.08774` (drop version suffix)
- `ArXiv:2310.06825` → `2310.06825`

### Step 2 — Try ar5iv first (full text)

```
web_fetch("https://ar5iv.org/abs/1706.03762")
```

**Good response**: contains section headings like "Introduction", "Method", "Results" etc.
**Bad response / error**: ar5iv page says "not available" or returns very little text.

### Step 3 — Fallback to arXiv abstract page

If ar5iv returns insufficient content (< 500 chars of real text, or error):
```
web_fetch("https://arxiv.org/abs/1706.03762")
```

This gives title + abstract + metadata, but not full paper sections.

## What to Extract

From a successful ar5iv response, extract and present:

1. **Title** + authors + year (from page header)
2. **Abstract** — first section
3. **Introduction** — motivation and problem setup
4. **Method / Approach** — the core technical contribution
5. **Experiments / Results** — datasets, metrics, main numbers
6. **Conclusion** — summary of findings
7. **Key tables and numbers** — benchmark results if present

If the user asks for a specific section, jump straight to it.

## Examples

### Fetch "Attention Is All You Need"
```
web_fetch("https://ar5iv.org/abs/1706.03762")
```

### Fetch a recent paper
```
web_fetch("https://ar5iv.org/abs/2303.08774")
```

### Fallback if ar5iv fails
```
web_fetch("https://arxiv.org/abs/1706.03762")
```

## Notes

- ar5iv lags arXiv by a few days — very recent papers (< 3 days old) may not be available yet
- Output from web_fetch is capped at ~8000 chars; for very long papers, multiple fetches may be needed
- If the paper is not on arXiv (conference-only), try fetching the PDF URL from `openAccessPdf` field obtained via `paper-read`
- For local PDF files, use the `paper-read-pdf` skill instead

## Tip: Section-targeted fetching

If you only need a specific section (e.g., just the experimental results), fetch the full ar5iv page and scan for the relevant heading. The text is structured with clear section titles.
