import os
from datetime import datetime, timedelta
from typing import Optional

try:
    from jose import JWTError, jwt
except Exception:
    JWTError = Exception
    jwt = None

try:
    from passlib.context import CryptContext
except Exception:
    CryptContext = None

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.database import SessionLocal
from app import models

SECRET_KEY = os.getenv('JWT_SECRET', 'dev-secret-change-me')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12

if CryptContext is not None:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
else:
    pwd_context = None
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if pwd_context is None:
        raise RuntimeError("passlib not installed; install passlib[bcrypt] to enable password hashing")
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    if pwd_context is None:
        raise RuntimeError("passlib not installed; install passlib[bcrypt] to enable password hashing")
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    if jwt is None:
        raise RuntimeError("python-jose not installed; install python-jose[cryptography] to enable JWT tokens")
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_caregiver(token: str = Depends(oauth2_scheme)) -> models.Caregiver:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if jwt is None:
        raise HTTPException(status_code=500, detail="JWT support not available on server")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    db = SessionLocal()
    try:
        caregiver = db.query(models.Caregiver).filter(models.Caregiver.username == username).first()
        if caregiver is None:
            raise credentials_exception
        return caregiver
    finally:
        db.close()
