from pydantic import BaseModel, Field
from model_hardware_standard.model.base_driver import BaseDriver

class BaseDevice(BaseModel):
    id: str = Field(min_length=36, max_length=36)
    driver_id: str = Field(min_length=36, max_length=36)
