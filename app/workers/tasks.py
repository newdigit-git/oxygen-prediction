"""
Celery application + background tasks for the oxygen cylinder IoT monitoring system.


"""

import logging
import statistics
from datetime import datetime, timedelta, timezone

from celery import Celery
from celery.utils.log import get_task_logger

from app.core.config import get_settings

settings = get_settings()

logger = get_task_logger(__name__)

# ---------------------------------------------------------------------------
# Celery app
# ---------------------------------------------------------------------------

celery_app = Celery(
    "oxygen_pred",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=30,  # seconds
    task_time_limit=300,
    task_soft_time_limit=240,
)

# Chain later stages automatically after a batch is enriched
celery_app.conf.task_routes = {
    "app.tasks.celery_app.process_telemetry_batch": {"queue": "telemetry"},
    "app.tasks.celery_app.generate_depletion_prediction": {"queue": "predictions"},
    "app.tasks.celery_app.generate_surge_forecast": {"queue": "forecasts"},
}


def _get_db():
    """Lazy import to avoid circulars between the celery app and the FastAPI app."""
    from app.db.session import SessionLocal

    return SessionLocal()


# ---------------------------------------------------------------------------
# Stage 1-4 enrichment helpers
# ---------------------------------------------------------------------------

def _stage1_validate(record) -> bool:
    """Reject physically impossible / malformed readings."""
    if record.pressure_psi is None or record.pressure_psi < 0:
        return False
    if record.flow_rate_lpm is not None and record.flow_rate_lpm < 0:
        return False
    if record.recorded_at is None:
        return False
    return True


def _stage2_normalize(record) -> None:
    """Normalize units / clamp sensor noise in place."""
    if record.pressure_psi is not None:
        record.pressure_psi = round(float(record.pressure_psi), 2)
    if record.flow_rate_lpm is not None:
        record.flow_rate_lpm = round(float(record.flow_rate_lpm), 3)


def _stage3_contextualize(db, record) -> None:
    """Attach session/region context if missing, using the cylinder_id lookup."""
    if record.session_id is None and getattr(record, "cylinder_id", None):
        from app.models.session import OxygenSession

        active_session = (
            db.query(OxygenSession)
            .filter(
                OxygenSession.cylinder_id == record.cylinder_id,
                OxygenSession.status == "active",
            )
            .order_by(OxygenSession.started_at.desc())
            .first()
        )
        if active_session:
            record.session_id = active_session.id
            record.region_code = record.region_code or active_session.region_code


def _stage4_anomaly_score(db, record) -> float:
    """
    Cheap anomaly score: how far this reading's pressure drop rate deviates
    from the recent rolling average for the same session. Returns 0-1.
    """
    from app.models.telemetry import TelemetryRecord

    if not record.session_id:
        return 0.0

    recent = (
        db.query(TelemetryRecord)
        .filter(
            TelemetryRecord.session_id == record.session_id,
            TelemetryRecord.id != record.id,
        )
        .order_by(TelemetryRecord.recorded_at.desc())
        .limit(10)
        .all()
    )

    if len(recent) < 2:
        return 0.0

    pressures = [r.pressure_psi for r in recent if r.pressure_psi is not None]
    if len(pressures) < 2:
        return 0.0

    mean_p = statistics.mean(pressures)
    stdev_p = statistics.pstdev(pressures) or 1.0
    z = abs(record.pressure_psi - mean_p) / stdev_p
    # squash to 0-1
    return round(min(z / 4.0, 1.0), 3)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, max_retries=3, default_retry_delay=15)
def process_telemetry_batch(self, telemetry_ids: list):
    """
    Background task to process a batch of telemetry records.
    Runs the enrichment pipeline (Stages 1-4):
      1. Validate  2. Normalize  3. Contextualize  4. Score anomalies
    Then kicks off depletion prediction for any affected sessions.
    """
    from app.models.telemetry import TelemetryRecord

    db = _get_db()
    processed, rejected = 0, 0
    affected_sessions = set()

    try:
        records = (
            db.query(TelemetryRecord)
            .filter(TelemetryRecord.id.in_(telemetry_ids))
            .all()
        )

        for record in records:
            try:
                if not _stage1_validate(record):
                    rejected += 1
                    continue

                _stage2_normalize(record)
                _stage3_contextualize(db, record)
                record.anomaly_score = _stage4_anomaly_score(db, record)

                record.enriched = True
                record.enriched_at = datetime.now(timezone.utc)
                processed += 1

                if record.session_id:
                    affected_sessions.add(str(record.session_id))

            except Exception:
                logger.exception("Failed enriching telemetry record %s", record.id)
                rejected += 1

        db.commit()

    except Exception as exc:
        db.rollback()
        logger.exception("process_telemetry_batch failed, retrying")
        raise self.retry(exc=exc)
    finally:
        db.close()

    # Fan out predictions for sessions that saw new data in this batch
    for session_id in affected_sessions:
        generate_depletion_prediction.delay(session_id)

    result = {
        "batch_size": len(telemetry_ids),
        "processed": processed,
        "rejected": rejected,
        "sessions_triggered": list(affected_sessions),
    }
    logger.info("process_telemetry_batch complete: %s", result)
    return result


@celery_app.task(bind=True, max_retries=3, default_retry_delay=15)
def generate_depletion_prediction(self, session_id: str):
    """
    Background task to generate an oxygen depletion prediction for a session.
    Uses recent pressure-drop rate (linear fit) to estimate remaining minutes.
    """
    from app.models.telemetry import TelemetryRecord
    from app.models.session import OxygenSession
    from app.models.prediction import DepletionPrediction

    db = _get_db()
    try:
        session = db.query(OxygenSession).filter(OxygenSession.id == session_id).first()
        if not session:
            logger.warning("generate_depletion_prediction: session %s not found", session_id)
            return {"session_id": session_id, "status": "session_not_found"}

        window_start = datetime.now(timezone.utc) - timedelta(hours=2)
        readings = (
            db.query(TelemetryRecord)
            .filter(
                TelemetryRecord.session_id == session_id,
                TelemetryRecord.enriched.is_(True),
                TelemetryRecord.recorded_at >= window_start,
            )
            .order_by(TelemetryRecord.recorded_at.asc())
            .all()
        )

        if len(readings) < 2:
            logger.info("Not enough readings to predict for session %s", session_id)
            return {"session_id": session_id, "status": "insufficient_data"}

        # Simple linear regression of pressure (psi) vs elapsed seconds
        t0 = readings[0].recorded_at
        xs = [(r.recorded_at - t0).total_seconds() for r in readings]
        ys = [r.pressure_psi for r in readings]

        n = len(xs)
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        denom = sum((x - mean_x) ** 2 for x in xs) or 1e-9
        slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom  # psi/sec

        latest_pressure = ys[-1]

        if slope >= -1e-6:
            # Pressure not measurably dropping — can't extrapolate depletion
            remaining_minutes = None
            confidence = 0.1
        else:
            seconds_to_empty = latest_pressure / abs(slope)
            remaining_minutes = round(seconds_to_empty / 60, 1)
            # confidence grows with sample size and reading recency, capped at 0.95
            recency_ok = (datetime.now(timezone.utc) - readings[-1].recorded_at) < timedelta(minutes=15)
            confidence = min(0.5 + 0.05 * n, 0.95) if recency_ok else 0.4

        predicted_empty_at = (
            datetime.now(timezone.utc) + timedelta(minutes=remaining_minutes)
            if remaining_minutes is not None
            else None
        )

        prediction = DepletionPrediction(
            session_id=session_id,
            remaining_minutes=remaining_minutes,
            predicted_empty_at=predicted_empty_at,
            confidence=confidence,
            generated_at=datetime.now(timezone.utc),
            method="linear_pressure_regression",
        )
        db.add(prediction)
        db.commit()

        result = {
            "session_id": session_id,
            "status": "ok",
            "remaining_minutes": remaining_minutes,
            "predicted_empty_at": predicted_empty_at.isoformat() if predicted_empty_at else None,
            "confidence": confidence,
        }
        logger.info("generate_depletion_prediction complete: %s", result)
        return result

    except Exception as exc:
        db.rollback()
        logger.exception("generate_depletion_prediction failed, retrying")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def generate_surge_forecast(self, region_code: str):
    """
    Background task to generate a climate/demand surge forecast for a region.
    Aggregates active session depletion rates in the region as a proxy for
    near-term oxygen demand pressure.
    """
    from app.models.session import OxygenSession
    from app.models.prediction import DepletionPrediction
    from app.models.forecast import SurgeForecast

    db = _get_db()
    try:
        active_sessions = (
            db.query(OxygenSession)
            .filter(
                OxygenSession.region_code == region_code,
                OxygenSession.status == "active",
            )
            .all()
        )

        session_ids = [s.id for s in active_sessions]
        if not session_ids:
            logger.info("No active sessions for region %s", region_code)
            forecast = SurgeForecast(
                region_code=region_code,
                forecast_date=datetime.now(timezone.utc).date(),
                predicted_surge_pct=0.0,
                confidence=0.2,
                generated_at=datetime.now(timezone.utc),
                contributing_sessions=0,
            )
            db.add(forecast)
            db.commit()
            return {"region_code": region_code, "status": "no_active_sessions"}

        latest_predictions = (
            db.query(DepletionPrediction)
            .filter(DepletionPrediction.session_id.in_(session_ids))
            .order_by(DepletionPrediction.generated_at.desc())
            .all()
        )

        # Keep only the most recent prediction per session
        seen, remaining_minutes_by_session = set(), []
        for p in latest_predictions:
            if p.session_id in seen or p.remaining_minutes is None:
                continue
            seen.add(p.session_id)
            remaining_minutes_by_session.append(p.remaining_minutes)

        if not remaining_minutes_by_session:
            surge_pct, confidence = 0.0, 0.2
        else:
            avg_remaining = sum(remaining_minutes_by_session) / len(remaining_minutes_by_session)
            critical_fraction = sum(
                1 for m in remaining_minutes_by_session if m < 60
            ) / len(remaining_minutes_by_session)

            # Heuristic: more sessions running low + shorter average runway -> higher surge %
            surge_pct = round(min(critical_fraction * 100 * 1.2, 100.0), 1)
            confidence = min(0.4 + 0.05 * len(remaining_minutes_by_session), 0.9)

        forecast = SurgeForecast(
            region_code=region_code,
            forecast_date=datetime.now(timezone.utc).date(),
            predicted_surge_pct=surge_pct,
            confidence=confidence,
            generated_at=datetime.now(timezone.utc),
            contributing_sessions=len(remaining_minutes_by_session),
        )
        db.add(forecast)
        db.commit()

        result = {
            "region_code": region_code,
            "status": "ok",
            "predicted_surge_pct": surge_pct,
            "confidence": confidence,
            "contributing_sessions": len(remaining_minutes_by_session),
        }
        logger.info("generate_surge_forecast complete: %s", result)
        return result

    except Exception as exc:
        db.rollback()
        logger.exception("generate_surge_forecast failed, retrying")
        raise self.retry(exc=exc)
    finally:
        db.close()
