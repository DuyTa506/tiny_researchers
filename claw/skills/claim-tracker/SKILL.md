---
name: claim-tracker
description: Track specific scientific claims across the literature over time — who made it, who replicated it, who challenged it, whether it still stands. Use when verifying a key assumption before building on it, or when checking whether a published result has been updated or superseded.
always: false
---

# Claim Tracker

## When to Use
- User wants to verify a specific claim before building research on it
- User asks "has anyone replicated [finding] from [paper]?"
- User needs to know if a result has been updated, corrected, or superseded
- User is writing a paper and needs the full citation chain for a key premise
- Before including a claim in a manuscript, verify it hasn't been challenged

## Core Concept

A **tracked claim** has a lifecycle:
```
Original paper → Replication studies → Challenges/Contradictions → Resolution
```

Track this lifecycle before citing a claim as established fact.

## Workflow

### Step 1: Define the Claim Precisely
State the claim exactly as it appears (or should appear) in your work:
- Be specific: include metric, dataset, model if quantitative
- Bad: "Transformers are better than RNNs"
- Good: "Transformers outperform LSTMs on WMT14 En-De by >2 BLEU with comparable parameters"

### Step 2: Find the Source Paper
- Use `paper-search` to find the original paper
- Use `paper-read` to get full metadata, citation count, and S2 ID
- Note: year, venue, citation count (proxy for influence)

### Step 3: Search for Follow-up Work
Search for papers that:
- **Replicated** the result: `paper-search` with "[claim keywords] replication" or "[method] follow-up"
- **Extended** the result: `paper-search` with "[method] + [new domain/scale]"
- **Challenged** the result: `paper-search` with "[method] limitations" or "beyond [method]"
- **Reviewed** the result: `paper-search` with "[topic] survey" — look for survey conclusions

Also use `web_fetch` on:
- `https://api.semanticscholar.org/graph/v1/paper/{s2_id}/citations` — who cites it
- `https://paperswithcode.com/` — is the result a SOTA benchmark entry?

### Step 4: Check for Retractions
- Use `web_search` for "[paper title] retraction" or "[paper title] correction"
- Check CrossRef: `web_fetch https://api.crossref.org/works/{doi}`
- If preprint: check whether the published version differs significantly

### Step 5: Assess Current Status
| Status | Criteria |
|--------|----------|
| **Standing** | No significant challenges; replicated by ≥1 independent group |
| **Qualified** | Holds under specific conditions, not universally |
| **Contested** | Mixed replication; significant challenges exist |
| **Superseded** | Newer work shows it was a limited result |
| **Refuted** | Strong evidence that the original claim is incorrect |
| **Retracted** | Paper formally retracted |

## Output Format

```
### Claim: [Precise claim statement]
- **Source**: [Paper title] ([Year]) — [arXiv ID or DOI]
- **Venue**: [Venue name and tier]
- **Citation count**: [N] (as of [date])
- **Status**: Standing | Qualified | Contested | Superseded | Refuted | Retracted
- **Replication**: [Replicated by X groups | Not yet independently replicated | Contradicted by Y]
- **Evidence chain**:
  - [Paper 1]: [what it found / how it relates]
  - [Paper 2]: [what it found / how it relates]
- **Safe to cite as**: [established fact | qualified claim | preliminary finding | contested claim]
- **Recommended hedging**: "[Suggested citation phrasing]"
```

## Citing Based on Status

| Status | How to cite |
|--------|-------------|
| Standing | Direct citation, no hedging needed |
| Qualified | "Under [conditions], [claim] (Author, Year)" |
| Contested | "Results are mixed: [A] report X while [B] find Y" |
| Superseded | Cite newer work, mention original for context |
| Refuted | Do NOT use as evidence; if relevant, cite with "despite earlier claims..." |

## Save Results
- Save claim records to `claims_{topic}_{date}.md`
- Update MEMORY.md when a key claim's status is confirmed or challenged

## Integration Tips
- Combine with `evidence-grading` to assess how strong the original evidence was
- Combine with `contradiction-detection` to systematically find all contested claims in a corpus
- Critical path: `paper-search` → `claim-tracker` → build on Standing/Qualified claims only
