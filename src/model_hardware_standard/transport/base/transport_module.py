from collections.abc import Iterable
from typing import Protocol

from .base_endpoint import BaseEndpoint


class TransportCandidate(Protocol):
    """The connection-only surface required by endpoint discovery."""

    @property
    def endpoint(self) -> BaseEndpoint:
        """Return the endpoint represented by this candidate."""
        ...

    def open(self) -> None:
        """Open the candidate connection."""
        ...

    def close(self) -> None:
        """Close the candidate connection."""
        ...


class TransportModule(Protocol):
    """Provide one finite pass of transport-specific endpoint discovery."""

    def discover(self) -> Iterable[TransportCandidate]:
        """Return closed candidates when the caller requests a discovery pass."""
        ...
