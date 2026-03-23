---
name: cross-paper-synthesis
description: Synthesize findings across multiple papers into a coherent narrative, structured comparison table, or temporal evolution. Use after collecting papers via survey or paper-search. Goes beyond summarizing individual papers to produce insights that only emerge when reading across the corpus as a whole.
always: false
---

# Cross-Paper Synthesis

## When to Use
- User asks "what's the big picture across all these papers?"
- User wants a related work section that actually synthesizes, not just lists papers
- User asks "how has the field's understanding of X evolved over time?"
- User wants to compare methodological approaches across papers
- User needs a structured comparison table of models/methods/results

## Synthesis Modes

Choose the mode that best fits the user's goal:

### Mode 1: Narrative Synthesis
Best for: related work sections, overview documents, explaining field evolution
- Identify the "through line" — the core insight that unifies disparate work
- Structure as: **what we knew** → **what changed** → **what it means**
- Write prose with inline citations `(Author et al., Year)`
- Highlight key turning points (papers that shifted the field)

### Mode 2: Structured Comparison Table
Best for: method comparison, benchmark results, dataset overview
- Define dimensions to compare (e.g., model, dataset, metric, result, year, venue)
- Build Markdown table with one row per paper
- Flag missing data with `—`
- Add a "Key Insight" column summarizing each paper's main contribution

```markdown
| Paper | Method | Dataset | Metric | Score | Key Insight |
|-------|--------|---------|--------|-------|-------------|
| Author et al. (Year) | ... | ... | ... | ... | ... |
```

### Mode 3: Temporal Evolution
Best for: showing how a field progressed year by year
- Group papers by year or phase (e.g., "Pre-2020 foundations", "2020–2022 scaling era", "2023+ efficiency focus")
- Identify what changed between phases
- Show which papers started each phase

### Mode 4: Cross-Domain Synthesis
Best for: connecting insights from different research areas
- Identify conceptual parallels between fields
- Note which techniques transferred successfully
- Flag potential transfers not yet attempted (this surfaces gaps)

## Workflow

### Step 1: Collect Papers
Use `paper-search` or read from MEMORY.md to get a paper set (10–50 papers is ideal).
For papers needing deep understanding, use `paper-fetch` or `paper-read-pdf` for full text.

### Step 2: Extract Per-Paper Information
For each paper, extract:
- Core claim/contribution
- Method summary
- Datasets used + metrics reported
- Stated limitations
- Year and venue

### Step 3: Synthesize
Apply chosen mode. Look for:
- **Consensus points** — what most papers agree on
- **Contested claims** — where papers disagree (hand off to `contradiction-detection`)
- **Evolution** — how approaches changed over time
- **Patterns** — recurring themes, methods, or failure modes

### Step 4: Write Output
- Narrative: prose with citations, ~500–1000 words
- Table: Markdown table, one row per paper
- Timeline: year-by-year with key papers anchoring each phase

### Step 5: Save
- Save to `synthesis_{topic}_{date}.md`
- Update MEMORY.md with key synthesis insights

## Notes
- Best results with 10–50 papers; >100 may require narrowing the topic first
- Always review AI-generated synthesis before including in manuscripts — factual errors possible
- Combine with `contradiction-detection` to surface and address conflicting findings
- Combine with `evidence-grading` to distinguish what's established vs. speculative
