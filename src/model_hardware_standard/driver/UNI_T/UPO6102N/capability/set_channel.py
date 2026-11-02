from model_hardware_standard.model.base_capability import BaseCapability, ParamSpec
from model_hardware_standard.id_generator import generate_capability_id
from model_hardware_standard.device_manager import DeviceManager, get_device_manager
import pyvisa, pyvisa_py
class SetChannel(BaseCapability):
    id = generate_capability_id("set_channel")
    name = "Set Channel"
    description = "设置通道打开状态"

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
                description="The channel number to set (1 or 2)",
                required=True,
                enum=[1, 2]
            ),
            ParamSpec(
                name="state",
                type="bool",
                description="The state to set for the channel (True for open, False for closed)",
                required=True
            )
        ]

    def execute(self, **kwargs):
        channel = kwargs.get("channel")
        if channel not in [1, 2]:
            raise ValueError("Invalid channel. Must be 1 or 2.")
        if "state" not in kwargs:
            raise ValueError("Missing required parameter: state")
        if not isinstance(kwargs["state"], bool):
            raise ValueError("Invalid state. Must be a boolean value.")
        if "device_id" not in kwargs:
            raise ValueError("Missing required parameter: device_id")
        device_id = kwargs["device_id"]
        device_manager = get_device_manager()
        devices = device_manager.get_devices()
        for device in devices:
            if device.id == device_id:
                # Here you would add the code to actually set the channel on the oscilloscope
                rm = pyvisa.ResourceManager('@py')
                instrument = rm.open_resource(device.visa_address)
                instrument.write(f':CHANnel{channel}:DISPlay {"ON" if kwargs["state"] else "OFF"}')
                return { 
                    "message": f"Channel {channel} set to {'open' if kwargs['state'] else 'closed'} on device {device_id}"
                }
        raise ValueError("Device not found")
        