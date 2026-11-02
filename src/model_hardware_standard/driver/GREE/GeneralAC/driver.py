from model_hardware_standard.model.base_driver import BaseDriver
from model_hardware_standard.driver_registry import register
from model_hardware_standard.id_generator import generate_driver_id
@register("GeneralAC")
class GeneralAC(BaseDriver):
    def __init__(self):
        self.brand = "GREE"
        self.name = "GeneralAC"
        self.type = "air conditioner"
        self.id = generate_driver_id(self.name)
        self.Capabilities = []

    def run(self):
        print("GeneralAC running")