"""Base pydantic model for channel configuration."""

from pydantic import BaseModel, ConfigDict


class Base(BaseModel):
    """Base config model with common settings."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        str_strip_whitespace=True,
    )
