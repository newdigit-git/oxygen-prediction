from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Telemetry
from app.schemas import TelemetryCreate, TelemetryResponse
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post("", response_model=TelemetryResponse, status_code=status.HTTP_201_CREATED)
def ingest_telemetry(
    telemetry: TelemetryCreate,
    db: Session = Depends(get_db),
) -> Telemetry:
    """Persist one device telemetry event."""
    try:
        return IngestionService.ingest_telemetry(db, telemetry)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Telemetry persistence failed") from exc


@router.get("/device/{device_id}", response_model=list[TelemetryResponse])
def get_device_telemetry(
    device_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[Telemetry]:
    """Return recent telemetry for a device, newest first."""
    rows = (
        db.query(Telemetry)
        .filter(Telemetry.device_id == device_id)
        .order_by(Telemetry.timestamp.desc(), Telemetry.id.desc())
        .limit(limit)
        .all()
    )
    return rows
