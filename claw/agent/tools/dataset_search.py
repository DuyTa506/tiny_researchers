"""Dataset search tool — searches HuggingFace Hub for datasets."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from claw.agent.tools.base import Tool

_HF_DATASETS_URL = "https://huggingface.co/api/datasets"


class DatasetSearchTool(Tool):
    """Search for datasets on HuggingFace Hub."""

    @property
    def name(self) -> str:
        return "dataset_search"

    @property
    def description(self) -> str:
        return (
            "Search HuggingFace Hub for datasets by keyword. Returns dataset names, "
            "descriptions, and download counts. Useful for finding training data, "
            "benchmarks, or evaluation datasets for ML research."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for finding datasets (e.g. 'sentiment analysis').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-50).",
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> str:
        query: str = kwargs["query"]
        max_results: int = min(kwargs.get("max_results", 5), 50)

        logger.info("dataset_search: query={!r} max_results={}", query, max_results)

        params: dict[str, Any] = {
            "search": query,
            "limit": max_results,
            "sort": "downloads",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(_HF_DATASETS_URL, params=params)
                resp.raise_for_status()
                datasets = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("HuggingFace API HTTP error: {}", exc)
            return f"Error: HuggingFace API returned status {exc.response.status_code}."
        except httpx.RequestError as exc:
            logger.error("HuggingFace request error: {}", exc)
            return f"Error: Could not reach HuggingFace API — {exc}"
        except Exception as exc:
            logger.error("dataset_search unexpected error: {}", exc)
            return f"Error: Unexpected failure during dataset search — {exc}"

        if not datasets:
            return f"No datasets found for query: '{query}'."

        lines: list[str] = [f"Found {len(datasets)} datasets for '{query}':\n"]
        for i, ds in enumerate(datasets, 1):
            ds_id = ds.get("id", "unknown")
            description = ds.get("description") or ""
            # Truncate long descriptions
            if len(description) > 200:
                description = description[:200].rstrip() + "..."

            downloads = ds.get("downloads", 0)
            likes = ds.get("likes", 0)
            tags = ds.get("tags") or []
            tag_str = ", ".join(tags[:5]) if tags else "N/A"

            lines.append(
                f"{i}. **{ds_id}**\n"
                f"   Downloads: {downloads:,} | Likes: {likes}\n"
                f"   Tags: {tag_str}"
                + (f"\n   Description: {description}" if description else "")
            )

        return "\n".join(lines)
