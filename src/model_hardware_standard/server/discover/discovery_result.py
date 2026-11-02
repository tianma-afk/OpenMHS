"""Results returned by connectivity discovery."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from ...transport.base.base_endpoint import BaseEndpoint
except ImportError:  # pragma: no cover - supports running with ``src`` on sys.path.
    from transport.base.base_endpoint import BaseEndpoint

from .discovery_error import DiscoveryError


@dataclass(frozen=True)
class DiscoveryResult:
    """Ordered reachable endpoints and non-fatal discovery failures."""

    endpoints: tuple[BaseEndpoint, ...]
    errors: tuple[DiscoveryError, ...]


__all__ = ["DiscoveryResult"]
