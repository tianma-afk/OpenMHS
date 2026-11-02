import pyvisa
import logging
from model_hardware_standard.model.visa_device import VisaDevice
from model_hardware_standard.driver_identifier import DriverIdentifier
from model_hardware_standard.id_generator import generate_device_id, generate_driver_id

logger = logging.getLogger(__name__)

class VISADiscovery:
    def __init__(self):
        self.rm = pyvisa.ResourceManager('@py')
        self.open_timeout_ms = 3000
        self.io_timeout_ms = 2000

    def discover(self):
        res_list = self.rm.list_resources()
        devices = []
        for res in res_list:
            instrument = None
            stage = "open"
            try :
                instrument = self.rm.open_resource(res, open_timeout=self.open_timeout_ms, timeout=self.io_timeout_ms)
                
                stage = "identify"
                instrument.write('*IDN?')
                device_info = instrument.read().strip()

                stage = "parse"
                parts = device_info.split(",")
                if len(parts) < 3:
                    raise ValueError(
                        f"设备身份信息格式不正确：{device_info!r}"
                    )

                manufacturer, model, serial = (
                    part.strip() for part in parts[:3]
                )
                if not all((manufacturer, model, serial)):
                    raise ValueError(
                        f"设备身份信息缺少厂商、型号或序列号：{device_info!r}"
                    )

                stage = "driver"
                driver = DriverIdentifier.identify(model)

                device = VisaDevice(
                    id=generate_device_id(manufacturer + model + serial),
                    driver_id=driver.id,
                    visa_address=res,
                )
                devices.append(device)
            except pyvisa.errors.VisaIOError as e:
                logger.warning(
                    "设备扫描通信失败：resource: %s, stage: %s, code: %s, error: %s",
                    res, 
                    stage, 
                    e.error_code,
                    str(e)
                )
            except ValueError as e:
                logger.warning(
                    "设备扫描识别失败：resource: %s, stage: %s, error: %s",
                    res, 
                    stage, 
                    str(e)
                )
            except Exception as e:
                logger.warning(
                    "设备扫描未知错误：resource: %s, stage: %s, error: %s",
                    res, 
                    stage, 
                    str(e)
                )
            finally:
                if instrument is not None:
                    try:
                        instrument.close()
                    except Exception as e:
                        logger.exception(
                            "关闭扫描连接失败：resource: %s, error: %s",
                            res,
                            str(e)
                        )
        return devices

if __name__ == "__main__":
    rm = pyvisa.ResourceManager('@py')
    res_list = rm.list_resources()
    print("Available VISA resources:", res_list)
    # discovery = VISADiscovery()
    # devices = discovery.discover()
    # for device in devices:
    #     print(f"Device ID: {device.id}, Driver ID: {device.driver_id}, VISA Address: {device.visa_address}")