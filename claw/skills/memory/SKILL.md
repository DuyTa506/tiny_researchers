---
name: memory
description: Two-layer memory system with grep-based recall for research sessions.
always: true
---

# Memory

## Structure

- `memory/MEMORY.md` — Long-term research facts (papers, gaps, decisions, preferences). Always loaded into your context.
- `memory/HISTORY.md` — Append-only research log. NOT loaded into context. Search it with grep or exec tool. Each entry starts with [YYYY-MM-DD HH:MM].

## Search Past Research

- Small `memory/HISTORY.md`: use `read_file`, then search in-memory
- Large history: use the `exec` tool for targeted search

Examples:
- `findstr /i "transformer" memory\HISTORY.md` (Windows)
- `grep -i "transformer" memory/HISTORY.md` (Linux/macOS)
- `python -c "from pathlib import Path; text = Path('memory/HISTORY.md').read_text(encoding='utf-8'); print('\n'.join([l for l in text.splitlines() if 'transformer' in l.lower()][-20:]))"`

## When to Update MEMORY.md

Write important research facts immediately using `write_file` or `edit_file`:
- Papers found: "Attention Is All You Need (Vaswani 2017) — introduced Transformer"
- Research gaps: "No efficient attention for multi-modal long sequences"
- Decisions: "User chose to focus on linear attention + SSM hybrid"
- Dataset sources: "WikiText-103 available on HuggingFace"
- Preferences: "User prefers PyTorch, writes in English"

## Auto-consolidation

Old conversations are automatically summarized and appended to HISTORY.md when the context grows large. Long-term facts are extracted to MEMORY.md.
