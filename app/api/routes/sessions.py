from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_device_key
from app.schemas import SessionCreate, SessionResponse
from app.services.ingestion_service import IngestionService

router = APIRouter(
    prefix="/sessions",
    tags=["sessions"],
    dependencies=[Depends(verify_device_key)],
)


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def ingest_session(
    session: SessionCreate,
    db: Session = Depends(get_db),
) -> object:
    try:
        return IngestionService.ingest_session(db, session)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Session persistence failed") from exc


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: Session = Depends(get_db)) -> object:
    from app.models.models import Session as SessionModel

    session = db.query(SessionModel).filter(SessionModel.sid == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return session


@router.get("/device/{device_id}", response_model=list[SessionResponse])
def get_device_sessions(
    device_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[object]:
    from app.models.models import Session as SessionModel

    return (
        db.query(SessionModel)
        .filter(SessionModel.device_id == device_id)
        .order_by(SessionModel.t_start.desc())
        .limit(limit)
        .all()
    )
