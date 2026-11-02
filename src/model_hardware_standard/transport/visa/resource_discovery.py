"""Strategies for discovering VISA resource names."""

from __future__ import annotations

import ipaddress
import math
import re
import socket
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol, TypeAlias


IPv4NetworkInput: TypeAlias = str | ipaddress.IPv4Network
IPv4InterfaceProvider: TypeAlias = Callable[[], Iterable[ipaddress.IPv4Interface]]
PortProbe: TypeAlias = Callable[[str, int, float], bool]

VXI11_PORT = 111
DEFAULT_PROBE_TIMEOUT = 0.25
DEFAULT_MAX_HOSTS = 4096
DEFAULT_MAX_WORKERS = 32
DEFAULT_MAX_CANDIDATES = 32
MAX_HOSTS = 4096
MAX_WORKERS = 128
MAX_CANDIDATES = 256
_LAN_DEVICE_NAME = re.compile(r"[A-Za-z0-9_.-]+")


class VisaResourceDiscoveryStrategy(Protocol):
    """Produce possible VISA resource names without opening instruments."""

    def discover(self) -> Iterable[str]:
        """Return resource names for one finite discovery pass."""
        ...


def _local_ipv4_interfaces() -> Iterator[ipaddress.IPv4Interface]:
    """Return IPv4 interfaces that can identify a local private network."""
    try:
        import psutil
    except ImportError as exc:  # pragma: no cover - dependency is declared.
        raise RuntimeError(
            "psutil is required for automatic local IPv4 VISA discovery"
        ) from exc

    interface_stats = psutil.net_if_stats()
    for name, addresses in psutil.net_if_addrs().items():
        stats = interface_stats.get(name)
        if stats is None or not stats.isup:
            continue
        for address in addresses:
            if address.family != socket.AF_INET or not address.netmask:
                continue
            try:
                interface = ipaddress.ip_interface(
                    f"{address.address}/{address.netmask}"
                )
            except ValueError:
                continue
            if isinstance(interface, ipaddress.IPv4Interface):
                yield interface


def _tcp_port_probe(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _host_count(network: ipaddress.IPv4Network) -> int:
    if network.prefixlen >= 31:
        return network.num_addresses
    return network.num_addresses - 2


def _validate_network(
    value: IPv4NetworkInput,
    *,
    allow_public_networks: bool,
) -> ipaddress.IPv4Network:
    if isinstance(value, ipaddress.IPv4Network):
        network = value
    elif isinstance(value, str):
        try:
            parsed = ipaddress.ip_network(value, strict=True)
        except ValueError as exc:
            raise ValueError(f"Invalid IPv4 network: {value!r}") from exc
        if not isinstance(parsed, ipaddress.IPv4Network):
            raise ValueError(f"Only IPv4 networks are supported: {value!r}")
        network = parsed
    else:
        raise TypeError("VISA subnet must be an IPv4Network or CIDR string")

    if (
        network.is_loopback
        or network.is_multicast
        or network.is_unspecified
        or network.is_reserved
    ):
        raise ValueError(f"Network cannot be scanned: {network}")
    if not allow_public_networks and not (
        network.is_private or network.is_link_local
    ):
        raise ValueError(
            f"Public IPv4 network is disabled by default: {network}"
        )
    return network


def _validate_positive_float(value: float, name: str, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    if not math.isfinite(value) or value <= 0 or value > maximum:
        raise ValueError(f"{name} must be between 0 and {maximum}")
    return float(value)


def _validate_positive_int(value: int, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


class PyVisaListResourceDiscovery:
    """Discover resources through PyVISA's process-shared resource manager."""

    def __init__(self, resource_manager_factory: Callable[[], Any]) -> None:
        self.resource_manager_factory = resource_manager_factory

    def discover(self) -> Iterator[str]:
        manager = self.resource_manager_factory()
        return iter(tuple(manager.list_resources()))


class IPv4SubnetVisaResourceDiscovery:
    """Find VXI-11 VISA candidates on bounded IPv4 networks.

    The strategy only probes the VXI-11 portmapper. A successful port probe
    produces a VISA resource name; the normal VISA candidate later verifies
    the complete connection through ``open_resource``.
    """

    def __init__(
        self,
        subnets: Iterable[IPv4NetworkInput] | None = None,
        *,
        lan_device_name: str = "inst0",
        interface_provider: IPv4InterfaceProvider = _local_ipv4_interfaces,
        port_probe: PortProbe = _tcp_port_probe,
        probe_timeout: float = DEFAULT_PROBE_TIMEOUT,
        max_hosts: int = DEFAULT_MAX_HOSTS,
        max_workers: int = DEFAULT_MAX_WORKERS,
        max_candidates: int = DEFAULT_MAX_CANDIDATES,
        allow_public_networks: bool = False,
    ) -> None:
        if not _LAN_DEVICE_NAME.fullmatch(lan_device_name):
            raise ValueError("lan_device_name contains invalid VISA components")
        if not 1 <= VXI11_PORT <= 65535:  # pragma: no cover - fixed constant.
            raise ValueError("VXI-11 port is invalid")

        self.subnets = None if subnets is None else tuple(subnets)
        self.interface_provider = interface_provider
        self.port_probe = port_probe
        self.probe_timeout = _validate_positive_float(
            probe_timeout, "probe_timeout", 60.0
        )
        self.max_hosts = _validate_positive_int(max_hosts, "max_hosts", MAX_HOSTS)
        self.max_workers = _validate_positive_int(
            max_workers, "max_workers", MAX_WORKERS
        )
        self.max_candidates = _validate_positive_int(
            max_candidates, "max_candidates", MAX_CANDIDATES
        )
        self.allow_public_networks = allow_public_networks
        self.lan_device_name = lan_device_name

    def _networks(self) -> tuple[ipaddress.IPv4Network, ...]:
        inferred = self.subnets is None
        source: Iterable[IPv4NetworkInput]
        if inferred:
            source = (
                interface.network for interface in self.interface_provider()
            )
        else:
            source = self.subnets or ()

        networks: list[ipaddress.IPv4Network] = []
        seen: set[ipaddress.IPv4Network] = set()
        oversized: list[ipaddress.IPv4Network] = []
        total_hosts = 0
        for subnet in source:
            try:
                network = _validate_network(
                    subnet,
                    allow_public_networks=self.allow_public_networks,
                )
            except ValueError:
                if inferred:
                    continue
                raise
            if network in seen:
                continue
            host_count = _host_count(network)
            if inferred and (
                host_count > self.max_hosts
                or total_hosts + host_count > self.max_hosts
            ):
                oversized.append(network)
                continue
            seen.add(network)
            networks.append(network)
            total_hosts += host_count

        if total_hosts > self.max_hosts:
            raise ValueError(
                f"VISA subnet scan has {total_hosts} hosts; "
                f"the limit is {self.max_hosts}"
            )
        if inferred and not networks and oversized:
            skipped = ", ".join(str(network) for network in oversized)
            raise ValueError(
                f"Local VISA networks exceed the {self.max_hosts}-host limit: "
                f"{skipped}; configure a smaller subnet explicitly"
            )
        return tuple(networks)

    def _probe_host(self, host: str) -> bool:
        return self.port_probe(host, VXI11_PORT, self.probe_timeout)

    def discover(self) -> Iterator[str]:
        networks = self._networks()
        hosts = tuple(
            dict.fromkeys(
                str(host)
                for network in networks
                for host in network.hosts()
            )
        )
        if not hosts:
            return iter(())

        worker_count = min(self.max_workers, len(hosts))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            reachable = tuple(executor.map(self._probe_host, hosts))

        resources = tuple(
            f"TCPIP0::{host}::{self.lan_device_name}::INSTR"
            for host, is_reachable in zip(hosts, reachable)
            if is_reachable
        )

        def limited_resources() -> Iterator[str]:
            yield from resources[: self.max_candidates]
            if len(resources) > self.max_candidates:
                raise RuntimeError(
                    f"VISA subnet scan found {len(resources)} portmapper hosts; "
                    f"only the first {self.max_candidates} candidates were returned"
                )

        return limited_resources()


__all__ = [
    "DEFAULT_MAX_CANDIDATES",
    "DEFAULT_MAX_HOSTS",
    "DEFAULT_MAX_WORKERS",
    "DEFAULT_PROBE_TIMEOUT",
    "IPv4SubnetVisaResourceDiscovery",
    "PyVisaListResourceDiscovery",
    "VisaResourceDiscoveryStrategy",
    "VXI11_PORT",
]
