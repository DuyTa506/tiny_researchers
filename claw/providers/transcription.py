"""Groq Whisper transcription provider."""

from __future__ import annotations

from pathlib import Path

import httpx
from loguru import logger


class GroqTranscriptionProvider:
    """Transcribe audio using Groq's Whisper endpoint."""

    API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
    DEFAULT_MODEL = "whisper-large-v3"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def transcribe(self, file_path: str | Path) -> str:
        """POST audio file to Groq Whisper API, return transcribed text."""
        file_path = Path(file_path)
        if not file_path.exists():
            logger.warning("Transcription: file not found: {}", file_path)
            return ""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                with open(file_path, "rb") as f:
                    files = {"file": (file_path.name, f, "application/octet-stream")}
                    data = {"model": self.DEFAULT_MODEL}
                    headers = {"Authorization": f"Bearer {self.api_key}"}
                    r = await client.post(
                        self.API_URL,
                        files=files,
                        data=data,
                        headers=headers,
                    )
                r.raise_for_status()
                return r.json().get("text", "")
        except httpx.HTTPStatusError as e:
            logger.warning("Groq transcription HTTP error {}: {}", e.response.status_code, e)
            return ""
        except Exception as e:
            logger.warning("Groq transcription failed: {}", e)
            return ""
