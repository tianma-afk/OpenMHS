import uuid

# 定义命名空间常量
device_id_ns = uuid.NAMESPACE_DNS
driver_id_ns = uuid.NAMESPACE_URL
capability_id_ns = uuid.NAMESPACE_URL
def generate_device_id(device_info: str) -> str:
    """
    根据设备信息生成唯一的设备ID
    :param device_info: 设备信息字符串
    :return: 唯一的设备ID
    """
    return str(uuid.uuid5(device_id_ns, device_info))

def generate_driver_id(driver_info: str) -> str:
    """
    根据驱动信息生成唯一的驱动ID
    :param driver_info: 驱动信息字符串
    :return: 唯一的驱动ID
    """
    return str(uuid.uuid5(driver_id_ns, driver_info))

def generate_capability_id(capability_info: str) -> str:
    """
    根据能力信息生成唯一的能力ID
    :param capability_info: 能力信息字符串
    :return: 唯一的能力ID
    """
    return str(uuid.uuid5(capability_id_ns, capability_info))