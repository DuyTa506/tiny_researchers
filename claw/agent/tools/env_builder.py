"""Environment builder tool — generates reproducible experiment setup files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from claw.agent.tools.base import Tool

# ---------------------------------------------------------------------------
# Framework-specific constants
# ---------------------------------------------------------------------------

_FRAMEWORK_DOCKER_BASE: dict[str, dict[str, str]] = {
    "pytorch": {
        "cuda": "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
        "cpu":  "python:{python_version}-slim",
    },
    "tensorflow": {
        "cuda": "tensorflow/tensorflow:2.14.0-gpu",
        "cpu":  "tensorflow/tensorflow:2.14.0",
    },
    "jax": {
        "cuda": "python:{python_version}-slim",   # JAX has no official Docker; install via pip
        "cpu":  "python:{python_version}-slim",
    },
    "generic": {
        "cuda": "python:{python_version}-slim",
        "cpu":  "python:{python_version}-slim",
    },
}

# Core pip packages for each framework (version-pinned where well-known)
_FRAMEWORK_PIP_PACKAGES: dict[str, list[str]] = {
    "pytorch": [
        "torch==2.1.0",
        "torchvision==0.16.0",
        "torchaudio==2.1.0",
    ],
    "tensorflow": [
        "tensorflow==2.14.0",
    ],
    "jax": [
        "jax[cuda12_pip]==0.4.20",
        "jaxlib==0.4.20",
        "flax==0.7.4",
        "optax==0.1.7",
    ],
    "generic": [],
}

# Conda channel + package for each framework (where conda packages exist)
_FRAMEWORK_CONDA_DEPS: dict[str, list[str]] = {
    "pytorch": ["pytorch==2.1.0", "torchvision==0.16.0", "pytorch-cuda=12.1"],
    "tensorflow": [],   # tensorflow is pip-only on conda-forge
    "jax": [],          # JAX is pip-only
    "generic": [],
}

_COMMON_RESEARCH_PACKAGES: list[str] = [
    "numpy>=1.24,<2.0",
    "pandas>=2.0",
    "matplotlib>=3.7",
    "tqdm>=4.65",
    "pyyaml>=6.0",
    "loguru>=0.7",
    "scikit-learn>=1.3",
    "scipy>=1.11",
]


# ---------------------------------------------------------------------------
# Main tool
# ---------------------------------------------------------------------------

class EnvBuilderTool(Tool):
    """Generate environment setup files for reproducing a paper experiment."""

    @property
    def name(self) -> str:
        return "env_builder"

    @property
    def description(self) -> str:
        return (
            "Generate environment setup files for reproducing a paper experiment. "
            "Creates Dockerfile, requirements.txt, environment.yml (conda), and "
            "cross-platform setup scripts in the specified output directory."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "output_dir": {
                    "type": "string",
                    "description": "Directory to write environment files into",
                },
                "framework": {
                    "type": "string",
                    "enum": ["pytorch", "tensorflow", "jax", "generic"],
                    "description": "ML framework. Default: pytorch",
                },
                "python_version": {
                    "type": "string",
                    "description": "Python version. Default: 3.11",
                },
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Additional pip packages to install "
                        "(e.g. ['transformers==4.35.0', 'datasets'])"
                    ),
                },
                "cuda": {
                    "type": "boolean",
                    "description": "Include CUDA/GPU support. Default: true",
                },
                "cuda_version": {
                    "type": "string",
                    "description": "CUDA version string. Default: 12.1",
                },
            },
            "required": ["output_dir"],
        }

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    async def execute(self, **kwargs: Any) -> str:
        output_dir: str        = kwargs["output_dir"]
        framework: str         = kwargs.get("framework", "pytorch")
        python_version: str    = kwargs.get("python_version", "3.11")
        extra_packages: list[str] = kwargs.get("packages") or []
        cuda: bool             = kwargs.get("cuda", True)
        cuda_version: str      = kwargs.get("cuda_version", "12.1")

        out = Path(output_dir).expanduser().resolve()
        logger.info(
            "env_builder: generating files in {} (framework={}, python={}, cuda={})",
            out, framework, python_version, cuda,
        )

        try:
            out.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return f"Error: Permission denied creating directory: {out}"
        except Exception as exc:
            logger.error("env_builder mkdir error: {}", exc)
            return f"Error: Could not create output directory — {exc}"

        # Resolve the full package list once so all files are consistent
        framework_packages  = _FRAMEWORK_PIP_PACKAGES.get(framework, [])
        all_pip_packages    = (
            framework_packages
            + _COMMON_RESEARCH_PACKAGES
            + extra_packages
        )
        docker_base = _resolve_docker_base(framework, cuda, python_version)

        files_written: list[tuple[str, str]] = []  # (filename, blurb)

        # --- 1. Dockerfile ------------------------------------------------
        dockerfile_content = _build_dockerfile(
            docker_base, python_version, cuda, framework
        )
        _write(out / "Dockerfile", dockerfile_content)
        files_written.append(("Dockerfile", f"Docker container ({docker_base})"))
        logger.debug("env_builder: wrote Dockerfile")

        # --- 2. requirements.txt ------------------------------------------
        requirements_content = _build_requirements(
            framework, cuda, cuda_version, all_pip_packages
        )
        _write(out / "requirements.txt", requirements_content)
        pkg_count = len([
            ln for ln in requirements_content.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ])
        files_written.append(("requirements.txt", f"{pkg_count} packages"))
        logger.debug("env_builder: wrote requirements.txt ({} packages)", pkg_count)

        # --- 3. environment.yml -------------------------------------------
        env_yml_content = _build_environment_yml(
            framework, python_version, cuda, extra_packages
        )
        _write(out / "environment.yml", env_yml_content)
        files_written.append(("environment.yml", "Conda environment"))
        logger.debug("env_builder: wrote environment.yml")

        # --- 4. setup.sh --------------------------------------------------
        setup_sh_content = _build_setup_sh(python_version)
        _write(out / "setup.sh", setup_sh_content)
        files_written.append(("setup.sh", "Linux/macOS setup (uv/conda/venv)"))
        logger.debug("env_builder: wrote setup.sh")

        # --- 5. setup.bat -------------------------------------------------
        setup_bat_content = _build_setup_bat(python_version)
        _write(out / "setup.bat", setup_bat_content)
        files_written.append(("setup.bat", "Windows setup"))
        logger.debug("env_builder: wrote setup.bat")

        # --- 6. docker-compose.yml ----------------------------------------
        compose_content = _build_docker_compose(cuda)
        _write(out / "docker-compose.yml", compose_content)
        files_written.append(("docker-compose.yml", ""))
        logger.debug("env_builder: wrote docker-compose.yml")

        return _format_result(out, files_written)


# ---------------------------------------------------------------------------
# File content builders
# ---------------------------------------------------------------------------

def _resolve_docker_base(framework: str, cuda: bool, python_version: str) -> str:
    """Pick the right Docker base image."""
    variants = _FRAMEWORK_DOCKER_BASE.get(framework, _FRAMEWORK_DOCKER_BASE["generic"])
    key = "cuda" if cuda else "cpu"
    base = variants[key]
    return base.format(python_version=python_version)


def _build_dockerfile(
    docker_base: str,
    python_version: str,
    cuda: bool,
    framework: str,
) -> str:
    cuda_comment = (
        "# GPU determinism — keeps results reproducible across runs"
        if cuda
        else "# CPU-only build"
    )
    lines: list[str] = [
        f"FROM {docker_base}",
        "",
        "RUN apt-get update && apt-get install -y \\",
        "        git wget curl \\",
        "    && rm -rf /var/lib/apt/lists/*",
        "",
        "WORKDIR /workspace",
        "",
        "COPY requirements.txt .",
        "RUN pip install --no-cache-dir -r requirements.txt",
        "",
        "# Reproducibility environment variables",
        "ENV PYTHONHASHSEED=0",
    ]
    if cuda:
        lines += [
            "ENV CUBLAS_WORKSPACE_CONFIG=:4096:8",
            cuda_comment,
        ]
    else:
        lines.append(cuda_comment)

    lines += [
        "",
        "CMD [\"bash\"]",
    ]
    return "\n".join(lines) + "\n"


def _build_requirements(
    framework: str,
    cuda: bool,
    cuda_version: str,
    all_pip_packages: list[str],
) -> str:
    sections: list[str] = []

    # Header comment
    sections.append("# Auto-generated by Claw Researcher — env_builder tool")
    sections.append("# Edit and re-run setup.sh / setup.bat to apply changes")
    sections.append("")

    # Framework section
    fw_packages = _FRAMEWORK_PIP_PACKAGES.get(framework, [])
    if fw_packages:
        sections.append(f"# --- {framework.capitalize()} ---")
        # For pytorch with CUDA, add the index URL hint as a comment
        if framework == "pytorch" and cuda:
            sections.append(
                "# Install via: pip install torch torchvision torchaudio "
                f"--index-url https://download.pytorch.org/whl/cu{cuda_version.replace('.', '')}"
            )
        for pkg in fw_packages:
            sections.append(pkg)
        sections.append("")

    # JAX CUDA extra-index hint
    if framework == "jax" and cuda:
        sections.append("# --- JAX CUDA ---")
        sections.append(
            f"# pip install --upgrade jax[cuda{cuda_version.split('.')[0]}_pip] "
            f"-f https://storage.googleapis.com/jax-releases/jax_cuda_releases.html"
        )
        sections.append("")

    # Common research packages
    sections.append("# --- Common research packages ---")
    for pkg in _COMMON_RESEARCH_PACKAGES:
        sections.append(pkg)
    sections.append("")

    # User-provided extras (deduplicated against framework + common)
    fw_and_common = set(fw_packages) | set(_COMMON_RESEARCH_PACKAGES)
    extra_packages = [
        p for p in all_pip_packages
        if p not in fw_and_common and p not in _COMMON_RESEARCH_PACKAGES
        and p not in fw_packages
    ]
    if extra_packages:
        sections.append("# --- Additional packages ---")
        for pkg in extra_packages:
            sections.append(pkg)
        sections.append("")

    return "\n".join(sections)


def _build_environment_yml(
    framework: str,
    python_version: str,
    cuda: bool,
    extra_packages: list[str],
) -> str:
    conda_deps = _FRAMEWORK_CONDA_DEPS.get(framework, [])

    # Decide channels
    channels: list[str]
    if framework == "pytorch" and conda_deps:
        channels = ["pytorch", "nvidia", "conda-forge", "defaults"]
    else:
        channels = ["conda-forge", "defaults"]

    # Common research packages as pip deps (conda versions may lag)
    pip_deps: list[str] = list(_COMMON_RESEARCH_PACKAGES)

    # Framework packages that have no conda equivalent go to pip
    if not conda_deps:
        pip_deps = _FRAMEWORK_PIP_PACKAGES.get(framework, []) + pip_deps

    # User-provided extras always go to pip
    pip_deps += extra_packages

    lines: list[str] = [
        "# Auto-generated by Claw Researcher — env_builder tool",
        "name: claw-reproduction",
        "channels:",
    ]
    for ch in channels:
        lines.append(f"  - {ch}")

    lines.append("dependencies:")
    lines.append(f"  - python={python_version}")

    if conda_deps:
        for dep in conda_deps:
            lines.append(f"  - {dep}")

    if pip_deps:
        lines.append("  - pip")
        lines.append("  - pip:")
        for dep in pip_deps:
            lines.append(f"    - {dep}")

    lines.append("")
    return "\n".join(lines)


def _build_setup_sh(python_version: str) -> str:
    return f"""\
#!/bin/bash
# Auto-generated by Claw Researcher — env_builder tool
set -e

echo "Setting up environment..."

# ── Option 1: uv (fastest) ──────────────────────────────────────────────────
if command -v uv &> /dev/null; then
    echo "[uv] Creating virtual environment..."
    uv venv .venv --python {python_version}
    # shellcheck source=/dev/null
    source .venv/bin/activate
    uv pip install -r requirements.txt

# ── Option 2: conda ─────────────────────────────────────────────────────────
elif command -v conda &> /dev/null; then
    echo "[conda] Creating environment from environment.yml..."
    conda env create -f environment.yml
    # shellcheck source=/dev/null
    conda activate claw-reproduction

# ── Option 3: plain venv + pip ──────────────────────────────────────────────
else
    echo "[venv] Creating virtual environment..."
    python -m venv .venv
    # shellcheck source=/dev/null
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
fi

echo ""
echo "Done! Activate the environment with:"
echo "  source .venv/bin/activate   (uv/venv)"
echo "  conda activate claw-reproduction   (conda)"
"""


def _build_setup_bat(python_version: str) -> str:
    return f"""\
@echo off
REM Auto-generated by Claw Researcher -- env_builder tool
echo Setting up environment...

REM ---- Try uv first (fastest) ---------------------------------------------
where uv >nul 2>nul
if %errorlevel% == 0 (
    echo [uv] Creating virtual environment...
    uv venv .venv --python {python_version}
    call .venv\\Scripts\\activate
    uv pip install -r requirements.txt
    goto :done
)

REM ---- Fallback: plain venv + pip -----------------------------------------
echo [venv] Creating virtual environment...
python -m venv .venv
call .venv\\Scripts\\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

:done
echo.
echo Done! The virtual environment is active.
echo To reactivate later: .venv\\Scripts\\activate
"""


def _build_docker_compose(cuda: bool) -> str:
    gpu_block = """\
    # GPU support — comment out the 'deploy' block entirely if no GPU available
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
"""
    gpu_section = gpu_block if cuda else (
        "    # GPU support disabled — remove the comment below and add the\n"
        "    # 'deploy' block to enable it (requires nvidia-container-toolkit)\n"
    )

    return f"""\
# Auto-generated by Claw Researcher — env_builder tool
version: '3.8'

services:
  experiment:
    build: .
    volumes:
      - ./data:/workspace/data
      - ./outputs:/workspace/outputs
{gpu_section}
"""


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------

def _format_result(out: Path, files: list[tuple[str, str]]) -> str:
    lines: list[str] = [
        f"Generated {len(files)} environment files in {out}:",
    ]

    max_name_len = max(len(name) for name, _ in files)
    for name, blurb in files:
        pad = " " * (max_name_len - len(name))
        suffix = f" — {blurb}" if blurb else ""
        lines.append(f"  \u2713 {name}{pad}{suffix}")

    lines += [
        "",
        "To get started:",
        "  Windows:    setup.bat",
        "  Linux/macOS: bash setup.sh",
        "  Docker:      docker compose up",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> None:
    """Write *content* to *path*, raising on error (caller handles)."""
    path.write_text(content, encoding="utf-8")
