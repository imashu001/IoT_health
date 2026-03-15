from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime


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

    @model_validator(mode="before")
    def check_future_timestamp(cls, values):
        ts = values.get("timestamp")
        if ts is None:
            return values

        # make sure ts is int
        try:
            ts = int(ts)
        except Exception:
            raise ValueError("timestamp must be an integer")

        # auto-detect milliseconds vs seconds
        if ts > 1e11:  # anything bigger than 100_000_000_000 → treat as ms
            ts = ts // 1000

        # get current UTC epoch in seconds
        current_ts = int(datetime.utcnow().timestamp())

        if ts > current_ts:
            raise ValueError(f"timestamp cannot be in the future. got {ts}, now {current_ts}")

        # save normalized seconds back
        values["timestamp"] = ts
        return values