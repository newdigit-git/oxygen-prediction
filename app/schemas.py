from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TelemetryCreate(BaseModel):
    """Compact device telemetry payload."""

    id: str = Field(min_length=1, max_length=128)
    t: int = Field(ge=0)
    b: int = Field(ge=0, le=100)
    p: float = Field(ge=0)
    f: float = Field(ge=0)
    c: int = Field(ge=-150, le=50)
    l: str = Field(min_length=1, max_length=128)

    @field_validator("id", "l")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class TelemetryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    timestamp: int
    battery: int
    pressure: float
    flow: float
    signal_strength: int
    location: str
    created_at: datetime


class SessionCreate(BaseModel):
    """Completed device session summary payload."""

    id: str = Field(min_length=1, max_length=128)
    sid: str = Field(min_length=1, max_length=128)
    lc: str = Field(min_length=1, max_length=128)
    t_start: datetime
    t_end: datetime
    i_p: float = Field(ge=0)
    f_p: float = Field(ge=0)
    f_r: float = Field(ge=0)
    fb_pct: float = Field(ge=0, le=100)
    hf_log: int = Field(ge=0, le=1)
    c_st: int = Field(ge=-150, le=50)

    @field_validator("id", "sid", "lc")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("t_end")
    @classmethod
    def end_after_start(cls, value: datetime, info):
        start = info.data.get("t_start")
        if start is not None and value <= start:
            raise ValueError("t_end must be after t_start")
        return value

    @field_validator("f_p")
    @classmethod
    def final_pressure_not_above_initial(cls, value: float, info):
        initial = info.data.get("i_p")
        if initial is not None and value > initial:
            raise ValueError("f_p cannot exceed i_p")
        return value


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sid: str
    device_id: str
    location: str
    t_start: datetime
    t_end: datetime
    initial_pressure: float
    final_pressure: float
    flow_rate: float
    battery_final: float
    fault_flag: int
    signal_strength: int
    created_at: datetime


class DepletionPredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    session_id: str
    time_to_empty_minutes: float
    depletion_time: datetime
    critical_alert_time: datetime
    status: str
    created_at: datetime


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    last_seen: Optional[datetime]


class HealthCheck(BaseModel):
    status: str
    message: str
