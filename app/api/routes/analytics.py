from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import DepletionPredictionResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/depletion/{device_id}", response_model=list[DepletionPredictionResponse])
def get_depletion_predictions(
    device_id: str,
    limit: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
):
    from app.models.models import DepletionPrediction

    return (
        db.query(DepletionPrediction)
        .filter(DepletionPrediction.device_id == device_id)
        .order_by(DepletionPrediction.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "Smart Oxygen & Energy Intelligence System"}
