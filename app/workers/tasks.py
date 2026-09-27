"""Celery workers for telemetry enrichment and depletion predictions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from celery import Celery
from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.core.config import get_settings

settings = get_settings()
logger = get_task_logger(__name__)

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
    task_default_retry_delay=30,
    task_time_limit=300,
    task_soft_time_limit=240,
    task_routes={
        "app.workers.tasks.process_telemetry_batch": {"queue": "telemetry"},
        "app.workers.tasks.generate_depletion_prediction": {"queue": "predictions"},
    },
)


def _get_db():
    from app.core.database import SessionLocal

    return SessionLocal()


def _predict(pressures: list[tuple[float, int]]) -> tuple[float | None, float]:
    """Return remaining minutes and confidence from timestamped readings."""
    if len(pressures) < 2:
        return None, 0.1
    pressures = sorted(pressures, key=lambda item: item[1])
    t0 = pressures[0][1]
    xs = [timestamp - t0 for _, timestamp in pressures]
    ys = [pressure for pressure, _ in pressures]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator <= 0:
        return None, 0.1
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator
    if slope >= -1e-9 or ys[-1] <= 0:
        return None, min(0.5 + 0.05 * n, 0.95)
    return round((ys[-1] / abs(slope)) / 60, 1), min(0.5 + 0.05 * n, 0.95)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=15)
def process_telemetry_batch(self, telemetry_ids: list[int]) -> dict:
    """Validate a committed telemetry batch and enqueue affected sessions."""
    from app.models.models import Session as SessionModel
    from app.models.models import Telemetry

    db = _get_db()
    try:
        records = db.execute(select(Telemetry).where(Telemetry.id.in_(telemetry_ids))).scalars().all()
        device_ids = {record.device_id for record in records}
        sessions = db.execute(select(SessionModel).where(SessionModel.device_id.in_(device_ids))).scalars().all()
        for session in sessions:
            generate_depletion_prediction.delay(session.sid)
        result = {
            "batch_size": len(telemetry_ids),
            "records_found": len(records),
            "sessions_triggered": len(sessions),
        }
        logger.info("telemetry batch processed: %s", result)
        return result
    except Exception as exc:
        db.rollback()
        logger.exception("telemetry batch failed")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=15)
def generate_depletion_prediction(self, session_id: str) -> dict:
    """Generate or refresh a linear pressure depletion prediction for a session."""
    from app.models.models import DepletionPrediction
    from app.models.models import Session as SessionModel
    from app.models.models import Telemetry

    db = _get_db()
    try:
        session = db.execute(select(SessionModel).where(SessionModel.sid == session_id)).scalar_one_or_none()
        if session is None:
            return {"session_id": session_id, "status": "session_not_found"}

        start = int(session.t_start.timestamp())
        end = int(session.t_end.timestamp())
        readings = db.execute(
            select(Telemetry)
            .where(
                Telemetry.device_id == session.device_id,
                Telemetry.timestamp >= start,
                Telemetry.timestamp <= end,
            )
            .order_by(Telemetry.timestamp.asc())
        ).scalars().all()
        remaining_minutes, confidence = _predict([(r.pressure, r.timestamp) for r in readings])
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        depletion_time = now + timedelta(minutes=remaining_minutes) if remaining_minutes is not None else None
        critical_minutes = None
        if remaining_minutes is not None and readings[-1].pressure > 20:
            critical_minutes = remaining_minutes * (readings[-1].pressure - 20) / readings[-1].pressure
        critical_time = now + timedelta(minutes=critical_minutes) if critical_minutes is not None else None
        status = "PREDICTED" if remaining_minutes is not None else "STABLE"

        latest = db.execute(
            select(DepletionPrediction)
            .where(DepletionPrediction.session_id == session_id)
            .order_by(DepletionPrediction.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        values = {
            "device_id": session.device_id,
            "time_to_empty_minutes": remaining_minutes,
            "depletion_time": depletion_time,
            "critical_alert_time": critical_time,
            "status": status,
        }
        if latest and latest.created_at and latest.created_at >= now - timedelta(minutes=5):
            for key, value in values.items():
                setattr(latest, key, value)
        else:
            db.add(DepletionPrediction(session_id=session_id, **values))
        db.commit()
        result = {
            "session_id": session_id,
            "status": status,
            "remaining_minutes": remaining_minutes,
            "confidence": confidence,
        }
        logger.info("depletion prediction generated: %s", result)
        return result
    except Exception as exc:
        db.rollback()
        logger.exception("depletion prediction failed")
        raise self.retry(exc=exc)
    finally:
        db.close()
