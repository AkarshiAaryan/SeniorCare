import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app import models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Scheduler")

scheduler = BackgroundScheduler()


def check_medication_schedules():
    """
    Background job running every minute to evaluate if any medication is due.
    Generates a MEDICATION_DUE EventLog entry when due.
    """
    now_str = datetime.now().strftime("%H:%M")
    db: Session = SessionLocal()
    try:
        schedules = db.query(models.MedicationSchedule).filter(models.MedicationSchedule.time == now_str).all()
        for sched in schedules:
            medication = sched.medication
            user_id = medication.user_id

            # Avoid duplicating event if already created in this minute
            existing_event = db.query(models.EventLog).filter(
                models.EventLog.event_type == "MEDICATION_DUE",
                models.EventLog.user_id == user_id,
                models.EventLog.message.like(f"%{medication.name}%"),
                models.EventLog.timestamp >= datetime.now().replace(second=0, microsecond=0)
            ).first()

            if not existing_event:
                msg = f"Medication '{medication.name}' ({medication.dosage}) is due at {sched.time}"
                event = models.EventLog(
                    event_type="MEDICATION_DUE",
                    user_id=user_id,
                    message=msg,
                    timestamp=datetime.now()
                )
                db.add(event)
                logger.info(f"[EVENT TRIGGERED] User {user_id}: {msg}")

        db.commit()
    except Exception as e:
        logger.error(f"Error checking medication schedules: {e}")
        db.rollback()
    finally:
        db.close()


def check_in_reminder(period: str):
    """
    Background job triggered at fixed times (08:00 Morning, 13:00 Afternoon, 20:00 Evening)
    """
    db: Session = SessionLocal()
    try:
        users = db.query(models.User).all()
        now_str = datetime.now().strftime("%H:%M")
        for user in users:
            msg = f"{period} check-in is due ({now_str})"
            event = models.EventLog(
                event_type="CHECK_IN_DUE",
                user_id=user.id,
                message=msg,
                timestamp=datetime.now()
            )
            db.add(event)
            logger.info(f"[CHECK-IN TRIGGERED] User {user.id} ({user.name}): {msg}")

        db.commit()
    except Exception as e:
        logger.error(f"Error triggering check-in reminders: {e}")
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    # Job 1: Check medication schedules every minute
    scheduler.add_job(
        check_medication_schedules,
        'cron',
        minute='*',
        id='medication_checker',
        replace_existing=True
    )

    # Job 2: Check-in schedules
    scheduler.add_job(
        check_in_reminder,
        'cron',
        hour=8, minute=0,
        args=['Morning'],
        id='morning_check_in',
        replace_existing=True
    )
    scheduler.add_job(
        check_in_reminder,
        'cron',
        hour=13, minute=0,
        args=['Afternoon'],
        id='afternoon_check_in',
        replace_existing=True
    )
    scheduler.add_job(
        check_in_reminder,
        'cron',
        hour=20, minute=0,
        args=['Evening'],
        id='evening_check_in',
        replace_existing=True
    )

    scheduler.start()
    logger.info("APScheduler started successfully.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler stopped.")
