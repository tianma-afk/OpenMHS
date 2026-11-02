from builtins import ExceptionGroup
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import sleep
from unittest import TestCase
from unittest.mock import Mock, patch

from src.server.discover.discover import Discovery
from src.transport.visa.resource_discovery import IPv4SubnetVisaResourceDiscovery
from src.transport.visa.visa import (
    PYVISA_BACKEND,
    VisaTransport,
    VisaTransportModule,
    create_pyvisa_resource_manager,
)
from src.transport.visa.visaendpoint import VisaEndpoint


RESOURCE = "TCPIP0::192.168.3.91::inst0::INSTR"


class FakeVisaResource:
    def __init__(self, log: list[object], *, close_error: Exception | None = None) -> None:
        self.log = log
        self.close_error = close_error
        self.closed = False
        self.query = Mock()
        self.read = Mock()
        self.write = Mock()

    def close(self) -> None:
        self.log.append("resource.close")
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class FakeResourceManager:
    def __init__(
        self,
        resources: tuple[str, ...] = (),
        *,
        resource: FakeVisaResource | None = None,
        list_error: Exception | None = None,
        open_error: Exception | None = None,
        close_error: Exception | None = None,
        log: list[object] | None = None,
    ) -> None:
        self.resources = resources
        self.resource = resource
        self.list_error = list_error
        self.open_error = open_error
        self.close_error = close_error
        self.log = log if log is not None else []
        self.closed = False
        self.list_calls = 0
        self.opened_resources: list[str] = []
        self.open_timeouts: list[int | None] = []

    def list_resources(self) -> tuple[str, ...]:
        self.log.append("manager.list_resources")
        self.list_calls += 1
        if self.list_error is not None:
            raise self.list_error
        return self.resources

    def open_resource(
        self,
        resource: str,
        *,
        open_timeout: int | None = None,
    ) -> FakeVisaResource:
        self.log.append(("manager.open_resource", resource, open_timeout))
        self.opened_resources.append(resource)
        self.open_timeouts.append(open_timeout)
        if self.open_error is not None:
            raise self.open_error
        if self.resource is None:
            raise AssertionError("A fake VISA resource was not configured")
        return self.resource

    def close(self) -> None:
        self.log.append("manager.close")
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class SequentialManagerFactory:
    def __init__(self, *managers: FakeResourceManager) -> None:
        self.managers = list(managers)
        self.calls = 0

    def __call__(self) -> FakeResourceManager:
        manager = self.managers[self.calls]
        self.calls += 1
        return manager


class StaticResourceDiscovery:
    def __init__(self, *resources: str, error: Exception | None = None) -> None:
        self.resources = resources
        self.error = error

    def discover(self):
        if self.error is not None:
            raise self.error
        return iter(self.resources)


class TestVisaTransport(TestCase):
    def test_default_factory_selects_pyvisa_py_explicitly(self):
        manager = Mock()
        with patch("src.transport.visa.visa.pyvisa") as pyvisa:
            pyvisa.ResourceManager.return_value = manager

            result = create_pyvisa_resource_manager()

        self.assertIs(result, manager)
        pyvisa.ResourceManager.assert_called_once_with(PYVISA_BACKEND)

    def test_default_factory_does_not_fallback_when_pyvisa_py_fails(self):
        with patch("src.transport.visa.visa.pyvisa") as pyvisa:
            pyvisa.ResourceManager.side_effect = RuntimeError("backend unavailable")

            with self.assertRaisesRegex(RuntimeError, "backend unavailable"):
                create_pyvisa_resource_manager()

        pyvisa.ResourceManager.assert_called_once_with(PYVISA_BACKEND)

    def test_default_factory_reports_a_missing_pyvisa_install(self):
        with patch("src.transport.visa.visa.pyvisa", None):
            with self.assertRaisesRegex(RuntimeError, "pyvisa-py"):
                create_pyvisa_resource_manager()

    def test_module_materializes_resources_before_creating_candidates(self):
        manager = FakeResourceManager((RESOURCE, "TCPIP0::192.168.3.92::inst0::INSTR"))
        created_after_enumeration: list[bool] = []

        def transport_factory(
            endpoint,
            *,
            resource_manager_factory,
            open_timeout_ms,
        ):
            created_after_enumeration.append(manager.list_calls == 1)
            return VisaTransport(
                endpoint,
                resource_manager_factory=resource_manager_factory,
                open_timeout_ms=open_timeout_ms,
            )

        module = VisaTransportModule(
            auto_discover_local_networks=False,
            resource_manager_factory=lambda: manager,
            transport_factory=transport_factory,
        )

        candidates = tuple(module.discover())

        self.assertFalse(manager.closed)
        self.assertEqual(created_after_enumeration, [True, True])
        self.assertEqual(
            [candidate.endpoint.resource for candidate in candidates],
            [RESOURCE, "TCPIP0::192.168.3.92::inst0::INSTR"],
        )
        self.assertEqual(manager.list_calls, 1)
        self.assertEqual(manager.opened_resources, [])

    def test_module_keeps_shared_manager_open_when_enumeration_fails(self):
        manager = FakeResourceManager(list_error=OSError("enumeration failed"))
        module = VisaTransportModule(
            auto_discover_local_networks=False,
            resource_manager_factory=lambda: manager,
        )

        with self.assertRaises(ExceptionGroup) as context:
            tuple(module.discover())

        self.assertIsInstance(context.exception.exceptions[0], OSError)
        self.assertFalse(manager.closed)

    def test_module_includes_configured_resources_when_enumeration_is_empty(self):
        manager = FakeResourceManager()
        module = VisaTransportModule(
            resources=(RESOURCE,),
            auto_discover_local_networks=False,
            resource_manager_factory=lambda: manager,
        )

        candidates = tuple(module.discover())

        self.assertEqual([candidate.endpoint.resource for candidate in candidates], [RESOURCE])
        self.assertFalse(manager.closed)

    def test_module_returns_fresh_candidates_for_each_scan(self):
        first_manager = FakeResourceManager((RESOURCE,))
        second_manager = FakeResourceManager((RESOURCE,))
        factory = SequentialManagerFactory(first_manager, second_manager)
        module = VisaTransportModule(
            auto_discover_local_networks=False,
            resource_manager_factory=factory,
        )

        first = tuple(module.discover())
        second = tuple(module.discover())

        self.assertIsNot(first[0], second[0])
        self.assertEqual(first[0].endpoint.id, second[0].endpoint.id)
        self.assertEqual(factory.calls, 2)
        self.assertFalse(first_manager.closed)
        self.assertFalse(second_manager.closed)

    def test_candidate_opens_exact_resource_and_is_idempotent(self):
        log: list[object] = []
        resource = FakeVisaResource(log)
        manager = FakeResourceManager(resource=resource, log=log)
        candidate = VisaTransport(
            VisaEndpoint.from_resource(RESOURCE),
            resource_manager_factory=lambda: manager,
        )

        candidate.open()
        candidate.open()

        self.assertTrue(candidate.is_open)
        self.assertEqual(manager.opened_resources, [RESOURCE])
        self.assertEqual(manager.open_timeouts, [2000])
        self.assertEqual(manager.list_calls, 0)

        candidate.close()
        candidate.close()

        self.assertFalse(candidate.is_open)
        self.assertTrue(resource.closed)
        self.assertFalse(manager.closed)
        self.assertEqual(log.count("resource.close"), 1)
        self.assertEqual(log.count("manager.close"), 0)

    def test_candidate_serializes_concurrent_open_calls(self):
        log: list[object] = []
        resource = FakeVisaResource(log)
        manager = FakeResourceManager(resource=resource, log=log)
        original_open = manager.open_resource
        barrier = Barrier(3)

        def delayed_open(*args, **kwargs):
            sleep(0.02)
            return original_open(*args, **kwargs)

        manager.open_resource = delayed_open
        candidate = VisaTransport(
            VisaEndpoint.from_resource(RESOURCE),
            resource_manager_factory=lambda: manager,
        )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(lambda: (barrier.wait(), candidate.open()))
                for _ in range(2)
            ]
            barrier.wait()
            for future in futures:
                future.result()

        self.assertEqual(manager.opened_resources, [RESOURCE])
        candidate.close()
        self.assertEqual(log.count("resource.close"), 1)

    def test_candidate_open_failure_keeps_shared_manager_open(self):
        manager = FakeResourceManager(open_error=OSError("open failed"))
        candidate = VisaTransport(
            VisaEndpoint.from_resource(RESOURCE),
            resource_manager_factory=lambda: manager,
        )

        with self.assertRaisesRegex(OSError, "open failed"):
            candidate.open()

        self.assertFalse(candidate.is_open)
        self.assertFalse(manager.closed)

    def test_candidate_close_keeps_manager_open_after_resource_failure(self):
        log: list[object] = []
        resource = FakeVisaResource(log, close_error=OSError("resource close failed"))
        manager = FakeResourceManager(resource=resource, log=log)
        candidate = VisaTransport(
            VisaEndpoint.from_resource(RESOURCE),
            resource_manager_factory=lambda: manager,
        )
        candidate.open()

        with self.assertRaisesRegex(OSError, "resource close failed"):
            candidate.close()

        self.assertFalse(candidate.is_open)
        self.assertTrue(resource.closed)
        self.assertFalse(manager.closed)
        self.assertNotIn("manager.close", log)

    def test_module_composes_strategies_and_deduplicates_visa_aliases(self):
        manager = FakeResourceManager(
            resource=FakeVisaResource([]),
        )
        module = VisaTransportModule(
            resources=(RESOURCE,),
            resource_discoveries=(
                StaticResourceDiscovery("TCPIP::192.168.3.91::INSTR"),
                IPv4SubnetVisaResourceDiscovery(
                    ("192.168.3.90/31",),
                    port_probe=lambda *_: True,
                ),
            ),
            resource_manager_factory=lambda: manager,
            open_timeout_ms=1234,
        )

        candidates = tuple(module.discover())

        self.assertEqual(
            [candidate.endpoint.resource for candidate in candidates],
            [
                "TCPIP0::192.168.3.91::inst0::INSTR",
                "TCPIP0::192.168.3.90::inst0::INSTR",
            ],
        )
        self.assertEqual(candidates[0].open_timeout_ms, 1234)

    def test_candidate_factory_failure_keeps_other_candidates(self):
        def transport_factory(
            endpoint,
            *,
            resource_manager_factory,
            open_timeout_ms,
        ):
            if endpoint.resource.endswith(".90::inst0::INSTR"):
                raise ValueError("candidate failed")
            return VisaTransport(
                endpoint,
                resource_manager_factory=resource_manager_factory,
                open_timeout_ms=open_timeout_ms,
            )

        module = VisaTransportModule(
            resource_discoveries=(
                StaticResourceDiscovery(
                    "TCPIP0::192.168.3.90::inst0::INSTR",
                    RESOURCE,
                ),
            ),
            resource_manager_factory=lambda: FakeResourceManager(),
            transport_factory=transport_factory,
        )

        iterator = module.discover()
        candidate = next(iterator)
        self.assertEqual(candidate.endpoint.resource, RESOURCE)
        with self.assertRaises(ExceptionGroup) as context:
            next(iterator)
        self.assertIsInstance(context.exception.exceptions[0], ValueError)

    def test_strategy_failure_keeps_other_candidates_and_is_reported(self):
        log: list[object] = []
        resource = FakeVisaResource(log)
        manager = FakeResourceManager(resource=resource, log=log)
        module = VisaTransportModule(
            resources=(RESOURCE,),
            resource_discoveries=(
                StaticResourceDiscovery(error=OSError("strategy failed")),
            ),
            resource_manager_factory=lambda: manager,
        )

        result = Discovery([module]).discover()

        self.assertEqual(len(result.endpoints), 1)
        self.assertEqual(result.endpoints[0].resource, RESOURCE)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].phase.value, "enumerate")
        self.assertIsInstance(result.errors[0].exception, ExceptionGroup)
        self.assertIsInstance(result.errors[0].exception.exceptions[0], OSError)

    def test_discovery_uses_visa_candidates_without_instrument_io(self):
        enum_manager = FakeResourceManager((RESOURCE,))
        log: list[object] = []
        resource = FakeVisaResource(log)
        probe_manager = FakeResourceManager(resource=resource, log=log)
        manager_factory = SequentialManagerFactory(enum_manager, probe_manager)
        module = VisaTransportModule(
            auto_discover_local_networks=False,
            resource_manager_factory=manager_factory,
        )

        result = Discovery([module]).discover()

        self.assertEqual(len(result.endpoints), 1)
        self.assertEqual(result.endpoints[0].resource, RESOURCE)
        self.assertEqual(result.errors, ())
        self.assertEqual(resource.query.call_count, 0)
        self.assertEqual(resource.read.call_count, 0)
        self.assertEqual(resource.write.call_count, 0)
        self.assertFalse(enum_manager.closed)
        self.assertTrue(resource.closed)
        self.assertFalse(probe_manager.closed)
