---
name: survey
description: Conduct a systematic literature survey on a research topic. Collects papers, reads key works, synthesizes findings, detects contradictions, identifies gaps, and produces a structured report.
always: false
---

# Literature Survey

## How to Conduct a Survey

When the user asks for a literature survey or review:

### Step 1: Define Scope
- Clarify the research topic, time range, and focus areas
- Ask user for specific keywords, conferences, or subfields if unclear

### Step 2: Search Papers (paper-search skill)
- Search with multiple query variations (e.g., "efficient transformers", "linear attention", "sparse attention")
- Search at least 3 different query angles
- Collect 30-100 papers depending on scope

### Step 3: Read Key Papers (paper-read skill)
- Read the top 10-15 most cited papers in detail
- Use `paper-fetch` skill to get full text of the most important papers
- Extract: title, authors, year, key contribution, method, results, limitations

### Step 4: Classify & Organize
- Group papers by methodology/approach
- Create a taxonomy (e.g., "Sparse Attention", "Linear Attention", "Kernel-based")
- Note which papers cite which (citation relationships)

### Step 5: Synthesize Across Papers (cross-paper-synthesis skill)
After collecting and reading papers, synthesize findings:
- Read the `cross-paper-synthesis` skill for detailed instructions
- Produce: narrative overview + structured comparison table + temporal evolution
- Identify the "through line" — core insight unifying the field

### Step 6: Detect Contradictions (contradiction-detection skill)
Before concluding, check for conflicting results:
- Read the `contradiction-detection` skill for detailed instructions
- Flag any papers with conflicting results on the same benchmark or task
- Include a "Contested Claims" section in the final survey if contradictions exist

### Step 7: Grade Key Evidence (evidence-grading skill) — optional but recommended
For the 3-5 most important claims the survey will build on:
- Read the `evidence-grading` skill for detailed instructions
- Grade each claim A/B+/B/C+/C/D
- Use calibrated hedging language in the survey text

### Step 8: Identify Research Gaps (gap-analysis skill)
- Read the `gap-analysis` skill for detailed instructions
- Mine limitations and future work sections from key papers
- Cross-reference claimed gaps against recent work to confirm they are still open
- Summarize top 3-5 actionable gaps

### Step 9: Write the Survey
Write a structured report with:
1. **Introduction** — what is the field, why it matters
2. **Taxonomy** — classification of approaches
3. **Method Comparison Table** — columns: Paper, Method, Dataset, Key Result, Limitations
4. **Timeline** — how the field evolved (from cross-paper-synthesis)
5. **Key Findings** — common themes and insights
6. **Contested Claims** — contradictions found (from contradiction-detection)
7. **Open Questions / Gaps** — what remains unsolved (from gap-analysis)
8. **References** — BibTeX-ready citations

### Step 10: Save Results
- Save the survey to a markdown file in the workspace: `survey_{topic}_{date}.md`
- Update MEMORY.md with key papers, findings, and top gaps
- Append to HISTORY.md with summary

## Quick vs. Deep Survey

| Mode | Steps | When to use |
|------|-------|-------------|
| **Quick** (Steps 1–4, 9–10) | Search + read + write | User wants fast overview, 10-20 papers |
| **Standard** (Steps 1–6, 9–10) | + synthesis + contradictions | Default for most surveys, 20-50 papers |
| **Deep** | All steps | User explicitly asks for thorough analysis; use `deep-research` skill instead |

## Output Format

Save as `survey_{topic}_{date}.md` in the workspace.
