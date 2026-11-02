from typing import Any

from pydantic import BaseModel, Field


class BaseEndpoint(BaseModel):
    """Serializable description of a connection endpoint."""

    id: str = Field(min_length=36, max_length=36)
    type: str = Field(min_length=1)
    options: dict[str, Any] = Field(default_factory=dict)
