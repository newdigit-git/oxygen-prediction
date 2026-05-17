
from __future__ import annotations

import os
import json
import logging
import structlog
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from sqlalchemy.orm import Session

from app.models.models import Device, Telemetry
from app.schemas import TelemetryCreate, SessionCreate


load_dotenv()

log = structlog.get_logger(__name__)

# --- Env config -------------------------------------------------------------

OPENAQ_API_KEY: str           = os.environ.get("OPENAQ_API_KEY", "")
OPENWEATHER_API_KEY: str      = os.environ.get("OPENWEATHER_API_KEY", "")
NEWDIGIT_LLM_URL: str         = os.environ.get("NEWDIGIT_LLM_URL", "")
NEWDIGIT_LLM_API_KEY: str     = os.environ.get("NEWDIGIT_LLM_API_KEY", "")
NEWDIGIT_LLM_MODEL: str       = os.environ.get("NEWDIGIT_LLM_MODEL", "newdigit-v1")
CRITICAL_PRESSURE_LEVEL: float = float(os.environ.get("CRITICAL_PRESSURE_LEVEL", "20.0"))
LLM_TIMEOUT_SECONDS: int      = int(os.environ.get("LLM_TIMEOUT_SECONDS", "30"))

# --- Retry policy for transient HTTP errors ---------------------------------

_RETRYABLE = (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)

_retry_transient = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(_RETRYABLE),
    before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
)


# ---------------------------------------------------------------------------
# Shared HTTP helpers
# ---------------------------------------------------------------------------

def _llm_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if NEWDIGIT_LLM_API_KEY:
        headers["Authorization"] = f"Bearer {NEWDIGIT_LLM_API_KEY}"
    return headers


@_retry_transient
def _llm_complete(system: str, user: str, max_tokens: int = 512) -> str:
    """
    POST a chat-completion request to the Newdigit LLM endpoint and return
    the assistant's text content.

    Raises:
        EnvironmentError: if NEWDIGIT_LLM_URL is not configured.
        httpx.HTTPStatusError: on non-2xx responses after all retries.
    """
    if not NEWDIGIT_LLM_URL:
        raise EnvironmentError("NEWDIGIT_LLM_URL is not set in the environment.")

    payload = {
        "model": NEWDIGIT_LLM_MODEL,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    }

    with httpx.Client(timeout=LLM_TIMEOUT_SECONDS) as client:
        resp = client.post(
            f"{NEWDIGIT_LLM_URL.rstrip('/')}/v1/messages",
            headers=_llm_headers(),
            json=payload,
        )
        resp.raise_for_status()

    data = resp.json()
    # Support both OpenAI-style and Anthropic-style response envelopes
    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    if "content" in data:
        blocks = data["content"]
        return " ".join(b["text"] for b in blocks if b.get("type") == "text")
    raise ValueError(f"Unrecognised LLM response shape: {list(data.keys())}")


# ---------------------------------------------------------------------------
# IngestionService
# ---------------------------------------------------------------------------

class IngestionService:
    """Service layer for data ingestion."""

    @staticmethod
    def ingest_telemetry(db: Session, telemetry_data: TelemetryCreate) -> Telemetry:
        """
        Upsert a Device record and persist a real-time Telemetry row.

        Args:
            db: SQLAlchemy session.
            telemetry_data: Validated telemetry payload.

        Returns:
            The newly created Telemetry ORM instance.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: on DB failure (caller should rollback).
        """
        log.info("ingest_telemetry.start", device_id=telemetry_data.id)

        try:
            device = db.query(Device).filter(Device.id == telemetry_data.id).first()
            if not device:
                device = Device(id=telemetry_data.id)
                db.add(device)
                log.info("ingest_telemetry.new_device", device_id=telemetry_data.id)

            device.last_seen = datetime.now(timezone.utc)

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

            log.info("ingest_telemetry.ok", device_id=telemetry_data.id, telemetry_id=telemetry.id)
            return telemetry

        except Exception:
            db.rollback()
            log.exception("ingest_telemetry.error", device_id=telemetry_data.id)
            raise

    @staticmethod
    def ingest_session(db: Session, session_data: SessionCreate):
        """
        Upsert a Device record and persist a Session summary row.

        Args:
            db: SQLAlchemy session.
            session_data: Validated session summary payload.

        Returns:
            The newly created Session ORM instance.
        """
        from app.models.models import Session as SessionModel

        log.info("ingest_session.start", device_id=session_data.id, sid=session_data.sid)

        try:
            device = db.query(Device).filter(Device.id == session_data.id).first()
            if not device:
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
            db.commit()
            db.refresh(session)

            log.info("ingest_session.ok", device_id=session_data.id, sid=session_data.sid)
            return session

        except Exception:
            db.rollback()
            log.exception("ingest_session.error", device_id=session_data.id)
            raise


# ---------------------------------------------------------------------------
# DepletionEngine
# ---------------------------------------------------------------------------

class DepletionEngine:
    """Predictive depletion analytics based on pressure telemetry."""

    @staticmethod
    def calculate_time_to_empty(
        initial_pressure: float,
        final_pressure: float,
        duration_minutes: float,
    ) -> float:
        """
        Estimate minutes until cylinder reaches zero pressure.

        Uses a linear pressure-drop-rate model (ideal-gas approximation):
            drop_rate  = (P_initial − P_final) / duration
            time_empty = P_final / drop_rate

        Args:
            initial_pressure: Pressure at the start of the measurement window.
            final_pressure:   Pressure at the end of the measurement window.
            duration_minutes: Length of the measurement window in minutes.

        Returns:
            Minutes until empty.  Returns 0 if already empty or inputs are
            invalid.  Returns float('inf') if no consumption was detected.

        Raises:
            ValueError: if duration_minutes is not positive.
        """
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be > 0")
        if final_pressure <= 0 or initial_pressure <= final_pressure:
            log.warning(
                "depletion.already_empty_or_invalid",
                initial=initial_pressure,
                final=final_pressure,
            )
            return 0.0

        pressure_drop = initial_pressure - final_pressure
        drop_rate = pressure_drop / duration_minutes

        if drop_rate <= 0:
            return float("inf")

        time_to_empty = final_pressure / drop_rate
        result = max(0.0, time_to_empty)

        log.info(
            "depletion.time_to_empty",
            initial=initial_pressure,
            final=final_pressure,
            duration_min=duration_minutes,
            drop_rate=round(drop_rate, 4),
            tte_minutes=round(result, 2),
        )
        return result

    @staticmethod
    def calculate_critical_threshold(
        final_pressure: float,
        initial_pressure: float,
        duration_minutes: float,
        critical_level: float = CRITICAL_PRESSURE_LEVEL,
    ) -> float:
        """
        Estimate minutes until pressure reaches the critical threshold.

        Args:
            final_pressure:   Current pressure reading.
            initial_pressure: Earlier pressure reading for rate calculation.
            duration_minutes: Time between the two readings.
            critical_level:   Pressure value considered critical (default from env).

        Returns:
            Minutes until critical level is reached, or 0 if already at/below it.
        """
        if final_pressure <= critical_level:
            log.warning(
                "depletion.already_critical",
                final=final_pressure,
                threshold=critical_level,
            )
            return 0.0

        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be > 0")

        pressure_drop = initial_pressure - final_pressure
        if pressure_drop <= 0:
            return float("inf")

        drop_rate = pressure_drop / duration_minutes
        time_to_critical = (final_pressure - critical_level) / drop_rate
        result = max(0.0, time_to_critical)

        log.info(
            "depletion.time_to_critical",
            final=final_pressure,
            threshold=critical_level,
            minutes=round(result, 2),
        )
        return result

    @staticmethod
    def get_llm_depletion_insight(
        initial_pressure: float,
        final_pressure: float,
        duration_minutes: float,
        device_id: str,
    ) -> str:
        """
        Ask the Newdigit LLM for a natural-language depletion narrative and
        recommended actions for the given device.

        Returns:
            Plain-text insight string from the LLM.
        """
        tte = DepletionEngine.calculate_time_to_empty(
            initial_pressure, final_pressure, duration_minutes
        )
        ttc = DepletionEngine.calculate_critical_threshold(
            final_pressure, initial_pressure, duration_minutes
        )

        user_prompt = (
            f"Device ID: {device_id}\n"
            f"Current pressure: {final_pressure} (was {initial_pressure} "
            f"{duration_minutes} minutes ago)\n"
            f"Time to empty: {round(tte, 1)} minutes\n"
            f"Time to critical threshold ({CRITICAL_PRESSURE_LEVEL}): {round(ttc, 1)} minutes\n\n"
            "Provide a concise clinical summary (≤ 120 words) explaining the "
            "urgency level and the single most important action a care coordinator "
            "should take right now."
        )

        insight = _llm_complete(
            system=(
                "You are a medical-device clinical analyst. Reply in plain text only. "
                "No markdown, no bullet points."
            ),
            user=user_prompt,
            max_tokens=200,
        )
        log.info("depletion.llm_insight_ok", device_id=device_id)
        return insight


# ---------------------------------------------------------------------------
# ClimateEngine
# ---------------------------------------------------------------------------

class ClimateEngine:
    """Climate & health-surge correlation with live air-quality data."""

    # ------------------------------------------------------------------
    # External API calls
    # ------------------------------------------------------------------

    @staticmethod
    @_retry_transient
    def fetch_air_quality(latitude: float, longitude: float) -> dict:
        """
        Fetch the latest PM2.5 reading nearest to (lat, lon) from the
        OpenAQ v3 API.

        https://docs.openaq.org/reference/locations_get_v3_locations_get

        Args:
            latitude:  WGS-84 latitude.
            longitude: WGS-84 longitude.

        Returns:
            Dict with keys: pm25 (float), station_name (str), measured_at (str).

        Raises:
            EnvironmentError: if OPENAQ_API_KEY is not set.
            httpx.HTTPStatusError: on non-2xx response after retries.
            ValueError: if no PM2.5 results are found nearby.
        """
        if not OPENAQ_API_KEY:
            raise EnvironmentError("OPENAQ_API_KEY is not set in the environment.")

        with httpx.Client(timeout=15) as client:
            # Step 1: find the nearest location that measures PM2.5
            loc_resp = client.get(
                "https://api.openaq.org/v3/locations",
                params={
                    "coordinates": f"{latitude},{longitude}",
                    "radius": 25000,          # 25 km search radius
                    "parameters_id": 2,       # 2 = PM2.5 in OpenAQ taxonomy
                    "limit": 1,
                    "order_by": "distance",
                    "sort": "asc",
                },
                headers={"X-API-Key": OPENAQ_API_KEY},
            )
            loc_resp.raise_for_status()
            loc_data = loc_resp.json()

            if not loc_data.get("results"):
                raise ValueError(
                    f"No PM2.5 monitoring station found within 25 km of "
                    f"({latitude}, {longitude})"
                )

            location = loc_data["results"][0]
            location_id = location["id"]
            station_name = location.get("name", "unknown")

            # Step 2: retrieve the latest PM2.5 measurement for that location
            meas_resp = client.get(
                f"https://api.openaq.org/v3/locations/{location_id}/latest",
                headers={"X-API-Key": OPENAQ_API_KEY},
            )
            meas_resp.raise_for_status()
            meas_data = meas_resp.json()

        pm25_results = [
            r for r in meas_data.get("results", [])
            if r.get("parameter", {}).get("name", "").lower() == "pm25"
        ]
        if not pm25_results:
            raise ValueError(f"No PM2.5 measurement returned for location {location_id}")

        latest = pm25_results[0]
        result = {
            "pm25": float(latest["value"]),
            "station_name": station_name,
            "measured_at": latest.get("datetime", {}).get("local", ""),
        }
        log.info("climate.air_quality_fetched", **result)
        return result

    @staticmethod
    @_retry_transient
    def fetch_weather(latitude: float, longitude: float) -> dict:
        """
        Fetch current temperature and relative humidity from OpenWeatherMap.

        https://openweathermap.org/current

        Args:
            latitude:  WGS-84 latitude.
            longitude: WGS-84 longitude.

        Returns:
            Dict with keys: temperature (°C, float), humidity (%, float).

        Raises:
            EnvironmentError: if OPENWEATHER_API_KEY is not set.
            httpx.HTTPStatusError: on non-2xx response after retries.
        """
        if not OPENWEATHER_API_KEY:
            raise EnvironmentError("OPENWEATHER_API_KEY is not set in the environment.")

        with httpx.Client(timeout=10) as client:
            resp = client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    "lat": latitude,
                    "lon": longitude,
                    "appid": OPENWEATHER_API_KEY,
                    "units": "metric",
                },
            )
            resp.raise_for_status()

        data = resp.json()
        result = {
            "temperature": float(data["main"]["temp"]),
            "humidity": float(data["main"]["humidity"]),
            "description": data["weather"][0]["description"],
        }
        log.info("climate.weather_fetched", **result)
        return result

    # ------------------------------------------------------------------
    # Risk scoring
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_surge_risk(
        pm25: float,
        humidity: float,
        temperature: float,
    ) -> tuple[str, float]:
        """
        Score environmental surge risk for respiratory patients.

        Scoring rubric
        ──────────────
        PM2.5 (µg/m³)          Humidity (%)        Temperature (°C)
        > 150  → +35            > 80  → +30          < 5  or > 38 → +20
        75–150 → +25            60–80 → +15          15–5 or 30–38 → +10
        35–75  → +15

        Risk bands: CRITICAL ≥ 70 | HIGH ≥ 50 | MODERATE ≥ 30 | LOW < 30

        Returns:
            (risk_level, surge_percentage) — surge capped at 100.
        """
        risk_score = 0

        if pm25 > 150:
            risk_score += 35
        elif pm25 > 75:
            risk_score += 25
        elif pm25 > 35:
            risk_score += 15

        if humidity > 80:
            risk_score += 30
        elif humidity > 60:
            risk_score += 15

        if temperature < 5 or temperature > 38:
            risk_score += 20
        elif temperature < 15 or temperature > 30:
            risk_score += 10

        if risk_score >= 70:
            risk_level = "CRITICAL"
        elif risk_score >= 50:
            risk_level = "HIGH"
        elif risk_score >= 30:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"

        surge_percentage = min(100.0, float(risk_score))

        log.info(
            "climate.surge_risk_scored",
            pm25=pm25,
            humidity=humidity,
            temperature=temperature,
            risk_level=risk_level,
            surge_percentage=surge_percentage,
        )
        return risk_level, surge_percentage

    # ------------------------------------------------------------------
    # Convenience: fetch live data → score → LLM narrative
    # ------------------------------------------------------------------

    @staticmethod
    def analyse_location(
        latitude: float,
        longitude: float,
    ) -> dict:
        """
        Full pipeline: fetch live air quality + weather, score surge risk,
        and generate an LLM-authored clinical alert narrative.

        Args:
            latitude:  Patient / device latitude.
            longitude: Patient / device longitude.

        Returns:
            Dict with keys:
                pm25, temperature, humidity, station_name, measured_at,
                weather_description, risk_level, surge_percentage, narrative.
        """
        air    = ClimateEngine.fetch_air_quality(latitude, longitude)
        weather = ClimateEngine.fetch_weather(latitude, longitude)

        risk_level, surge_pct = ClimateEngine.calculate_surge_risk(
            pm25=air["pm25"],
            humidity=weather["humidity"],
            temperature=weather["temperature"],
        )

        narrative = ClimateEngine._get_llm_narrative(
            pm25=air["pm25"],
            humidity=weather["humidity"],
            temperature=weather["temperature"],
            risk_level=risk_level,
            surge_pct=surge_pct,
            station_name=air["station_name"],
        )

        return {
            "pm25": air["pm25"],
            "temperature": weather["temperature"],
            "humidity": weather["humidity"],
            "station_name": air["station_name"],
            "measured_at": air["measured_at"],
            "weather_description": weather["description"],
            "risk_level": risk_level,
            "surge_percentage": surge_pct,
            "narrative": narrative,
        }

    @staticmethod
    def _get_llm_narrative(
        pm25: float,
        humidity: float,
        temperature: float,
        risk_level: str,
        surge_pct: float,
        station_name: str,
    ) -> str:
        """Generate a plain-text clinical alert via the Newdigit LLM."""
        user_prompt = (
            f"Environmental conditions near monitoring station '{station_name}':\n"
            f"  PM2.5: {pm25} µg/m³\n"
            f"  Humidity: {humidity}%\n"
            f"  Temperature: {temperature}°C\n"
            f"  Calculated surge risk: {risk_level} ({surge_pct}%)\n\n"
            "Write a concise (≤ 100 words) clinical alert message suitable for "
            "a respiratory care coordinator. Include the risk level, which "
            "environmental factor is driving it, and one actionable recommendation."
        )
        return _llm_complete(
            system=(
                "You are a respiratory health clinical advisor. "
                "Reply in plain text only. No markdown."
            ),
            user=user_prompt,
            max_tokens=180,
        )


# ---------------------------------------------------------------------------
# ProductionEngine
# ---------------------------------------------------------------------------

class ProductionEngine:
    """Production planning with LLM-assisted demand forecasting."""

    @staticmethod
    def optimize_demand_forecast(
        current_utilization: float,
        demand_forecast: list[float],
        plant_id: Optional[str] = None,
    ) -> dict:
        """
        Generate an optimized production plan.

        Deterministic rules handle the core logic; the Newdigit LLM enriches
        the plan with a natural-language rationale and secondary recommendations.

        Args:
            current_utilization: Current plant utilisation 0–100 %.
            demand_forecast:     Forecasted demand per upcoming period
                                 (arbitrary units, must be non-empty).
            plant_id:            Optional identifier for logging.

        Returns:
            Dict with keys:
                adjust_production, optimize_scheduling, alert_distribution,
                peak_forecast_period, avg_forecast_demand, llm_rationale.

        Raises:
            ValueError: if demand_forecast is empty or utilization out of range.
        """
        if not demand_forecast:
            raise ValueError("demand_forecast must contain at least one value.")
        if not 0 <= current_utilization <= 100:
            raise ValueError("current_utilization must be between 0 and 100.")

        avg_demand = sum(demand_forecast) / len(demand_forecast)
        peak_period = int(demand_forecast.index(max(demand_forecast)))

        if current_utilization > 90:
            adjust = "emergency_increase"
        elif current_utilization > 70:
            adjust = "maintain"
        else:
            adjust = "increase"

        action_plan = {
            "adjust_production": adjust,
            "optimize_scheduling": True,
            "alert_distribution": current_utilization > 80,
            "peak_forecast_period": peak_period,
            "avg_forecast_demand": round(avg_demand, 2),
        }

        try:
            action_plan["llm_rationale"] = ProductionEngine._get_llm_rationale(
                current_utilization=current_utilization,
                demand_forecast=demand_forecast,
                action_plan=action_plan,
            )
        except Exception as exc:
            log.warning("production.llm_rationale_failed", error=str(exc))
            action_plan["llm_rationale"] = None

        log.info(
            "production.plan_generated",
            plant_id=plant_id,
            utilization=current_utilization,
            **{k: v for k, v in action_plan.items() if k != "llm_rationale"},
        )
        return action_plan

    @staticmethod
    def _get_llm_rationale(
        current_utilization: float,
        demand_forecast: list[float],
        action_plan: dict,
    ) -> str:
        user_prompt = (
            f"Current plant utilisation: {current_utilization}%\n"
            f"Demand forecast (next {len(demand_forecast)} periods): "
            f"{demand_forecast}\n"
            f"Recommended action: {action_plan['adjust_production']}\n"
            f"Peak demand at period index: {action_plan['peak_forecast_period']}\n\n"
            "In ≤ 80 words, explain the rationale for this production decision "
            "and flag any supply-chain risks the operations team should monitor."
        )
        return _llm_complete(
            system=(
                "You are a supply-chain operations analyst for medical-gas production. "
                "Reply in plain text only."
            ),
            user=user_prompt,
            max_tokens=150,
        )


# ---------------------------------------------------------------------------
# ClinicalEngine
# ---------------------------------------------------------------------------

class ClinicalEngine:
    """Clinical outcomes loop with LLM-generated feedback and recommendations."""

    @staticmethod
    def evaluate_cohort_outcomes(
        cohort_data: dict,
        intervention_metrics: dict,
    ) -> dict:
        """
        Evaluate clinical outcomes for a patient cohort and generate structured
        feedback via the Newdigit LLM.

        Args:
            cohort_data: Patient cohort data.  Expected keys (all optional but
                         richer data yields better insights):
                            patient_count (int)
                            avg_daily_usage_minutes (float)
                            adherence_rate_pct (float)
                            hospitalization_rate_pct (float)
                            avg_spo2 (float)
                            cohort_id (str)
            intervention_metrics: Metrics from recent care interventions.
                            intervention_type (str)
                            reach_pct (float)
                            completion_rate_pct (float)
                            avg_response_time_hours (float)

        Returns:
            Dict with keys:
                outcome_status, recommendations (list[str]),
                next_actions (list[str]), llm_feedback (str),
                evaluated_at (ISO timestamp).

        Raises:
            ValueError: if neither cohort_data nor intervention_metrics contain
                        any usable keys.
        """
        if not cohort_data and not intervention_metrics:
            raise ValueError("At least one of cohort_data or intervention_metrics must be provided.")

        # --- Rule-based outcome classification ----------------------------
        adherence  = cohort_data.get("adherence_rate_pct", 100.0)
        hosp_rate  = cohort_data.get("hospitalization_rate_pct", 0.0)
        avg_spo2   = cohort_data.get("avg_spo2", 98.0)

        if adherence >= 85 and hosp_rate <= 5 and avg_spo2 >= 95:
            outcome_status = "positive"
        elif adherence >= 65 and hosp_rate <= 15:
            outcome_status = "borderline"
        else:
            outcome_status = "negative"

        recommendations: list[str] = []
        next_actions: list[str] = []

        if adherence < 85:
            recommendations.append("Investigate barriers to device adherence.")
            next_actions.append("Schedule adherence counselling for non-compliant patients.")
        if hosp_rate > 10:
            recommendations.append("Review exacerbation prevention protocols.")
            next_actions.append("Flag high-risk patients for proactive clinical review.")
        if avg_spo2 < 92:
            recommendations.append("Audit prescribed flow rates against actual usage data.")
            next_actions.append("Escalate patients with SpO2 < 88% to pulmonologist.")

        if not recommendations:
            recommendations.append("Continue current care pathway.")
        if not next_actions:
            next_actions.append("Maintain scheduled quarterly cohort review.")

        # --- LLM narrative feedback ---------------------------------------
        llm_feedback: Optional[str] = None
        try:
            llm_feedback = ClinicalEngine._get_llm_feedback(
                cohort_data=cohort_data,
                intervention_metrics=intervention_metrics,
                outcome_status=outcome_status,
                recommendations=recommendations,
            )
        except Exception as exc:
            log.warning("clinical.llm_feedback_failed", error=str(exc))

        result = {
            "outcome_status": outcome_status,
            "recommendations": recommendations,
            "next_actions": next_actions,
            "llm_feedback": llm_feedback,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

        log.info(
            "clinical.cohort_evaluated",
            cohort_id=cohort_data.get("cohort_id"),
            outcome_status=outcome_status,
            patient_count=cohort_data.get("patient_count"),
        )
        return result

    @staticmethod
    def _get_llm_feedback(
        cohort_data: dict,
        intervention_metrics: dict,
        outcome_status: str,
        recommendations: list[str],
    ) -> str:
        cohort_summary = json.dumps(cohort_data, indent=2)
        intervention_summary = json.dumps(intervention_metrics, indent=2)
        rec_text = "\n".join(f"- {r}" for r in recommendations)

        user_prompt = (
            f"Cohort data:\n{cohort_summary}\n\n"
            f"Intervention metrics:\n{intervention_summary}\n\n"
            f"Rule-based outcome status: {outcome_status}\n"
            f"Rule-based recommendations:\n{rec_text}\n\n"
            "As the clinical outcomes lead, write a brief (≤ 150 words) "
            "narrative for the medical director summarising cohort performance, "
            "validating or refining the recommendations, and identifying any "
            "patterns in the data that rule-based logic may have missed."
        )
        return _llm_complete(
            system=(
                "You are a senior respiratory medicine clinical outcomes analyst. "
                "Reply in plain text only. No markdown, no bullet points."
            ),
            user=user_prompt,
            max_tokens=250,
        )
