from pydantic import BaseModel, Field
from abc import ABC, abstractmethod
from model_hardware_standard.model.base_capability import BaseCapability, CapabilitySpec

class BaseDriver(ABC):
    id: str = Field(min_length=36, max_length=36)
    name: str #产品型号名称
    brand: str #制造商品牌
    type: str #产品类型
    Capabilities: list[BaseCapability] = [] #该驱动支持的能力列表


    def get_capabilities_by_id(self, cap_id :str) -> BaseCapability:
        """返回该驱动支持的能力对象，若不存在则抛出异常"""
        for cap in self.Capabilities:
            if cap.id == cap_id:
                return cap
        raise ValueError(f"Capability with id {cap_id} not found in driver {self.name}")


    def get_capability_specs(self) -> list[CapabilitySpec]:
        """返回该驱动支持的能力规范列表"""
        return [cap.get_spec() for cap in self.Capabilities]


    def execute(self, capability: BaseCapability, **kwargs):
        """执行指定的能力"""
        return capability.execute(**kwargs)