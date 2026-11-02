import pyvisa

from model_hardware_standard.device_manager import get_device_manager
from model_hardware_standard.id_generator import generate_capability_id
from model_hardware_standard.model.base_capability import BaseCapability, ParamSpec


class GetChannel(BaseCapability):
    id = generate_capability_id("get_channel")
    name = "Get Channel"
    description = "查询波形发生器通道输出状态"

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
        ]

    def execute(self, **kwargs):
        device_id = kwargs.get("device_id")
        channel = kwargs.get("channel")
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("device_id 必须是非空字符串")
        if type(channel) is not int or channel not in (1, 2):
            raise ValueError("channel 必须是 1 或 2")

        device_manager = get_device_manager()
        devices = device_manager.get_devices()
        for device in devices:
            if device.id == device_id:
                instrument = None
                try:
                    rm = pyvisa.ResourceManager("@py")
                    instrument = rm.open_resource(device.visa_address)
                    response = instrument.query(
                        f":CHANnel{channel}:OUTPut?"
                    ).strip().upper()
                    if response in {"ON", "TRUE", "1"}:
                        state = True
                    elif response in {"OFF", "FALSE", "0"}:
                        state = False
                    else:
                        raise ValueError(
                            f"无法识别通道状态: {response}"
                        )
                    return {
                        "device_id": device_id,
                        "channel": channel,
                        "state": state,
                    }
                finally:
                    if instrument is not None:
                        instrument.close()
        raise ValueError("Device not found")
