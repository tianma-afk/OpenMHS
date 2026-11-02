from unittest import TestCase
from uuid import uuid4

from pydantic import ValidationError

from src.transport.base.base_endpoint import BaseEndpoint
from src.transport.tcp.tcpendpoint import TCPEndpoint
from src.transport.visa.visaendpoint import VisaEndpoint


class TestEndpointModels(TestCase):
    def test_base_endpoint_has_independent_options_by_default(self):
        first = BaseEndpoint(id=str(uuid4()), type="fake")
        second = BaseEndpoint(id=str(uuid4()), type="fake")

        first.options["address"] = "example"

        self.assertEqual(second.options, {})

    def test_base_endpoint_rejects_invalid_identity_fields(self):
        with self.assertRaises(ValidationError):
            BaseEndpoint(id="short", type="fake")
        with self.assertRaises(ValidationError):
            BaseEndpoint(id=str(uuid4()), type="")

    def test_tcp_endpoint_describes_a_tcp_connection(self):
        endpoint = TCPEndpoint.from_address(" HOST ", 5025)

        self.assertEqual(endpoint.type, "tcp")
        self.assertEqual(endpoint.address, "HOST")
        self.assertEqual(endpoint.port, 5025)
        self.assertEqual(len(endpoint.id), 36)

    def test_tcp_endpoint_id_is_stable_for_connection_details(self):
        first = TCPEndpoint.from_address("host", 5025)
        second = TCPEndpoint.from_address(" HOST ", 5025)
        different_port = TCPEndpoint.from_address("host", 5026)

        self.assertEqual(first.id, second.id)
        self.assertNotEqual(first.id, different_port.id)

    def test_tcp_endpoint_rejects_invalid_ports(self):
        with self.assertRaises(ValidationError):
            TCPEndpoint.from_address("host", 0)
        with self.assertRaises(ValidationError):
            TCPEndpoint.from_address("host", 65536)

    def test_tcp_endpoint_type_is_fixed(self):
        with self.assertRaises(ValidationError):
            TCPEndpoint(
                id=str(uuid4()),
                type="udp",
                address="host",
                port=5025,
            )

    def test_visa_endpoint_normalizes_resource_and_stabilizes_id(self):
        first = VisaEndpoint.from_resource(" TCPIP0::HOST::inst0::INSTR ")
        second = VisaEndpoint.from_resource("tcpip0::host::INST0::instr")

        self.assertEqual(first.type, "visa")
        self.assertEqual(first.resource, "TCPIP0::HOST::inst0::INSTR")
        self.assertEqual(first.id, second.id)

    def test_visa_endpoint_id_changes_for_a_different_resource(self):
        first = VisaEndpoint.from_resource("TCPIP0::host-a::inst0::INSTR")
        second = VisaEndpoint.from_resource("TCPIP0::host-b::inst0::INSTR")

        self.assertNotEqual(first.id, second.id)

    def test_visa_endpoint_rejects_an_empty_resource(self):
        with self.assertRaises(ValueError):
            VisaEndpoint.from_resource("  ")

    def test_visa_endpoint_copies_options(self):
        options = {"backend": "@py"}
        endpoint = VisaEndpoint.from_resource("TCPIP0::host::inst0::INSTR", options=options)

        options["timeout_ms"] = 3000

        self.assertNotIn("timeout_ms", endpoint.options)
