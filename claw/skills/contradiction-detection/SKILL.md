---
name: contradiction-detection
description: Scan papers for conflicting empirical claims, methodological disagreements, or opposing conclusions on the same topic. Use when writing discussion sections, evaluating conflicting results, or checking if a claim is contested before building on it.
always: false
---

# Contradiction Detection

## When to Use
- User asks "do any of these papers disagree with each other?"
- User is writing a discussion section and needs to address conflicting findings
- User wants to know if a claim they're making is contested in the literature
- User asks "why do paper A and paper B get different results on [benchmark]?"
- Before building on a result, check whether other papers contradict it

## Contradiction Types

| Type | Description | Example |
|------|-------------|---------|
| **Empirical** | Different quantitative results on same benchmark | Paper A: BLEU 42.1 vs Paper B: BLEU 31.8 on WMT14 |
| **Methodological** | Different "best practices" claimed | Paper A: dropout improves generalization; Paper B: dropout hurts large models |
| **Interpretive** | Same data, different explanations | Paper A: gains come from depth; Paper B: gains come from width |

## Workflow

### Step 1: Collect Claims
For each paper in scope:
- Use `paper-fetch` or `paper-read-pdf` to get full text
- Extract explicit quantitative results (numbers, metrics, rankings)
- Extract qualitative conclusions ("X is better than Y because...")
- Note: dataset used, evaluation protocol, model size, hyperparameters

### Step 2: Group by Topic/Benchmark
- Cluster claims that address the same research question, dataset, or benchmark
- Only compare papers evaluating the **same thing** (different datasets ≠ contradiction)

### Step 3: Identify Contradictions
For each cluster, compare claims:
- Do any papers report significantly different numbers on the same benchmark?
- Do any papers draw opposite conclusions from similar setups?
- Do any papers explicitly refute or question a finding from another?

### Step 4: Assess Severity
- **Minor discrepancy**: differences explainable by hyperparameters, compute, random seed
- **Significant disagreement**: different conclusions with similar setups — needs investigation
- **Fundamental contradiction**: one paper's results invalidate another's claims

### Step 5: Trace Causes
For each contradiction identified, check:
1. Different datasets or splits?
2. Different evaluation metrics or protocols?
3. Different model sizes or training budgets?
4. Different time periods (newer work may use better baselines)?
5. Was one paper later retracted or corrected?

## Output Format

For each contradiction pair:

```
### Contradiction: [Brief description]
- **Type**: empirical | methodological | interpretive
- **Severity**: minor | significant | fundamental
- **Paper A**: [Title (Year)] — [claim with metric/number]
- **Paper B**: [Title (Year)] — [conflicting claim]
- **Potential causes**: [dataset difference / eval protocol / compute / other]
- **Resolution**: [which paper has stronger evidence, or "unresolved — requires investigation"]
- **Action**: [cite both with hedging / investigate further / defer to stronger evidence]
```

Organize contradictions by topic cluster.

## Hedging Language for Contradictions

When writing about contested claims, use calibrated language:
- "Results are mixed: [A] report X while [B] find Y, potentially due to..."
- "Evidence is contested. [A] demonstrate X, though [B] challenge this finding..."
- "While [A] suggest X, subsequent work by [B] finds the opposite under [different conditions]"

## Save Results
- Write to `contradictions_{topic}_{date}.md`
- Update MEMORY.md with any critical contradictions that affect the research direction

## Integration Tips
- Combine with `evidence-grading` — when two papers contradict, grade which has stronger evidence
- Combine with `gap-analysis` — unresolved contradictions are research gaps worth filling
- Run after `cross-paper-synthesis` to surface tensions in the synthesized narrative
