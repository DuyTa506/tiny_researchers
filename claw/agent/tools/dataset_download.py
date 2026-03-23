"""Dataset download tool — generates a download script for datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from loguru import logger

from claw.agent.tools.base import Tool

# ---------------------------------------------------------------------------
# Script templates
# ---------------------------------------------------------------------------

_HUGGINGFACE_SCRIPT = '''\
"""Auto-generated dataset download script."""
from pathlib import Path
from datasets import load_dataset

output_dir = Path(__file__).parent / "data"
output_dir.mkdir(parents=True, exist_ok=True)

print("Downloading {dataset_name!r} from HuggingFace Hub...")
dataset = load_dataset({load_args}, cache_dir=str(output_dir))
dataset.save_to_disk(str(output_dir / "{safe_name}"))
print(f"Saved to {{output_dir}}")

# Show stats
for split, ds in dataset.items():
    print(f"  {{split}}: {{len(ds):,}} samples, columns: {{ds.column_names}}")
'''

_HUGGINGFACE_AUTO_HEADER = """\
# Auto-detected source: HuggingFace Hub
# If this fails, try manually searching: https://huggingface.co/datasets?search={dataset_name}
# Or check: https://paperswithcode.com/datasets

"""

_HUGGINGFACE_SPLIT_SCRIPT = '''\
"""Auto-generated dataset download script."""
from pathlib import Path
from datasets import load_dataset

output_dir = Path(__file__).parent / "data"
output_dir.mkdir(parents=True, exist_ok=True)

print("Downloading {dataset_name!r} ({split} split) from HuggingFace Hub...")
dataset = load_dataset({load_args}, split="{split}", cache_dir=str(output_dir))
save_path = output_dir / "{safe_name}_{split}"
dataset.save_to_disk(str(save_path))
print(f"Saved to {{save_path}}")
print(f"  {split}: {{len(dataset):,}} samples, columns: {{dataset.column_names}}")
'''

_URL_SCRIPT = '''\
"""Auto-generated dataset download script."""
import urllib.request
from pathlib import Path

output_dir = Path(__file__).parent / "data"
output_dir.mkdir(parents=True, exist_ok=True)

url = "{url}"
filename = output_dir / "{filename}"
print(f"Downloading from {{url}}...")
urllib.request.urlretrieve(url, filename)
print(f"Saved to {{filename}}")
'''

_KAGGLE_SCRIPT = '''\
"""Auto-generated dataset download script."""
from pathlib import Path
import subprocess
import sys

output_dir = Path(__file__).parent / "data"
output_dir.mkdir(parents=True, exist_ok=True)

dataset_name = "{dataset_name}"
print(f"Downloading {{dataset_name!r}} from Kaggle...")
print("Note: requires 'kaggle' CLI and ~/.kaggle/kaggle.json credentials.")

result = subprocess.run(
    [sys.executable, "-m", "kaggle", "datasets", "download", "-d", dataset_name, "-p", str(output_dir), "--unzip"],
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    print(f"Error: {{result.stderr}}")
    sys.exit(result.returncode)

print(f"Saved to {{output_dir}}")
print(result.stdout)
'''

_REQUIREMENTS = """\
datasets>=2.14.0
huggingface-hub>=0.20.0
tqdm
"""

_KAGGLE_REQUIREMENTS = """\
datasets>=2.14.0
huggingface-hub>=0.20.0
tqdm
kaggle>=1.6.0
"""

_RETURN_TEMPLATE = """\
Generated download scripts in {output_dir}/:
  ✓ download_data.py       — Python download script
  ✓ requirements_data.txt  — Dependencies

To download the dataset:
  1. pip install -r requirements_data.txt
  2. python download_data.py

Dataset: {dataset_name}
Source: {source_label}
Expected location: {output_dir}/data/\
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _filename_from_url(url: str) -> str:
    """Extract a filename from a URL, falling back to 'dataset.bin'."""
    parsed = urlparse(url)
    name = Path(parsed.path).name
    return name if name else "dataset.bin"


def _build_load_args(dataset_name: str, subset: str | None) -> str:
    """Build the positional/keyword argument string for load_dataset()."""
    parts = [f'"{dataset_name}"']
    if subset:
        parts.append(f'"{subset}"')
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

class DatasetDownloadTool(Tool):
    """Generate a Python script to download a dataset."""

    @property
    def name(self) -> str:
        return "dataset_download"

    @property
    def description(self) -> str:
        return (
            "Generate a Python script to download a dataset. Supports HuggingFace Hub, "
            "direct URL download, and Kaggle. The generated script is saved to "
            "output_dir/download_data.py — run it with the exec tool."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dataset_name": {
                    "type": "string",
                    "description": (
                        "Dataset name or identifier "
                        "(e.g. 'squad', 'wikitext', 'cifar10', 'HuggingFaceFW/fineweb')"
                    ),
                },
                "output_dir": {
                    "type": "string",
                    "description": (
                        "Directory to save the dataset and the generated download script"
                    ),
                },
                "source": {
                    "type": "string",
                    "enum": ["huggingface", "kaggle", "url", "auto"],
                    "description": (
                        "Source to download from. 'auto' tries HuggingFace first. "
                        "Default: auto"
                    ),
                },
                "url": {
                    "type": "string",
                    "description": "Direct download URL (required when source=url)",
                },
                "subset": {
                    "type": "string",
                    "description": "Dataset subset/config name (e.g. 'en', 'mrpc')",
                },
                "split": {
                    "type": "string",
                    "description": (
                        "Split to download: train, validation, test, or all. Default: all"
                    ),
                },
            },
            "required": ["dataset_name", "output_dir"],
        }

    # ------------------------------------------------------------------
    # Script builders
    # ------------------------------------------------------------------

    def _hf_script(
        self,
        dataset_name: str,
        subset: str | None,
        split: str | None,
        auto_header: bool,
    ) -> str:
        """Build a HuggingFace download script."""
        load_args = _build_load_args(dataset_name, subset)
        safe_name = dataset_name.replace("/", "_")

        download_all = split is None or split.lower() == "all"

        if download_all:
            body = _HUGGINGFACE_SCRIPT.format(
                dataset_name=dataset_name,
                load_args=load_args,
                safe_name=safe_name,
            )
        else:
            body = _HUGGINGFACE_SPLIT_SCRIPT.format(
                dataset_name=dataset_name,
                load_args=load_args,
                safe_name=safe_name,
                split=split,
            )

        if auto_header:
            header = _HUGGINGFACE_AUTO_HEADER.format(dataset_name=dataset_name)
            return header + body
        return body

    def _url_script(self, url: str) -> str:
        """Build a direct-URL download script."""
        filename = _filename_from_url(url)
        return _URL_SCRIPT.format(url=url, filename=filename)

    def _kaggle_script(self, dataset_name: str) -> str:
        """Build a Kaggle download script."""
        return _KAGGLE_SCRIPT.format(dataset_name=dataset_name)

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    async def execute(self, **kwargs: Any) -> str:
        dataset_name: str = kwargs["dataset_name"]
        output_dir_str: str = kwargs["output_dir"]
        source: str = kwargs.get("source", "auto")
        url: str | None = kwargs.get("url")
        subset: str | None = kwargs.get("subset")
        split: str | None = kwargs.get("split")

        logger.info(
            "dataset_download: dataset={!r} source={!r} output_dir={!r}",
            dataset_name,
            source,
            output_dir_str,
        )

        # Validate source=url requires a url
        if source == "url" and not url:
            return "Error: 'url' parameter is required when source='url'."

        output_dir = Path(output_dir_str).expanduser().resolve()

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return f"Error: Permission denied creating directory: {output_dir}"
        except Exception as exc:
            logger.error("dataset_download mkdir error: {}", exc)
            return f"Error: Could not create output directory — {exc}"

        # Choose requirements content and source label
        if source == "kaggle":
            requirements_content = _KAGGLE_REQUIREMENTS
            source_label = "Kaggle"
        else:
            requirements_content = _REQUIREMENTS
            source_label = "HuggingFace Hub" if source in ("huggingface", "auto") else "Direct URL"

        # Build the download script
        try:
            if source == "url":
                assert url is not None  # already validated above
                script_content = self._url_script(url)
                source_label = "Direct URL"
            elif source == "kaggle":
                script_content = self._kaggle_script(dataset_name)
            elif source == "huggingface":
                script_content = self._hf_script(
                    dataset_name, subset, split, auto_header=False
                )
            else:  # auto
                script_content = self._hf_script(
                    dataset_name, subset, split, auto_header=True
                )
        except Exception as exc:
            logger.error("dataset_download script build error: {}", exc)
            return f"Error: Failed to generate download script — {exc}"

        # Write files
        script_path = output_dir / "download_data.py"
        requirements_path = output_dir / "requirements_data.txt"

        try:
            script_path.write_text(script_content, encoding="utf-8")
            logger.debug("dataset_download: wrote {}", script_path)
        except PermissionError:
            return f"Error: Permission denied writing: {script_path}"
        except Exception as exc:
            logger.error("dataset_download write script error: {}", exc)
            return f"Error: Could not write download_data.py — {exc}"

        try:
            requirements_path.write_text(requirements_content, encoding="utf-8")
            logger.debug("dataset_download: wrote {}", requirements_path)
        except PermissionError:
            return f"Error: Permission denied writing: {requirements_path}"
        except Exception as exc:
            logger.error("dataset_download write requirements error: {}", exc)
            return f"Error: Could not write requirements_data.txt — {exc}"

        return _RETURN_TEMPLATE.format(
            output_dir=output_dir,
            dataset_name=dataset_name,
            source_label=source_label,
        )
