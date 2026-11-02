import importlib
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from src.id_generator import generate_capability_id


PREFIX = "src.driver.UNI_T.UPO6102N.capability"
RESOURCE = "TCPIP0::192.0.2.1::inst0::INSTR"
CAPABILITIES = [
    ("get_channel", "GetChannel"),
    ("get_vpp", "GetVpp"),
    ("get_vrms", "GetVrms"),
    ("get_frequency", "GetFrequency"),
]


class TestUPO6102NCapabilities(TestCase):
    def setUp(self):
        self.instrument = Mock()
        self.resource_manager = Mock()
        self.resource_manager.open_resource.return_value = self.instrument
        self.device_manager = Mock()
        self.device_manager.get_devices.return_value = [
            SimpleNamespace(id="scope", visa_address=RESOURCE)
        ]

    def capability(self, module_name, class_name):
        module = importlib.import_module(f"{PREFIX}.{module_name}")
        self.factory = self.enterContext(
            patch.object(module.pyvisa, "ResourceManager", return_value=self.resource_manager)
        )
        self.enterContext(
            patch.object(module, "get_device_manager", return_value=self.device_manager)
        )
        return getattr(module, class_name)()

    def test_registration_and_parameters(self):
        from src.driver.UNI_T.UPO6102N.driver import UPO6102N

        driver = UPO6102N()
        for capability in driver.Capabilities:
            self.assertIs(driver.get_capabilities_by_id(capability.id), capability)
        self.assertEqual(
            [cap.id for cap in driver.Capabilities],
            [generate_capability_id(name) for name in [
                "set_channel", "get_channel", "get_vpp", "get_vrms", "get_frequency"
            ]]
        )
        for module_name, class_name in CAPABILITIES:
            with self.subTest(capability=module_name):
                capability = self.capability(module_name, class_name)
                self.assertEqual(capability.id, generate_capability_id(module_name))
                specs = capability.get_params()
                self.assertEqual([spec.name for spec in specs], ["device_id", "channel"])
                self.assertEqual([spec.type for spec in specs], ["str", "int"])
                self.assertTrue(all(spec.required for spec in specs))
                self.assertEqual(specs[1].enum, [1, 2])

    def test_channel_states(self):
        capability = self.capability("get_channel", "GetChannel")
        for channel in [1, 2]:
            for response, state in [
                ("ON", True), ("TRUE", True), ("1", True),
                ("OFF", False), ("FALSE", False), ("0", False),
                (" on\n", True), (" false\r\n", False)
            ]:
                with self.subTest(channel=channel, response=response):
                    self.instrument.reset_mock()
                    self.instrument.query.return_value = response
                    self.assertEqual(capability.execute(device_id="scope", channel=channel), {
                        "device_id": "scope", "channel": channel, "state": state
                    })
                    self.instrument.query.assert_called_once_with(f":CHANnel{channel}:DISPlay?")
                    self.instrument.write.assert_not_called()
                    self.instrument.close.assert_called_once_with()
        self.factory.assert_called_with('@py')
        self.resource_manager.open_resource.assert_called_with(RESOURCE)
        self.resource_manager.close.assert_not_called()

    def test_numeric_measurements(self):
        for name, class_name, command, key, unit in [
            ("get_vpp", "GetVpp", "VPP", "vpp", "V"),
            ("get_vrms", "GetVrms", "VRMS", "vrms", "V"),
            ("get_frequency", "GetFrequency", "FREQuency", "frequency", "Hz")
        ]:
            capability = self.capability(name, class_name)
            for channel in [1, 2]:
                for response, value in [
                    (" 1.25E+03\r\n", 1250.0), ("0", 0.0),
                    (f" 1.230e000 {unit}\r\n", 1.23)
                ]:
                    with self.subTest(capability=name, channel=channel, response=response):
                        self.instrument.reset_mock()
                        self.instrument.query.return_value = response
                        result = capability.execute(device_id="scope", channel=channel)
                        self.assertEqual(result, {
                            "device_id": "scope", "channel": channel, key: value, "unit": unit
                        })
                        self.assertIsInstance(result[key], float)
                        source = f"CHANnel{channel}"
                        if name == "get_vrms":
                            source = f"DISPlay,{source}"
                        self.instrument.query.assert_called_once_with(
                            f":MEASure:{command}? {source}"
                        )
                        self.instrument.write.assert_not_called()
                        self.instrument.close.assert_called_once_with()

    def test_invalid_responses_close_resource(self):
        for name, class_name in CAPABILITIES:
            capability = self.capability(name, class_name)
            for response in ["", "unavailable", "nan", "inf", "-inf", "1e999"]:
                with self.subTest(capability=name, response=response):
                    self.instrument.reset_mock()
                    self.instrument.query.return_value = response
                    with self.assertRaises(ValueError):
                        capability.execute(device_id="scope", channel=1)
                    self.instrument.close.assert_called_once_with()

    def test_invalid_parameters_do_not_open_resource(self):
        invalid_kwargs = [
            {}, {"device_id": "scope"}, {"channel": 1},
            *({"device_id": "scope", "channel": channel}
              for channel in [None, True, False, 1.0, "1", 0, 3]),
            *({"device_id": device_id, "channel": 1}
              for device_id in [None, 1, "", " "])
        ]
        for name, class_name in CAPABILITIES:
            capability = self.capability(name, class_name)
            for kwargs in invalid_kwargs:
                with self.subTest(capability=name, kwargs=kwargs):
                    with self.assertRaises(ValueError):
                        capability.execute(**kwargs)
            self.factory.assert_not_called()
        self.resource_manager.open_resource.assert_not_called()

    def test_missing_device(self):
        for name, class_name in CAPABILITIES:
            capability = self.capability(name, class_name)
            with self.subTest(capability=name):
                with self.assertRaisesRegex(ValueError, "Device not found"):
                    capability.execute(device_id="missing", channel=1)
                self.factory.assert_not_called()

    def test_query_error_closes_resource(self):
        self.instrument.query.side_effect = RuntimeError("communication failed")
        for name, class_name in CAPABILITIES:
            capability = self.capability(name, class_name)
            with self.subTest(capability=name):
                self.instrument.reset_mock()
                with self.assertRaisesRegex(RuntimeError, "communication failed"):
                    capability.execute(device_id="scope", channel=1)
                self.instrument.close.assert_called_once_with()
                self.resource_manager.close.assert_not_called()

    def test_open_error_propagates(self):
        self.resource_manager.open_resource.side_effect = RuntimeError("open failed")
        for name, class_name in CAPABILITIES:
            capability = self.capability(name, class_name)
            with self.subTest(capability=name):
                with self.assertRaisesRegex(RuntimeError, "open failed"):
                    capability.execute(device_id="scope", channel=1)
                self.instrument.close.assert_not_called()
