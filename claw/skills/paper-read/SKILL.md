---
name: paper-read
description: Fetch full details of a specific academic paper by its Semantic Scholar ID or arXiv ID. Use when the user wants to read, understand, or get the abstract/references of a specific paper.
---

# Paper Read

Fetch full details for a single paper from the Semantic Scholar API.

## Usage

```bash
python ${CLAUDE_SKILL_DIR}/scripts/read_paper.py "<paper_id>"
```

## Arguments

| Argument | Format | Example |
|---|---|---|
| Semantic Scholar ID | alphanumeric hash | `204e3073870fae3d05bcbc2f6a8e263d9b72e776` |
| arXiv ID | `arXiv:YYMM.NNNNN` | `arXiv:1706.03762` |

## Examples

```bash
# By Semantic Scholar ID (from paper-search results)
python ${CLAUDE_SKILL_DIR}/scripts/read_paper.py "204e3073870fae3d05bcbc2f6a8e263d9b72e776"

# By arXiv ID
python ${CLAUDE_SKILL_DIR}/scripts/read_paper.py "arXiv:1706.03762"
```

## Output

Returns: title, year, citation count, authors, arXiv/DOI identifiers, TLDR summary, full abstract, and top 10 references (with their S2 IDs for chaining).

## Workflow tip

Use `paper-search` first to get S2 IDs, then pass them to `paper-read` for deep detail:

```bash
# Step 1 — find papers
python ${CLAUDE_SKILL_DIR}/../paper-search/scripts/search_papers.py "attention is all you need"

# Step 2 — read the top result
python ${CLAUDE_SKILL_DIR}/scripts/read_paper.py "<s2_id_from_step1>"
```
