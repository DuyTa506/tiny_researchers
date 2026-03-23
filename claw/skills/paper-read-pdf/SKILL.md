---
name: paper-read-pdf
description: Read and extract text from a local research paper PDF file. Use when the user has a PDF file on disk (e.g. downloaded from a conference or journal) and wants to read its content, extract specific sections (abstract, methodology, results, conclusion), or understand the paper's structure. Requires the [pdf] optional dependency group.
---

# Paper Read PDF — Local PDF Deep Reader

Extract and structure the full text of a research paper from a local PDF file.
Detects standard academic sections automatically.

## Usage

```bash
python ${CLAUDE_SKILL_DIR}/scripts/read_pdf_paper.py "<path/to/paper.pdf>" [--sections SECTION ...] [--pages N-M]
```

## Arguments

| Argument | Required | Description |
|---|---|---|
| `<pdf_path>` | ✅ | Absolute or relative path to the PDF file |
| `--sections` | ❌ | One or more section names to extract (see below). Default: all |
| `--pages N-M` | ❌ | Page range, e.g. `1-5` or `3` (1-indexed). Default: all pages |

## Section names (--sections filter)

| Name | Matches headings like… |
|---|---|
| `abstract` | Abstract |
| `introduction` | Introduction, Motivation, Overview |
| `related` | Related Work, Background, Prior Work, Literature Review |
| `method` | Method, Methodology, Approach, Model, Architecture, Framework, Proposed |
| `experiments` | Experiments, Experimental Setup, Evaluation, Benchmark |
| `results` | Results, Analysis, Discussion, Findings |
| `conclusion` | Conclusion, Summary, Future Work, Limitations |
| `references` | References, Bibliography |

## Examples

```bash
# Extract the full paper
python ${CLAUDE_SKILL_DIR}/scripts/read_pdf_paper.py "/downloads/attention_is_all_you_need.pdf"

# Extract only the methodology and results
python ${CLAUDE_SKILL_DIR}/scripts/read_pdf_paper.py "paper.pdf" --sections method results

# Read only the first 5 pages
python ${CLAUDE_SKILL_DIR}/scripts/read_pdf_paper.py "paper.pdf" --pages 1-5

# Get just the abstract and conclusion
python ${CLAUDE_SKILL_DIR}/scripts/read_pdf_paper.py "paper.pdf" --sections abstract conclusion
```

## Output

Returns structured markdown with:
- **File info** — filename, total pages, library used
- **Detected sections** — each section as a labeled block
- If no sections detected, returns raw text per page

## Requirements

Install the `[pdf]` optional group:
```bash
uv pip install -e ".[pdf]"
# installs: pymupdf (primary), pypdf (fallback)
```

The script tries **pymupdf** (fitz) first — better for multi-column layouts common in
conference papers (NeurIPS, ICML, ACL, CVPR). Falls back to **pypdf** if not installed.

## Notes

- Works with any research PDF — arXiv downloads, conference papers, journal articles
- For arXiv papers where you only have the ID (not a local file), use `paper-fetch` instead
- Very large PDFs (100+ pages) are capped at 80 000 characters
- Scanned PDFs (image-only) cannot be extracted — text must be embedded
