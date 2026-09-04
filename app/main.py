from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import users, medications, health, medication_logs, reports, events
from app.scheduler import start_scheduler, stop_scheduler

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
    title="SeniorCare Backend Data API",
    description="Backend service for senior patient profiles, medication management, health record ingestion, automated schedulers, and daily reports.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(users.router)
app.include_router(medications.router)
app.include_router(health.router)
app.include_router(medication_logs.router)
app.include_router(reports.router)
app.include_router(events.router)


@app.get("/")
def root():
    return {
        "message": "SeniorCare Backend Data API is running.",
        "docs": "/docs",
        "redoc": "/redoc"
    }
