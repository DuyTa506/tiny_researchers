"""
End-to-end Phase 1 → Phase 2 test.

Phase 1 (Research):
  paper_search → paper_read → extract method + hyperparams

Phase 2 (Reproduction):
  env_builder → dataset_download → code_gen → write_file (fill TODOs) → exec (run)

Target paper: "Dropout: A Simple Way to Prevent Neural Networks from Overfitting"
              Srivastava et al., 2014 — MNIST, clean hyperparams, tiny model.

Why this paper:
  - MNIST fits in seconds on CPU (no GPU needed)
  - Architecture is a 3-layer MLP — trivial to implement
  - Hyperparams are explicitly stated in the paper
  - Results are reproducible (~98.5% test accuracy)

Run (requires OPENAI_API_KEY in .env):
    pytest tests/test_e2e_phase1_to_phase2.py -v -s

The test verifies:
  1. Agent uses paper_search + paper_read (Phase 1)
  2. Agent calls code_gen + env_builder (scaffolding)
  3. Agent fills in model.py + dataset.py via write_file (TODOs resolved)
  4. exec runs the training — script finishes with exit code 0
  5. Training output contains a loss number (model actually trained)
"""
from __future__ import annotations

import ast
import os
import sys
import time
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

# ── skip guard ────────────────────────────────────────────────────────────────

def _has_llm_key() -> bool:
    from dotenv import load_dotenv
    load_dotenv()
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

requires_llm = pytest.mark.skipif(
    not _has_llm_key(),
    reason="No LLM API key — set OPENAI_API_KEY or ANTHROPIC_API_KEY",
)

# ── session harness (reused from conversational tests) ───────────────────────

@dataclass
class Turn:
    user: str
    response: str = ""
    tool_calls: list[str] = field(default_factory=list)
    elapsed: float = 0.0

    def used_tool(self, *names: str) -> bool:
        return any(any(n in c for c in self.tool_calls) for n in names)

    def assert_tool(self, *names: str) -> None:
        assert self.used_tool(*names), (
            f"Expected one of {names}.\nCalled: {self.tool_calls}\n"
            f"Response: {self.response[:300]}"
        )

    def assert_contains(self, *keywords: str) -> None:
        text = self.response.lower()
        missing = [kw for kw in keywords if kw.lower() not in text]
        assert not missing, (
            f"Missing keywords {missing}.\nResponse: {self.response[:400]}"
        )


class Session:
    def __init__(self, workspace: Path, model: str = "openai/gpt-4o-mini", max_iter: int = 10):
        self.workspace = workspace
        self.model = model
        self.max_iter = max_iter
        self._agent = None
        self.history: list[Turn] = []

    async def __aenter__(self) -> "Session":
        from claw.agent.loop import AgentLoop
        from claw.agent.providers import LLMProvider
        provider = LLMProvider(model=self.model, api_key=None)
        self._agent = AgentLoop(
            workspace=self.workspace,
            provider=provider,
            model=self.model,
            max_iterations=self.max_iter,
        )
        return self

    async def __aexit__(self, *_): self._agent = None

    async def say(self, msg: str) -> Turn:
        turn = Turn(user=msg)
        t0 = time.time()
        async def _prog(text):
            if text.startswith("🔧"):
                turn.tool_calls.append(text)
        turn.response = await self._agent.chat(msg, on_progress=_prog)
        turn.elapsed = time.time() - t0
        _print_turn(turn)
        self.history.append(turn)
        return turn

    def all_tools(self) -> list[str]:
        return [c for t in self.history for c in t.tool_calls]

    def total_time(self) -> float:
        return sum(t.elapsed for t in self.history)


def _print_turn(t: Turn) -> None:
    bar = "─" * 62
    print(f"\n{bar}")
    print(f"USER  : {t.user[:120]}")
    print(f"TOOLS : {t.tool_calls or '(none)'}")
    print(f"TIME  : {t.elapsed:.1f}s")
    print(f"REPLY : {t.response[:500]}{'...' if len(t.response) > 500 else ''}")


# ── Phase 2 helpers (no LLM — direct tool execution) ─────────────────────────

async def _run_env_builder(ws: Path) -> str:
    from claw.agent.tools.env_builder import EnvBuilderTool
    return await EnvBuilderTool().execute(
        output_dir=str(ws),
        framework="pytorch",
        python_version="3.11",
        packages=["torch", "torchvision"],
        cuda=False,
    )


async def _run_dataset_download(ws: Path) -> str:
    from claw.agent.tools.dataset_download import DatasetDownloadTool
    return await DatasetDownloadTool().execute(
        dataset_name="mnist",
        output_dir=str(ws),
        source="torchvision",
    )


async def _run_code_gen(ws: Path) -> str:
    from claw.agent.tools.code_gen import CodeGenTool
    return await CodeGenTool().execute(
        output_dir=str(ws),
        paper_title="Dropout: A Simple Way to Prevent Neural Networks from Overfitting",
        framework="pytorch",
        architecture="3-layer MLP: 784→1024→1024→10, ReLU, Dropout(p=0.5)",
        hyperparams={
            "lr": 0.01,
            "batch_size": 128,
            "epochs": 1,         # 1 epoch — fast on CPU for testing
            "optimizer": "sgd",
            "weight_decay": 0.0,
            "grad_clip": 5.0,
        },
        dataset_name="mnist",
        task="image_classification",
    )


# ── Implemented model.py / dataset.py (fills in code_gen TODOs) ──────────────
# These are self-contained, minimal, CPU-friendly implementations.

_MODEL_PY = '''\
"""MLP with Dropout — Srivastava et al. (2014), Table 1, MNIST."""
import torch
import torch.nn as nn


class Model(nn.Module):
    def __init__(self, config: dict):
        super().__init__()
        # 784 → 1024 → 1024 → 10  with Dropout(0.5) after each hidden layer
        self.net = nn.Sequential(
            nn.Flatten(),
            nn.Linear(784, 1024),
            nn.ReLU(),
            nn.Dropout(p=0.5),
            nn.Linear(1024, 1024),
            nn.ReLU(),
            nn.Dropout(p=0.5),
            nn.Linear(1024, 10),
        )
        self.criterion = nn.CrossEntropyLoss()

    def forward(self, batch):
        x, y = batch
        logits = self.net(x)
        return self.criterion(logits, y)

    def predict(self, x):
        return self.net(x).argmax(dim=1)
'''

_DATASET_PY = '''\
"""MNIST data loading."""
from __future__ import annotations
import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms


def get_dataloaders(config: dict):
    tf = transforms.Compose([transforms.ToTensor(),
                              transforms.Normalize((0.1307,), (0.3081,))])
    root = "./data"
    batch = config["training"]["batch_size"]
    workers = min(config["data"]["num_workers"], 0)   # 0 = main process (Windows safe)
    train_ds = datasets.MNIST(root, train=True,  download=True, transform=tf)
    val_ds   = datasets.MNIST(root, train=False, download=True, transform=tf)
    return (DataLoader(train_ds, batch_size=batch, shuffle=True,  num_workers=workers),
            DataLoader(val_ds,   batch_size=batch, shuffle=False, num_workers=workers))
'''

# Minimal train script: 1 epoch → prints "Epoch 0 avg loss: X.XXXX" → exit 0
_TRAIN_PY = '''\
"""Quick training script — 1 epoch on MNIST."""
from __future__ import annotations
import sys, random
from pathlib import Path
import numpy as np
import torch
import yaml

def set_seed(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)

def load_config(path):
    with open(path) as f: return yaml.safe_load(f)

def train(config):
    set_seed(config["reproducibility"]["seed"])
    device = torch.device("cpu")
    sys.path.insert(0, str(Path(__file__).parent))
    from model import Model
    from dataset import get_dataloaders

    model = Model(config["model"]).to(device)
    optimizer = torch.optim.SGD(model.parameters(),
                                lr=config["training"]["learning_rate"],
                                momentum=0.9)
    train_loader, val_loader = get_dataloaders(config)

    # ── Train 1 epoch ────────────────────────────────────────────
    model.train()
    total_loss, n_steps = 0.0, 0
    for step, batch in enumerate(train_loader):
        batch = [t.to(device) for t in batch]
        optimizer.zero_grad()
        loss = model(batch)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),
                                       config["training"]["grad_clip"])
        optimizer.step()
        total_loss += loss.item(); n_steps += 1
        if step % 100 == 0:
            print(f"  step {step:4d}  loss {loss.item():.4f}")
        if step >= 200:       # cap at 200 steps for test speed
            break

    avg_loss = total_loss / n_steps
    print(f"Epoch 0 avg loss: {avg_loss:.4f}")

    # ── Quick accuracy on 1024 test samples ──────────────────────
    model.eval()
    correct, total = 0, 0
    with torch.no_grad():
        for x, y in val_loader:
            preds = model.predict(x.to(device))
            correct += (preds == y.to(device)).sum().item()
            total += len(y)
            if total >= 1024: break
    acc = correct / total * 100
    print(f"Test accuracy (first 1024 samples): {acc:.1f}%")
    print("Training complete.")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/default.yaml")
    args = p.parse_args()
    train(load_config(args.config))
'''


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1 — Phase 1 only (research pipeline)
# ═══════════════════════════════════════════════════════════════════════════════

@requires_llm
@pytest.mark.asyncio
async def test_phase1_research_dropout_paper():
    """
    Phase 1: Find the Dropout paper, read full details, extract key info.

    Verifies:
    - paper_search is called
    - paper_read is called for the specific paper
    - Response contains: authors, citation count, dropout mentioned
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        async with Session(workspace=Path(tmpdir), max_iter=8) as s:

            # Turn 1 — search + read in one shot (agent already called both in practice)
            t1 = await s.say(
                "Search for the paper 'Dropout: A Simple Way to Prevent Neural "
                "Networks from Overfitting' by Srivastava et al. 2014, "
                "then use paper_read to get its full metadata. "
                "Report: OpenAlex ID, citation count, and abstract."
            )
            t1.assert_tool("paper_search")
            t1.assert_tool("paper_read")
            t1.assert_contains("dropout")
            assert any(w in t1.response for w in ["34,", "W2", "citation"]), (
                f"Expected citation count or OpenAlex ID. Got: {t1.response[:300]}"
            )

            # Turn 2 — extract architecture from what the agent already knows
            # Keep it simple: just ask what it knows, no new tool calls needed
            t2 = await s.say(
                "Based on the abstract and your knowledge of this paper: "
                "what neural network architecture did Srivastava use on MNIST? "
                "Answer in 1-2 sentences, no tools needed."
            )
            assert t2.response
            resp_lower = t2.response.lower()
            assert any(w in resp_lower for w in ["mlp", "hidden", "layer", "1024", "784", "fully", "network"]), (
                f"Expected architecture info. Got: {t2.response[:300]}"
            )

            print(f"\n✅ Phase 1 complete in {s.total_time():.1f}s")
            print(f"   Tools used: {s.all_tools()}")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2 — Phase 2 only (scaffold + run, no LLM)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_phase2_scaffold_and_run():
    """
    Phase 2 (direct tool calls, no LLM):
      env_builder → dataset_download → code_gen → fill TODOs → exec run

    Verifies the full reproduction pipeline works end-to-end
    on MNIST with a tiny MLP. No LLM key needed.
    """
    import asyncio
    from claw.agent.tools.exec_tool import ExecTool

    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)

        # ── Step 1: env_builder ──────────────────────────────────
        print("\n── Step 1: env_builder")
        env_result = await _run_env_builder(ws)
        assert "error" not in env_result.lower(), f"env_builder failed: {env_result}"
        assert (ws / "requirements.txt").exists()
        assert (ws / "Dockerfile").exists()
        print(f"   {env_result.splitlines()[0]}")

        # ── Step 2: dataset_download (generates script, doesn't run) ──
        print("── Step 2: dataset_download")
        dl_result = await _run_dataset_download(ws)
        assert "error" not in dl_result.lower(), f"dataset_download failed: {dl_result}"
        assert (ws / "download_data.py").exists()
        dl_content = (ws / "download_data.py").read_text()
        assert "mnist" in dl_content.lower()
        print(f"   download_data.py generated ({len(dl_content)} chars)")

        # ── Step 3: code_gen ──────────────────────────────────────
        print("── Step 3: code_gen")
        gen_result = await _run_code_gen(ws)
        assert "error" not in gen_result.lower(), f"code_gen failed: {gen_result}"
        assert (ws / "src" / "model.py").exists()
        assert (ws / "src" / "train.py").exists()
        assert (ws / "src" / "dataset.py").exists()
        assert (ws / "configs" / "default.yaml").exists()
        print(f"   scaffold created")

        # ── Step 4: fill in the TODOs ─────────────────────────────
        print("── Step 4: fill TODOs (write_file)")
        (ws / "src" / "model.py").write_text(_MODEL_PY, encoding="utf-8")
        (ws / "src" / "dataset.py").write_text(_DATASET_PY, encoding="utf-8")
        (ws / "src" / "train.py").write_text(_TRAIN_PY, encoding="utf-8")

        # Verify syntax
        for fname in ["model.py", "dataset.py", "train.py"]:
            src = (ws / "src" / fname).read_text()
            try:
                ast.parse(src)
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {fname}: {e}")
        print("   all files parse cleanly")

        # ── Step 5: exec — run training ───────────────────────────
        print("── Step 5: exec (train 1 epoch on MNIST CPU)")
        python_exe = sys.executable
        exec_tool = ExecTool()
        config_path = ws / "configs" / "default.yaml"
        train_py = ws / "src" / "train.py"
        t0 = time.time()
        result = await exec_tool.execute(
            command=f'"{python_exe}" "{train_py}" --config "{config_path}"',
            timeout=180,
        )
        elapsed = time.time() - t0
        print(f"   exec finished in {elapsed:.1f}s")
        print(f"   output:\n{result}")

        # ── Assertions on exec output ─────────────────────────────
        assert "Exit code: 0" in result, (
            f"Training script failed (non-zero exit).\nOutput:\n{result}"
        )
        assert "epoch 0 avg loss" in result.lower(), (
            f"Expected 'Epoch 0 avg loss' in output.\nOutput:\n{result}"
        )
        assert "training complete" in result.lower(), (
            f"Expected 'Training complete' in output.\nOutput:\n{result}"
        )

        # Loss should be a real number (not NaN / inf)
        import re
        loss_match = re.search(r"avg loss:\s*([\d.]+)", result, re.IGNORECASE)
        assert loss_match, f"Could not parse avg loss from output: {result}"
        avg_loss = float(loss_match.group(1))
        assert 0.01 < avg_loss < 5.0, (
            f"Suspicious avg loss value: {avg_loss}. Expected 0.01–5.0 range."
        )

        print(f"\n✅ Phase 2 complete — avg_loss={avg_loss:.4f} in {elapsed:.1f}s")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3 — Full Phase 1 → Phase 2 (agent-driven, conversational)
# ═══════════════════════════════════════════════════════════════════════════════

@requires_llm
@pytest.mark.asyncio
async def test_full_pipeline_phase1_to_phase2():
    """
    Full end-to-end: agent drives Phase 1 (research) then Phase 2 (reproduce).

    Turn 1: search + read paper
    Turn 2: build environment scaffold
    Turn 3: generate code scaffold
    Turn 4: agent writes the implemented model.py + dataset.py via write_file
    Turn 5: run training via exec → verify loss printed

    The agent MUST:
    - Use paper_search and paper_read (Phase 1)
    - Use env_builder and code_gen (Phase 2 setup)
    - Use write_file to fill in the model + dataset implementations
    - Use exec to actually run the training
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)

        async with Session(workspace=ws, max_iter=12) as s:

            # ── Turn 1: Phase 1 — research ────────────────────────
            t1 = await s.say(
                "Search for 'Dropout: A Simple Way to Prevent Neural Networks "
                "from Overfitting' by Srivastava 2014, then use paper_read to "
                "get its full details. I need the architecture and hyperparams "
                "used on MNIST."
            )
            t1.assert_tool("paper_search", "paper_read")

            # ── Turn 2: scaffolding ───────────────────────────────
            t2 = await s.say(
                f"Now set up the reproduction environment. "
                f"Use env_builder to create a PyTorch CPU environment in '{ws}'. "
                f"Then use code_gen to scaffold the project in '{ws}' with: "
                f"paper_title='Dropout: A Simple Way to Prevent Neural Networks from Overfitting', "
                f"framework='pytorch', "
                f"architecture='3-layer MLP: 784→1024→1024→10, ReLU, Dropout(0.5)', "
                f"hyperparams={{lr:0.01, batch_size:128, epochs:1, optimizer:sgd, grad_clip:5.0}}, "
                f"dataset_name='mnist', task='image_classification'."
            )
            t2.assert_tool("env_builder", "code_gen")
            assert (ws / "src" / "model.py").exists(), "code_gen didn't create src/model.py"
            assert (ws / "configs" / "default.yaml").exists(), "code_gen didn't create config"

            # ── Turn 3: fill in model + dataset ───────────────────
            t3 = await s.say(
                f"The generated src/model.py and src/dataset.py have TODOs. "
                f"Use write_file to replace src/model.py in '{ws}' with a working "
                f"implementation: 3-layer MLP (784→1024→1024→10) with ReLU + Dropout(0.5), "
                f"CrossEntropyLoss. "
                f"Also replace src/dataset.py with MNIST loading via torchvision. "
                f"Use num_workers=0 (Windows safe). "
                f"Then replace src/train.py with a working 1-epoch training loop "
                f"that prints 'Epoch 0 avg loss: X.XXXX' and 'Training complete.' at the end."
            )
            t3.assert_tool("write_file")

            # Syntax-check what was written
            for fname in ["model.py", "dataset.py", "train.py"]:
                fpath = ws / "src" / fname
                if fpath.exists():
                    try:
                        ast.parse(fpath.read_text())
                    except SyntaxError as e:
                        # Agent may have made a syntax error — give it a chance to fix
                        print(f"  ⚠ Syntax error in {fname}: {e} — will attempt fix")

            # ── Turn 4: run training ───────────────────────────────
            python_exe = sys.executable
            t4 = await s.say(
                f"Now run the training with exec: "
                f"cd \"{ws}\" && {python_exe} src/train.py --config configs/default.yaml "
                f"with timeout=180. "
                f"The script should print 'Epoch 0 avg loss:' and 'Training complete.'."
            )
            t4.assert_tool("exec")

            # ── Validate training actually ran ────────────────────
            resp_lower = t4.response.lower()
            assert any(kw in resp_lower for kw in ["loss", "epoch", "complete", "accuracy"]), (
                f"Expected training output in response.\nGot: {t4.response[:400]}"
            )

            print(f"\n✅ Full Phase 1 → Phase 2 complete in {s.total_time():.1f}s")
            print(f"   All tools used: {s.all_tools()}")
