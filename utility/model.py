from pydantic import BaseModel, Field
from typing import Optional


class UserCreate(BaseModel):
    user_id: str
    name: str
    status: str
    created_by: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None

class IoTDataCreate(BaseModel):
    user_id: str
    metric_1: float = Field(..., ge=0, le=100)
    metric_2: float = Field(..., ge=0, le=200)
    metric_3: float
    timestamp: int