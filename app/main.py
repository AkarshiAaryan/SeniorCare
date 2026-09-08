import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import users, medications, health, medication_logs, reports, events, voice, caregiver, auth
from app.scheduler import start_scheduler, stop_scheduler
from app.config import settings

# Create database tables
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start APScheduler background jobs
    start_scheduler()
    yield
    # Shutdown: Stop APScheduler background jobs
    stop_scheduler()


app = FastAPI(
    title="SeniorCare Voice & Data Platform API",
    description="Backend service for senior patient profiles, medication management, Rime Voice integration, health record ingestion, automated schedulers, and daily reports.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware configuration: restrict to configured trusted origins
trusted = os.getenv('TRUSTED_ORIGINS')
if trusted:
    origins = [o.strip() for o in trusted.split(',') if o.strip()]
else:
    # sensible defaults for local dev; override via TRUSTED_ORIGINS env var
    origins = ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:3000", "http://localhost:3000"]

allow_creds = os.getenv('ALLOW_CREDENTIALS', 'false').lower() in ('1', 'true', 'yes')

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_creds,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Include API Routers
app.include_router(users.router)
app.include_router(medications.router)
app.include_router(health.router)
app.include_router(medication_logs.router)
app.include_router(reports.router)
app.include_router(events.router)
app.include_router(voice.router)
app.include_router(caregiver.router)
app.include_router(auth.router)


@app.get("/")
def root():
    return {
        "message": "SeniorCare Backend Data API is running.",
        "docs": "/docs",
        "redoc": "/redoc"
    }
