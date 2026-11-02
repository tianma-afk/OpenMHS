import math

import pyvisa

from model_hardware_standard.device_manager import get_device_manager
from model_hardware_standard.id_generator import generate_capability_id
from model_hardware_standard.model.base_capability import BaseCapability, ParamSpec


class SetFrequency(BaseCapability):
    id = generate_capability_id("set_frequency")
    name = "Set Frequency"
    description = "设置波形发生器通道频率"

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
                name="frequency",
                type="float",
                description="频率，单位 Hz，必须为正数",
                required=True,
                minimum=0,
            ),
        ]

    def execute(self, **kwargs):
        device_id = kwargs.get("device_id")
        channel = kwargs.get("channel")
        frequency = kwargs.get("frequency")
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("device_id 必须是非空字符串")
        if type(channel) is not int or channel not in (1, 2):
            raise ValueError("channel 必须是 1 或 2")
        if (
            isinstance(frequency, bool)
            or not isinstance(frequency, (int, float))
            or not math.isfinite(frequency)
            or frequency <= 0
        ):
            raise ValueError("frequency 必须是有限正数")

        device_manager = get_device_manager()
        devices = device_manager.get_devices()
        for device in devices:
            if device.id == device_id:
                instrument = None
                try:
                    rm = pyvisa.ResourceManager("@py")
                    instrument = rm.open_resource(device.visa_address)
                    instrument.write(
                        f":CHANnel{channel}:BASE:FREQuency {frequency}"
                    )
                    return {
                        "device_id": device_id,
                        "channel": channel,
                        "frequency": frequency,
                        "message": "频率设置成功",
                    }
                finally:
                    if instrument is not None:
                        instrument.close()
        raise ValueError("Device not found")
