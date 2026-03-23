---
name: reproducibility-check
description: Audit a paper's reproducibility before building on its results or before submitting your own work. Checks for missing details (seeds, hyperparameters, dataset splits, hardware), code/data availability, and scores against venue-specific reproducibility standards (NeurIPS, ICML, Nature, etc.).
always: false
---

# Reproducibility Check

## When to Use
- Before deciding to build on a paper's results — can it actually be reproduced?
- Auditing your own paper before submission for reproducibility gaps
- Checking if an external paper meets reproducibility standards
- Responding to a reviewer concern about reproducibility
- Reviewing a paper and needing a structured reproducibility assessment

## Reproducibility Checklist

### Core Requirements (apply to all ML/CS papers)

**Code:**
- [ ] Source code publicly available (GitHub, Zenodo, project page)
- [ ] Code includes model definition, training script, evaluation script
- [ ] README with setup instructions
- [ ] Dependencies specified (requirements.txt, conda env, Dockerfile)
- [ ] Pretrained weights/checkpoints available (if applicable)

**Data:**
- [ ] Dataset name and version explicitly stated
- [ ] Dataset publicly available or access instructions provided
- [ ] Data splits (train/val/test) specified — or script to recreate
- [ ] Preprocessing steps documented

**Hyperparameters:**
- [ ] All hyperparameters reported (lr, batch size, epochs, optimizer, scheduler)
- [ ] Hyperparameter search method described (grid search, Bayesian, manual)
- [ ] Final hyperparameters used for reported results stated explicitly

**Randomness:**
- [ ] Random seeds reported
- [ ] Results reported over multiple seeds (with variance/std dev)
- [ ] Determinism flags set (CUBLAS_WORKSPACE_CONFIG, etc.)

**Hardware & Compute:**
- [ ] Hardware specified (GPU model, memory, number of GPUs)
- [ ] Compute budget reported (GPU-hours or equivalent)
- [ ] Approximate training time reported

**Evaluation:**
- [ ] Evaluation metrics defined precisely (not just "accuracy" — which one, on what split)
- [ ] Baselines reproduced from original papers or taken from same eval setup
- [ ] Statistical significance reported where applicable

### Venue-Specific Standards

**NeurIPS (2024+):** Mandatory reproducibility checklist required at submission.
Additional requirements: ethics statement, limitations section.

**ICML:** Paper checklist includes reproducibility items.
Additional: broader impact statement.

**ICLR:** OpenReview-style review includes reproducibility scores.

**ACL/EMNLP/NAACL:** Responsible NLP checklist.
Additional: computational budget, hyperparameter sensitivity.

**Nature/Science:** Methods section must be independently reproducible.
Additional: data deposition in domain-specific repositories.

## Workflow

### Step 1: Get the Paper
- Use `paper-fetch` for arXiv papers (gets full text including appendix)
- Use `paper-read-pdf` for local PDFs
- Use `paper-read` for metadata and abstract only (limited — prefer full text)

### Step 2: Check Code Availability
- Look for GitHub/GitLab link in paper text or footnotes
- Try `web_search` for "[paper title] github" or "[first author] [method name] code"
- Check Papers With Code: `web_fetch https://paperswithcode.com/paper/[arxiv-id]`
- Verify links are not broken (404 = link rot)

### Step 3: Check Dataset Availability
- Identify all datasets used
- Verify public availability:
  - HuggingFace Hub: `dataset-search` skill
  - Papers With Code datasets: `web_fetch https://paperswithcode.com/datasets`
  - Zenodo, UCI, official project pages
- Flag datasets that are gated, deprecated, or license-restricted

### Step 4: Read Methods for Completeness
Scan Methodology + Appendix for missing items from the checklist above.
Common gaps in ML papers:
- Seeds not reported (very common)
- Hyperparameter search not described
- Evaluation on a custom (private) test set
- Baselines taken from other papers with different compute budgets

### Step 5: Score and Report

## Output Format

```
### Reproducibility Report: [Paper Title] (Year)
- **Overall Score**: X/10
- **Code**: ✅ Available | ⚠️ Partial | ❌ Unavailable | 🔗 [link if found]
- **Data**: ✅ Available | ⚠️ Gated/restricted | ❌ Unavailable
- **Hyperparameters**: ✅ Complete | ⚠️ Partial | ❌ Missing
- **Seeds**: ✅ Reported + multi-seed | ⚠️ Single seed | ❌ Not reported
- **Hardware**: ✅ Specified | ⚠️ Vague | ❌ Not reported

#### Critical Gaps (must fix before reproducing / submitting)
- [ ] [Gap 1]: [specific fix needed, e.g., "Random seeds not reported in Section 4.2"]
- [ ] [Gap 2]: [specific fix needed]

#### Minor Gaps (good to fix)
- [ ] [Gap 3]: [e.g., "Exact dataset split proportions not stated"]

#### Reproducibility Assessment
**Can this paper be reproduced?**
- High confidence (7–10): Results likely reproducible with moderate effort
- Medium confidence (4–6): Gaps exist; may require author contact or estimation
- Low confidence (0–3): Critical information missing; reproduction very difficult

**Recommendation**: [Proceed | Proceed with caution — X is missing | Contact authors | Use alternative paper]
```

## Integration Tips
- Run before the `reproduce` skill — identify gaps before investing compute
- Combine with `evidence-grading` — low reproducibility → lower evidence grade
- Combine with `claim-tracker` — papers with poor reproducibility = contested or unverified claims
- For your own papers: run this skill BEFORE submission, not during reviewer revision
