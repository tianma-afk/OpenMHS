from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from src.server.discover.discover import Discovery, discover
from src.server.discover.discovery_error import DiscoveryError
from src.server.discover.discovery_phase import DiscoveryPhase
from src.server.discover.discovery_result import DiscoveryResult
from src.transport.base.base_endpoint import BaseEndpoint
from src.transport.base.transport import Transport


def make_endpoint(kind: str = "fake") -> BaseEndpoint:
    return BaseEndpoint(id=str(uuid4()), type=kind)


class FakeTransport(Transport):
    def __init__(
        self,
        endpoint: BaseEndpoint | None = None,
        *,
        open_error: Exception | None = None,
        close_error: Exception | None = None,
    ) -> None:
        super().__init__("fake")
        self._endpoint = endpoint or make_endpoint()
        self.open_error = open_error
        self.close_error = close_error
        self.opened = False
        self.closed = False
        self.writes: list[bytes] = []
        self.read_count = 0

    @property
    def endpoint(self) -> BaseEndpoint:
        return self._endpoint

    def open(self) -> None:
        if self.open_error is not None:
            raise self.open_error
        self.opened = True

    def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def read(self, size: int = 4096) -> bytes:
        self.read_count += 1
        return b""


class DuckTransport:
    def __init__(self, endpoint: BaseEndpoint) -> None:
        self.endpoint = endpoint
        self.opened = False
        self.closed = False

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True


class FailingEndpointTransport(FakeTransport):
    @property
    def endpoint(self) -> BaseEndpoint:
        raise ValueError("endpoint unavailable")


class FakeTransportModule:
    def __init__(
        self,
        *transports,
        error: Exception | None = None,
    ) -> None:
        self.transports = transports
        self.error = error
        self.calls = 0

    def discover(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return iter(self.transports)


class TestDiscovery(TestCase):
    def test_accepts_connection_only_transport_candidates(self):
        transport = DuckTransport(make_endpoint("duck"))

        result = discover([FakeTransportModule(transport)])

        self.assertIsInstance(result, DiscoveryResult)
        self.assertEqual(result.endpoints, (transport.endpoint,))
        self.assertEqual(result.errors, ())
        self.assertTrue(transport.opened)
        self.assertTrue(transport.closed)

    def test_returns_endpoint_and_only_checks_connectivity(self):
        endpoint = make_endpoint("tcp")
        transport = FakeTransport(endpoint)
        module = FakeTransportModule(transport)

        result = discover([module])

        self.assertEqual(result.endpoints, (endpoint,))
        self.assertEqual(result.errors, ())
        self.assertTrue(transport.opened)
        self.assertTrue(transport.closed)
        self.assertEqual(transport.writes, [])
        self.assertEqual(transport.read_count, 0)

    def test_preserves_endpoint_order_across_modules(self):
        first = FakeTransport(make_endpoint("first"))
        second = FakeTransport(make_endpoint("second"))

        result = discover(
            [
                FakeTransportModule(first),
                FakeTransportModule(second),
            ]
        )

        self.assertEqual(result.endpoints, (first.endpoint, second.endpoint))

    def test_module_failure_does_not_stop_later_modules(self):
        working = FakeTransport(make_endpoint("working"))
        failed_module = FakeTransportModule(error=RuntimeError("enumeration failed"))
        working_module = FakeTransportModule(working)

        result = discover([failed_module, working_module])

        self.assertEqual(result.endpoints, (working.endpoint,))
        self.assertEqual(len(result.errors), 1)
        self.assertIsInstance(result.errors[0], DiscoveryError)
        self.assertIs(result.errors[0].module, failed_module)
        self.assertIsNone(result.errors[0].endpoint)
        self.assertEqual(result.errors[0].phase, DiscoveryPhase.ENUMERATE)

    def test_candidate_failure_does_not_stop_later_candidates(self):
        failed = FakeTransport(open_error=ConnectionError("offline"))
        working = FakeTransport(make_endpoint("working"))
        module = FakeTransportModule(failed, working)

        result = discover([module])

        self.assertEqual(result.endpoints, (working.endpoint,))
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].phase, DiscoveryPhase.OPEN)
        self.assertIs(result.errors[0].endpoint, failed.endpoint)
        self.assertTrue(failed.closed)
        self.assertTrue(working.closed)

    def test_close_failure_is_reported_after_success(self):
        endpoint = make_endpoint()
        transport = FakeTransport(endpoint, close_error=OSError("close failed"))

        result = discover([FakeTransportModule(transport)])

        self.assertEqual(result.endpoints, (endpoint,))
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].phase, DiscoveryPhase.CLOSE)
        self.assertIs(result.errors[0].endpoint, endpoint)

    def test_close_failure_does_not_mask_candidate_failure(self):
        transport = FakeTransport(
            open_error=ConnectionError("offline"),
            close_error=OSError("close failed"),
        )

        result = discover([FakeTransportModule(transport)])

        self.assertEqual(result.endpoints, ())
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].phase, DiscoveryPhase.OPEN)
        self.assertIsInstance(result.errors[0].cleanup_exception, OSError)
        self.assertEqual(str(result.errors[0].exception), "offline")

    def test_endpoint_failure_is_reported_and_transport_is_closed(self):
        transport = FailingEndpointTransport()

        result = discover([FakeTransportModule(transport)])

        self.assertEqual(result.endpoints, ())
        self.assertEqual(result.errors[0].phase, DiscoveryPhase.ENDPOINT)
        self.assertTrue(transport.closed)

    def test_discovery_can_be_reused(self):
        transport = FakeTransport(make_endpoint())
        module = FakeTransportModule(transport)
        discovery = Discovery([module])

        first_result = discovery.discover()
        second_result = discovery.discover()

        self.assertEqual(first_result.endpoints, second_result.endpoints)
        self.assertEqual(module.calls, 2)
        self.assertTrue(transport.closed)

    def test_control_flow_exceptions_propagate_after_cleanup(self):
        transport = FakeTransport()
        with patch.object(transport, "open", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                discover([FakeTransportModule(transport)])
        self.assertTrue(transport.closed)
