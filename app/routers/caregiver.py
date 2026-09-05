from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from app.database import get_db
from app import models

router = APIRouter(prefix="/caregiver", tags=["Caregiver Dashboard & Analytics"])


# --- Schemas ---
class PanicRequest(BaseModel):
    user_id: int
    note: Optional[str] = "Elderly user pressed the emergency panic button"
    location: Optional[str] = "Home"


class AlertResponse(BaseModel):
    id: int
    event_type: str
    user_id: int
    message: str
    timestamp: datetime
    processed: bool

    model_config = ConfigDict(from_attributes=True)


class AnalyticsResponse(BaseModel):
    user_id: int
    user_name: str
    age: int
    preferred_language: str
    caregiver_name: Optional[str] = None
    overall_adherence_rate: float
    total_medications_count: int
    active_alerts_count: int
    latest_health: dict
    adherence_trend: List[dict]
    sleep_trend: List[dict]
    mood_distribution: List[dict]
    pain_logs: List[dict]
    active_alerts: List[AlertResponse]


# --- Endpoints ---

@router.post("/panic", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
def trigger_panic_alert(req: PanicRequest, db: Session = Depends(get_db)):
    """
    Emergency panic button triggered by the elderly patient.
    Logs an immediate critical PANIC_ALERT event for caregiver notification.
    """
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    message = f"EMERGENCY PANIC ALERT: {user.name} pressed the panic button. Note: {req.note}"
    panic_event = models.EventLog(
        event_type="PANIC_ALERT",
        user_id=user.id,
        message=message,
        timestamp=datetime.now(),
        processed=False
    )
    db.add(panic_event)
    db.commit()
    db.refresh(panic_event)
    return panic_event


@router.post("/alerts/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    """
    Caregiver marks an emergency alert or reminder as resolved.
    """
    alert = db.query(models.EventLog).filter(models.EventLog.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.processed = True
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/analytics/{user_id}", response_model=AnalyticsResponse)
def get_caregiver_analytics(user_id: int, days: int = 7, db: Session = Depends(get_db)):
    """
    Aggregates multi-day health, medication adherence, and emergency alert trends
    specifically structured for Caregiver graphs and analytics charts.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    today = date.today()
    start_date = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time())

    # 1. Fetch Medications
    user_meds = db.query(models.Medication).filter(models.Medication.user_id == user_id).all()
    total_meds_count = len(user_meds)

    # 2. Fetch Medication Logs over past 'days'
    med_logs = (
        db.query(models.MedicationLog)
        .join(models.Medication)
        .filter(models.Medication.user_id == user_id, models.MedicationLog.confirmed_at >= start_dt)
        .all()
    )

    total_taken = sum(1 for log in med_logs if log.taken)
    total_logs = len(med_logs)
    adherence_rate = round((total_taken / total_logs * 100), 1) if total_logs > 0 else 100.0

    # 3. Daily Adherence Trend for Bar Chart
    adherence_trend = []
    for i in range(days):
        current_day = start_date + timedelta(days=i)
        day_str = current_day.strftime("%Y-%m-%d")
        day_label = current_day.strftime("%a (%d %b)")
        
        day_logs = [log for log in med_logs if log.confirmed_at.date() == current_day]
        taken_count = sum(1 for log in day_logs if log.taken)
        missed_count = sum(1 for log in day_logs if not log.taken)
        scheduled_est = max(len(day_logs), sum(len(m.schedules) for m in user_meds))
        
        # If no log yet for today, show pending
        pending_count = max(0, scheduled_est - (taken_count + missed_count))

        adherence_trend.append({
            "date": day_str,
            "day": day_label,
            "taken": taken_count,
            "missed": missed_count,
            "pending": pending_count
        })

    # 4. Health Records over past 'days'
    health_records = (
        db.query(models.HealthRecord)
        .filter(models.HealthRecord.user_id == user_id, models.HealthRecord.timestamp >= start_dt)
        .order_by(models.HealthRecord.timestamp.asc())
        .all()
    )

    # Sleep score mapping: good=3, normal/fair=2, poor=1
    sleep_score_map = {"good": 3, "fair": 2, "normal": 2, "poor": 1, "interrupted": 1}
    sleep_trend = []
    for i in range(days):
        current_day = start_date + timedelta(days=i)
        day_label = current_day.strftime("%a")
        day_records = [hr for hr in health_records if hr.timestamp.date() == current_day]
        
        if day_records:
            latest_day_hr = day_records[-1]
            sleep_label = latest_day_hr.sleep or "normal"
            score = sleep_score_map.get(sleep_label.lower(), 2)
        else:
            sleep_label = "not reported"
            score = 2

        sleep_trend.append({
            "day": day_label,
            "date": current_day.strftime("%Y-%m-%d"),
            "score": score,
            "quality": sleep_label
        })

    # 5. Mood Distribution for Donut / Pie Chart
    mood_counts = {}
    for hr in health_records:
        if hr.mood and hr.mood.lower() != "not reported":
            m_clean = hr.mood.capitalize()
            mood_counts[m_clean] = mood_counts.get(m_clean, 0) + 1
    
    if not mood_counts:
        mood_counts = {"Calm": 3, "Good": 2}

    mood_distribution = [{"mood": k, "count": v} for k, v in mood_counts.items()]

    # 6. Pain Logs
    pain_logs = []
    for hr in reversed(health_records):
        if hr.pain and hr.pain.lower() not in ["none", "none reported", "no"]:
            pain_logs.append({
                "timestamp": hr.timestamp.strftime("%Y-%m-%d %H:%M"),
                "pain": hr.pain,
                "mood": hr.mood or "Normal"
            })

    # 7. Active Alerts
    active_alerts = (
        db.query(models.EventLog)
        .filter(models.EventLog.user_id == user_id, models.EventLog.processed == False)
        .order_by(models.EventLog.timestamp.desc())
        .all()
    )

    # 8. Latest Health
    latest_hr = health_records[-1] if health_records else None
    latest_health = {
        "mood": latest_hr.mood if latest_hr else "Good",
        "sleep": latest_hr.sleep if latest_hr else "Good",
        "appetite": latest_hr.appetite if latest_hr else "Normal",
        "pain": latest_hr.pain if latest_hr else "None reported"
    }

    return AnalyticsResponse(
        user_id=user.id,
        user_name=user.name,
        age=user.age,
        preferred_language=user.preferred_language,
        caregiver_name=user.caregiver.name if user.caregiver else None,
        overall_adherence_rate=adherence_rate,
        total_medications_count=total_meds_count,
        active_alerts_count=len(active_alerts),
        latest_health=latest_health,
        adherence_trend=adherence_trend,
        sleep_trend=sleep_trend,
        mood_distribution=mood_distribution,
        pain_logs=pain_logs,
        active_alerts=active_alerts
    )


@router.get("/patients/{caregiver_id}")
def get_caregiver_patients(caregiver_id: int, db: Session = Depends(get_db)):
    """
    Get all patients assigned to a caregiver with live status indicators.
    """
    caregiver = db.query(models.Caregiver).filter(models.Caregiver.id == caregiver_id).first()
    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")

    result = []
    for user in caregiver.users:
        pending_alerts = db.query(models.EventLog).filter(
            models.EventLog.user_id == user.id,
            models.EventLog.processed == False
        ).count()

        med_count = len(user.medications)
        result.append({
            "id": user.id,
            "name": user.name,
            "age": user.age,
            "preferred_language": user.preferred_language,
            "medications_count": med_count,
            "pending_alerts_count": pending_alerts
        })
    return result
