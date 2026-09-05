from datetime import datetime
from app.scheduler import check_medication_schedules, check_in_reminder
from app.database import SessionLocal
from app import models


def test_scheduler_check_in_reminder():
    db = SessionLocal()
    try:
        # Create a test user
        user = models.User(name="Scheduler Test Patient", age=85, preferred_language="English")
        db.add(user)
        db.commit()
        db.refresh(user)

        # Trigger check-in reminder
        check_in_reminder("Afternoon")

        # Verify event was logged
        event = db.query(models.EventLog).filter(
            models.EventLog.user_id == user.id,
            models.EventLog.event_type == "CHECK_IN_DUE"
        ).first()
        assert event is not None
        assert "Afternoon" in event.message and "check-in is due" in event.message
    finally:
        db.close()


def test_scheduler_medication_due_trigger():
    db = SessionLocal()
    try:
        user = models.User(name="Med Scheduler Patient", age=76)
        db.add(user)
        db.commit()
        db.refresh(user)

        now_str = datetime.now().strftime("%H:%M")
        med = models.Medication(user_id=user.id, name="Daily Heart Med", dosage="10mg")
        db.add(med)
        db.commit()
        db.refresh(med)

        sched = models.MedicationSchedule(medication_id=med.id, time=now_str)
        db.add(sched)
        db.commit()

        # Run schedule check
        check_medication_schedules()

        # Verify event was created
        event = db.query(models.EventLog).filter(
            models.EventLog.user_id == user.id,
            models.EventLog.event_type == "MEDICATION_DUE"
        ).first()
        assert event is not None
        assert "Daily Heart Med" in event.message
    finally:
        db.close()
