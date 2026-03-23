---
name: paper-fetch
description: Fetch the FULL TEXT of an arXiv paper (all sections, not just abstract). Use when the user wants to deeply read a paper's methodology, results, or any specific section. Accepts arXiv IDs, arXiv URLs, or ar5iv URLs. For metadata-only (abstract, citations), use paper-read instead.
---

# Paper Fetch — Full Text

Fetch the complete text of an arXiv paper via ar5iv.org (rendered LaTeX → clean HTML),
with automatic fallback to the arXiv abstract page if ar5iv is unavailable.

## Usage

```bash
python ${CLAUDE_SKILL_DIR}/scripts/fetch_paper.py "<paper_id>"
```

## Accepted input formats

| Format | Example |
|---|---|
| Bare arXiv ID | `1706.03762` |
| arXiv ID with prefix | `arxiv:1706.03762` |
| arXiv abstract URL | `https://arxiv.org/abs/1706.03762` |
| arXiv PDF URL | `https://arxiv.org/pdf/1706.03762` |
| ar5iv URL | `https://ar5iv.org/abs/1706.03762` |

## Examples

```bash
# Fetch "Attention Is All You Need"
python ${CLAUDE_SKILL_DIR}/scripts/fetch_paper.py "1706.03762"

# From a full URL
python ${CLAUDE_SKILL_DIR}/scripts/fetch_paper.py "https://arxiv.org/abs/2303.08774"
```

## Output

Returns structured text with:
- **Source** — ar5iv.org (full rendered text) or arXiv fallback (abstract only)
- **Full Text** — all sections as plain text, up to 50 000 characters

## How it works

1. **Primary:** fetches `https://ar5iv.org/abs/<id>` — ar5iv renders LaTeX to HTML, giving clean full text including equations (as text), tables, and all sections
2. **Fallback:** if ar5iv fails, fetches `https://arxiv.org/abs/<id>` to get at least the title and abstract

## Notes

- Only works for arXiv papers. For local PDF files, use the `paper-read-pdf` skill instead.
- ar5iv may not have very recent papers (usually available within a few days of arXiv submission)
- Output is capped at 50 000 characters; very long papers may be truncated
