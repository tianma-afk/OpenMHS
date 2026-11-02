from pydantic import BaseModel, Field
from model_hardware_standard.model.base_device import BaseDevice

class VisaDevice(BaseDevice):
    visa_address: str = Field(min_length=1, max_length=255)

    def get_visa_address(self) -> str:
        return self.visa_address
    