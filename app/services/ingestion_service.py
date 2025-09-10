from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime

from app.models.models import Device, Telemetry
from app.schemas import TelemetryCreate, SessionCreate


class IngestionService:
    """Service layer for data ingestion"""
    
    @staticmethod
    def ingest_telemetry(db: Session, telemetry_data: TelemetryCreate):
        """
        Ingest real time telemetry data (sync version)
        
        Args:
            db: Database session
            telemetry_data: Telemetry payload
            
        Returns:
            Created telemetry record
        """
        # Ensure device exists
        device = db.query(Device).filter(Device.id == telemetry_data.id).first()
        if not device:
            device = Device(id=telemetry_data.id)
            db.add(device)
        
        # Update last_seen
        device.last_seen = datetime.utcnow()
        
        # Create telemetry record
        telemetry = Telemetry(
            device_id=telemetry_data.id,
            timestamp=telemetry_data.t,
            battery=telemetry_data.b,
            pressure=telemetry_data.p,
            flow=telemetry_data.f,
            signal_strength=telemetry_data.c,
            location=telemetry_data.l,
        )
        
        db.add(telemetry)
        db.commit()
        db.refresh(telemetry)
        
        return telemetry
    
    @staticmethod
    def ingest_session(db: Session, session_data: SessionCreate):
        """
        Ingest session summary data (sync version)
        
        Args:
            db: Database session
            session_data: Session summary payload
            
        Returns:
            Created session record
        """
        from app.models.models import Session as SessionModel
        
        # Ensure device exists
        device = db.query(Device).filter(Device.id == session_data.id).first()
        if not device:
            device = Device(id=session_data.id)
            db.add(device)
        
        # Create session record
        session = SessionModel(
            sid=session_data.sid,
            device_id=session_data.id,
            location=session_data.lc,
            t_start=session_data.t_start,
            t_end=session_data.t_end,
            initial_pressure=session_data.i_p,
            final_pressure=session_data.f_p,
            flow_rate=session_data.f_r,
            battery_final=session_data.fb_pct,
            fault_flag=session_data.hf_log,
            signal_strength=session_data.c_st,
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return session


class DepletionEngine:
    """Service layer for predictive depletion analytics"""
    
    @staticmethod
    def calculate_time_to_empty(
        initial_pressure: float,
        final_pressure: float,
        duration_minutes: float,
    ) -> float:
        """
        Calculate time to empty using pressure drop gradient
        
        Uses ideal gas approximation:
        - Measure pressure drop over a period
        - Calculate consumption rate
        - Estimate when pressure reaches zero
        
        Args:
            initial_pressure: Starting pressure (in system units)
            final_pressure: Current pressure (in system units)
            duration_minutes: Duration of measurement period in minutes
            
        Returns:
            Minutes until empty (0 pressure)
        """
        if final_pressure <= 0 or initial_pressure <= final_pressure:
            return 0
        
        pressure_drop = initial_pressure - final_pressure
        drop_rate = pressure_drop / duration_minutes  # pressure drop per minute
        
        if drop_rate <= 0:
            return float('inf')
        
        # Calculate time for pressure to drop from current level to zero
        time_to_empty = final_pressure / drop_rate
        return max(0, time_to_empty)
    
    @staticmethod
    def calculate_critical_threshold(final_pressure: float, critical_level: float = 20.0) -> float:
        """
        Calculate time until critical pressure level is reached
        
        Args:
            final_pressure: Current pressure
            critical_level: Critical pressure threshold
            
        Returns:
            Time in minutes until critical level
        """
        if final_pressure <= critical_level:
            return 0
        
        return (final_pressure - critical_level)


class ClimateEngine:
    """Service layer for climate & health surge correlation"""
    
    @staticmethod
    def calculate_surge_risk(
        pm25: float,
        humidity: float,
        temperature: float,
    ) -> tuple[str, float]:
        """
        Calculate climate surge risk level
        
        Args:
            pm25: PM2.5 concentration
            humidity: Relative humidity percentage
            temperature: Temperature in Celsius
            
        Returns:
            Tuple of (risk_level, surge_percentage)
        """
        risk_score = 0
        
        # PM2.5 scoring
        if pm25 > 150:
            risk_score += 35
        elif pm25 > 75:
            risk_score += 25
        elif pm25 > 35:
            risk_score += 15
        
        # Humidity scoring
        if humidity > 80:
            risk_score += 30
        elif humidity > 60:
            risk_score += 15
        
        # Temperature scoring
        if temperature < 5 or temperature > 38:
            risk_score += 20
        elif temperature < 15 or temperature > 30:
            risk_score += 10
        
        # Determine risk level
        if risk_score >= 70:
            risk_level = "CRITICAL"
        elif risk_score >= 50:
            risk_level = "HIGH"
        elif risk_score >= 30:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"
        
        surge_percentage = min(100, risk_score)
        
        return risk_level, surge_percentage


class ProductionEngine:
    """Service layer for production planning"""
    
    @staticmethod
    def optimize_demand_forecast(
        current_utilization: float,
        demand_forecast: list,
    ) -> dict:
        """
        Generate optimized production plan based on demand
        
        Args:
            current_utilization: Current plant utilization (0-100%)
            demand_forecast: Forecasted demand per period
            
        Returns:
            Action plan dictionary
        """
        action_plan = {
            "adjust_production": "maintain" if current_utilization > 70 else "increase",
            "optimize_scheduling": True,
            "alert_distribution": current_utilization > 80,
        }
        
        return action_plan


class ClinicalEngine:
    """Service layer for clinical outcomes loop"""
    
    @staticmethod
    def evaluate_cohort_outcomes(
        cohort_data: dict,
        intervention_metrics: dict,
    ) -> dict:
        """
        Evaluate clinical outcomes and generate feedback
        
        Args:
            cohort_data: Patient cohort data
            intervention_metrics: Metrics from interventions
            
        Returns:
            Model feedback and recommendations
        """
        feedback = {
            "outcome_status": "positive",
            "recommendations": [],
            "next_actions": []
        }
        
        return feedback
