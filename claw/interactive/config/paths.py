"""Media directory helper for channel file downloads."""

from pathlib import Path

from claw.config import get_settings


def get_media_dir(channel: str = "") -> Path:
    """Return workspace/media/<channel> dir, creating it if needed."""
    settings = get_settings()
    media = settings.workspace / "media"
    if channel:
        media = media / channel
    media.mkdir(parents=True, exist_ok=True)
    return media
