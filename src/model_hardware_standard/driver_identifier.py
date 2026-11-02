from model_hardware_standard.driver_registry import create_driver
class DriverIdentifier:

    @staticmethod
    def identify(driver_name:str):
        # 基于驱动名称区分驱动
        return create_driver(driver_name)