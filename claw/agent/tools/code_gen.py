"""Code generation tool — scaffold a complete ML training project from a paper spec."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from claw.agent.tools.base import Tool


class CodeGenTool(Tool):
    """Generate a complete ML training project scaffold from a paper specification."""

    @property
    def name(self) -> str:
        return "code_gen"

    @property
    def description(self) -> str:
        return (
            "Generate a complete ML training project scaffold from a paper specification. "
            "Creates model.py, train.py, dataset.py, evaluate.py, config.yaml, and README.md "
            "in the output directory."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "output_dir": {
                    "type": "string",
                    "description": "Directory to write the project scaffold",
                },
                "paper_title": {
                    "type": "string",
                    "description": "Paper title for documentation",
                },
                "framework": {
                    "type": "string",
                    "enum": ["pytorch", "tensorflow", "jax"],
                    "description": "ML framework. Default: pytorch",
                },
                "architecture": {
                    "type": "string",
                    "description": (
                        "Architecture description "
                        "(e.g. 'Transformer encoder-decoder, 6 layers, d_model=512')"
                    ),
                },
                "hyperparams": {
                    "type": "object",
                    "description": (
                        "Training hyperparameters dict: "
                        "{lr, batch_size, epochs, optimizer, weight_decay, ...}"
                    ),
                },
                "dataset_name": {
                    "type": "string",
                    "description": "Dataset name for data loading code",
                },
                "task": {
                    "type": "string",
                    "description": (
                        "Task type: classification, seq2seq, language_modeling, "
                        "image_classification, etc."
                    ),
                },
            },
            "required": ["output_dir"],
        }

    # ------------------------------------------------------------------
    # Template builders
    # ------------------------------------------------------------------

    def _build_config_yaml(
        self,
        paper_title: str,
        dataset_name: str,
        hyperparams: dict[str, Any],
    ) -> str:
        hp = hyperparams or {}
        lr = hp.get("lr", hp.get("learning_rate", 0.0001))
        batch_size = hp.get("batch_size", 32)
        epochs = hp.get("epochs", 100)
        optimizer = hp.get("optimizer", "adam")
        weight_decay = hp.get("weight_decay", 0.01)
        warmup_steps = hp.get("warmup_steps", 4000)
        grad_clip = hp.get("grad_clip", 1.0)

        return f"""\
# Hyperparameters from paper: {paper_title}
training:
  learning_rate: {lr}
  batch_size: {batch_size}
  epochs: {epochs}
  optimizer: {optimizer}
  weight_decay: {weight_decay}
  warmup_steps: {warmup_steps}
  grad_clip: {grad_clip}

model:
  # Fill from paper
  d_model: 512
  n_layers: 6
  dropout: 0.1

data:
  dataset: {dataset_name}
  train_split: train
  val_split: validation
  num_workers: 4

reproducibility:
  seed: 42

logging:
  log_dir: outputs/logs
  checkpoint_dir: outputs/checkpoints
  log_every: 100
  save_every: 1
"""

    def _build_model_py(self, paper_title: str, architecture: str) -> str:
        return f'''\
"""Model architecture — {paper_title}"""
# TODO: Implement architecture: {architecture}
# Reference: {paper_title}
from __future__ import annotations

import torch
import torch.nn as nn


class Model(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        # TODO: Define layers based on: {architecture}
        pass

    def forward(self, x):
        # TODO: Implement forward pass
        raise NotImplementedError("Implement forward() based on paper architecture")
'''

    def _build_train_py(self, paper_title: str) -> str:
        return f'''\
"""Training script — {paper_title}"""
from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

import numpy as np
import torch
import yaml


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def train(config: dict) -> None:
    set_seed(config["reproducibility"]["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {{device}}")

    # TODO: Initialize model, optimizer, dataloader
    from src.model import Model
    from src.dataset import get_dataloaders

    model = Model(config["model"]).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config["training"]["learning_rate"],
        weight_decay=config["training"]["weight_decay"],
    )
    train_loader, val_loader = get_dataloaders(config)

    ckpt_dir = Path(config["logging"]["checkpoint_dir"])
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(config["training"]["epochs"]):
        model.train()
        total_loss = 0.0
        for step, batch in enumerate(train_loader):
            optimizer.zero_grad()
            loss = model(batch)  # TODO: adjust to your model\'s forward signature
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), config["training"]["grad_clip"]
            )
            optimizer.step()
            total_loss += loss.item()
            if step % config["logging"]["log_every"] == 0:
                print(f"Epoch {{epoch}} Step {{step}} Loss {{loss.item():.4f}}")

        # Save checkpoint
        torch.save(
            {{"epoch": epoch, "model": model.state_dict()}},
            ckpt_dir / f"epoch_{{epoch:03d}}.pt",
        )
        print(f"Epoch {{epoch}} avg loss: {{total_loss / len(train_loader):.4f}}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    args = parser.parse_args()
    train(load_config(args.config))
'''

    def _build_dataset_py(self, dataset_name: str) -> str:
        return f'''\
"""Dataset loading — {dataset_name}"""
from __future__ import annotations

from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset


class ResearchDataset(Dataset):
    def __init__(self, split: str, config: dict):
        # TODO: Load {dataset_name} for split
        # Hint: use datasets.load_dataset("{dataset_name}", split=split)
        self.data = []

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int):
        return self.data[idx]


def get_dataloaders(config: dict):
    train_ds = ResearchDataset(config["data"]["train_split"], config)
    val_ds = ResearchDataset(config["data"]["val_split"], config)
    train_loader = DataLoader(
        train_ds,
        batch_size=config["training"]["batch_size"],
        shuffle=True,
        num_workers=config["data"]["num_workers"],
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=config["training"]["batch_size"],
        shuffle=False,
        num_workers=config["data"]["num_workers"],
    )
    return train_loader, val_loader
'''

    def _build_evaluate_py(self, paper_title: str, task: str) -> str:
        return f'''\
"""Evaluation — {paper_title}"""
from __future__ import annotations

import argparse
from pathlib import Path

import torch
import yaml


def evaluate(config: dict, checkpoint: str) -> dict:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    from src.model import Model
    from src.dataset import get_dataloaders

    model = Model(config["model"]).to(device)
    ckpt = torch.load(checkpoint, map_location=device)
    model.load_state_dict(ckpt["model"])
    model.eval()

    _, val_loader = get_dataloaders(config)

    # TODO: implement metric computation for {task}
    metrics: dict = {{}}
    print("Evaluation metrics:", metrics)
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args()
    with open(args.config) as f:
        config = yaml.safe_load(f)
    evaluate(config, args.checkpoint)
'''

    def _build_readme_md(self, paper_title: str, architecture: str) -> str:
        # The inner fenced code blocks must use different fence lengths to avoid
        # closing the outer triple-quote string prematurely.
        return f"""\
# Reproduction: {paper_title}

## Quick Start

### 1. Setup environment
```bash
# Windows
setup.bat

# Linux/macOS
bash setup.sh
```

### 2. Download dataset
```bash
pip install -r requirements_data.txt
python download_data.py
```

### 3. Implement TODOs
Edit these files to match the paper:
- `src/model.py` — implement architecture
- `src/dataset.py` — implement data loading

### 4. Train
```bash
python src/train.py --config configs/default.yaml
```

### 5. Evaluate
```bash
python src/evaluate.py --config configs/default.yaml --checkpoint outputs/checkpoints/epoch_099.pt
```

## Architecture Notes
{architecture}

## Expected Results
| Metric | Paper Value | Your Result |
|--------|-------------|-------------|
| TODO   | TODO        |             |
"""

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    async def execute(self, **kwargs: Any) -> str:
        output_dir: str = kwargs["output_dir"]
        paper_title: str = kwargs.get("paper_title", "Untitled Paper")
        framework: str = kwargs.get("framework", "pytorch")
        architecture: str = kwargs.get("architecture", "TODO: specify architecture")
        hyperparams: dict[str, Any] = kwargs.get("hyperparams") or {}
        dataset_name: str = kwargs.get("dataset_name", "TODO: specify dataset")
        task: str = kwargs.get("task", "TODO: specify task")

        logger.debug(
            "code_gen: output_dir={!r} paper_title={!r} framework={!r}",
            output_dir,
            paper_title,
            framework,
        )

        root = Path(output_dir).expanduser().resolve()

        # Map of relative path → content builder
        files: dict[Path, str] = {
            root / "configs" / "default.yaml": self._build_config_yaml(
                paper_title, dataset_name, hyperparams
            ),
            root / "src" / "model.py": self._build_model_py(paper_title, architecture),
            root / "src" / "train.py": self._build_train_py(paper_title),
            root / "src" / "dataset.py": self._build_dataset_py(dataset_name),
            root / "src" / "evaluate.py": self._build_evaluate_py(paper_title, task),
            root / "src" / "__init__.py": "",
            root / "README.md": self._build_readme_md(paper_title, architecture),
        }

        written: list[str] = []
        errors: list[str] = []

        for path, content in files.items():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                rel = path.relative_to(root)
                written.append(str(rel))
                logger.debug("code_gen: wrote {}", path)
            except PermissionError as exc:
                errors.append(f"Permission denied writing {path}: {exc}")
                logger.error("code_gen: permission error writing {}: {}", path, exc)
            except Exception as exc:
                errors.append(f"Failed to write {path}: {exc}")
                logger.error("code_gen: error writing {}: {}", path, exc)

        if errors:
            error_block = "\n".join(f"  ✗ {e}" for e in errors)
            return (
                f"code_gen completed with errors for {output_dir}/:\n"
                f"{error_block}\n\n"
                f"Files successfully written: {len(written)}/{len(files)}"
            )

        return (
            f"Generated project scaffold in {output_dir}/:\n"
            f"  ✓ configs/default.yaml  — Hyperparameters\n"
            f"  ✓ src/model.py          — Architecture (needs implementation)\n"
            f"  ✓ src/train.py          — Training loop (ready to run)\n"
            f"  ✓ src/dataset.py        — Data loading (needs dataset-specific code)\n"
            f"  ✓ src/evaluate.py       — Evaluation loop\n"
            f"  ✓ src/__init__.py\n"
            f"  ✓ README.md             — Step-by-step guide\n"
            f"\n"
            f"Next steps:\n"
            f"  1. Implement src/model.py — architecture: {architecture}\n"
            f"  2. Implement src/dataset.py — dataset: {dataset_name}\n"
            f"  3. Run: python src/train.py --config configs/default.yaml\n"
            f"\n"
            f"TODOs remaining: 4 (model.py x2, dataset.py x1, evaluate.py x1)"
        )
