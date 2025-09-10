from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas import DepletionPredictionResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/depletion/{device_id}", response_model=list[DepletionPredictionResponse])
def get_depletion_predictions(
    device_id: str,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get depletion predictions for a device"""
    from app.models.models import DepletionPrediction
    
    predictions = db.query(DepletionPrediction).filter(
        DepletionPrediction.device_id == device_id
    ).order_by(
        DepletionPrediction.created_at.desc()
    ).limit(limit).all()
    
    if not predictions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No depletion predictions found for device {device_id}"
        )
    
    return predictions


@router.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Smart Oxygen & Energy Intelligence System"
    }
