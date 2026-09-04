from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas

router = APIRouter(tags=["Medication Logs"])


@router.post("/medication-logs", response_model=schemas.MedicationLogResponse, status_code=status.HTTP_201_CREATED)
def create_medication_log(log: schemas.MedicationLogCreate, db: Session = Depends(get_db)):
    medication = db.query(models.Medication).filter(models.Medication.id == log.medication_id).first()
    if not medication:
        raise HTTPException(status_code=404, detail="Medication not found")

    db_log = models.MedicationLog(
        medication_id=log.medication_id,
        scheduled_time=log.scheduled_time,
        taken=log.taken,
        confirmed_at=log.confirmed_at or datetime.now()
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


@router.get("/medication-logs/user/{user_id}", response_model=List[schemas.MedicationLogResponse])
def get_user_medication_logs(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    logs = (
        db.query(models.MedicationLog)
        .join(models.Medication)
        .filter(models.Medication.user_id == user_id)
        .order_by(models.MedicationLog.confirmed_at.desc())
        .all()
    )
    return logs
