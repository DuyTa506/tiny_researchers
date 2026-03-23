---
name: deep-research
description: Full end-to-end deep research pipeline on a topic. Use when the user wants thorough, rigorous research — not just a survey. Orchestrates all research skills in sequence: collect → synthesize → critique claims → grade evidence → find gaps → assess reproducibility → optionally reproduce → write report.
always: false
---

# Deep Research Pipeline

## When to Use
- User asks for "deep research", "thorough analysis", or "comprehensive review"
- User wants to understand a topic well enough to build new research on it
- User wants to find the most reliable results to build on, verify claims, and identify what's truly novel
- Before starting a new research project in an area

## Overview

Deep research is a **6-phase pipeline**. Each phase uses a dedicated skill.
Read each skill's SKILL.md file before executing that phase.

```
Phase 1: COLLECT      paper-search + paper-fetch + paper-read-pdf
Phase 2: SYNTHESIZE   cross-paper-synthesis
Phase 3: CRITIQUE     contradiction-detection + claim-tracker + evidence-grading
Phase 4: GAP          gap-analysis
Phase 5: REPRODUCE?   reproducibility-check → reproduce (optional)
Phase 6: REPORT       report
```

---

## Phase 1 — Collect Papers

**Goal**: Build a corpus of 20–60 relevant papers.

1. Read the `paper-search` skill, then search with **3–5 different query angles**:
   - Core concept: `"[main topic]"`
   - Methodological: `"[main method] [application]"`
   - Recent work: `"[topic]"` with `--year-from [current_year - 2]`
   - Benchmarks: `"[topic] benchmark evaluation"`
   - Surveys: `"[topic] survey review"`

2. For the top 15–20 most cited papers:
   - Use `paper-read` skill for metadata + abstract
   - Use `paper-fetch` skill for full text of the 5–8 most important ones

3. For papers available as local PDFs:
   - Use `paper-read-pdf` skill with `--sections method results`

4. Build an initial list: title, year, venue, key contribution, S2 ID

**Output**: Paper list saved to `research_{topic}/corpus.md`

---

## Phase 2 — Synthesize

**Goal**: Understand the big picture across all collected papers.

Read the `cross-paper-synthesis` skill, then produce all three modes:

1. **Narrative synthesis** — the story of how the field evolved
2. **Comparison table** — methods / datasets / metrics / results side by side
3. **Temporal timeline** — year-by-year key advances

**Output**: `research_{topic}/synthesis.md`

---

## Phase 3 — Critique Claims

**Goal**: Identify which results are solid and which are contested.

Run all three critique skills in order:

### 3a. Contradiction Detection
Read the `contradiction-detection` skill.
- Scan corpus for conflicting empirical results on the same benchmark
- Flag methodological disagreements ("best practice" claims that conflict)
- Output: list of contradiction pairs with severity scores

### 3b. Claim Tracking
Read the `claim-tracker` skill.
Identify the **3–5 central claims** the field (or the user's research direction) relies on.
For each:
- Find the original paper
- Search for replications and challenges
- Assign status: Standing / Contested / Superseded / Refuted

### 3c. Evidence Grading
Read the `evidence-grading` skill.
For each of the 3–5 central claims:
- Assign grade: A / B+ / B / C+ / C / D
- Note: claims graded C or lower are **research opportunities** (weak evidence = gap to fill)

**Output**: `research_{topic}/critique.md`

---

## Phase 4 — Find Gaps

**Goal**: Identify what is missing, understudied, or not yet resolved.

Read the `gap-analysis` skill, then run all strategies:
1. Limitation mining (scan Future Work sections from fetched papers)
2. Benchmark gap analysis (Papers With Code)
3. Methodological monoculture detection
4. Temporal trend analysis
5. Novelty validation for any research direction the user already has in mind

**Key input from Phase 3**:
- Unresolved contradictions from Phase 3a → these ARE gaps
- Claims graded C/D from Phase 3c → weak evidence = gap to fill

**Output**: `research_{topic}/gaps.md` with top 5 gaps, each scored for novelty × feasibility × impact

---

## Phase 5 — Reproducibility & Reproduction (Optional)

**Goal**: If the user wants to build on specific results, verify they can be reproduced.

### 5a. Reproducibility Check (always do this before Phase 5b)
Read the `reproducibility-check` skill.
For the 1–3 most important papers you want to build on:
- Check code availability, dataset availability, seeds, hyperparameters
- Score 0–10
- Papers scoring < 5: consider contacting authors or using an alternative

### 5b. Reproduce (only if reproducibility score ≥ 5)
Read the `reproduce` skill.
Full 7-phase reproduction: parse paper → find resources → setup env → get dataset → generate/adapt code → run → verify

**Output**: `research_{topic}/reproducibility_report.md`, optionally `outputs/reproduction_{arxiv_id}/`

---

## Phase 6 — Write Report

**Goal**: Synthesize all findings into a comprehensive, actionable research report.

Read the `report` skill, then write a **Technical Report** with:

```markdown
# Deep Research Report: [Topic]
**Date**: [date] | **Papers analyzed**: [N] | **Depth**: Full pipeline

## Executive Summary
[3–5 bullet points: key findings, best methods, top gap, recommendation]

## 1. Field Overview
[From Phase 2 narrative synthesis]

## 2. Method Comparison
[From Phase 2 comparison table]

## 3. Timeline
[From Phase 2 temporal evolution]

## 4. Evidence Assessment
[From Phase 3: contested claims, evidence grades for key results]

## 5. Research Gaps
[From Phase 4: top 5 gaps with scores]

## 6. Recommended Starting Points
[Best-evidenced methods to build on + which gaps are most tractable]

## 7. Reproducibility Notes
[From Phase 5 if run: which papers have verified code/data]

## References
[BibTeX for all cited papers]
```

**Output**: `research_{topic}/report_{date}.md`

---

## Summary Checklist

```
Phase 1 — Collect
  [ ] 3-5 search angles run
  [ ] Top 15-20 papers read (metadata)
  [ ] Top 5-8 papers full text fetched
  [ ] corpus.md saved

Phase 2 — Synthesize
  [ ] Narrative synthesis written
  [ ] Comparison table built
  [ ] Timeline mapped
  [ ] synthesis.md saved

Phase 3 — Critique
  [ ] Contradictions scanned
  [ ] 3-5 central claims tracked
  [ ] Evidence grades assigned
  [ ] critique.md saved

Phase 4 — Gaps
  [ ] All 5 gap strategies run
  [ ] Contradiction gaps + weak-evidence gaps included
  [ ] gaps.md saved

Phase 5 — Reproducibility (optional)
  [ ] Key papers scored on reproducibility rubric
  [ ] reproduction run if score ≥ 5

Phase 6 — Report
  [ ] Full report written and saved
  [ ] MEMORY.md updated with key papers, central claims, top gaps
  [ ] HISTORY.md entry added
```

## Tips

- **Don't skip Phase 3** — the most common mistake is building on a C-grade claim
- **Unresolved contradictions from Phase 3a feed directly into Phase 4** — they are gaps
- **Save intermediate outputs** (corpus.md, synthesis.md, critique.md, gaps.md) — the agent can resume from any phase if the conversation is interrupted
- For very large topics (>100 papers), narrow the scope in Phase 1 first, then run the full pipeline on a focused subtopic
