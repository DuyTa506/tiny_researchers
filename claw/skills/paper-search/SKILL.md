---
name: paper-search
description: Search for academic papers by keyword using Semantic Scholar. Use when the user asks to find, discover, or look up research papers on a topic. Supports filtering by year.
---

# Paper Search

Search academic papers via the Semantic Scholar API.

## Usage

```bash
python ${CLAUDE_SKILL_DIR}/scripts/search_papers.py "<query>" [--max <N>] [--year-from <YYYY>]
```

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `<query>` | ✅ | — | Search keywords (e.g. `"transformer attention"`) |
| `--max N` | ❌ | 10 | Number of results to return (1–100) |
| `--year-from YYYY` | ❌ | — | Only papers published from this year onwards |

## Examples

```bash
# Basic search
python ${CLAUDE_SKILL_DIR}/scripts/search_papers.py "vision transformer image classification"

# Limit results and filter by year
python ${CLAUDE_SKILL_DIR}/scripts/search_papers.py "diffusion models" --max 20 --year-from 2022
```

## Output

Each result includes: title, year, authors, citation count, Semantic Scholar ID, arXiv ID (if available), and URL.

## Notes

- Results are sorted by relevance (Semantic Scholar default)
- The S2 ID returned can be passed directly to the `paper-read` skill
- `SEMANTIC_SCHOLAR_API_KEY` env var is optional but increases rate limits
