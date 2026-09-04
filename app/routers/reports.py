from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import models, schemas

router = APIRouter(tags=["Daily Reports"])


@router.get("/daily-report/{user_id}", response_model=schemas.DailyReportResponse)
def generate_daily_report(
    user_id: int,
    target_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format. Defaults to today."),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if target_date:
        try:
            report_day = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    else:
        report_day = date.today()

    start_dt = datetime.combine(report_day, datetime.min.time())
    end_dt = datetime.combine(report_day, datetime.max.time())

    # 1. Fetch Health Records for the day
    health_records = db.query(models.HealthRecord).filter(
        models.HealthRecord.user_id == user_id,
        models.HealthRecord.timestamp >= start_dt,
        models.HealthRecord.timestamp <= end_dt
    ).order_by(models.HealthRecord.timestamp.desc()).all()

    latest_health = health_records[0] if health_records else None
    health_summary = {
        "sleep": latest_health.sleep if latest_health else "Not reported",
        "mood": latest_health.mood if latest_health else "Not reported",
        "appetite": latest_health.appetite if latest_health else "Not reported",
        "pain": latest_health.pain if latest_health else "None reported"
    }

    # 2. Fetch Medications & Logs for the day
    user_meds = db.query(models.Medication).filter(models.Medication.user_id == user_id).all()
    medication_summary = []

    for med in user_meds:
        for sched in med.schedules:
            log = db.query(models.MedicationLog).filter(
                models.MedicationLog.medication_id == med.id,
                models.MedicationLog.scheduled_time == sched.time,
                models.MedicationLog.confirmed_at >= start_dt,
                models.MedicationLog.confirmed_at <= end_dt
            ).first()

            status_str = "Taken ✓" if (log and log.taken) else ("Missed ⚠" if log else "Pending / No Log")
            medication_summary.append({
                "medication_name": med.name,
                "dosage": med.dosage,
                "scheduled_time": sched.time,
                "status": status_str,
                "confirmed_at": log.confirmed_at.strftime("%H:%M") if log else None
            })

    # 3. Check-ins count for the day
    check_in_events = db.query(models.EventLog).filter(
        models.EventLog.user_id == user_id,
        models.EventLog.event_type == "CHECK_IN_DUE",
        models.EventLog.timestamp >= start_dt,
        models.EventLog.timestamp <= end_dt
    ).all()
    
    total_check_ins = len(check_in_events) if check_in_events else 3
    completed_check_ins = len(health_records)
    check_ins_summary_str = f"{min(completed_check_ins, total_check_ins)}/{total_check_ins} completed"

    # 4. Generate notes
    notes = []
    if latest_health and latest_health.pain and latest_health.pain.lower() != "none":
        notes.append(f"User reported: {latest_health.pain}")
    if any(item["status"].startswith("Missed") for item in medication_summary):
        notes.append("User missed one or more scheduled medication doses.")
    if not notes:
        notes.append("No critical alerts for today.")

    return schemas.DailyReportResponse(
        user_id=user.id,
        user_name=user.name,
        date=report_day.strftime("%Y-%m-%d"),
        health_summary=health_summary,
        medication_summary=medication_summary,
        check_ins_completed=check_ins_summary_str,
        notes=notes
    )
