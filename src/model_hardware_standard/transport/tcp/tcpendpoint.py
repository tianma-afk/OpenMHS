from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field

from ..base.base_endpoint import BaseEndpoint


class TCPEndpoint(BaseEndpoint):
    """Connection details for a TCP endpoint."""

    type: Literal["tcp"] = "tcp"
    address: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)

    @classmethod
    def from_address(
        cls,
        address: str,
        port: int,
        *,
        options: dict[str, Any] | None = None,
    ) -> "TCPEndpoint":
        normalized_address = address.strip()
        key = "\x00".join(("tcp", normalized_address.casefold(), str(port)))
        endpoint_id = str(uuid5(NAMESPACE_URL, f"model-hardware-standard:endpoint:{key}"))
        return cls(
            id=endpoint_id,
            address=normalized_address,
            port=port,
            options=options or {},
        )
