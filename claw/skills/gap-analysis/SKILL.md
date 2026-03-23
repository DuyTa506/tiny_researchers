---
name: gap-analysis
description: Find research gaps and suggest future directions.
always: false
---

# Research Gap Analysis

## When to Use
After a survey or paper synthesis, when the user wants to find what's missing in the field.

## Strategies

### Strategy 1: Limitation Mining
- Read the "Limitations" and "Future Work" sections from key papers (use paper_read)
- Cluster common limitations across papers
- Rank by frequency and tractability

### Strategy 2: Benchmark Gap Analysis
- Search Papers With Code for SOTA results (use web_fetch on paperswithcode.com)
- Find tasks/datasets where performance plateaus or no solution exists
- Identify performance gaps between methods

### Strategy 3: Cross-Domain Transfer
- Find methods successful in domain A (e.g., NLP)
- Check if applied in domain B (e.g., computer vision) — use paper_search
- Propose transfer opportunities

### Strategy 4: Temporal Trend Analysis
- Compare paper counts by subtopic over years
- Find "cooling" areas (fewer recent papers) vs "heating" areas
- Identify emerging trends

### Strategy 5: Method Combination
- Identify papers using method X and papers using method Y
- Check if anyone combined X+Y — use paper_search
- Assess feasibility of the combination

## Output Format

For each gap found:

```
### Gap: [Title]
- Score: novelty(X) × feasibility(X) × impact(X) = [composite]
- Evidence: [which papers point to this gap]
- Strategy: [which strategy found it]
- Suggested approach: [how to tackle it]
- Required resources: [compute, data, skills needed]
- Related papers: [arXiv IDs]
```

## Save Results
- Write to `gaps_{topic}_{date}.md`
- Update MEMORY.md with top gaps
