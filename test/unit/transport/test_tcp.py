from unittest import TestCase
from unittest.mock import Mock, patch

from src.transport.tcp.tcp import TCPTransport, TCPTransportModule


ADDRESS = "192.168.1.20"
PORT = 5025


class TestTCPTransport(TestCase):
    def make_transport(self, timeout: float = 5.0) -> TCPTransport:
        return TCPTransport(
            address=ADDRESS,
            port=PORT,
            timeout=timeout,
        )

    def test_endpoint_describes_the_transport_connection(self):
        transport = self.make_transport()

        endpoint = transport.endpoint

        self.assertEqual(endpoint.type, "tcp")
        self.assertEqual(endpoint.address, ADDRESS)
        self.assertEqual(endpoint.port, PORT)
        self.assertEqual(len(endpoint.id), 36)

    def test_transport_module_yields_closed_candidates(self):
        module = TCPTransportModule([(ADDRESS, PORT)], timeout=2.5)

        candidates = tuple(module.discover())

        self.assertEqual(len(candidates), 1)
        self.assertIsInstance(candidates[0], TCPTransport)
        self.assertFalse(candidates[0].is_open)
        self.assertEqual(candidates[0].endpoint.address, ADDRESS)
        self.assertEqual(candidates[0].endpoint.port, PORT)

    def test_open_connects_to_address_and_stores_socket(self):
        transport = self.make_transport(timeout=2.5)
        fake_socket = Mock()

        with patch(
            "src.transport.tcp.tcp.socket.create_connection",
            return_value=fake_socket,
        ) as create_connection:
            transport.open()

        create_connection.assert_called_once_with(
            (ADDRESS, PORT),
            timeout=2.5,
        )
        self.assertIs(transport._socket, fake_socket)
        self.assertTrue(transport.is_open)
        self.assertEqual(transport.timeout, 2.5)

    def test_open_is_idempotent_when_socket_is_already_open(self):
        transport = self.make_transport()
        existing_socket = Mock()
        transport._socket = existing_socket

        with patch("src.transport.tcp.tcp.socket.create_connection") as create_connection:
            transport.open()

        create_connection.assert_not_called()
        existing_socket.close.assert_not_called()
        self.assertIs(transport._socket, existing_socket)

    def test_open_failure_leaves_transport_closed(self):
        transport = self.make_transport()

        with patch(
            "src.transport.tcp.tcp.socket.create_connection",
            side_effect=OSError("connection refused"),
        ):
            with self.assertRaisesRegex(OSError, "connection refused"):
                transport.open()

        self.assertIsNone(transport._socket)
        self.assertFalse(transport.is_open)

    def test_write_sends_data_through_open_socket(self):
        transport = self.make_transport()
        fake_socket = Mock()
        transport._socket = fake_socket

        transport.write(b"*IDN?\n")

        fake_socket.sendall.assert_called_once_with(b"*IDN?\n")

    def test_read_returns_data_from_open_socket(self):
        transport = self.make_transport()
        fake_socket = Mock()
        fake_socket.recv.return_value = b"RIGOL TECHNOLOGIES,DS1054Z\n"
        transport._socket = fake_socket

        response = transport.read()

        self.assertEqual(response, b"RIGOL TECHNOLOGIES,DS1054Z\n")
        fake_socket.recv.assert_called_once_with(4096)

    def test_read_passes_requested_size_to_socket(self):
        transport = self.make_transport()
        fake_socket = Mock()
        fake_socket.recv.return_value = b"response"
        transport._socket = fake_socket

        response = transport.read(size=128)

        self.assertEqual(response, b"response")
        fake_socket.recv.assert_called_once_with(128)

    def test_close_closes_socket_and_clears_connection(self):
        transport = self.make_transport()
        fake_socket = Mock()
        transport._socket = fake_socket

        transport.close()

        fake_socket.close.assert_called_once_with()
        self.assertIsNone(transport._socket)
        self.assertFalse(transport.is_open)

    def test_close_clears_state_when_socket_close_fails(self):
        transport = self.make_transport()
        fake_socket = Mock()
        fake_socket.close.side_effect = OSError("close failed")
        transport._socket = fake_socket

        with self.assertRaisesRegex(OSError, "close failed"):
            transport.close()

        self.assertIsNone(transport._socket)
        self.assertFalse(transport.is_open)

    def test_close_without_open_socket_is_noop(self):
        transport = self.make_transport()

        transport.close()

        self.assertIsNone(transport._socket)

    def test_close_is_idempotent(self):
        transport = self.make_transport()
        fake_socket = Mock()
        transport._socket = fake_socket

        transport.close()
        transport.close()

        fake_socket.close.assert_called_once_with()
        self.assertIsNone(transport._socket)

    def test_write_requires_open_socket(self):
        transport = self.make_transport()

        with self.assertRaisesRegex(RuntimeError, "Transport is not open"):
            transport.write(b"data")

    def test_read_requires_open_socket(self):
        transport = self.make_transport()

        with self.assertRaisesRegex(RuntimeError, "Transport is not open"):
            transport.read()
