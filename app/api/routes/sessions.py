from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas import SessionCreate, SessionResponse
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def ingest_session(
    session: SessionCreate,
    db: Session = Depends(get_db)
):
    """
    Ingest session summary data
    
    Payload:
    - id: Device ID
    - sid: Session ID
    - lc: Location
    - t_start: Session start time
    - t_end: Session end time
    - i_p: Initial pressure
    - f_p: Final pressure
    - f_r: Flow rate
    - fb_pct: Final battery percentage
    - hf_log: Fault flag
    - c_st: Signal strength
    """
    try:
        result = IngestionService.ingest_session(db, session)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to ingest session: {str(e)}"
        )


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific session by ID"""
    from app.models.models import Session as SessionModel
    
    session = db.query(SessionModel).filter(
        SessionModel.sid == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    return session


@router.get("/device/{device_id}", response_model=list[SessionResponse])
def get_device_sessions(
    device_id: str,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get all sessions for a specific device"""
    from app.models.models import Session as SessionModel
    
    sessions = db.query(SessionModel).filter(
        SessionModel.device_id == device_id
    ).order_by(
        SessionModel.t_start.desc()
    ).limit(limit).all()
    
    if not sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No sessions found for device {device_id}"
        )
    
    return sessions
