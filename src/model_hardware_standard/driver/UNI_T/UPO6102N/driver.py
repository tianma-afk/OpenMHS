from model_hardware_standard.model.base_driver import BaseDriver
from model_hardware_standard.driver_registry import register
from model_hardware_standard.id_generator import generate_driver_id
from .capability.set_channel import SetChannel
from .capability.get_channel import GetChannel
from .capability.get_vpp import GetVpp
from .capability.get_vrms import GetVrms
from .capability.get_frequency import GetFrequency
@register("UPO6102N")
class UPO6102N(BaseDriver):
    def __init__(self):
        self.brand = "UNI-T"
        self.name = "UPO6102N"
        self.type = "oscilloscope"
        self.id = generate_driver_id(self.name)
        self.Capabilities = [SetChannel(), GetChannel(), GetVpp(), GetVrms(), GetFrequency()]

    def run(self):
        print("UPO6102N running")