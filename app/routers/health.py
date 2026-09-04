import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas

router = APIRouter(tags=["Health Records & Conversations"])


@router.post("/health-records", response_model=schemas.HealthRecordResponse, status_code=status.HTTP_201_CREATED)
def create_health_record(record: schemas.HealthRecordCreate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db_record = models.HealthRecord(
        user_id=record.user_id,
        timestamp=record.timestamp or datetime.now(),
        mood=record.mood,
        sleep=record.sleep,
        appetite=record.appetite,
        pain=record.pain
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


@router.get("/health-records/{user_id}", response_model=List[schemas.HealthRecordResponse])
def get_user_health_records(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    records = db.query(models.HealthRecord).filter(
        models.HealthRecord.user_id == user_id
    ).order_by(models.HealthRecord.timestamp.desc()).all()
    return records


@router.post("/conversations", response_model=schemas.ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(conv: schemas.ConversationCreate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == conv.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    extracted_str = None
    if conv.extracted_data is not None:
        if isinstance(conv.extracted_data, (dict, list)):
            extracted_str = json.dumps(conv.extracted_data)
        else:
            extracted_str = str(conv.extracted_data)

    db_conv = models.Conversation(
        user_id=conv.user_id,
        transcript=conv.transcript,
        extracted_data=extracted_str,
        timestamp=datetime.now()
    )
    db.add(db_conv)
    db.commit()
    db.refresh(db_conv)
    return db_conv
