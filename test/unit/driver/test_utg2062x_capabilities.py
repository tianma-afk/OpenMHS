import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from src.driver.UNI_T.UTG2062X.driver import UTG2062X
from src.driver.UNI_T.UTG2062X.capability.get_channel import GetChannel
from src.driver.UNI_T.UTG2062X.capability.set_channel import SetChannel
from src.driver.UNI_T.UTG2062X.capability.set_frequency import SetFrequency
from src.driver.UNI_T.UTG2062X.capability.set_voltage import SetVoltage
from src.driver.UNI_T.UTG2062X.capability.set_waveform import SetWaveform


class TestUTG2062XCapabilities(unittest.TestCase):
    def setUp(self):
        self.instrument = Mock()
        self.resource_manager = Mock()
        self.resource_manager.open_resource.return_value = self.instrument
        self.visa_factory = Mock(return_value=self.resource_manager)
        self.manager = Mock()
        self.manager.get_devices.return_value = [
            SimpleNamespace(id="device-1", visa_address="USB::1")
        ]

    def patch_capability(self, module):
        return patch.multiple(
            module,
            get_device_manager=Mock(return_value=self.manager),
            pyvisa=SimpleNamespace(ResourceManager=self.visa_factory),
        )

    def test_registration_metadata_and_params(self):
        driver = UTG2062X()
        self.assertEqual(driver.brand, "UNI-T")
        self.assertEqual(driver.name, "UTG2062X")
        self.assertEqual(driver.type, "waveform generator")
        self.assertEqual(
            [type(cap) for cap in driver.Capabilities],
            [GetChannel, SetChannel, SetWaveform, SetFrequency, SetVoltage],
        )
        self.assertEqual(SetVoltage().get_params()[-1].enum, ["Vpp", "Vrms"])

    def test_invalid_arguments_do_not_open_visa(self):
        invalid_calls = [
            (GetChannel(), {"device_id": " ", "channel": 1}),
            (GetChannel(), {"device_id": "device-1", "channel": True}),
            (SetChannel(), {"device_id": "device-1", "channel": 1, "state": 1}),
            (SetWaveform(), {"device_id": "device-1", "channel": 1, "waveform": "bad"}),
            (SetFrequency(), {"device_id": "device-1", "channel": 1, "frequency": "2"}),
            (SetFrequency(), {"device_id": "device-1", "channel": 1, "frequency": True}),
            (SetVoltage(), {"device_id": "device-1", "channel": 1, "voltage": True, "unit": "Vpp"}),
            (SetVoltage(), {"device_id": "device-1", "channel": 1, "voltage": 1, "unit": "VPP"}),
        ]
        for capability, kwargs in invalid_calls:
            with self.subTest(capability=type(capability).__name__):
                with self.patch_capability(sys.modules[type(capability).__module__]):
                    with self.assertRaises(ValueError):
                        capability.execute(**kwargs)
                self.visa_factory.assert_not_called()

    def test_get_channel_all_states_and_channels(self):
        for channel in (1, 2):
            for response, expected in (("ON", True), ("OFF", False), ("TRUE", True), ("FALSE", False), ("1", True), ("0", False)):
                with self.subTest(channel=channel, response=response):
                    self.instrument.reset_mock()
                    self.instrument.query.return_value = response
                    with self.patch_capability(sys.modules[GetChannel.__module__]):
                        result = GetChannel().execute(device_id="device-1", channel=channel)
                    self.assertEqual(result["state"], expected)
                    self.instrument.query.assert_called_once_with(f":CHANnel{channel}:OUTPut?")
                    self.instrument.write.assert_not_called()
                    self.instrument.close.assert_called_once()
                    self.visa_factory.assert_called_with("@py")
                    self.resource_manager.open_resource.assert_called_with("USB::1")
                    self.resource_manager.close.assert_not_called()

    def test_set_channel_both_channels_and_states(self):
        for channel in (1, 2):
            for state, command in ((True, "ON"), (False, "OFF")):
                self.instrument.reset_mock()
                with self.patch_capability(sys.modules[SetChannel.__module__]):
                    SetChannel().execute(device_id="device-1", channel=channel, state=state)
                self.instrument.write.assert_called_once_with(f":CHANnel{channel}:OUTPut {command}")
                self.instrument.close.assert_called_once()

    def test_voltage_both_units_and_order(self):
        for channel in [1, 2]:
            for unit, scpi_unit in (("Vpp", "VPP"), ("Vrms", "VRMS")):
                self.instrument.reset_mock()
                self.instrument.query.return_value = scpi_unit
                with self.patch_capability(sys.modules[SetVoltage.__module__]):
                    result = SetVoltage().execute(device_id="device-1", channel=channel, voltage=1.5, unit=unit)
                self.assertEqual(result["unit"], unit)
                self.assertEqual(self.instrument.method_calls, [
                    call.write(f":CHANnel{channel}:AMPLitude:UNIT {scpi_unit}"),
                    call.query(f":CHANnel{channel}:AMPLitude:UNIT?"),
                    call.write(f":CHANnel{channel}:BASE:AMPLitude 1.5"),
                    call.close()
                ])

    def test_voltage_mismatch_and_transport_failures_cleanup(self):
        self.instrument.query.return_value = "VPP"
        with self.patch_capability(sys.modules[SetVoltage.__module__]):
            with self.assertRaises(ValueError):
                SetVoltage().execute(device_id="device-1", channel=1, voltage=1, unit="Vrms")
        self.instrument.write.assert_called_once_with(":CHANnel1:AMPLitude:UNIT VRMS")
        self.instrument.close.assert_called_once()
        self.instrument.reset_mock()
        self.instrument.write.side_effect = RuntimeError("write failed")
        with self.patch_capability(sys.modules[SetChannel.__module__]):
            with self.assertRaises(RuntimeError):
                SetChannel().execute(device_id="device-1", channel=1, state=True)
        self.instrument.close.assert_called_once()

    def valid_calls(self):
        return [
            (GetChannel(), {}),
            (SetChannel(), {"state": True}),
            (SetWaveform(), {"waveform": "sine"}),
            (SetFrequency(), {"frequency": 1000}),
            (SetVoltage(), {"voltage": 1.5, "unit": "Vpp"}),
        ]

    def test_all_capabilities_reject_missing_and_invalid_parameters(self):
        for capability, extra in self.valid_calls():
            valid = {"device_id": "device-1", "channel": 1, **extra}
            invalid = [{key: value for key, value in valid.items() if key != missing}
                       for missing in valid]
            invalid.extend({**valid, "channel": value} for value in [None, True, 1.0, "1", 0, 3])
            invalid.extend({**valid, "device_id": value} for value in [None, 1, "", " "])
            for kwargs in invalid:
                with self.subTest(capability=type(capability).__name__, kwargs=kwargs):
                    with self.patch_capability(sys.modules[type(capability).__module__]):
                        with self.assertRaises(ValueError):
                            capability.execute(**kwargs)
                    self.visa_factory.assert_not_called()
        for capability, field, extra in [
            (SetFrequency(), "frequency", {}),
            (SetVoltage(), "voltage", {"unit": "Vpp"})
        ]:
            for value in [None, True, "1", 0, -1, float("nan"), float("inf"), float("-inf")]:
                with self.subTest(field=field, value=value):
                    with self.patch_capability(sys.modules[type(capability).__module__]):
                        with self.assertRaises(ValueError):
                            capability.execute(device_id="device-1", channel=1, **{field: value}, **extra)
                    self.visa_factory.assert_not_called()

    def test_frequency_and_waveform_commands(self):
        for channel in [1, 2]:
            self.instrument.reset_mock()
            with self.patch_capability(sys.modules[SetFrequency.__module__]):
                result = SetFrequency().execute(device_id="device-1", channel=channel, frequency=1000.5)
            self.assertEqual(result["frequency"], 1000.5)
            self.instrument.write.assert_called_once_with(f":CHANnel{channel}:BASE:FREQuency 1000.5")
            self.instrument.close.assert_called_once_with()
            for waveform, token in [
                ("sine", "SINe"), ("square", "SQUare"), ("pulse", "PULSe"),
                ("ramp", "RAMP"), ("arb", "ARB"), ("noise", "NOISe"),
                ("dc", "DC"), ("harmonic", "HARMonic"), ("prbs", "PRBS"), ("exp", "EXP")
            ]:
                with self.subTest(channel=channel, waveform=waveform):
                    self.instrument.reset_mock()
                    with self.patch_capability(sys.modules[SetWaveform.__module__]):
                        result = SetWaveform().execute(device_id="device-1", channel=channel, waveform=waveform)
                    self.assertEqual(result["waveform"], waveform)
                    self.instrument.write.assert_called_once_with(f":CHANnel{channel}:BASE:WAVe {token}")
                    self.instrument.close.assert_called_once_with()

    def test_missing_device_does_not_open_resource(self):
        self.manager.get_devices.return_value = []
        for capability, extra in self.valid_calls():
            with self.subTest(capability=type(capability).__name__):
                with self.patch_capability(sys.modules[type(capability).__module__]):
                    with self.assertRaisesRegex(ValueError, "Device not found"):
                        capability.execute(device_id="device-1", channel=1, **extra)
                self.visa_factory.assert_not_called()

    def test_open_and_io_errors(self):
        for capability, extra in self.valid_calls():
            for stage in ["open", "io"]:
                with self.subTest(capability=type(capability).__name__, stage=stage):
                    self.instrument.reset_mock(side_effect=True)
                    self.resource_manager.open_resource.side_effect = (
                        RuntimeError("open failed") if stage == "open" else None
                    )
                    if stage == "io":
                        method = self.instrument.query if isinstance(capability, GetChannel) else self.instrument.write
                        method.side_effect = RuntimeError("io failed")
                    with self.patch_capability(sys.modules[type(capability).__module__]):
                        with self.assertRaisesRegex(RuntimeError, f"{stage} failed"):
                            capability.execute(device_id="device-1", channel=1, **extra)
                    if stage == "open":
                        self.instrument.close.assert_not_called()
                    else:
                        self.instrument.close.assert_called_once_with()
                    self.resource_manager.close.assert_not_called()

    def test_invalid_state_response_closes_resource(self):
        self.instrument.query.return_value = "unknown"
        with self.patch_capability(sys.modules[GetChannel.__module__]):
            with self.assertRaises(ValueError):
                GetChannel().execute(device_id="device-1", channel=1)
        self.instrument.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
