import math

import pyvisa

from model_hardware_standard.device_manager import get_device_manager
from model_hardware_standard.id_generator import generate_capability_id
from model_hardware_standard.model.base_capability import BaseCapability, ParamSpec


class SetVoltage(BaseCapability):
    id = generate_capability_id("set_voltage")
    name = "Set Voltage"
    description = "设置波形发生器通道电压及幅度单位"

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
                name="voltage",
                type="float",
                description="幅度，必须为有限正数",
                required=True,
                minimum=0,
            ),
            ParamSpec(
                name="unit",
                type="str",
                description="幅度单位，支持 Vpp 或 Vrms",
                required=True,
                enum=["Vpp", "Vrms"],
            ),
        ]

    def execute(self, **kwargs):
        device_id = kwargs.get("device_id")
        channel = kwargs.get("channel")
        voltage = kwargs.get("voltage")
        unit = kwargs.get("unit")
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("device_id 必须是非空字符串")
        if type(channel) is not int or channel not in (1, 2):
            raise ValueError("channel 必须是 1 或 2")
        if (
            isinstance(voltage, bool)
            or not isinstance(voltage, (int, float))
            or not math.isfinite(voltage)
            or voltage <= 0
        ):
            raise ValueError("voltage 必须是有限正数")
        if not isinstance(unit, str) or unit not in {"Vpp", "Vrms"}:
            raise ValueError("unit 必须是 Vpp 或 Vrms")

        scpi_unit = unit.upper()
        device_manager = get_device_manager()
        devices = device_manager.get_devices()
        for device in devices:
            if device.id == device_id:
                instrument = None
                try:
                    rm = pyvisa.ResourceManager("@py")
                    instrument = rm.open_resource(device.visa_address)
                    instrument.write(
                        f":CHANnel{channel}:AMPLitude:UNIT {scpi_unit}"
                    )
                    reported_unit = instrument.query(
                        f":CHANnel{channel}:AMPLitude:UNIT?"
                    ).strip().upper()
                    if reported_unit != scpi_unit:
                        raise ValueError(
                            "仪器返回的幅度单位与请求不一致: "
                            f"{reported_unit} != {scpi_unit}"
                        )
                    instrument.write(
                        f":CHANnel{channel}:BASE:AMPLitude {voltage}"
                    )
                    return {
                        "device_id": device_id,
                        "channel": channel,
                        "voltage": voltage,
                        "unit": unit,
                        "message": "电压设置成功",
                    }
                finally:
                    if instrument is not None:
                        instrument.close()
        raise ValueError("Device not found")
