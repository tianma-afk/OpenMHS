"""Connectivity discovery through transport modules."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

try:
    from ...transport.base.base_endpoint import BaseEndpoint
    from ...transport.base.transport_module import TransportCandidate, TransportModule
except ImportError:  # pragma: no cover - supports running with ``src`` on sys.path.
    from transport.base.base_endpoint import BaseEndpoint
    from transport.base.transport_module import TransportCandidate, TransportModule

from . import discovery_error, discovery_phase, discovery_result


def _normalize_modules(
    modules: Iterable[TransportModule],
) -> tuple[TransportModule, ...]:
    return tuple(modules)


class Discovery:
    """Find reachable endpoints exposed by caller-supplied transport modules.

    Discovery owns each candidate probe connection and always closes it, even
    when opening or endpoint acquisition fails. It does not identify devices,
    register them, or retain a live connection.
    """

    def __init__(self, modules: Iterable[TransportModule] = ()) -> None:
        self.modules = _normalize_modules(modules)

    def discover(
        self,
        modules: Iterable[TransportModule] | None = None,
    ) -> discovery_result.DiscoveryResult:
        """Enumerate modules and return reachable endpoint models."""
        normalized_modules = self.modules if modules is None else _normalize_modules(modules)
        endpoints: list[BaseEndpoint] = []
        errors: list[discovery_error.DiscoveryError] = []

        for module in normalized_modules:
            try:
                candidates = iter(module.discover())
            except Exception as exc:
                errors.append(
                    discovery_error.DiscoveryError(module, None, discovery_phase.DiscoveryPhase.ENUMERATE, exc)
                )
                continue

            while True:
                try:
                    candidate = next(candidates)
                except StopIteration:
                    break
                except Exception as exc:
                    errors.append(
                        discovery_error.DiscoveryError(module, None, discovery_phase.DiscoveryPhase.ENUMERATE, exc)
                    )
                    break

                endpoint, error = self._discover_candidate(module, candidate)
                if endpoint is not None:
                    endpoints.append(endpoint)
                if error is not None:
                    errors.append(error)

        return discovery_result.DiscoveryResult(tuple(endpoints), tuple(errors))

    def _discover_candidate(
        self,
        module: TransportModule,
        transport: TransportCandidate,
    ) -> tuple[BaseEndpoint | None, discovery_error.DiscoveryError | None]:
        endpoint: BaseEndpoint | None = None
        error: discovery_error.DiscoveryError | None = None
        connected = False
        phase = discovery_phase.DiscoveryPhase.ENDPOINT

        try:
            endpoint = transport.endpoint
            if not isinstance(endpoint, BaseEndpoint):
                raise TypeError("Transport.endpoint must return a BaseEndpoint")

            phase = discovery_phase.DiscoveryPhase.OPEN
            transport.open()
            connected = True
        except Exception as exc:
            error = discovery_error.DiscoveryError(module, endpoint, phase, exc)
        finally:
            try:
                transport.close()
            except Exception as close_exc:
                if error is None:
                    error = discovery_error.DiscoveryError(
                        module,
                        endpoint,
                        discovery_phase.DiscoveryPhase.CLOSE,
                        close_exc,
                    )
                else:
                    error = replace(error, cleanup_exception=close_exc)

        return (endpoint if connected else None), error


def discover(modules: Iterable[TransportModule]) -> discovery_result.DiscoveryResult:
    """Discover reachable endpoints through transport modules."""
    return Discovery(modules).discover()


__all__ = ["Discovery", "discover"]
