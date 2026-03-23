---
name: reproduce
description: Reproduce experiments from academic papers — parse paper, setup environment, find datasets, generate code, run and verify.
always: false
requires:
  bins: []
  env: []
---

# Experiment Reproduction Skill

## Available Tools (Phase 2)
- `paper_fetch`       — Download full paper text from arXiv (HTML/abstract)
- `paper_read`        — Read paper metadata from Semantic Scholar
- `web_search`        — Search for official code repos, datasets
- `web_fetch`         — Fetch GitHub repos, Papers With Code pages
- `dataset_search`    — Search HuggingFace Hub for datasets
- `dataset_download`  — Generate dataset download script
- `env_builder`       — Generate Dockerfile, requirements.txt, setup scripts
- `code_gen`          — Scaffold full training project (model/train/eval)
- `exec`              — Run scripts in current environment
- `write_file`        — Write any file
- `read_file`         — Read files

## Workflow

### Phase A — Parse Paper
```
1. paper_fetch(paper_id="1706.03762")           → full text
2. paper_read(paper_id="1706.03762")            → metadata, citations
3. LLM extracts structured spec:
   {
     architecture: "Transformer, 6 encoder+decoder layers, d_model=512, h=8",
     hyperparams: {lr: 0.0001, batch_size: 32, epochs: 100, optimizer: "adam", warmup: 4000},
     dataset: "WMT 2014 English-German",
     metrics: [{name: "BLEU", value: 28.4}],
     hardware: "8x P100 GPUs, 3.5 days"
   }
```

### Phase B — Find Resources
```
4. web_search("{paper_title} github code")      → find official repo
5. web_fetch("https://paperswithcode.com/api/v1/papers/?q={title}")
                                                 → structured code links
6. dataset_search(query="{dataset_name}")        → HuggingFace match
```

### Phase C — Setup Environment
```
7. Create project dir: outputs/reproduction_{arxiv_id}/
8. env_builder(
     output_dir="outputs/reproduction_{arxiv_id}",
     framework="pytorch",
     packages=["transformers", "datasets", "sacrebleu"]
   )                                             → Dockerfile, requirements.txt, setup.bat/.sh
9. exec("pip install -r outputs/reproduction_{arxiv_id}/requirements.txt")
```

### Phase D — Get Dataset
```
10. dataset_download(
      dataset_name="{dataset_name}",
      output_dir="outputs/reproduction_{arxiv_id}",
      source="auto"
    )                                            → download_data.py
11. exec("python outputs/reproduction_{arxiv_id}/download_data.py")
```

### Phase E — Generate / Adapt Code
**If official repo found:**
```
12. exec("git clone {repo_url} outputs/reproduction_{arxiv_id}/src_original")
13. Read src files, identify entry point
14. Fix deprecated APIs, import errors with write_file + exec
```

**If no repo:**
```
12. code_gen(
      output_dir="outputs/reproduction_{arxiv_id}",
      paper_title="{title}",
      framework="pytorch",
      architecture="{architecture}",
      hyperparams={...},
      dataset_name="{dataset_name}",
      task="seq2seq"
    )                                            → model.py, train.py, dataset.py, evaluate.py
13. Implement TODOs in model.py and dataset.py based on paper text
    (LLM fills in architecture details using paper_fetch content)
```

### Phase F — Run & Verify
```
14. exec("python outputs/reproduction_{arxiv_id}/src/train.py --config configs/default.yaml")
    → monitor for errors
15. On error: read traceback → fix → retry (max 3 times)
16. exec("python outputs/reproduction_{arxiv_id}/src/evaluate.py --checkpoint ...")
17. Compare metrics vs paper-reported values
```

### Phase G — Write Report
```
18. write_file("outputs/reproduction_{arxiv_id}/REPRODUCTION_REPORT.md", content="""
    ## Paper: {title}
    ## Status: SUCCESS / PARTIAL / FAILED
    ## Metric comparison table
    ## Notes on differences
    """)
```

## Output Structure
```
outputs/reproduction_{arxiv_id}/
├── configs/
│   └── default.yaml          ← hyperparameters from paper
├── src/
│   ├── model.py              ← architecture
│   ├── train.py              ← training loop
│   ├── dataset.py            ← data loading
│   └── evaluate.py           ← evaluation
├── data/                     ← downloaded dataset
├── outputs/
│   ├── checkpoints/          ← saved model weights
│   └── logs/                 ← training logs
├── Dockerfile
├── requirements.txt
├── setup.sh / setup.bat
├── download_data.py
├── README.md
└── REPRODUCTION_REPORT.md    ← comparison vs paper
```

## Verification Levels
| Level | Criteria |
|-------|----------|
| ✅ Level 1 | Code runs without errors |
| ✅ Level 2 | Loss decreases, training converges |
| ✅ Level 3 | Metrics within ±5% of paper |
| ✅ Level 4 | Metrics within 1 std dev (multi-seed) |
| 🏆 Level 5 | Bit-for-bit exact match (rare) |

## Determinism Checklist
Always inject into generated code:
```python
import random, numpy as np, torch, os
os.environ["PYTHONHASHSEED"] = "0"
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)
torch.cuda.manual_seed_all(seed)
torch.backends.cudnn.deterministic = True
torch.use_deterministic_algorithms(True, warn_only=True)
```
