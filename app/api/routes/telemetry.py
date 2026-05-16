"""
services.py — Full implementation of all service engines
Ingestion · Depletion · Climate · Production · Clinical
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.models import Device, Telemetry
from app.schemas import SessionCreate, TelemetryCreate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# IngestionService
# ---------------------------------------------------------------------------

class IngestionService:
    """Service layer for data ingestion (sync + async)."""

    # ------------------------------------------------------------------ sync

    @staticmethod
    def ingest_telemetry(db: Session, telemetry_data: TelemetryCreate) -> Telemetry:
        """
        Ingest real-time telemetry data (sync).

        * Upserts the device row (creates if absent, updates last_seen always).
        * Writes one Telemetry row per call.
        * Rolls back on integrity errors so the session stays usable.

        Args:
            db: SQLAlchemy sync session.
            telemetry_data: Validated telemetry payload.

        Returns:
            The freshly-committed Telemetry ORM instance.

        Raises:
            ValueError: If required fields are missing or out of range.
            RuntimeError: On unrecoverable database errors.
        """
        IngestionService._validate_telemetry(telemetry_data)

        try:
            # Upsert device
            device = db.query(Device).filter(Device.id == telemetry_data.id).first()
            if device is None:
                device = Device(id=telemetry_data.id)
                db.add(device)
                logger.info("Created new device record: %s", telemetry_data.id)

            device.last_seen = datetime.utcnow()

            # Persist telemetry
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

            logger.debug(
                "Telemetry ingested — device=%s pressure=%.2f battery=%.1f%%",
                telemetry_data.id,
                telemetry_data.p,
                telemetry_data.b,
            )
            return telemetry

        except IntegrityError as exc:
            db.rollback()
            logger.error("Integrity error ingesting telemetry for device %s: %s", telemetry_data.id, exc)
            raise RuntimeError(f"Duplicate or constraint violation for device {telemetry_data.id}") from exc
        except Exception as exc:
            db.rollback()
            logger.exception("Unexpected error during telemetry ingestion")
            raise RuntimeError("Telemetry ingestion failed") from exc

    @staticmethod
    def ingest_session(db: Session, session_data: SessionCreate):
        """
        Ingest a completed session summary (sync).

        * Upserts the device row.
        * Inserts a Session row; if the sid already exists the existing record
          is returned without raising (idempotent behaviour for retried POSTs).

        Args:
            db: SQLAlchemy sync session.
            session_data: Validated session summary payload.

        Returns:
            The created (or pre-existing) Session ORM instance.

        Raises:
            ValueError: If temporal ordering is invalid.
            RuntimeError: On unrecoverable database errors.
        """
        from app.models.models import Session as SessionModel

        IngestionService._validate_session(session_data)

        try:
            # Idempotency: return existing session if sid already persisted
            existing = db.query(SessionModel).filter(SessionModel.sid == session_data.sid).first()
            if existing is not None:
                logger.info("Session %s already exists — skipping insert", session_data.sid)
                return existing

            # Upsert device
            device = db.query(Device).filter(Device.id == session_data.id).first()
            if device is None:
                device = Device(id=session_data.id)
                db.add(device)
                logger.info("Created new device record: %s", session_data.id)

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

            logger.debug(
                "Session ingested sid=%s device=%s duration=%.1f min",
                session_data.sid,
                session_data.id,
                (session_data.t_end - session_data.t_start).total_seconds() / 60,
            )
            return session

        except IntegrityError as exc:
            db.rollback()
            logger.error("Integrity error ingesting session %s: %s", session_data.sid, exc)
            raise RuntimeError(f"Duplicate or constraint violation for session {session_data.sid}") from exc
        except Exception as exc:
            db.rollback()
            logger.exception("Unexpected error during session ingestion")
            raise RuntimeError("Session ingestion failed") from exc

    # ----------------------------------------------------------------- async

    @staticmethod
    async def async_ingest_telemetry(db: AsyncSession, telemetry_data: TelemetryCreate) -> Telemetry:
        """Async variant of ingest_telemetry."""
        IngestionService._validate_telemetry(telemetry_data)

        try:
            result = await db.execute(select(Device).where(Device.id == telemetry_data.id))
            device = result.scalar_one_or_none()
            if device is None:
                device = Device(id=telemetry_data.id)
                db.add(device)

            device.last_seen = datetime.utcnow()

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
            await db.commit()
            await db.refresh(telemetry)
            return telemetry

        except IntegrityError as exc:
            await db.rollback()
            raise RuntimeError(f"Duplicate or constraint violation for device {telemetry_data.id}") from exc
        except Exception as exc:
            await db.rollback()
            raise RuntimeError("Async telemetry ingestion failed") from exc

    @staticmethod
    async def async_ingest_session(db: AsyncSession, session_data: SessionCreate):
        """Async variant of ingest_session."""
        from app.models.models import Session as SessionModel

        IngestionService._validate_session(session_data)

        try:
            result = await db.execute(select(SessionModel).where(SessionModel.sid == session_data.sid))
            existing = result.scalar_one_or_none()
            if existing is not None:
                return existing

            result = await db.execute(select(Device).where(Device.id == session_data.id))
            device = result.scalar_one_or_none()
            if device is None:
                device = Device(id=session_data.id)
                db.add(device)

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
            await db.commit()
            await db.refresh(session)
            return session

        except IntegrityError as exc:
            await db.rollback()
            raise RuntimeError(f"Duplicate or constraint violation for session {session_data.sid}") from exc
        except Exception as exc:
            await db.rollback()
            raise RuntimeError("Async session ingestion failed") from exc


    @staticmethod
    def _validate_telemetry(data: TelemetryCreate) -> None:
        """Raise ValueError if telemetry payload violates basic constraints."""
        if not data.id:
            raise ValueError("Device ID must not be empty")
        if not (0.0 <= data.b <= 100.0):
            raise ValueError(f"Battery percentage out of range: {data.b}")
        if data.p < 0:
            raise ValueError(f"Pressure cannot be negative: {data.p}")
        if data.f < 0:
            raise ValueError(f"Flow rate cannot be negative: {data.f}")

    @staticmethod
    def _validate_session(data: SessionCreate) -> None:
        """Raise ValueError if session payload violates basic constraints."""
        if not data.id:
            raise ValueError("Device ID must not be empty")
        if not data.sid:
            raise ValueError("Session ID must not be empty")
        if data.t_end <= data.t_start:
            raise ValueError(
                f"Session end ({data.t_end}) must be after start ({data.t_start})"
            )
        if data.f_p > data.i_p:
            raise ValueError(
                f"Final pressure ({data.f_p}) cannot exceed initial ({data.i_p})"
            )

class DepletionEngine:
    """Predictive depletion analytics using pressure-drop gradient models."""

    # Minimum meaningful pressure drop (avoids noise-driven spurious predictions)
    _MIN_PRESSURE_DROP: float = 0.5
    # Pressure floor considered "empty" for medical gas cylinders (bar / psi)
    _EMPTY_FLOOR: float = 0.0

    @staticmethod
    def calculate_time_to_empty(
        initial_pressure: float,
        final_pressure: float,
        duration_minutes: float,
    ) -> float:
        """
        Estimate minutes until the cylinder reaches zero pressure.

        Uses a linear pressure-drop model (ideal-gas approximation):
            drop_rate = (P_initial - P_final) / duration
            time_to_empty = P_final / drop_rate

        Edge-cases handled:
        * Already empty or inverted pressures → 0
        * Zero or negative duration → raises ValueError
        * Negligible drop (noise) → float('inf')  (effectively stable)
        * Negative result (should not occur with valid inputs) → 0

        Args:
            initial_pressure: Pressure at the start of the measurement window.
            final_pressure:   Pressure at the end of the measurement window.
            duration_minutes: Length of measurement window in minutes (> 0).

        Returns:
            Estimated minutes until pressure reaches zero; float('inf') if
            the cylinder appears stable.

        Raises:
            ValueError: If duration_minutes ≤ 0.
        """
        if duration_minutes <= 0:
            raise ValueError(f"duration_minutes must be positive, got {duration_minutes}")

        # Already empty or counter-physical reading
        if final_pressure <= DepletionEngine._EMPTY_FLOOR:
            return 0.0
        if initial_pressure <= final_pressure:
            # Pressure increased or stayed the same — consider stable
            return float("inf")

        pressure_drop = initial_pressure - final_pressure

        # Drop too small to be meaningful; treat as stable
        if pressure_drop < DepletionEngine._MIN_PRESSURE_DROP:
            return float("inf")

        drop_rate = pressure_drop / duration_minutes  # units/min

        time_to_empty = final_pressure / drop_rate
        return max(0.0, time_to_empty)

    @staticmethod
    def calculate_critical_threshold(
        final_pressure: float,
        critical_level: float = 20.0,
        drop_rate: Optional[float] = None,
    ) -> float:
        """
        Estimate time (minutes) until the cylinder reaches a critical pressure level.

        Two modes:
        * If drop_rate is supplied: returns time in **minutes** derived from the
          actual consumption rate.
        * If drop_rate is None:  returns the raw pressure headroom above
          critical_level (legacy behaviour preserved for backward compatibility).

        Args:
            final_pressure: Current cylinder pressure.
            critical_level: Alarm threshold (default 20 units).
            drop_rate:      Pressure consumed per minute; None for legacy mode.

        Returns:
            Minutes until critical level (if drop_rate provided), or pressure
            headroom (if drop_rate is None).  Returns 0 if already at or below
            critical_level.
        """
        if final_pressure <= critical_level:
            return 0.0

        headroom = final_pressure - critical_level

        if drop_rate is not None and drop_rate > 0:
            return headroom / drop_rate  # minutes

        # Legacy: return raw pressure headroom
        return headroom

    @staticmethod
    def multi_session_trend(
        sessions: list[dict[str, float]],
    ) -> dict[str, Any]:
        """
        Analyse depletion trends across multiple completed sessions.

        Each session dict must contain:
            {
                "initial_pressure": float,
                "final_pressure":   float,
                "duration_minutes": float,
            }

        Returns a dict with:
            avg_drop_rate      — mean pressure drop per minute across sessions
            std_drop_rate      — standard deviation (0.0 if < 2 sessions)
            predicted_tte      — predicted time-to-empty (minutes) using avg rate
                                  given the most recent final_pressure
            trend              — "ACCELERATING" | "STABLE" | "DECELERATING" | "INSUFFICIENT_DATA"
        """
        if not sessions:
            return {
                "avg_drop_rate": 0.0,
                "std_drop_rate": 0.0,
                "predicted_tte": float("inf"),
                "trend": "INSUFFICIENT_DATA",
            }

        rates: list[float] = []
        for s in sessions:
            try:
                drop = s["initial_pressure"] - s["final_pressure"]
                dur = s["duration_minutes"]
                if dur > 0 and drop >= DepletionEngine._MIN_PRESSURE_DROP:
                    rates.append(drop / dur)
            except (KeyError, ZeroDivisionError):
                continue

        if not rates:
            return {
                "avg_drop_rate": 0.0,
                "std_drop_rate": 0.0,
                "predicted_tte": float("inf"),
                "trend": "INSUFFICIENT_DATA",
            }

        avg_rate = statistics.mean(rates)
        std_rate = statistics.stdev(rates) if len(rates) > 1 else 0.0

        last_pressure = sessions[-1]["final_pressure"]
        predicted_tte = last_pressure / avg_rate if avg_rate > 0 else float("inf")

        # Trend: compare first-half vs second-half average rates
        mid = len(rates) // 2
        if len(rates) >= 4:
            first_half_avg = statistics.mean(rates[:mid])
            second_half_avg = statistics.mean(rates[mid:])
            if second_half_avg > first_half_avg * 1.10:
                trend = "ACCELERATING"
            elif second_half_avg < first_half_avg * 0.90:
                trend = "DECELERATING"
            else:
                trend = "STABLE"
        else:
            trend = "INSUFFICIENT_DATA"

        return {
            "avg_drop_rate": round(avg_rate, 4),
            "std_drop_rate": round(std_rate, 4),
            "predicted_tte": round(predicted_tte, 2),
            "trend": trend,
        }


class ClimateEngine:
    """Climate & health surge correlation engine."""

    # Scoring weights (must sum to 100 for intuitive percentage output)
    _PM25_MAX_SCORE: int = 40
    _HUMIDITY_MAX_SCORE: int = 30
    _TEMP_MAX_SCORE: int = 20
    _AQI_MAX_SCORE: int = 10  # optional auxiliary input

    _RISK_THRESHOLDS = {
        "CRITICAL": 70,
        "HIGH": 50,
        "MODERATE": 30,
        "LOW": 0,
    }

    @staticmethod
    def calculate_surge_risk(
        pm25: float,
        humidity: float,
        temperature: float,
        aqi: Optional[float] = None,
    ) -> tuple[str, float]:
        """
        Calculate climate-driven demand-surge risk level.

        Scoring model (additive, capped at 100):
            PM2.5   — up to 40 pts  (dominant respiratory driver)
            Humidity — up to 30 pts
            Temperature — up to 20 pts  (extreme heat or cold)
            AQI (optional) — up to 10 pts bonus

        Risk bands:
            CRITICAL  ≥ 70
            HIGH      ≥ 50
            MODERATE  ≥ 30
            LOW       < 30

        Args:
            pm25:        PM2.5 concentration (µg/m³).
            humidity:    Relative humidity (%).
            temperature: Ambient temperature (°C).
            aqi:         Optional Air Quality Index for bonus scoring.

        Returns:
            (risk_level: str, surge_percentage: float)

        Raises:
            ValueError: If any primary input is outside physically valid range.
        """
        ClimateEngine._validate_climate_inputs(pm25, humidity, temperature)

        risk_score: float = 0.0

        # --- PM2.5 scoring (WHO tiers) ---
        if pm25 > 150:         # Hazardous
            risk_score += 40
        elif pm25 > 75:        # Very Unhealthy
            risk_score += 30
        elif pm25 > 55:        # Unhealthy
            risk_score += 22
        elif pm25 > 35:        # Unhealthy for sensitive groups
            risk_score += 14
        elif pm25 > 12:        # Moderate
            risk_score += 6

        # --- Humidity scoring ---
        if humidity > 85:      # Very high — mould / dust mite proliferation
            risk_score += 30
        elif humidity > 70:
            risk_score += 20
        elif humidity > 60:
            risk_score += 12
        elif humidity < 20:    # Very dry — mucosal irritation
            risk_score += 15
        elif humidity < 30:
            risk_score += 8

        # --- Temperature scoring (dual extremes) ---
        if temperature < 0 or temperature > 40:    # Severe
            risk_score += 20
        elif temperature < 5 or temperature > 38:  # High stress
            risk_score += 14
        elif temperature < 10 or temperature > 35: # Moderate stress
            risk_score += 8
        elif temperature < 15 or temperature > 30: # Mild stress
            risk_score += 4

        # --- Optional AQI bonus ---
        if aqi is not None:
            if aqi > 200:
                risk_score += 10
            elif aqi > 150:
                risk_score += 7
            elif aqi > 100:
                risk_score += 4

        surge_percentage = min(100.0, round(risk_score, 1))

        # Determine risk level (highest matching threshold wins)
        risk_level = "LOW"
        for level, threshold in ClimateEngine._RISK_THRESHOLDS.items():
            if surge_percentage >= threshold:
                risk_level = level
                break

        return risk_level, surge_percentage

    @staticmethod
    def calculate_regional_surge(
        stations: list[dict[str, float]],
    ) -> dict[str, Any]:
        """
        Aggregate climate readings from multiple monitoring stations into a
        single regional risk assessment.

        Each station dict:
            { "pm25": float, "humidity": float, "temperature": float,
              "aqi": float (optional), "weight": float (optional, default 1.0) }

        Returns:
            {
                "regional_risk_level":    str,
                "regional_surge_pct":     float,
                "station_count":          int,
                "worst_station_pct":      float,
                "avg_pm25":               float,
                "avg_humidity":           float,
                "avg_temperature":        float,
            }
        """
        if not stations:
            return {
                "regional_risk_level": "LOW",
                "regional_surge_pct": 0.0,
                "station_count": 0,
                "worst_station_pct": 0.0,
                "avg_pm25": 0.0,
                "avg_humidity": 0.0,
                "avg_temperature": 0.0,
            }

        weighted_surge_sum = 0.0
        total_weight = 0.0
        worst_pct = 0.0
        pm25_vals, humidity_vals, temp_vals = [], [], []

        for station in stations:
            try:
                pm25 = float(station["pm25"])
                humidity = float(station["humidity"])
                temperature = float(station["temperature"])
                aqi = station.get("aqi")
                weight = float(station.get("weight", 1.0))

                _, surge_pct = ClimateEngine.calculate_surge_risk(
                    pm25, humidity, temperature, aqi
                )
                weighted_surge_sum += surge_pct * weight
                total_weight += weight
                worst_pct = max(worst_pct, surge_pct)
                pm25_vals.append(pm25)
                humidity_vals.append(humidity)
                temp_vals.append(temperature)

            except (KeyError, ValueError):
                continue

        if total_weight == 0:
            regional_surge = 0.0
        else:
            regional_surge = round(weighted_surge_sum / total_weight, 1)

        regional_risk = "LOW"
        for level, threshold in ClimateEngine._RISK_THRESHOLDS.items():
            if regional_surge >= threshold:
                regional_risk = level
                break

        return {
            "regional_risk_level": regional_risk,
            "regional_surge_pct": regional_surge,
            "station_count": len(pm25_vals),
            "worst_station_pct": round(worst_pct, 1),
            "avg_pm25": round(statistics.mean(pm25_vals), 2) if pm25_vals else 0.0,
            "avg_humidity": round(statistics.mean(humidity_vals), 2) if humidity_vals else 0.0,
            "avg_temperature": round(statistics.mean(temp_vals), 2) if temp_vals else 0.0,
        }

    @staticmethod
    def _validate_climate_inputs(pm25: float, humidity: float, temperature: float) -> None:
        if pm25 < 0:
            raise ValueError(f"PM2.5 cannot be negative: {pm25}")
        if not (0.0 <= humidity <= 100.0):
            raise ValueError(f"Humidity out of range [0,100]: {humidity}")
        if not (-90.0 <= temperature <= 60.0):
            raise ValueError(f"Temperature out of plausible range [-90, 60]°C: {temperature}")


# ---------------------------------------------------------------------------
# ProductionEngine
# ---------------------------------------------------------------------------

class ProductionEngine:
    """Production planning and demand-optimisation engine."""

    _HIGH_UTILIZATION: float = 80.0   # % — trigger distribution alert
    _TARGET_UTILIZATION: float = 70.0  # % — maintain/increase crossover
    _SURGE_BUFFER_PCT: float = 0.15   # 15% safety stock buffer
    _MAX_RAMP_PER_PERIOD: float = 0.20  # maximum 20% ramp per period

    @staticmethod
    def optimize_demand_forecast(
        current_utilization: float,
        demand_forecast: list[float],
        inventory_days: float = 7.0,
        lead_time_days: float = 3.0,
    ) -> dict[str, Any]:
        """
        Generate a multi-period optimised production plan.

        Algorithm:
        1. Validate inputs.
        2. Compute a safety-stock adjusted target for each forecast period.
        3. Determine ramp direction and magnitude (capped at _MAX_RAMP_PER_PERIOD).
        4. Set procurement and distribution alerts.
        5. Return a structured action plan with period-level recommendations.

        Args:
            current_utilization: Plant utilisation as a percentage (0–100).
            demand_forecast:     Ordered list of demand units per planning period.
            inventory_days:      Current stock expressed in days of supply.
            lead_time_days:      Procurement lead time in days.

        Returns:
            Detailed action plan dictionary.

        Raises:
            ValueError: On out-of-range inputs.
        """
        if not (0.0 <= current_utilization <= 100.0):
            raise ValueError(f"current_utilization must be 0–100, got {current_utilization}")
        if inventory_days < 0:
            raise ValueError("inventory_days cannot be negative")
        if lead_time_days < 0:
            raise ValueError("lead_time_days cannot be negative")
        if not demand_forecast:
            raise ValueError("demand_forecast must contain at least one period")

        # Clip to valid range
        demand_forecast = [max(0.0, d) for d in demand_forecast]

        peak_demand = max(demand_forecast)
        avg_demand = statistics.mean(demand_forecast)
        demand_volatility = (
            statistics.stdev(demand_forecast) / avg_demand
            if len(demand_forecast) > 1 and avg_demand > 0
            else 0.0
        )

        # Safety stock: higher volatility → larger buffer
        safety_buffer = ProductionEngine._SURGE_BUFFER_PCT * (1 + demand_volatility)
        target_production = avg_demand * (1 + safety_buffer)

        # Utilisation-based adjustment direction
        if current_utilization >= ProductionEngine._HIGH_UTILIZATION:
            adjust_production = "maintain"
        elif current_utilization >= ProductionEngine._TARGET_UTILIZATION:
            adjust_production = "slight_increase"
        else:
            adjust_production = "increase"

        # Period-level plan
        period_plans: list[dict] = []
        for i, period_demand in enumerate(demand_forecast):
            adjusted_target = period_demand * (1 + safety_buffer)
            ramp = min(
                (adjusted_target - (current_utilization / 100 * peak_demand))
                / max(peak_demand, 1),
                ProductionEngine._MAX_RAMP_PER_PERIOD,
            )
            period_plans.append(
                {
                    "period": i + 1,
                    "forecast_demand": round(period_demand, 2),
                    "target_production": round(adjusted_target, 2),
                    "recommended_ramp_pct": round(max(0.0, ramp) * 100, 1),
                }
            )

        # Stock-out risk: compare inventory cover against lead time
        avg_daily_demand = avg_demand  # assume period == 1 day; caller can normalise
        days_of_cover = inventory_days
        stock_out_risk = days_of_cover < lead_time_days * 1.5

        action_plan = {
            "adjust_production": adjust_production,
            "optimize_scheduling": True,
            "alert_distribution": current_utilization > ProductionEngine._HIGH_UTILIZATION,
            "stock_out_risk": stock_out_risk,
            "recommended_procurement": stock_out_risk,
            "peak_demand": round(peak_demand, 2),
            "avg_demand": round(avg_demand, 2),
            "demand_volatility_pct": round(demand_volatility * 100, 1),
            "safety_buffer_pct": round(safety_buffer * 100, 1),
            "target_production_per_period": round(target_production, 2),
            "period_plans": period_plans,
            "summary": (
                f"Plant at {current_utilization:.1f}% utilisation. "
                f"{'Stock-out risk detected — expedite procurement. ' if stock_out_risk else ''}"
                f"Recommended action: {adjust_production.replace('_', ' ')}."
            ),
        }

        return action_plan

    @staticmethod
    def reorder_point(
        avg_daily_usage: float,
        lead_time_days: float,
        safety_stock_days: float = 2.0,
    ) -> float:
        """
        Calculate the reorder point for a consumable.

        ROP = (avg_daily_usage × lead_time_days) + (avg_daily_usage × safety_stock_days)

        Args:
            avg_daily_usage:   Average units consumed per day.
            lead_time_days:    Procurement lead time in days.
            safety_stock_days: Safety stock expressed as days of supply.

        Returns:
            Reorder point (units).
        """
        if avg_daily_usage < 0 or lead_time_days < 0 or safety_stock_days < 0:
            raise ValueError("All reorder_point arguments must be non-negative")

        return avg_daily_usage * (lead_time_days + safety_stock_days)


# ---------------------------------------------------------------------------
# ClinicalEngine
# ---------------------------------------------------------------------------

class ClinicalEngine:
    """Clinical outcomes evaluation and feedback loop engine."""

    # Outcome improvement thresholds
    _SIGNIFICANT_IMPROVEMENT: float = 0.10   # 10% improvement = significant
    _CRITICAL_DETERIORATION: float = -0.15   # 15% deterioration = critical

    @staticmethod
    def evaluate_cohort_outcomes(
        cohort_data: dict[str, Any],
        intervention_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Evaluate clinical outcomes and generate structured feedback.

        Inputs
        ------
        cohort_data:
            {
                "cohort_id":           str,
                "size":                int,
                "baseline_scores":     list[float],  # pre-intervention outcome scores
                "followup_scores":     list[float],  # post-intervention outcome scores
                "adherence_rates":     list[float],  # % adherence per patient (0–1)
                "adverse_events":      int,           # count of adverse events
                "dropout_count":       int,
            }

        intervention_metrics:
            {
                "intervention_id":     str,
                "type":                str,           # e.g. "pharmacological", "device"
                "duration_days":       int,
                "protocol_version":    str,
                "compliance_target":   float,         # target adherence rate (0–1)
            }

        Returns
        -------
        A structured dict containing outcome_status, delta statistics,
        recommendations, next_actions, and flag fields for escalation.

        Raises
        ------
        ValueError: If cohort_data is structurally invalid.
        """
        ClinicalEngine._validate_cohort_data(cohort_data)

        baseline = cohort_data["baseline_scores"]
        followup = cohort_data["followup_scores"]
        adherence = cohort_data.get("adherence_rates", [])
        cohort_size = cohort_data.get("size", len(baseline))
        adverse_events = cohort_data.get("adverse_events", 0)
        dropout_count = cohort_data.get("dropout_count", 0)

        # Outcome deltas
        deltas = [f - b for b, f in zip(baseline, followup)]
        mean_baseline = statistics.mean(baseline) if baseline else 0.0
        mean_followup = statistics.mean(followup) if followup else 0.0
        mean_delta = statistics.mean(deltas) if deltas else 0.0
        std_delta = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
        pct_change = (mean_delta / mean_baseline) if mean_baseline != 0 else 0.0

        # Responder rate (patients with any improvement)
        responders = sum(1 for d in deltas if d > 0)
        responder_rate = responders / len(deltas) if deltas else 0.0

        # Adherence analysis
        mean_adherence = statistics.mean(adherence) if adherence else None
        compliance_target = intervention_metrics.get("compliance_target", 0.80)
        adherence_gap = (mean_adherence - compliance_target) if mean_adherence is not None else None

        # Adverse event rate
        ae_rate = adverse_events / cohort_size if cohort_size else 0.0
        dropout_rate = dropout_count / cohort_size if cohort_size else 0.0

        # Determine outcome status
        if pct_change >= ClinicalEngine._SIGNIFICANT_IMPROVEMENT:
            outcome_status = "POSITIVE"
        elif pct_change <= ClinicalEngine._CRITICAL_DETERIORATION:
            outcome_status = "CRITICAL"
        elif pct_change < 0:
            outcome_status = "NEGATIVE"
        else:
            outcome_status = "NEUTRAL"

        # Build recommendations
        recommendations: list[str] = []
        next_actions: list[str] = []
        escalate_flag = False

        if outcome_status == "CRITICAL":
            escalate_flag = True
            recommendations.append(
                "Immediate protocol review required — cohort shows significant deterioration."
            )
            next_actions.append("Convene clinical safety board within 48 hours.")
            next_actions.append("Pause enrolment pending root-cause analysis.")

        if outcome_status in ("POSITIVE",):
            recommendations.append(
                f"Protocol '{intervention_metrics.get('intervention_id', 'N/A')}' "
                f"demonstrates meaningful improvement ({pct_change:.1%}) — consider scaling."
            )
            next_actions.append("Prepare peer-review submission with current cohort data.")

        if mean_adherence is not None and adherence_gap is not None and adherence_gap < -0.10:
            recommendations.append(
                f"Adherence is {mean_adherence:.1%}, below target of {compliance_target:.1%}. "
                "Implement digital reminder or simplified dosing protocol."
            )
            next_actions.append("Deploy adherence-support intervention within 2 weeks.")

        if ae_rate > 0.05:
            escalate_flag = True
            recommendations.append(
                f"Adverse event rate ({ae_rate:.1%}) exceeds 5% threshold — pharmacovigilance review needed."
            )
            next_actions.append("Submit adverse event report to clinical governance team.")

        if dropout_rate > 0.20:
            recommendations.append(
                f"High dropout rate ({dropout_rate:.1%}) may introduce selection bias. "
                "Review retention strategy."
            )
            next_actions.append("Conduct exit interviews for withdrawn participants.")

        if not recommendations:
            recommendations.append("Outcomes within expected range. Continue current protocol.")
            next_actions.append("Schedule 30-day follow-up assessment.")

        return {
            "cohort_id": cohort_data.get("cohort_id", "unknown"),
            "intervention_id": intervention_metrics.get("intervention_id", "unknown"),
            "outcome_status": outcome_status,
            "mean_baseline_score": round(mean_baseline, 3),
            "mean_followup_score": round(mean_followup, 3),
            "mean_delta": round(mean_delta, 3),
            "std_delta": round(std_delta, 3),
            "pct_change": round(pct_change * 100, 2),
            "responder_rate_pct": round(responder_rate * 100, 1),
            "mean_adherence": round(mean_adherence, 3) if mean_adherence is not None else None,
            "adverse_event_rate_pct": round(ae_rate * 100, 2),
            "dropout_rate_pct": round(dropout_rate * 100, 2),
            "escalate": escalate_flag,
            "recommendations": recommendations,
            "next_actions": next_actions,
            "evaluated_at": datetime.utcnow().isoformat() + "Z",
        }

    @staticmethod
    def _validate_cohort_data(cohort_data: dict) -> None:
        for field in ("baseline_scores", "followup_scores"):
            if field not in cohort_data:
                raise ValueError(f"cohort_data missing required field: '{field}'")
            if not isinstance(cohort_data[field], list) or not cohort_data[field]:
                raise ValueError(f"'{field}' must be a non-empty list of floats")
        if len(cohort_data["baseline_scores"]) != len(cohort_data["followup_scores"]):
            raise ValueError(
                "baseline_scores and followup_scores must have the same length"
            )