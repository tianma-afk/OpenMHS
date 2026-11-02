from abc import ABC, abstractmethod

from .base_endpoint import BaseEndpoint


class Transport(ABC):
    def __init__(
        self,
        address: str,
        timeout: float = 5.0,
    ) -> None:
        self.address = address
        self.timeout = timeout

    @property
    @abstractmethod
    def endpoint(self) -> BaseEndpoint:
        """Return the endpoint represented by this transport."""

    @abstractmethod
    def write(self, data: bytes) -> None:
        """Write data through the transport."""

    @abstractmethod
    def read(self, size: int = 4096) -> bytes:
        """Read up to size bytes from the transport."""

    @abstractmethod
    def open(self) -> None:
        """Open the transport connection."""

    @abstractmethod
    def close(self) -> None:
        """Close the transport connection."""
