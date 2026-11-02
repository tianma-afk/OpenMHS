"""Errors reported during connectivity discovery."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from ...transport.base.base_endpoint import BaseEndpoint
    from ...transport.base.transport_module import TransportModule
except ImportError:  # pragma: no cover - supports running with ``src`` on sys.path.
    from transport.base.base_endpoint import BaseEndpoint
    from transport.base.transport_module import TransportModule

from .discovery_phase import DiscoveryPhase


@dataclass(frozen=True)
class DiscoveryError:
    """A failure while enumerating or checking one connection candidate."""

    module: TransportModule
    endpoint: BaseEndpoint | None
    phase: DiscoveryPhase
    exception: Exception
    cleanup_exception: Exception | None = None

    @property
    def message(self) -> str:
        return str(self.exception)


__all__ = ["DiscoveryError"]
