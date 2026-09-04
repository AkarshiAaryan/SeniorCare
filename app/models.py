from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Caregiver(Base):
    __tablename__ = "caregivers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contact = Column(String, nullable=False)

    users = relationship("User", back_populates="caregiver")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    preferred_language = Column(String, default="English")
    caregiver_id = Column(Integer, ForeignKey("caregivers.id"), nullable=True)

    caregiver = relationship("Caregiver", back_populates="users")
    medications = relationship("Medication", back_populates="user", cascade="all, delete-orphan")
    health_records = relationship("HealthRecord", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")


class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    dosage = Column(String, nullable=False)
    instructions = Column(String, nullable=True)

    user = relationship("User", back_populates="medications")
    schedules = relationship("MedicationSchedule", back_populates="medication", cascade="all, delete-orphan")
    logs = relationship("MedicationLog", back_populates="medication", cascade="all, delete-orphan")


class MedicationSchedule(Base):
    __tablename__ = "medication_schedules"

    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=False)
    time = Column(String, nullable=False)  # HH:MM format e.g. "20:00"

    medication = relationship("Medication", back_populates="schedules")


class HealthRecord(Base):
    __tablename__ = "health_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    mood = Column(String, nullable=True)
    sleep = Column(String, nullable=True)
    appetite = Column(String, nullable=True)
    pain = Column(String, nullable=True)

    user = relationship("User", back_populates="health_records")


class MedicationLog(Base):
    __tablename__ = "medication_logs"

    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=False)
    scheduled_time = Column(String, nullable=False)
    taken = Column(Boolean, default=False, nullable=False)
    confirmed_at = Column(DateTime, default=datetime.now, nullable=False)

    medication = relationship("Medication", back_populates="logs")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    transcript = Column(Text, nullable=False)
    extracted_data = Column(Text, nullable=True)  # Store JSON string representation

    user = relationship("User", back_populates="conversations")


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False)  # e.g., "MEDICATION_DUE", "CHECK_IN_DUE"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
