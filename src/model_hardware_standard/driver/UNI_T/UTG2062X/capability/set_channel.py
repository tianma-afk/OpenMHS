import pyvisa

from model_hardware_standard.device_manager import get_device_manager
from model_hardware_standard.id_generator import generate_capability_id
from model_hardware_standard.model.base_capability import BaseCapability, ParamSpec


class SetChannel(BaseCapability):
    id = generate_capability_id("set_channel")
    name = "Set Channel"
    description = "设置波形发生器通道输出状态"

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
                name="state",
                type="bool",
                description="是否打开输出",
                required=True,
            ),
        ]

    def execute(self, **kwargs):
        device_id = kwargs.get("device_id")
        channel = kwargs.get("channel")
        state = kwargs.get("state")
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("device_id 必须是非空字符串")
        if type(channel) is not int or channel not in (1, 2):
            raise ValueError("channel 必须是 1 或 2")
        if not isinstance(state, bool):
            raise ValueError("state 必须是布尔值")

        device_manager = get_device_manager()
        devices = device_manager.get_devices()
        for device in devices:
            if device.id == device_id:
                instrument = None
                try:
                    rm = pyvisa.ResourceManager("@py")
                    instrument = rm.open_resource(device.visa_address)
                    instrument.write(
                        f":CHANnel{channel}:OUTPut {'ON' if state else 'OFF'}"
                    )
                    return {
                        "device_id": device_id,
                        "channel": channel,
                        "state": state,
                        "message": f"通道 {channel} 已{'打开' if state else '关闭'}",
                    }
                finally:
                    if instrument is not None:
                        instrument.close()
        raise ValueError("Device not found")
