---
name: gap-analysis
description: Find research gaps and suggest future directions. Analyzes a literature corpus to identify what has NOT been studied, contested, or resolved — surfacing research gaps, contradictions left unaddressed, and methodological blind spots.
always: false
---

# Research Gap Analysis

## When to Use
- After a survey or paper synthesis, when the user wants to find what's missing in the field
- User asks "what hasn't been done yet in this area?"
- User is preparing a manuscript introduction or grant significance section
- User asks "where are the open questions in [topic]?"
- User wants to position a new project in the existing literature landscape
- Lab wants to avoid duplicating work already done elsewhere

## Strategies

### Strategy 1: Limitation Mining (Highest Signal)
- Fetch full text of key papers using `paper-fetch` skill
- Scan explicitly stated **Limitations** and **Future Work** sections
- Cluster common limitations across papers (unstudied conditions, populations, datasets, modalities)
- Rank by frequency (many papers mention) and tractability (solvable with available resources)
- Cross-reference claimed gaps against recent work via `paper-search` — verify the gap is still open

### Strategy 2: Benchmark Gap Analysis
- Search Papers With Code for SOTA results (use web_fetch on paperswithcode.com)
- Find tasks/datasets where performance plateaus or no solution exists
- Identify performance gaps between methods
- Look for datasets/tasks that exist but have few papers (low competition)

### Strategy 3: Methodological Monoculture Detection
- Identify if most papers use the same dataset, benchmark, or architectural pattern
- Ask: what happens if we change the dataset? the modality? the evaluation metric?
- Cross-domain transfer: find methods successful in domain A (e.g., NLP) not yet applied to domain B (e.g., genomics)
- Check feasibility of transfer via `paper-search`

### Strategy 4: Temporal Trend Analysis
- Compare paper counts by subtopic over years using `paper-search` with `--year-from`
- Find "cooling" areas (fewer recent papers) vs "heating" areas (accelerating interest)
- Identify emerging trends that haven't yet been well-studied
- Note: a "cooling" area may indicate saturation OR an opportunity if other fields have advanced

### Strategy 5: Method Combination
- Identify papers using method X and papers using method Y
- Check if anyone combined X+Y — use `paper-search`
- Assess feasibility, prerequisites, and likely impact

### Strategy 6: Novelty Validation
- When user proposes a research direction, verify it is genuinely novel
- Search variations: different keywords, synonyms, related formulations
- Check arXiv recent submissions (last 6–12 months) for near-duplicates
- Report confidence in novelty: High / Medium / Low with supporting evidence

## Output Format

For each gap found:

```
### Gap: [Title]
- Type: empirical | theoretical | applied | methodological
- Score: novelty(1-5) × feasibility(1-5) × impact(1-5) = [composite]
- Evidence: [paper excerpts or findings pointing to this gap]
- Strategy: [which strategy found it]
- Suggested approach: [how to tackle it]
- Required resources: [compute, data, skills needed]
- Related papers: [arXiv IDs]
- Novelty confidence: High / Medium / Low
```

Organize output as a **gap map** with sections:
1. **Empirical gaps** — unstudied conditions, datasets, populations
2. **Theoretical gaps** — missing formal explanations or proofs
3. **Applied gaps** — real-world applications not yet explored
4. **Methodological blind spots** — everyone uses the same approach

## Save Results
- Write to `gaps_{topic}_{date}.md`
- Update MEMORY.md with top 3–5 gaps and their novelty scores

## Integration Tips
- Combine with `contradiction-detection` skill — contradictions that remain unresolved ARE gaps
- Combine with `evidence-grading` skill — weak evidence areas signal gaps worth filling
- Run `survey` first to build the corpus, then run this skill on the results
