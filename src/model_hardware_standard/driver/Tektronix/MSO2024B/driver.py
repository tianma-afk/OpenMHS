from model_hardware_standard.model.base_driver import BaseDriver
from model_hardware_standard.driver_registry import register
from model_hardware_standard.id_generator import generate_driver_id
@register("MSO2024B")
class MSO2024B(BaseDriver):
    def __init__(self):
        self.brand = "Tektronix"
        self.name = "MSO2024B"
        self.type = "oscilloscope"
        self.id = generate_driver_id(self.name)
        self.Capabilities = []

    def run(self):
        print("MSO2024B running")