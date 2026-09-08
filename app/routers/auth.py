from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app import models
from app.database import SessionLocal
from app.auth import verify_password, get_password_hash, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post('/register-caregiver')
def register_caregiver(name: str, contact: str, username: str, password: str):
    db = SessionLocal()
    try:
        existing = db.query(models.Caregiver).filter(models.Caregiver.username == username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")
        cg = models.Caregiver(name=name, contact=contact, username=username, password_hash=get_password_hash(password))
        db.add(cg)
        db.commit()
        db.refresh(cg)
        return {"id": cg.id, "username": cg.username}
    finally:
        db.close()


@router.post('/token')
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    db = SessionLocal()
    try:
        user = db.query(models.Caregiver).filter(models.Caregiver.username == form_data.username).first()
        if not user or not user.password_hash or not verify_password(form_data.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

        access_token_expires = timedelta(minutes=60 * 12)
        access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
        return {"access_token": access_token, "token_type": "bearer"}
    finally:
        db.close()


@router.get('/me')
def read_current_user(current=Depends()):
    # Intentionally loose to be wired by dependency injection in callers
    return {"note": "Use dependency get_current_caregiver from app.auth in protected routes."}
