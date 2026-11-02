from ipaddress import IPv4Interface
from unittest import TestCase

from src.transport.visa.resource_discovery import (
    IPv4SubnetVisaResourceDiscovery,
    PyVisaListResourceDiscovery,
    VXI11_PORT,
)


class FakeResourceManager:
    def __init__(
        self,
        resources: tuple[str, ...] = (),
        *,
        list_error: Exception | None = None,
    ) -> None:
        self.resources = resources
        self.list_error = list_error
        self.closed = False

    def list_resources(self) -> tuple[str, ...]:
        if self.list_error is not None:
            raise self.list_error
        return self.resources

    def close(self) -> None:
        self.closed = True


class TestPyVisaListResourceDiscovery(TestCase):
    def test_materializes_resources_without_closing_shared_manager(self):
        manager = FakeResourceManager(("TCPIP::192.168.3.91::INSTR",))
        strategy = PyVisaListResourceDiscovery(lambda: manager)

        resources = tuple(strategy.discover())

        self.assertEqual(resources, ("TCPIP::192.168.3.91::INSTR",))
        self.assertFalse(manager.closed)

    def test_keeps_shared_manager_open_when_enumeration_fails(self):
        manager = FakeResourceManager(list_error=OSError("list failed"))
        strategy = PyVisaListResourceDiscovery(lambda: manager)

        with self.assertRaisesRegex(OSError, "list failed"):
            tuple(strategy.discover())

        self.assertFalse(manager.closed)


class TestIPv4SubnetVisaResourceDiscovery(TestCase):
    def test_probes_hosts_and_formats_vxi11_resources(self):
        probes: list[tuple[str, int, float]] = []

        def probe(host: str, port: int, timeout: float) -> bool:
            probes.append((host, port, timeout))
            return host == "192.168.3.1"

        strategy = IPv4SubnetVisaResourceDiscovery(
            ("192.168.3.0/30",),
            port_probe=probe,
            probe_timeout=0.5,
            max_workers=1,
        )

        resources = tuple(strategy.discover())

        self.assertEqual(
            resources,
            ("TCPIP0::192.168.3.1::inst0::INSTR",),
        )
        self.assertEqual(
            [host for host, _, _ in probes],
            ["192.168.3.1", "192.168.3.2"],
        )
        self.assertTrue(all(port == VXI11_PORT for _, port, _ in probes))
        self.assertTrue(all(timeout == 0.5 for _, _, timeout in probes))

    def test_excludes_network_and_broadcast_addresses(self):
        probed: list[str] = []
        strategy = IPv4SubnetVisaResourceDiscovery(
            ("192.168.3.0/30",),
            port_probe=lambda host, _, __: probed.append(host) or False,
        )

        self.assertEqual(tuple(strategy.discover()), ())
        self.assertCountEqual(probed, ["192.168.3.1", "192.168.3.2"])

    def test_can_derive_a_configured_network_from_an_interface(self):
        probed: list[str] = []
        strategy = IPv4SubnetVisaResourceDiscovery(
            None,
            interface_provider=lambda: (IPv4Interface("192.168.3.1/30"),),
            port_probe=lambda host, _, __: probed.append(host) or True,
        )

        self.assertEqual(
            tuple(strategy.discover()),
            (
                "TCPIP0::192.168.3.1::inst0::INSTR",
                "TCPIP0::192.168.3.2::inst0::INSTR",
            ),
        )
        self.assertCountEqual(probed, ["192.168.3.1", "192.168.3.2"])

    def test_automatic_scan_skips_loopback_and_public_interfaces(self):
        probed: list[str] = []
        strategy = IPv4SubnetVisaResourceDiscovery(
            None,
            interface_provider=lambda: (
                IPv4Interface("127.0.0.1/8"),
                IPv4Interface("8.8.8.1/30"),
                IPv4Interface("192.168.3.1/30"),
            ),
            port_probe=lambda host, _, __: probed.append(host) or False,
        )

        self.assertEqual(tuple(strategy.discover()), ())
        self.assertCountEqual(probed, ["192.168.3.1", "192.168.3.2"])

    def test_automatic_scan_skips_an_interface_over_the_host_limit(self):
        probed: list[str] = []
        strategy = IPv4SubnetVisaResourceDiscovery(
            None,
            interface_provider=lambda: (
                IPv4Interface("169.254.1.1/16"),
                IPv4Interface("192.168.3.1/30"),
            ),
            port_probe=lambda host, _, __: probed.append(host) or False,
            max_hosts=256,
        )

        self.assertEqual(tuple(strategy.discover()), ())
        self.assertCountEqual(probed, ["192.168.3.1", "192.168.3.2"])

    def test_automatic_scan_reports_when_only_network_is_too_large(self):
        strategy = IPv4SubnetVisaResourceDiscovery(
            None,
            interface_provider=lambda: (IPv4Interface("169.254.1.1/16"),),
            port_probe=lambda *_: False,
            max_hosts=256,
        )

        with self.assertRaisesRegex(ValueError, "configure a smaller subnet"):
            tuple(strategy.discover())

    def test_limits_false_positive_portmapper_candidates(self):
        strategy = IPv4SubnetVisaResourceDiscovery(
            ("192.168.3.0/29",),
            port_probe=lambda *_: True,
            max_candidates=2,
            max_workers=1,
        )

        iterator = strategy.discover()
        self.assertEqual(
            (next(iterator), next(iterator)),
            (
                "TCPIP0::192.168.3.1::inst0::INSTR",
                "TCPIP0::192.168.3.2::inst0::INSTR",
            ),
        )
        with self.assertRaisesRegex(RuntimeError, "only the first 2"):
            next(iterator)

    def test_empty_subnets_do_not_consult_interfaces_or_probe(self):
        interface_calls = 0
        probe_calls = 0

        def interfaces():
            nonlocal interface_calls
            interface_calls += 1
            return (IPv4Interface("192.168.3.1/30"),)

        def probe(*args):
            nonlocal probe_calls
            probe_calls += 1
            return True

        strategy = IPv4SubnetVisaResourceDiscovery(
            (),
            interface_provider=interfaces,
            port_probe=probe,
        )

        self.assertEqual(tuple(strategy.discover()), ())
        self.assertEqual(interface_calls, 0)
        self.assertEqual(probe_calls, 0)

    def test_supports_a_custom_vxi11_device_name(self):
        strategy = IPv4SubnetVisaResourceDiscovery(
            ("192.168.3.0/31",),
            lan_device_name="inst1",
            port_probe=lambda *_: True,
        )

        self.assertEqual(
            tuple(strategy.discover()),
            (
                "TCPIP0::192.168.3.0::inst1::INSTR",
                "TCPIP0::192.168.3.1::inst1::INSTR",
            ),
        )

    def test_rejects_invalid_or_unsafe_networks(self):
        invalid_networks = (
            "192.168.3.1/24",
            "2001:db8::/64",
            "not-a-network",
            "127.0.0.0/8",
            "224.0.0.0/4",
            "0.0.0.0/0",
            "8.8.8.0/24",
        )

        for subnet in invalid_networks:
            with self.subTest(subnet=subnet), self.assertRaises((TypeError, ValueError)):
                IPv4SubnetVisaResourceDiscovery((subnet,)).discover()

    def test_allows_a_public_network_only_when_explicitly_enabled(self):
        strategy = IPv4SubnetVisaResourceDiscovery(
            ("8.8.8.0/30",),
            allow_public_networks=True,
            port_probe=lambda *_: True,
        )

        self.assertEqual(
            tuple(strategy.discover()),
            (
                "TCPIP0::8.8.8.1::inst0::INSTR",
                "TCPIP0::8.8.8.2::inst0::INSTR",
            ),
        )

    def test_rejects_a_scan_over_the_host_limit(self):
        strategy = IPv4SubnetVisaResourceDiscovery(
            ("192.168.0.0/24", "192.168.1.0/24"),
            max_hosts=256,
            port_probe=lambda *_: True,
        )

        with self.assertRaisesRegex(ValueError, "limit is 256"):
            tuple(strategy.discover())

    def test_rejects_invalid_limits_and_device_names(self):
        with self.assertRaises(ValueError):
            IPv4SubnetVisaResourceDiscovery(("192.168.3.0/30",), max_hosts=0)
        with self.assertRaises(ValueError):
            IPv4SubnetVisaResourceDiscovery(("192.168.3.0/30",), max_hosts=4097)
        with self.assertRaises(ValueError):
            IPv4SubnetVisaResourceDiscovery(
                ("192.168.3.0/30",), max_candidates=257
            )
        with self.assertRaises(ValueError):
            IPv4SubnetVisaResourceDiscovery(
                ("192.168.3.0/30",), lan_device_name="inst0::bad"
            )
