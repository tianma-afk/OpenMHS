from model_hardware_standard.model.base_driver import BaseDriver
from model_hardware_standard.driver_registry import register
from model_hardware_standard.id_generator import generate_driver_id
@register("TFG6030")
class TFG6030(BaseDriver):
    def __init__(self):
        self.brand = "SUNING"
        self.name = "TFG6030"
        self.type = "waveform generator"
        self.id = generate_driver_id(self.name)
        self.Capabilities = []

    def run(self):
        print("TFG6030 running")