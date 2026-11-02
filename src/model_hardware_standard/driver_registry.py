from model_hardware_standard.model.base_driver import BaseDriver
import importlib,pkgutil
import sys
from pathlib import Path
_DRIVERS = {}

def register(name):
    """装饰器：把 driver 类按名字注册到工厂里"""
    def deco(cls):
        _DRIVERS[name] = cls
        return cls
    return deco

def create_driver(name: str) -> BaseDriver:
    cls = _DRIVERS.get(name)
    if cls is None:
        raise ValueError(f"unknown driver: {name}")
    return cls()

def load_all_drivers():
    driver_root = Path(__file__).resolve().parent / "driver"

    for file_path in driver_root.rglob("driver.py"):
        relative_path = file_path.relative_to(Path(__file__).resolve().parent)
        module_name = ".".join(relative_path.with_suffix("").parts)
        importlib.import_module(f"model_hardware_standard.{module_name}")