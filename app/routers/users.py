from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas

router = APIRouter(tags=["Users & Caregivers"])


@router.post("/caregivers", response_model=schemas.CaregiverResponse, status_code=status.HTTP_201_CREATED)
def create_caregiver(caregiver: schemas.CaregiverCreate, db: Session = Depends(get_db)):
    db_caregiver = models.Caregiver(name=caregiver.name, contact=caregiver.contact)
    db.add(db_caregiver)
    db.commit()
    db.refresh(db_caregiver)
    return db_caregiver


@router.get("/caregivers/{id}", response_model=schemas.CaregiverResponse)
def get_caregiver(id: int, db: Session = Depends(get_db)):
    db_caregiver = db.query(models.Caregiver).filter(models.Caregiver.id == id).first()
    if not db_caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")
    return db_caregiver


@router.post("/users", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if user.caregiver_id:
        caregiver = db.query(models.Caregiver).filter(models.Caregiver.id == user.caregiver_id).first()
        if not caregiver:
            raise HTTPException(status_code=400, detail="Specified Caregiver ID does not exist")

    db_user = models.User(
        name=user.name,
        age=user.age,
        preferred_language=user.preferred_language,
        caregiver_id=user.caregiver_id
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/users/{id}", response_model=schemas.UserResponse)
def get_user(id: int, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.put("/users/{id}", response_model=schemas.UserResponse)
def update_user(id: int, user_update: schemas.UserUpdate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_update.caregiver_id is not None:
        caregiver = db.query(models.Caregiver).filter(models.Caregiver.id == user_update.caregiver_id).first()
        if not caregiver:
            raise HTTPException(status_code=400, detail="Specified Caregiver ID does not exist")
        db_user.caregiver_id = user_update.caregiver_id

    if user_update.name is not None:
        db_user.name = user_update.name
    if user_update.age is not None:
        db_user.age = user_update.age
    if user_update.preferred_language is not None:
        db_user.preferred_language = user_update.preferred_language

    db.commit()
    db.refresh(db_user)
    return db_user
