from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional, Literal
from datetime import datetime, date  # ✅ เพิ่ม date

# -----------------------------
# Users
# -----------------------------
class UserCreate(BaseModel):
    email: Optional[str] = None
    username: str
    password: str

    # ✅ แก้ไข: รับได้ทั้ง firstName และ first_name
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    gender: Optional[str] = None
    birth_date: Optional[date] = None  # ✅ แก้: age → birth_date
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    target_weight_kg: Optional[float] = None
    waist_cm: Optional[float] = None
    activity_level: Optional[str] = None
    goal: Optional[str] = None
    health_info: Optional[str] = None
    citizen_id: str
    role: Literal["user", "doctor", "admin"] = "user"

    # ✅ รวม firstName/first_name ให้เป็นค่าเดียวกัน
    @model_validator(mode="after")
    def merge_name_fields(self) -> "UserCreate":
        if not self.firstName and self.first_name:
            self.firstName = self.first_name
        if not self.lastName and self.last_name:
            self.lastName = self.last_name
        return self

    class Config:
        populate_by_name = True


class UserResponse(BaseModel):
    id: str
    email: Optional[EmailStr] = None
    username: str
    firstName: Optional[str] = Field(None, alias="firstName")
    lastName: Optional[str] = Field(None, alias="lastName")
    birth_date: Optional[date] = None  # ✅ แก้: age → birth_date
    created_at: Optional[datetime] = None
    role: Optional[str] = None
    target_calories: Optional[int] = 0
    target_carbs: Optional[int] = 0
    target_protein: Optional[int] = 0
    target_fat: Optional[int] = 0
    bmi: Optional[float] = None
    bmr: Optional[float] = None
    goal: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True


# -----------------------------
# Doctors
# -----------------------------
class DoctorCreate(BaseModel):
    org_code: str
    citizen_id: str
    first_name: str
    last_name: str
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    username: str
    email: EmailStr
    role: Literal["doctor"] = "doctor"
    password: str  
    position: str


# -----------------------------
# Password Reset
# -----------------------------
class ResetPassword(BaseModel):
    identifier: str
    is_email: bool
    username: str
    new_password: str


# -----------------------------
# Food Logs
# -----------------------------
class FoodLogCreate(BaseModel):
    user_id: str
    food_name: str
    calories: float
    carbs: float
    protein: float
    fat: float
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


# -----------------------------
# Health Records
# -----------------------------
class HealthRecordCreate(BaseModel):
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    pulse: Optional[int] = None
    blood_pressure: Optional[str] = None
    blood_sugar: Optional[float] = None
    recommendation: str


# ✅ แก้: age → birth_date
class UserProfileUpdateReq(BaseModel):
    birth_date: Optional[date] = None  # ← เปลี่ยน
    weight_kg: float
    height_cm: float
    health_info: Optional[str] = None
    bmr: Optional[float] = None
    bmi: Optional[float] = None

    class Config:
        from_attributes = True


# -----------------------------
# Admin
# -----------------------------
class AdminCreate(BaseModel):
    org_code: str
    citizen_id: str
    first_name: str
    last_name: str
    email: EmailStr
    username: str
    role: Literal["admin"] = "admin"


class AdminResponse(BaseModel):
    admin_id: str
    org_code: str
    citizen_id: str
    first_name: str
    last_name: str
    email: EmailStr
    username: str

    class Config:
        from_attributes = True

class UserProfileHistoryResponse(BaseModel):
    id: int
    weightKg: Optional[float]
    heightCm: Optional[float]
    healthInfo: Optional[str]
    createdAt: Optional[str]