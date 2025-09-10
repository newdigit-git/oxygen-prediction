from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, BigInteger, JSON, func
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Device(Base):
    """Devices Table"""
    __tablename__ = "devices"
    
    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=func.now())
    last_seen = Column(DateTime, nullable=True)
    
    # Relationships
    telemetry = relationship("Telemetry", back_populates="device")
    sessions = relationship("Session", back_populates="device")


class Telemetry(Base):
    """Telemetry Table (can be partitioned by month)"""
    __tablename__ = "telemetry"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String, ForeignKey("devices.id"), index=True)
    timestamp = Column(BigInteger, index=True) 
    battery = Column(Integer)
    pressure = Column(Float)
    flow = Column(Float)
    signal_strength = Column(Integer)
    location = Column(String)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    device = relationship("Device", back_populates="telemetry")


class Session(Base):
    """Session Table"""
    __tablename__ = "sessions"
    
    sid = Column(String, primary_key=True, index=True)
    device_id = Column(String, ForeignKey("devices.id"), index=True)
    location = Column(String)
    t_start = Column(DateTime, index=True)
    t_end = Column(DateTime, index=True)
    initial_pressure = Column(Float)
    final_pressure = Column(Float)
    flow_rate = Column(Float)
    battery_final = Column(Float)
    fault_flag = Column(Integer, default=0)
    signal_strength = Column(Integer)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    device = relationship("Device", back_populates="sessions")
    depletion_predictions = relationship("DepletionPrediction", back_populates="session")


class DepletionPrediction(Base):
    """Depletion Predictions Table"""
    __tablename__ = "depletion_predictions"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String, index=True)
    session_id = Column(String, ForeignKey("sessions.sid"), index=True)
    time_to_empty_minutes = Column(Float)
    depletion_time = Column(DateTime)
    critical_alert_time = Column(DateTime)
    status = Column(String)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    session = relationship("Session", back_populates="depletion_predictions")


class SurgeForecast(Base):
    """Climate Surge Forecast Table"""
    __tablename__ = "surge_forecasts"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    region_code = Column(String, index=True)
    pm25 = Column(Float)
    humidity = Column(Float)
    temperature = Column(Float)
    risk_level = Column(String)
    surge_percentage = Column(Float)
    confidence = Column(Float)
    forecast_window = Column(DateTime)
    created_at = Column(DateTime, default=func.now())


class ProductionPlan(Base):
    """Production Planning Table"""
    __tablename__ = "production_plans"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    plant_id = Column(String, index=True)
    demand_forecast = Column(JSON)
    utilization = Column(Float)
    action_plan = Column(JSON)
    created_at = Column(DateTime, default=func.now())


class ClinicalOutcome(Base):
    """Clinical Outcomes Loop Table"""
    __tablename__ = "clinical_outcomes"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    facility_id = Column(String, index=True)
    cohort_data = Column(JSON)
    survival_rate = Column(Float)
    intervention_metrics = Column(JSON)
    model_feedback = Column(JSON)
    created_at = Column(DateTime, default=func.now())
