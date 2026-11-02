from model_hardware_standard.model.base_driver import BaseDriver
from model_hardware_standard.driver_registry import register
from model_hardware_standard.id_generator import generate_driver_id
from .capability.get_channel import GetChannel
from .capability.set_channel import SetChannel
from .capability.set_waveform import SetWaveform
from .capability.set_frequency import SetFrequency
from .capability.set_voltage import SetVoltage


@register("UTG2062X")
class UTG2062X(BaseDriver):
    def __init__(self):
        self.brand = "UNI-T"
        self.name = "UTG2062X"
        self.type = "waveform generator"
        self.id = generate_driver_id(self.name)
        self.Capabilities = [GetChannel(), SetChannel(), SetWaveform(), SetFrequency(), SetVoltage()]

    def run(self):
        print("UTG2062X running")
