from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager
from model_hardware_standard.device_manager import DeviceManager, set_device_manager, get_device_manager
from model_hardware_standard.visa_discovery import VISADiscovery
from model_hardware_standard.registry import Registry
from model_hardware_standard.driver_registry import load_all_drivers,_DRIVERS
from pydantic import BaseModel
from typing import Any
from fastapi import Body
from fastapi_mcp import FastApiMCP
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    print("应用启动中...")

    load_all_drivers()
    # print("Loaded drivers:", _DRIVERS)
    discovery = VISADiscovery()
    registry = Registry()
    device_manager = DeviceManager(discovery, registry)
    set_device_manager(device_manager)
    app.state.device_manager = get_device_manager()
    device_manager.start() 
    
    yield  # 应用运行期间
    
    # 关闭时执行
    print("应用关闭中...")
    device_manager.stop()  # 停止调度器

app = FastAPI(lifespan=lifespan)

@app.get("/health", operation_id="health_check")
def root():
    """健康检查接口，验证设备服务是否已启动并可访问。"""
    return {"message": "health check passed"}

@app.get("/devices", operation_id="get_devices")
def get_devices():
    """获取当前已发现并注册的设备列表，返回设备的元数据和状态。"""
    devices = app.state.device_manager.get_devices()

    return {
        "code": 200,
        "message": "success",
        "data": [device.__dict__ for device in devices]
    }

@app.get("/drivers", operation_id="list_drivers")
def get_drivers():
    """获取系统中已加载的所有驱动概览信息，包括驱动 ID、品牌、名称和类型。"""
    drivers = []
    driver_names = list(_DRIVERS.keys())
    for driver_name in driver_names:
        driver_class = _DRIVERS[driver_name]
        driver_instance = driver_class()
        drivers.append({
            "id": driver_instance.id,
            "brand": driver_instance.brand,
            "name": driver_instance.name,
            "type": driver_instance.type
        })
    return {
        "code": 200,
        "message": "success",
        "data": drivers
    }

@app.get("/drivers/{driver_name}", operation_id="get_driver_detail")
def get_driver(driver_name: str):
    """根据驱动名称查询单个驱动的基本信息。"""
    if driver_name in list(_DRIVERS.keys()):
        driver_class = _DRIVERS[driver_name]
        driver_instance = driver_class()
        return {
            "code": 200,
            "message": "success",
            "data": {
                "id": driver_instance.id,
                "brand": driver_instance.brand,
                "name": driver_instance.name,
                "type": driver_instance.type
            }
        }
    else:
        return {
            "code": 404,
            "message": "driver not found",
            "data": None
        }

@app.get("/drivers/{driver_name}/capabilities", operation_id="list_driver_capabilities")
def get_driver_capabilities(driver_name: str):
    """查询指定驱动支持的所有能力列表及各能力的参数规范。"""
    if driver_name in list(_DRIVERS.keys()):
        driver_class = _DRIVERS[driver_name]
        driver_instance = driver_class()
        capability_specs = [spec for spec in driver_instance.get_capability_specs()]
        return {
            "code": 200,
            "message": "success",
            "data": capability_specs
        }
    else:
        return {
            "code": 404,
            "message": "driver not found",
            "data": None
        }

@app.get("/drivers/{driver_name}/capabilities/{capability_id}", operation_id="get_driver_capability_detail")
def get_driver_capability(driver_name: str, capability_id: str):
    """根据驱动名和能力 ID，获取指定能力的参数定义说明。"""
    if driver_name in list(_DRIVERS.keys()):
        driver_class = _DRIVERS[driver_name]
        driver_instance = driver_class()
        try:
            capability = driver_instance.get_capabilities_by_id(capability_id)
            return {
                "code": 200,
                "message": "success",
                "data": capability.get_params()
            }
        except ValueError as e:
            return {
                "code": 404,
                "message": str(e),
                "data": None
            }
    else:
        return {
            "code": 404,
            "message": "driver not found",
            "data": None
        }

@app.post(
    "/drivers/{driver_name}/capabilities/{capability_id}/execute",
    operation_id="execute_driver_capability",
)
def execute_capability(
    driver_name: str,
    capability_id: str,
    kwargs: dict = Body(...,embed=True , description="要执行的参数，键为参数名，值为参数值。可先调用 get_driver_capability 获取所需参数列表。"),
):
    """执行指定驱动下某个能力，并传入对应的参数键值对。"""

    if driver_name in list(_DRIVERS.keys()):
        driver_class = _DRIVERS[driver_name]
        driver_instance = driver_class()
        try:
            capability = driver_instance.get_capabilities_by_id(capability_id)
            return {
                "code": 200,
                "message": "success",
                "data": capability.execute(**kwargs)
            }
        except ValueError as e:
            return {
                "code": 404,
                "message": str(e),
                "data": None
            }
    else:
        return {
            "code": 404,
            "message": "driver not found",
            "data": None
        }
mcp = FastApiMCP(
    app,
    name="HardwareMCP"
)
mcp.mount_http(mount_path="/mcp")  # MCP 服务将自动挂载到 /mcp 路径

def main():
    uvicorn.run("model_hardware_standard.main:app", host="127.0.0.1", port=8899, reload=False)

if __name__ == "__main__":
    main()