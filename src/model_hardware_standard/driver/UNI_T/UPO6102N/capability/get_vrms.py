from model_hardware_standard.model.base_capability import BaseCapability, ParamSpec
from model_hardware_standard.id_generator import generate_capability_id
from model_hardware_standard.device_manager import get_device_manager
import math
import pyvisa


class GetVrms(BaseCapability):
    id = generate_capability_id("get_vrms")
    name = "Get Vrms"
    description = "获取通道屏幕显示范围内的电压有效值，单位 V"

    def get_params(self):
        return [
            ParamSpec(
                name="device_id",
                type="str",
                description="The ID of the device",
                required=True
            ),
            ParamSpec(
                name="channel",
                type="int",
                description="The channel number to query (1 or 2)",
                required=True,
                enum=[1, 2]
            )
        ]

    def execute(self, **kwargs):
        channel = kwargs.get("channel")
        if type(channel) is not int or channel not in [1, 2]:
            raise ValueError("Invalid channel. Must be 1 or 2.")
        if "device_id" not in kwargs:
            raise ValueError("Missing required parameter: device_id")
        device_id = kwargs["device_id"]
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("Invalid device_id. Must be a non-empty string.")
        device_manager = get_device_manager()
        devices = device_manager.get_devices()
        for device in devices:
            if device.id == device_id:
                rm = pyvisa.ResourceManager('@py')
                instrument = rm.open_resource(device.visa_address)
                try:
                    response = instrument.query(f':MEASure:VRMS? DISPlay,CHANnel{channel}').strip()
                    try:
                        vrms = float(response.removesuffix("V").strip())
                    except ValueError as error:
                        raise ValueError(f"Invalid Vrms response: {response!r}") from error
                    if not math.isfinite(vrms):
                        raise ValueError(f"Invalid Vrms response: {response!r}")
                    return {
                        "device_id": device_id,
                        "channel": channel,
                        "vrms": vrms,
                        "unit": "V"
                    }
                finally:
                    instrument.close()
        raise ValueError("Device not found")
