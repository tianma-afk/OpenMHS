from pydantic import BaseModel, Field
from dataclasses import dataclass, field
from typing import Any
from abc import ABC, abstractmethod

@dataclass
class ParamSpec:
    name: str
    type: str                    # "int" / "str" / "bytes" / "bool" ...
    description: str             # 给 AI 看的自然语言说明
    required: bool = True
    default: Any = None
    enum: list | None = None     # 可选值，帮 AI 约束
    minimum: float | None = None
    maximum: float | None = None

@dataclass
class CapabilitySpec:
    id: str 
    name: str
    description: str

class BaseCapability(ABC):
    id: str = Field(min_length=36, max_length=36)
    name: str = "" #能力名称
    description: str = ""        # 能力描述：这个能力干什么，给 AI 看
    param_specs: list[ParamSpec] = field(default_factory=list) #能力参数规范列表

    @abstractmethod
    def get_params(self) -> list[ParamSpec]:
        """告诉 AI：执行我需要哪些参数"""
        raise NotImplementedError

    @abstractmethod
    def execute(self, **kwargs):
        raise NotImplementedError


    def get_spec(self) -> CapabilitySpec:
        """返回能力的规范信息"""
        return CapabilitySpec(
            id=self.id,
            name=self.name,
            description=self.description
        )