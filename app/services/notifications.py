import os
import smtplib
from email.message import EmailMessage
from typing import List

from app.config import settings
from app import models
from app.database import SessionLocal

def _send_email(to_addresses: List[str], subject: str, body: str) -> bool:
    host = settings.SMTP_HOST
    port = settings.SMTP_PORT
    user = settings.SMTP_USER
    pwd = settings.SMTP_PASS
    sender = settings.SENDER_EMAIL

    if not host or not sender:
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(to_addresses)
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=10) as s:
            s.starttls()
            if user and pwd:
                s.login(user, pwd)
            s.send_message(msg)
        return True
    except Exception:
        return False

def _send_sms_via_twilio(to_number: str, body: str) -> bool:
    try:
        from twilio.rest import Client
    except Exception:
        return False

    sid = settings.TWILIO_SID
    token = settings.TWILIO_TOKEN
    from_num = settings.TWILIO_FROM
    if not sid or not token or not from_num:
        return False

    try:
        client = Client(sid, token)
        client.messages.create(body=body, from_=from_num, to=to_number)
        return True
    except Exception:
        return False


def notify_panic(user: models.User, message: str, location: str) -> dict:
    """Notify the patient's caregiver(s) and admin according to configured channels.

    Returns a dict with channels and success flags for auditing.
    """
    channels = [c.strip().lower() for c in settings.NOTIFY_CHANNELS.split(',') if c.strip()]
    results = {}

    # build recipients: primary caregiver if exists, else admin
    recipients = []
    if user.caregiver:
        recipients.append(user.caregiver.contact)
    if settings.NOTIFY_ADMIN_EMAIL:
        recipients.append(settings.NOTIFY_ADMIN_EMAIL)

    # normalize recipients unique
    recipients = list(dict.fromkeys([r for r in recipients if r]))

    # attempt email
    if 'email' in channels:
        addrs = [r for r in recipients if '@' in r]
        if not addrs and settings.NOTIFY_ADMIN_EMAIL:
            addrs = [settings.NOTIFY_ADMIN_EMAIL]
        if addrs:
            subject = f"Panic Alert for {user.name}"
            body = f"{message}\nLocation: {location}\nUser ID: {user.id}"
            results['email'] = _send_email(addrs, subject, body)
        else:
            results['email'] = False

    # attempt sms
    if 'sms' in channels:
        nums = [r for r in recipients if '@' not in r]
        if nums:
            ok_any = False
            for n in nums:
                ok = _send_sms_via_twilio(n, message)
                ok_any = ok_any or ok
            results['sms'] = ok_any
        else:
            results['sms'] = False

    # push placeholder
    if 'push' in channels:
        # push provider not implemented in this demo
        results['push'] = False

    # write audit record as an EventLog entry to preserve notification trail
    db = SessionLocal()
    try:
        audit_msg = f"Panic notification attempted for user {user.id}. Channels: {results}"
        notif = models.EventLog(
            event_type="PANIC_NOTIFICATION",
            user_id=user.id,
            message=audit_msg,
            timestamp=models.datetime.now() if hasattr(models, 'datetime') else None,
            processed=True,
        )
        db.add(notif)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    return results
