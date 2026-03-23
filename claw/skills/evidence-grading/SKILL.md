---
name: evidence-grading
description: Evaluate the strength of evidence behind scientific claims based on study design, replication status, venue quality, sample size, and recency. Use when deciding how much weight to put on a finding, or when calibrating how confidently to write about a result.
always: false
---

# Evidence Grading

## When to Use
- User asks "how strong is the evidence for [claim]?"
- Before building on a published result — assess how solid the foundation is
- Deciding between citing a claim as "established" vs. "promising" vs. "preliminary"
- Ranking a set of papers by evidentiary weight
- When two papers contradict each other — which has stronger evidence?

## Grading Factors

Evidence is evaluated across 5 dimensions:

| Dimension | Strong | Weak |
|-----------|--------|------|
| **Study design** | Controlled experiment, ablations, comparisons | Single-condition, no ablations |
| **Replication** | Replicated by independent groups | Single study, preprint only |
| **Sample/scale** | Large dataset, multiple seeds, statistical tests | Small dataset, single seed |
| **Venue** | Top-tier venue (NeurIPS/ICML/Nature/Science) | Workshop / preprint / self-published |
| **Recency** | Recent (last 2 years) | Older work that may have been superseded |

## Grade Schema

### For ML/CS Research:

| Grade | Label | Criteria |
|-------|-------|----------|
| **A** | Established | Multiple top-venue replications; widely accepted; in textbooks |
| **B+** | Strong | Published top venue + ≥1 independent replication |
| **B** | Good | Top-venue paper, solid methodology, not yet replicated independently |
| **C+** | Moderate | Smaller venue or preprint + single replication |
| **C** | Preliminary | Single top-venue paper, no independent replication |
| **D** | Weak | Workshop paper, preprint, limited evaluation |
| **F** | Insufficient | Single experiment, no baselines, no ablations |

### Hedging Language by Grade:

| Grade | Suggested language |
|-------|--------------------|
| A | "It is established that..." / "[Method] has been shown to..." |
| B+ | "[Method] consistently demonstrates..." |
| B | "[Paper] shows that... (though independent replication is limited)" |
| C+ | "[Paper] suggests that... with moderate evidence" |
| C | "[Paper] provides preliminary evidence that..." |
| D | "[Paper] reports that... (preliminary; requires replication)" |
| F | Avoid citing as evidence; mention only for context |

## Workflow

### Step 1: Identify the Claim and Source Paper
- State the specific claim being evaluated
- Use `paper-read` to get: venue, year, citation count
- Note citation count as a rough proxy (highly cited = more scrutiny + replication)

### Step 2: Assess Study Design Quality
Read methodology (via `paper-fetch` or `paper-read-pdf`):
- Were multiple baselines included?
- Were ablation studies conducted?
- Were multiple random seeds used?
- Were results statistically significant (error bars, p-values)?
- Were results on standard benchmarks or custom/cherry-picked?

### Step 3: Check Replication Status
Use `paper-search` and `claim-tracker`:
- Has the result been replicated by independent groups?
- Have surveys/meta-analyses included this finding?
- Has anyone failed to replicate it?

### Step 4: Check Venue and Recency
- Venue tier: NeurIPS/ICML/ICLR/ACL/CVPR/NeurIPS (A*) > AAAI/EMNLP/ECCV (A) > arXiv preprint
- Recency: older results may be superseded by newer work — verify with `paper-search --year-from [year]`

### Step 5: Assign Grade and Write Summary

## Output Format

```
### Evidence Grade: [Claim]
- **Grade**: [A / B+ / B / C+ / C / D / F]
- **Source**: [Paper title] ([Year], [Venue])
- **Replication**: [Independent replications: N | Not yet replicated]
- **Study design**: [Controlled with ablations | Limited baselines | Single condition]
- **Scale**: [Large-scale, multi-seed | Small-scale, single seed]
- **Recency**: [Current | Potentially outdated — see [newer paper]]
- **Rationale**: [2–3 sentence explanation of the grade]
- **Recommended citation language**: "[Suggested phrasing]"
- **Caution**: [Any specific caveats about using this evidence]
```

## Save Results
- Include evidence grades inline in survey or gap-analysis documents
- Update MEMORY.md when a key result is graded, especially if lower than expected (C or below)

## Integration Tips
- Combine with `claim-tracker` — verify claim status first, then grade evidence strength
- Combine with `contradiction-detection` — contradicted claims automatically receive a grade penalty (max B-)
- Run before `reproduce` skill — prioritize reproducing B or lower results that are being relied upon
- Low-grade evidence (C/D) on a central assumption = a **research opportunity** (gap to fill)
