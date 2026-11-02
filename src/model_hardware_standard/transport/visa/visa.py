"""PyVISA-py transport candidates for endpoint discovery."""

from __future__ import annotations

from builtins import ExceptionGroup
from collections.abc import Callable, Iterable, Iterator
from threading import Lock
from typing import Any

from ..base.transport_module import TransportCandidate
from .resource_discovery import (
    IPv4NetworkInput,
    IPv4SubnetVisaResourceDiscovery,
    PyVisaListResourceDiscovery,
    VisaResourceDiscoveryStrategy,
)
from .visaendpoint import VisaEndpoint

try:
    import pyvisa
except ImportError:  # pragma: no cover - exercised through the default factory.
    pyvisa = None  # type: ignore[assignment]


PYVISA_BACKEND = "@py"
DEFAULT_OPEN_TIMEOUT_MS = 2000
MAX_OPEN_TIMEOUT_MS = 60_000
ResourceManagerFactory = Callable[[], Any]
TransportFactory = Callable[..., TransportCandidate]


def _validate_open_timeout_ms(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("open_timeout_ms must be an integer")
    if value < 1 or value > MAX_OPEN_TIMEOUT_MS:
        raise ValueError(
            f"open_timeout_ms must be between 1 and {MAX_OPEN_TIMEOUT_MS}"
        )
    return value


def _canonical_resource(resource: str) -> str:
    normalized_resource = VisaEndpoint.from_resource(resource).resource
    if pyvisa is None:
        return normalized_resource

    try:
        canonicalizer = getattr(pyvisa, "rname", None)
        canonical_name = canonicalizer.to_canonical_name(normalized_resource)
    except Exception:
        return normalized_resource

    if not isinstance(canonical_name, str) or not canonical_name.strip():
        return normalized_resource
    return canonical_name.strip()


def create_pyvisa_resource_manager() -> Any:
    """Create a ResourceManager using only the PyVISA-py backend."""
    if pyvisa is None:
        raise RuntimeError(
            "PyVISA and pyvisa-py are required for VISA transport discovery"
        )
    return pyvisa.ResourceManager(PYVISA_BACKEND)


def _close_resource(resource: Any) -> None:
    if resource is not None:
        resource.close()


class VisaTransport:
    """A short-lived, connection-only candidate backed by PyVISA-py."""

    def __init__(
        self,
        endpoint: VisaEndpoint | str,
        *,
        resource_manager_factory: ResourceManagerFactory = create_pyvisa_resource_manager,
        open_timeout_ms: int = DEFAULT_OPEN_TIMEOUT_MS,
    ) -> None:
        self._endpoint = (
            endpoint
            if isinstance(endpoint, VisaEndpoint)
            else VisaEndpoint.from_resource(_canonical_resource(endpoint))
        )
        self.resource_manager_factory = resource_manager_factory
        self.open_timeout_ms = _validate_open_timeout_ms(open_timeout_ms)
        self._resource_manager: Any = None
        self._resource: Any = None
        self._lifecycle_lock = Lock()

    @property
    def endpoint(self) -> VisaEndpoint:
        return self._endpoint

    @property
    def is_open(self) -> bool:
        with self._lifecycle_lock:
            return self._resource is not None

    def open(self) -> None:
        with self._lifecycle_lock:
            if self._resource is not None:
                return

            manager = self.resource_manager_factory()
            resource = None
            try:
                resource = manager.open_resource(
                    self.endpoint.resource,
                    open_timeout=self.open_timeout_ms,
                )
                if resource is None:
                    raise RuntimeError("VISA ResourceManager returned no resource")
            except BaseException as primary:
                try:
                    _close_resource(resource)
                except BaseException as cleanup:
                    raise primary from cleanup
                raise

            self._resource_manager = manager  # Keep the shared manager alive.
            self._resource = resource

    def close(self) -> None:
        with self._lifecycle_lock:
            resource = self._resource
            self._resource = None
            try:
                _close_resource(resource)
            finally:
                self._resource_manager = None


class VisaTransportModule:
    """Enumerate VISA resources using composable, one-shot strategies."""

    def __init__(
        self,
        *,
        resources: Iterable[str] = (),
        resource_discoveries: Iterable[VisaResourceDiscoveryStrategy] | None = None,
        auto_discover_local_networks: bool = True,
        subnets: Iterable[IPv4NetworkInput] | None = None,
        resource_manager_factory: ResourceManagerFactory = create_pyvisa_resource_manager,
        transport_factory: TransportFactory = VisaTransport,
        open_timeout_ms: int = DEFAULT_OPEN_TIMEOUT_MS,
    ) -> None:
        if resource_discoveries is not None:
            strategies = list(resource_discoveries)
        else:
            strategies = [PyVisaListResourceDiscovery(resource_manager_factory)]
            if auto_discover_local_networks or subnets is not None:
                strategies.append(IPv4SubnetVisaResourceDiscovery(subnets))

        self.resources = tuple(_canonical_resource(resource) for resource in resources)
        self.resource_discoveries = tuple(strategies)
        self.resource_manager_factory = resource_manager_factory
        self.transport_factory = transport_factory
        self.open_timeout_ms = _validate_open_timeout_ms(open_timeout_ms)

    def discover(self) -> Iterator[TransportCandidate]:
        """Return fresh candidates, reporting strategy failures after them."""
        resource_names: list[str] = []
        failures: list[Exception] = []

        for strategy in self.resource_discoveries:
            try:
                for resource in strategy.discover():
                    resource_names.append(_canonical_resource(resource))
            except Exception as exc:
                failures.append(exc)

        resource_names.extend(self.resources)
        seen: set[str] = set()
        unique_resources: list[str] = []
        for resource in resource_names:
            normalized_resource = _canonical_resource(resource)
            key = normalized_resource.casefold()
            if key in seen:
                continue
            seen.add(key)
            unique_resources.append(normalized_resource)

        candidates: list[TransportCandidate] = []
        for resource in unique_resources:
            try:
                candidate = self.transport_factory(
                    VisaEndpoint.from_resource(resource),
                    resource_manager_factory=self.resource_manager_factory,
                    open_timeout_ms=self.open_timeout_ms,
                )
            except Exception as exc:
                failures.append(exc)
                continue
            candidates.append(candidate)
        yield from candidates

        if failures:
            raise ExceptionGroup("VISA resource discovery failed", failures)


__all__ = [
    "DEFAULT_OPEN_TIMEOUT_MS",
    "MAX_OPEN_TIMEOUT_MS",
    "PYVISA_BACKEND",
    "ResourceManagerFactory",
    "TransportFactory",
    "VisaEndpoint",
    "VisaTransport",
    "VisaTransportModule",
    "create_pyvisa_resource_manager",
]
