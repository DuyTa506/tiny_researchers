---
name: dataset-search
description: Search HuggingFace Hub for datasets by keyword. Use when the user wants to find training data, benchmarks, or evaluation datasets for ML/NLP/CV research.
always: false
---

# Dataset Search

Search for datasets on HuggingFace Hub using `web_fetch`.

## API Endpoint

```
GET https://huggingface.co/api/datasets
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `search` | string | required | Search keywords |
| `limit` | int | 10 | Number of results (1–100) |
| `sort` | string | `downloads` | Sort by: `downloads`, `likes`, `lastModified`, `createdAt` |
| `direction` | int | `-1` | `-1` = descending (most popular first) |
| `full` | bool | `false` | Include full dataset card info |

## How to Use

### Step 1 — Build the URL

```
https://huggingface.co/api/datasets?search=<query>&limit=10&sort=downloads&direction=-1
```

### Step 2 — Call web_fetch

```
web_fetch("https://huggingface.co/api/datasets?search=sentiment+analysis&limit=10&sort=downloads&direction=-1")
```

### Step 3 — Parse the JSON response

The response is a JSON array:
```json
[
  {
    "id": "stanfordnlp/sst2",
    "downloads": 5000000,
    "likes": 320,
    "tags": ["task_categories:text-classification", "language:en"],
    "description": "The Stanford Sentiment Treebank...",
    "lastModified": "2023-10-01T00:00:00.000Z",
    "cardData": {
      "license": "mit",
      "task_categories": ["text-classification"],
      "language": ["en"]
    }
  }
]
```

### Step 4 — Present results

For each dataset, show:
- **Dataset ID** (e.g. `stanfordnlp/sst2`) — use with HuggingFace `datasets` library
- **Downloads** — popularity indicator
- **Likes**
- **Tags** — task type, language, modality
- **Description snippet**
- **HuggingFace page**: `https://huggingface.co/datasets/<id>`

## Examples

### Search for NLP sentiment datasets
```
web_fetch("https://huggingface.co/api/datasets?search=sentiment+analysis&limit=10&sort=downloads&direction=-1")
```

### Search for image classification datasets
```
web_fetch("https://huggingface.co/api/datasets?search=image+classification&limit=10&sort=downloads&direction=-1")
```

### Search for question answering benchmarks
```
web_fetch("https://huggingface.co/api/datasets?search=question+answering&limit=10&sort=likes&direction=-1")
```

### Get dataset details (full card)
```
web_fetch("https://huggingface.co/api/datasets/stanfordnlp/sst2")
```

## How to Use a Dataset (in code)

Once you have the dataset ID, the user can load it with:
```python
from datasets import load_dataset
ds = load_dataset("stanfordnlp/sst2")
```

Or download via CLI:
```bash
huggingface-cli download stanfordnlp/sst2 --repo-type dataset
```

## Notes

- Results sorted by `downloads` by default — gives most widely-used datasets first
- `sort=likes` gives community-favorite datasets (newer, high quality)
- For private/gated datasets, user needs to authenticate with HuggingFace token
- Dataset IDs can also be used with `dataset_download` tool to generate a full download script
