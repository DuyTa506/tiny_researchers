---
name: report
description: Generate professional research reports (survey, proposal, technical).
always: false
---

# Report Generation

## When to Use
When the user asks to compile research findings into a formal report.

## Report Types

### 1. Literature Review
Sections: Introduction, Background, Taxonomy, Comparison Table, Discussion, References
Format: Academic (LaTeX-ready markdown)

### 2. Research Proposal
Sections: Abstract, Problem Statement, Related Work, Proposed Method, Timeline, References
Format: Grant-style

### 3. Technical Report
Sections: Abstract, Method, Experiments, Results, Discussion, Conclusion
Format: Technical

### 4. Executive Summary
Sections: Key Findings, Recommendations, Next Steps
Format: 1-2 pages, bullet-point heavy

## How to Write

### Step 1: Gather Material
- Read MEMORY.md for research context
- Search HISTORY.md for past findings
- Read any saved survey/gap-analysis files in workspace

### Step 2: Structure
- Choose appropriate report type
- Create outline first
- Fill sections with referenced claims

### Step 3: Quality Checks
- Every claim must cite a paper (use paper title + year)
- Tables must have consistent formatting
- Include arXiv IDs for all cited papers
- Generate BibTeX entries for references section

### Step 4: Save
- Save as `report_{type}_{topic}_{date}.md`
- For LaTeX: save as `report_{type}_{topic}_{date}.tex`

## Citation Format
Use inline citations: (Author et al., Year) or [arXiv:XXXX.XXXXX]
Include full BibTeX at the end.
