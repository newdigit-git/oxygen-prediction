from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas import TelemetryCreate, TelemetryResponse
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post("", response_model=TelemetryResponse, status_code=status.HTTP_201_CREATED)
def ingest_telemetry(
    telemetry: TelemetryCreate,
    db: Session = Depends(get_db)
):
    """
    Ingest real time telemetry data from IoT device
    
    Payload:
    - id: Device ID
    - t: Unix timestamp
    - b: Battery percentage
    - p: Pressure
    - f: Flow rate
    - c: Signal strength
    - l: Location coordinates
    """
    try:
        result = IngestionService.ingest_telemetry(db, telemetry)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to ingest telemetry: {str(e)}"
        )


@router.get("/device/{device_id}", response_model=list[TelemetryResponse])
def get_device_telemetry(
    device_id: str,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get recent telemetry records for a specific device"""
    from app.models.models import Telemetry
    
    records = db.query(Telemetry).filter(
        Telemetry.device_id == device_id
    ).order_by(
        Telemetry.created_at.desc()
    ).limit(limit).all()
    
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No telemetry found for device {device_id}"
        )
    
    return records
