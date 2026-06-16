# app/models.py
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
    birth_date = Column(Date, nullable=True)  # ✅
    gender = Column(String(10), nullable=True)
    heightCm   = Column(Float)  # ✅ เปลี่ยน
    weightKg   = Column(Float)  # ✅ เปลี่ยน
    targetWeightKg = Column(Float)  # ✅ เปลี่ยน
    activityLevel   = Column(String(50))  # ✅ เปลี่ยน
    goal        = Column(String(100))
    healthInfo = Column(Text)  # ✅ เปลี่ยน
    createdAt  = Column(DateTime, server_default=func.now())  # ✅ เปลี่ยน

    target_calories = Column(Integer, default=0)
    target_carbs = Column(Integer, default=0)
    target_protein = Column(Integer, default=0)
    target_fat = Column(Integer, default=0)
    bmr = Column(Float, nullable=True)
    bmi = Column(Float, nullable=True)

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

