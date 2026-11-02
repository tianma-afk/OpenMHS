import socket
from collections.abc import Iterable, Iterator
from typing import Callable

from ..base.base_endpoint import BaseEndpoint
from ..base.transport import Transport
from ..base.transport_module import TransportCandidate
from .tcpendpoint import TCPEndpoint


class TCPTransport(Transport):

    def __init__(
        self,
        address: str,
        port: int,
        timeout: float = 5.0,
    ) -> None:
        normalized_address = address.strip()
        super().__init__(normalized_address, timeout)

        self.port = port
        self._endpoint = TCPEndpoint.from_address(normalized_address, port)
        self._socket: socket.socket | None = None

    @property
    def endpoint(self) -> BaseEndpoint:
        return self._endpoint

    @property
    def is_open(self) -> bool:
        return self._socket is not None

    def open(self) -> None:
        if self._socket is not None:
            return

        self._socket = socket.create_connection(
            (self.address, self.port),
            timeout=self.timeout,
        )

    def close(self) -> None:
        socket_, self._socket = self._socket, None
        if socket_ is not None:
            socket_.close()

    def write(self, data: bytes) -> None:
        if self._socket is None:
            raise RuntimeError("Transport is not open")

        self._socket.sendall(data)

    def read(self, size: int = 4096) -> bytes:
        if self._socket is None:
            raise RuntimeError("Transport is not open")

        return self._socket.recv(size)


class TCPTransportModule:
    """Enumerate configured TCP connection candidates."""

    def __init__(
        self,
        targets: Iterable[tuple[str, int]],
        *,
        timeout: float = 5.0,
        transport_factory: Callable[..., TransportCandidate] = TCPTransport,
    ) -> None:
        self.targets = tuple(
            self._normalize_target(address, port) for address, port in targets
        )
        self.timeout = timeout
        self.transport_factory = transport_factory

    @staticmethod
    def _normalize_target(address: str, port: int) -> tuple[str, int]:
        endpoint = TCPEndpoint.from_address(address, port)
        return endpoint.address, endpoint.port

    def discover(self) -> Iterator[TransportCandidate]:
        """Yield a fresh, closed transport for each configured target."""
        for address, port in self.targets:
            yield self.transport_factory(
                address=address,
                port=port,
                timeout=self.timeout,
            )
