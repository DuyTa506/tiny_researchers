---
name: survey
description: Conduct a systematic literature survey on a research topic.
always: false
---

# Literature Survey

## How to Conduct a Survey

When the user asks for a literature survey or review:

### Step 1: Define Scope
- Clarify the research topic, time range, and focus areas
- Ask user for specific keywords, conferences, or subfields if unclear

### Step 2: Search Papers (use paper_search tool)
- Search with multiple query variations (e.g., "efficient transformers", "linear attention", "sparse attention")
- Search at least 3 different query angles
- Collect 30-100 papers depending on scope

### Step 3: Read Key Papers (use paper_read tool)
- Read the top 10-15 most cited papers in detail
- Extract: title, authors, year, key contribution, method, results, limitations

### Step 4: Classify & Organize
- Group papers by methodology/approach
- Create a taxonomy (e.g., "Sparse Attention", "Linear Attention", "Kernel-based")
- Note which papers cite which (citation relationships)

### Step 5: Write the Survey
Write a structured report with:
1. **Introduction** — what is the field, why it matters
2. **Taxonomy** — classification of approaches
3. **Method Comparison Table** — columns: Paper, Method, Dataset, Key Result, Limitations
4. **Timeline** — how the field evolved
5. **Key Findings** — common themes and insights
6. **Open Questions** — what remains unsolved
7. **References** — BibTeX-ready citations

### Step 6: Save Results
- Save the survey to a markdown file in the workspace
- Update MEMORY.md with key papers and findings
- Append to HISTORY.md with summary

## Output Format

Save as `survey_{topic}_{date}.md` in the workspace.
