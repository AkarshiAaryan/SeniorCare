from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, ConfigDict


# --- Caregiver Schemas ---
class CaregiverBase(BaseModel):
    name: str
    contact: str


class CaregiverCreate(CaregiverBase):
    pass


class CaregiverResponse(CaregiverBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# --- User Schemas ---
class UserBase(BaseModel):
    name: str
    age: int
    preferred_language: Optional[str] = "English"
    caregiver_id: Optional[int] = None


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    preferred_language: Optional[str] = None
    caregiver_id: Optional[int] = None


class UserResponse(UserBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# --- Medication Schedule Schemas ---
class MedicationScheduleBase(BaseModel):
    time: str  # Format: "HH:MM", e.g. "20:00"


class MedicationScheduleCreate(MedicationScheduleBase):
    pass


class MedicationScheduleResponse(MedicationScheduleBase):
    id: int
    medication_id: int

    model_config = ConfigDict(from_attributes=True)


# --- Medication Schemas ---
class MedicationBase(BaseModel):
    name: str
    dosage: str
    instructions: Optional[str] = None


class MedicationCreate(MedicationBase):
    user_id: int
    times: List[str] = []  # e.g., ["08:00", "20:00"]


class MedicationUpdate(BaseModel):
    name: Optional[str] = None
    dosage: Optional[str] = None
    instructions: Optional[str] = None
    times: Optional[List[str]] = None


class MedicationResponse(MedicationBase):
    id: int
    user_id: int
    schedules: List[MedicationScheduleResponse] = []

    model_config = ConfigDict(from_attributes=True)


# --- Health Record Schemas ---
class HealthRecordBase(BaseModel):
    mood: Optional[str] = None
    sleep: Optional[str] = None
    appetite: Optional[str] = None
    pain: Optional[str] = None


class HealthRecordCreate(HealthRecordBase):
    user_id: int
    timestamp: Optional[datetime] = None


class HealthRecordResponse(HealthRecordBase):
    id: int
    user_id: int
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Medication Log Schemas ---
class MedicationLogBase(BaseModel):
    scheduled_time: str
    taken: bool


class MedicationLogCreate(MedicationLogBase):
    medication_id: int
    confirmed_at: Optional[datetime] = None


class MedicationLogResponse(MedicationLogBase):
    id: int
    medication_id: int
    confirmed_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Conversation Schemas ---
class ConversationCreate(BaseModel):
    user_id: int
    transcript: str
    extracted_data: Optional[Any] = None


class ConversationResponse(BaseModel):
    id: int
    user_id: int
    timestamp: datetime
    transcript: str
    extracted_data: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --- Daily Report Schemas ---
class DailyReportResponse(BaseModel):
    user_id: int
    user_name: str
    date: str
    health_summary: dict
    medication_summary: List[dict]
    check_ins_completed: str
    notes: List[str]
