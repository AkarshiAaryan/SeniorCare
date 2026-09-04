from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas

router = APIRouter(tags=["Medication Management"])


@router.post("/medications", response_model=schemas.MedicationResponse, status_code=status.HTTP_201_CREATED)
def create_medication(med: schemas.MedicationCreate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == med.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db_med = models.Medication(
        user_id=med.user_id,
        name=med.name,
        dosage=med.dosage,
        instructions=med.instructions
    )
    db.add(db_med)
    db.commit()
    db.refresh(db_med)

    for schedule_time in med.times:
        db_schedule = models.MedicationSchedule(
            medication_id=db_med.id,
            time=schedule_time
        )
        db.add(db_schedule)

    db.commit()
    db.refresh(db_med)
    return db_med


@router.get("/medications/{user_id}", response_model=List[schemas.MedicationResponse])
def get_user_medications(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    medications = db.query(models.Medication).filter(models.Medication.user_id == user_id).all()
    return medications


@router.put("/medications/{id}", response_model=schemas.MedicationResponse)
def update_medication(id: int, med_update: schemas.MedicationUpdate, db: Session = Depends(get_db)):
    db_med = db.query(models.Medication).filter(models.Medication.id == id).first()
    if not db_med:
        raise HTTPException(status_code=404, detail="Medication not found")

    if med_update.name is not None:
        db_med.name = med_update.name
    if med_update.dosage is not None:
        db_med.dosage = med_update.dosage
    if med_update.instructions is not None:
        db_med.instructions = med_update.instructions

    if med_update.times is not None:
        # Clear existing schedules and set new ones
        db.query(models.MedicationSchedule).filter(models.MedicationSchedule.medication_id == id).delete()
        for schedule_time in med_update.times:
            db_schedule = models.MedicationSchedule(
                medication_id=id,
                time=schedule_time
            )
            db.add(db_schedule)

    db.commit()
    db.refresh(db_med)
    return db_med


@router.delete("/medications/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_medication(id: int, db: Session = Depends(get_db)):
    db_med = db.query(models.Medication).filter(models.Medication.id == id).first()
    if not db_med:
        raise HTTPException(status_code=404, detail="Medication not found")

    db.delete(db_med)
    db.commit()
    return None
