from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import declarative_base, relationship

from app.core.database import Base

AUTOINCREMENT_ID = BigInteger().with_variant(Integer, "sqlite")


class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=func.now())
    last_seen = Column(DateTime, nullable=True)

    telemetry = relationship("Telemetry", back_populates="device")
    sessions = relationship("Session", back_populates="device")


class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(AUTOINCREMENT_ID, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String, ForeignKey("devices.id"), index=True, nullable=False)
    timestamp = Column(BigInteger, index=True, nullable=False)
    battery = Column(Integer, nullable=False)
    pressure = Column(Float, nullable=False)
    flow = Column(Float, nullable=False)
    signal_strength = Column(Integer, nullable=False)
    location = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    device = relationship("Device", back_populates="telemetry")


class Session(Base):
    __tablename__ = "sessions"

    sid = Column(String, primary_key=True, index=True)
    device_id = Column(String, ForeignKey("devices.id"), index=True, nullable=False)
    location = Column(String, nullable=False)
    t_start = Column(DateTime, index=True, nullable=False)
    t_end = Column(DateTime, index=True, nullable=False)
    initial_pressure = Column(Float, nullable=False)
    final_pressure = Column(Float, nullable=False)
    flow_rate = Column(Float, nullable=False)
    battery_final = Column(Float, nullable=False)
    fault_flag = Column(Integer, default=0, nullable=False)
    signal_strength = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    device = relationship("Device", back_populates="sessions")
    depletion_predictions = relationship("DepletionPrediction", back_populates="session")


class DepletionPrediction(Base):
    __tablename__ = "depletion_predictions"

    id = Column(AUTOINCREMENT_ID, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String, index=True, nullable=False)
    session_id = Column(String, ForeignKey("sessions.sid"), index=True, nullable=False)
    time_to_empty_minutes = Column(Float, nullable=True)
    depletion_time = Column(DateTime, nullable=True)
    critical_alert_time = Column(DateTime, nullable=True)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    session = relationship("Session", back_populates="depletion_predictions")


class SurgeForecast(Base):
    __tablename__ = "surge_forecasts"

    id = Column(AUTOINCREMENT_ID, primary_key=True, index=True, autoincrement=True)
    region_code = Column(String, index=True, nullable=False)
    pm25 = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    risk_level = Column(String, nullable=False)
    surge_percentage = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    forecast_window = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class ProductionPlan(Base):
    __tablename__ = "production_plans"

    id = Column(AUTOINCREMENT_ID, primary_key=True, index=True, autoincrement=True)
    plant_id = Column(String, index=True, nullable=False)
    demand_forecast = Column(JSON, nullable=False)
    utilization = Column(Float, nullable=False)
    action_plan = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class ClinicalOutcome(Base):
    __tablename__ = "clinical_outcomes"

    id = Column(AUTOINCREMENT_ID, primary_key=True, index=True, autoincrement=True)
    facility_id = Column(String, index=True, nullable=False)
    cohort_data = Column(JSON, nullable=False)
    survival_rate = Column(Float, nullable=False)
    intervention_metrics = Column(JSON, nullable=False)
    model_feedback = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
