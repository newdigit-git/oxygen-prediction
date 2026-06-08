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


class AssetMetadata(BaseModel):
    device_id: str
    facility_id: str
    facility_name: str
    ward_type: str
    bed_number: str
    cylinder_type: str


class ThermodynamicMetrics(BaseModel):
    current_pressure_psi: float
    current_flow_rate_lmin: float
    calculated_volume_liters: float
    consumption_velocity_psi_per_hour: float


class Projections(BaseModel):
    time_to_empty_minutes: float
    estimated_depletion_time: datetime
    critical_threshold_alert_time: datetime
    status: str


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

# ── Stage 2: Climate & Health Surge Correlation ──────────────────────────────

class GeographicalScope(BaseModel):
    region_code: str
    zone: str
    monitored_clinics_count: int


class EnvironmentalInputs(BaseModel):
    pm2_5_aqi: float
    humidity_percentage: float
    temperature_celsius: float
    harmattan_dust_index: str
    climate_anomaly_detected: bool


class MLSurgeForecasting(BaseModel):
    historical_pattern_match_id: str
    predicted_respiratory_admission_increase_percentage: float
    forecast_confidence_score: float
    surge_window_start: datetime
    time_horizon_hours: float
    risk_level: str


class ClimateSurgeCorrelationResponse(BaseModel):
    stage: str
    processed_at: datetime
    geographical_scope: GeographicalScope
    environmental_inputs: EnvironmentalInputs
    ml_surge_forecasting: MLSurgeForecasting

    class Config:
        from_attributes = True


# ── Stage 3: Closed-Loop Production Coordination ─────────────────────────────

class TargetPlant(BaseModel):
    plant_id: str
    location: str
    current_daily_capacity_liters: float


class AIDemandForecast(BaseModel):
    baseline_regional_demand_liters: float
    predicted_surge_demand_liters: float
    deficit_risk_liters: float
    recommended_plant_utilization_percentage: float


class PriorityRoutingItem(BaseModel):
    facility_id: str
    facility_name: str
    urgency_score: float
    allocated_cylinders: int
    dispatch_deadline: datetime


class AutomatedActionPlan(BaseModel):
    production_schedule_shift: str
    priority_routing_queue: list[PriorityRoutingItem]


class ClosedLoopProductionResponse(BaseModel):
    stage: str
    processed_at: datetime
    target_plant: TargetPlant
    ai_demand_forecast: AIDemandForecast
    automated_action_plan: AutomatedActionPlan

    class Config:
        from_attributes = True


# ── Stage 4: Patient Outcome & Efficacy Loop ──────────────────────────────────

class ClinicalEnvironment(BaseModel):
    facility_id: str
    facility_name: str
    evaluation_period: str  # free-text range string


class GenderDistribution(BaseModel):
    male_percentage: float
    female_percentage: float


class ClinicalOutcomes(BaseModel):
    discharged_healthy: int
    transferred_to_tertiary: int
    mortality_count: int
    survival_rate_percentage: float


class PatientCohort(BaseModel):
    cohort_id: str
    age_group: str
    gender_distribution: GenderDistribution
    primary_diagnosis: str
    total_patients_tracked: int
    clinical_outcomes: ClinicalOutcomes


class AIInterventionCorrelation(BaseModel):
    predictive_alerts_issued_to_ward: int
    average_delivery_lead_time_hours: float
    zero_oxygen_stockout_incidents_maintained: bool
    historical_cohort_survival_baseline_percentage: float
    measured_survival_improvement_percentage: float


class ModelFeedbackLoop(BaseModel):
    supply_adequacy_score: float
    clinical_need_met_index: str
    algorithm_tuning_action: str


class PatientOutcomeEfficacyResponse(BaseModel):
    stage: str
    processed_at: datetime
    clinical_environment: ClinicalEnvironment
    anonymized_patient_cohort_data: list[PatientCohort]
    ai_intervention_correlation: AIInterventionCorrelation
    model_feedback_loop: ModelFeedbackLoop

    class Config:
        from_attributes = True
