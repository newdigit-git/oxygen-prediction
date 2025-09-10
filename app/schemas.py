from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# Telemetry Schemas
class TelemetryCreate(BaseModel):
    """Telemetry ingestion request schema"""
    id: str  # Device ID
    t: int  # Unix timestamp
    b: int  # Battery %
    p: float  # Pressure
    f: float  # Flow
    c: int  # Signal strength
    l: str  # Location


class TelemetryResponse(BaseModel):
    """Telemetry response schema"""
    id: int
    device_id: str
    timestamp: int
    battery: int
    pressure: float
    flow: float
    signal_strength: int
    location: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# Session Schemas
class SessionCreate(BaseModel):
    """Session summary ingestion request schema"""
    id: str  # Device ID
    sid: str  # Session ID
    lc: str  # Location
    t_start: datetime
    t_end: datetime
    i_p: float  # Initial pressure
    f_p: float  # Final pressure
    f_r: float  # Flow rate
    fb_pct: float  # Battery final %
    hf_log: int  # Fault flag
    c_st: int  # Signal strength


class SessionResponse(BaseModel):
    """Session response schema"""
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
    
    class Config:
        from_attributes = True


# Depletion Prediction Schemas
class DepletionPredictionResponse(BaseModel):
    """Depletion prediction response schema"""
    id: int
    device_id: str
    session_id: str
    time_to_empty_minutes: float
    depletion_time: datetime
    critical_alert_time: datetime
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# Device Schemas
class DeviceResponse(BaseModel):
    """Device response schema"""
    id: str
    created_at: datetime
    last_seen: Optional[datetime]
    
    class Config:
        from_attributes = True


# Health Check
class HealthCheck(BaseModel):
    status: str
    message: str
