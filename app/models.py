# app/models.py - เพิ่ม DoctorApplication + แก้ Doctors

from sqlalchemy import Column, String, Integer, Float, Text, DateTime, func, Boolean, ForeignKey
from uuid import uuid4
from .database import Base
from sqlalchemy import Date


class User(Base):
    __tablename__ = "user"

    id          = Column(String(191), primary_key=True, default=lambda: str(uuid4()))
    email       = Column(String(191), unique=True, nullable=True)
    username    = Column(String(191), unique=True, nullable=False)
    password    = Column(String(255), nullable=False)
    role        = Column(String(20), nullable=False, default="user")
    citizen_id  = Column(String(13), unique=True, nullable=True)

    firstName  = Column(String(191))
    lastName   = Column(String(20))
    birth_date = Column(Date, nullable=True)
    gender = Column(String(10), nullable=True)
    heightCm   = Column(Float)
    weightKg   = Column(Float)
    targetWeightKg = Column(Float)
    activityLevel   = Column(String(50))
    goal        = Column(String(100))
    healthInfo = Column(Text)
    createdAt  = Column(DateTime, server_default=func.now())

    target_calories = Column(Integer, default=0)
    target_carbs = Column(Integer, default=0)
    target_protein = Column(Integer, default=0)
    target_fat = Column(Integer, default=0)
    bmr = Column(Float, nullable=True)
    bmi = Column(Float, nullable=True)


# ============================================================
# ✅ NEW: DoctorApplication (ตาราง doctor_applications)
# ============================================================

class DoctorApplication(Base):
    """
    เก็บข้อมูลแพทย์ที่รอการอนุมัติ
    """
    __tablename__ = "doctor_applications"

    id = Column(Integer, primary_key=True, index=True)
    org_code = Column(String(20), nullable=False, index=True)
    citizen_id = Column(String(13), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    position = Column(String(100), nullable=True)
    
    status = Column(String(20), default='pending', nullable=False, index=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    otp_token = Column(String(6), nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    
    user_id = Column(String(36), nullable=True, unique=True)  # Supabase Auth UUID
    
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<DoctorApplication {self.id}: {self.first_name} {self.last_name}>"


# ============================================================
# ✅ UPDATED: Doctors (เพิ่ม status field)
# ============================================================

class Doctors(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    org_code = Column(String(50), nullable=False) 
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    citizen_id = Column(String(13), unique=True, nullable=True)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), nullable=True)
    position = Column(String, nullable=True)
    
    # ✅ เพิ่มบรรทัดนี้
    status = Column(String(20), default='approved', nullable=False, index=True)  # approved, rejected
    user_id = Column(String(36), nullable=True, unique=True)  # Supabase Auth UUID
    created_at = Column(DateTime, default=func.now(), nullable=True)
    
    def __repr__(self):
        return f"<Doctor {self.id}: {self.first_name} {self.last_name}>"


class FoodLog(Base):
    __tablename__ = "food_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), nullable=False) # รองรับ UUID
    food_name = Column(String(255), nullable=False)
    calories = Column(Float, default=0.0)
    carbs = Column(Float, default=0.0)
    protein = Column(Float, default=0.0)
    fat = Column(Float, default=0.0)
    image_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Admin(Base):
    __tablename__ = "admins"

    admin_id = Column(Integer, primary_key=True, index=True)
    org_code = Column(String(50), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    citizen_id = Column(String(13), nullable=False, unique=True)
    email = Column(String(100), nullable=False)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


# Token management models for secure authentication
class TokenBlacklist(Base):
    """Store revoked tokens"""
    __tablename__ = "token_blacklist"
    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(500), unique=True, index=True)  # JWT ID
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)


class RefreshToken(Base):
    """Store refresh tokens for token rotation"""
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(191), index=True, nullable=False)
    token_hash = Column(String(255), unique=True)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Integer, default=0)