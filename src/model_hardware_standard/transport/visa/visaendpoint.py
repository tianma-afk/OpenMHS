from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field

from ..base.base_endpoint import BaseEndpoint


class VisaEndpoint(BaseEndpoint):
    """Connection details for a VISA resource."""

    type: Literal["visa"] = "visa"
    resource: str = Field(min_length=1)

    @classmethod
    def from_resource(
        cls,
        resource: str,
        *,
        options: dict[str, Any] | None = None,
    ) -> "VisaEndpoint":
        normalized_resource = resource.strip()
        if not normalized_resource:
            raise ValueError("VISA resource must not be empty")

        key = "\x00".join(("visa", normalized_resource.casefold()))
        endpoint_id = str(
            uuid5(NAMESPACE_URL, f"model-hardware-standard:endpoint:{key}")
        )
        return cls(
            id=endpoint_id,
            resource=normalized_resource,
            options=dict(options or {}),
        )
