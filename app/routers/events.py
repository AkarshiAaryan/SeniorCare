from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from app.database import get_db
from app import models

router = APIRouter(tags=["Scheduler Events"])


class EventLogResponse(BaseModel):
    id: int
    event_type: str
    user_id: int
    message: str
    timestamp: datetime
    processed: bool

    model_config = ConfigDict(from_attributes=True)


@router.get("/events/pending", response_model=List[EventLogResponse])
def get_pending_events(user_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.EventLog).filter(models.EventLog.processed == False)
    if user_id:
        query = query.filter(models.EventLog.user_id == user_id)
    return query.order_by(models.EventLog.timestamp.asc()).all()


@router.post("/events/{event_id}/acknowledge", response_model=EventLogResponse)
def acknowledge_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.EventLog).filter(models.EventLog.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event.processed = True
    db.commit()
    db.refresh(event)
    return event


@router.post("/events/trigger-test-checkin", status_code=status.HTTP_201_CREATED)
def trigger_test_checkin(user_id: int, period: str = "Manual", db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    msg = f"{period} check-in is due"
    event = models.EventLog(
        event_type="CHECK_IN_DUE",
        user_id=user.id,
        message=msg,
        timestamp=datetime.now()
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
