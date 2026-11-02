import pyvisa

from model_hardware_standard.device_manager import get_device_manager
from model_hardware_standard.id_generator import generate_capability_id
from model_hardware_standard.model.base_capability import BaseCapability, ParamSpec

_WAVEFORMS = {
    "sine": "SINe",
    "square": "SQUare",
    "pulse": "PULSe",
    "ramp": "RAMP",
    "arb": "ARB",
    "noise": "NOISe",
    "dc": "DC",
    "harmonic": "HARMonic",
    "prbs": "PRBS",
    "exp": "EXP",
}


class SetWaveform(BaseCapability):
    id = generate_capability_id("set_waveform")
    name = "Set Waveform"
    description = "设置波形发生器通道波形"

    def get_params(self):
        return [
            ParamSpec(
                name="device_id",
                type="str",
                description="设备 ID",
                required=True,
            ),
            ParamSpec(
                name="channel",
                type="int",
                description="通道号，仅支持 1 或 2",
                required=True,
                enum=[1, 2],
            ),
            ParamSpec(
                name="waveform",
                type="str",
                description="波形类型",
                required=True,
                enum=list(_WAVEFORMS),
            ),
        ]

    def execute(self, **kwargs):
        device_id = kwargs.get("device_id")
        channel = kwargs.get("channel")
        waveform = kwargs.get("waveform")
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("device_id 必须是非空字符串")
        if type(channel) is not int or channel not in (1, 2):
            raise ValueError("channel 必须是 1 或 2")
        if (
            not isinstance(waveform, str)
            or waveform.strip().lower() not in _WAVEFORMS
        ):
            raise ValueError(f"不支持的波形: {waveform}")

        waveform = waveform.strip().lower()
        device_manager = get_device_manager()
        devices = device_manager.get_devices()
        for device in devices:
            if device.id == device_id:
                instrument = None
                try:
                    rm = pyvisa.ResourceManager("@py")
                    instrument = rm.open_resource(device.visa_address)
                    instrument.write(
                        f":CHANnel{channel}:BASE:WAVe {_WAVEFORMS[waveform]}"
                    )
                    return {
                        "device_id": device_id,
                        "channel": channel,
                        "waveform": waveform,
                        "message": f"波形已设置为 {waveform}",
                    }
                finally:
                    if instrument is not None:
                        instrument.close()
        raise ValueError("Device not found")
