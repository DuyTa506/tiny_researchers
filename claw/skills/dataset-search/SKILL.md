---
name: dataset-search
description: Search HuggingFace Hub for datasets by keyword. Use when the user wants to find training data, benchmarks, or evaluation datasets for ML/NLP/CV research.
---

# Dataset Search

Search for datasets on HuggingFace Hub, sorted by download count.

## Usage

```bash
python ${CLAUDE_SKILL_DIR}/scripts/search_datasets.py "<query>" [--max <N>]
```

## Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `<query>` | ✅ | — | Search keywords (e.g. `"sentiment analysis"`) |
| `--max N` | ❌ | 5 | Number of results to return (1–50) |

## Examples

```bash
# Find sentiment datasets
python ${CLAUDE_SKILL_DIR}/scripts/search_datasets.py "sentiment analysis"

# Find more image classification datasets
python ${CLAUDE_SKILL_DIR}/scripts/search_datasets.py "image classification" --max 15
```

## Output

Each result includes: dataset ID, download count, likes, tags, and description snippet.

## Notes

- Results sorted by download count (most popular first)
- The dataset ID (e.g. `stanfordnlp/sst2`) can be used directly with HuggingFace `datasets` library:
  ```python
  from datasets import load_dataset
  ds = load_dataset("stanfordnlp/sst2")
  ```
