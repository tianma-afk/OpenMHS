from model_hardware_standard.model.visa_device import VisaDevice
class Registry():
    def __init__(self):
        self.device_repo = []

    def register(self, devices: list[VisaDevice]):
        for device in devices:
            if device not in self.device_repo:
                self.device_repo.append(device)

    def unregister(self, device: VisaDevice):
        if device in self.device_repo:
            self.device_repo.remove(device)