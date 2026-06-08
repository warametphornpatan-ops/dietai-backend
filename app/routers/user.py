import hashlib
import os
from uuid import uuid4
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, text, func
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from ..database import get_db
from .. import models, schemas
from ..security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, get_current_user
)
from ..models import RefreshToken

router = APIRouter()


# ---------- Schemas ----------
class LoginReq(BaseModel):
    username: str
    password: str


class ResetPasswordReq(BaseModel):
    identifier: str
    is_email: bool
    firstName: str
    lastName: str
    new_password: str


class UserTargetReq(BaseModel):
    target_calories: int
    target_carbs: int
    target_protein: int
    target_fat: int


class UserProfileUpdateReq(BaseModel):
    age: int
    weight_kg: float
    height_cm: float
    health_info: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900


# ---------- Register ----------
@router.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    print(f"[DEBUG] username received: '{user.username}'")
    # ตรวจเลขบัตรประชาชน
    citizen_digits = "".join(ch for ch in (user.citizen_id or "") if ch.isdigit())
    if len(citizen_digits) != 13:
        raise HTTPException(status_code=400, detail="เลขบัตรประชาชนต้องเป็นตัวเลข 13 หลัก")

    # ✅ เพิ่มการประกาศตัวแปรล้างค่าตรงนี้ เพื่อป้องกัน NameError และ AttributeError
    username_clean = user.username.strip() if user.username else ""
    email_clean = user.email.strip() if user.email and user.email.strip() else None
    first_name_clean = user.firstName.strip() if user.firstName else None
    last_name_clean = user.lastName.strip() if user.lastName else None

    # ✅ แก้ไขบั๊กตรวจสอบข้อมูลซ้ำ: แยกเช็ค Email เฉพาะคนที่มีค่าจริง เพื่อไม่ให้บล็อกคนไม่มีอีเมล
    conditions = [
        func.lower(models.User.username) == username_clean.lower(),
        models.User.citizen_id == citizen_digits
    ]
    if email_clean:
        conditions.append(models.User.email == email_clean)

    # ✅ แก้ไข: เช็ค case-sensitive สำหรับ username เพื่อให้ User1 และ user1 เป็นคนละ username
    existing = db.query(models.User).filter(or_(*conditions)).first()
    if existing:
        if existing.username.lower() == username_clean.lower():
            raise HTTPException(status_code=400, detail="Email, Username หรือเลขบัตรประชาชนถูกใช้แล้ว")
        elif existing.citizen_id == citizen_digits:
            raise HTTPException(status_code=400, detail="Email, Username หรือเลขบัตรประชาชนถูกใช้แล้ว")
        elif email_clean and existing.email == email_clean:
            raise HTTPException(status_code=400, detail="Email, Username หรือเลขบัตรประชาชนถูกใช้แล้ว")

    hashed_password = hash_password(user.password)

    # คำนวณ BMI
    w = float(user.weight_kg or 0)
    h = float(user.height_cm or 0)
    a = float(user.age or 0)

    bmi_value = 0.0
    if h > 0:
        bmi_value = round(w / ((h / 100.0) ** 2), 2)

    # คำนวณ BMR (Harris-Benedict)
    gender_str = str(user.gender or "").strip().lower()
    if gender_str in ["หญิง", "female", "f"]:
        bmrHB = 447.593 + (9.274 * w) + (3.098 * h) - (4.330 * a)
    else:
        bmrHB = 88.362 + (13.397 * w) + (4.799 * h) - (5.677 * a)
    bmr = int(round(bmrHB))

    # คำนวณ TDEE
    multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    }
    act_val = multipliers.get(str(user.activity_level or "").strip().lower(), 1.2)
    maintenance_tdee = int(round(bmr * act_val))

    # คำนวณแคลอรี่เป้าหมายตาม goal
    goal_str = str(user.goal or "").strip().lower()
    if goal_str in ["ลดน้ำหนัก", "lose_weight", "ลดไขมัน"]:
        cal_tdee = max(maintenance_tdee - 500, 1200)
        carb_pct, protein_pct, fat_pct = 0.45, 0.30, 0.25
    elif goal_str in ["เพิ่มน้ำหนัก", "gain_weight", "เพิ่มกล้ามเนื้อ"]:
        cal_tdee = maintenance_tdee + 300
        carb_pct, protein_pct, fat_pct = 0.55, 0.25, 0.20
    else:
        cal_tdee = maintenance_tdee
        carb_pct, protein_pct, fat_pct = 0.50, 0.20, 0.30

    # คำนวณสารอาหาร (ใช้ประเภทข้อมูล Integer ให้สอดคล้องกัน)
    gram_fat = int(round((cal_tdee * fat_pct) / 9))
    cal_fat_actual = gram_fat * 9

    gram_protein = max(
        int(round((cal_tdee * protein_pct) / 4)),
        int(round(0.8 * w))
    )
    cal_protein_actual = gram_protein * 4
    gram_carbs = int(round(max(cal_tdee - cal_protein_actual - cal_fat_actual, 0) / 4))

    # บันทึกลง DB
    db_user = models.User(
        id=str(uuid4()),
        email=email_clean,
        username=username_clean,
        password=hashed_password,
        citizen_id=citizen_digits,
        firstName=first_name_clean,
        lastName=last_name_clean,
        gender=user.gender,
        age=user.age,
        height_cm=user.height_cm,
        weight_kg=user.weight_kg,
        target_weight_kg=user.target_weight_kg,
        activity_level=user.activity_level,
        goal=user.goal,
        health_info=user.health_info,
        role="user",
        target_calories=cal_tdee,
        target_carbs=gram_carbs,
        target_protein=gram_protein,
        target_fat=gram_fat,
        bmr=bmr,
        bmi=bmi_value,
    )

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email, Username หรือเลขบัตรประชาชนถูกใช้แล้ว")

    # ---------------------------------------------------------
    # ✅ เช็กการตอบกลับ Flow หน้าบ้านตามเงื่อนไข Email
    # ---------------------------------------------------------
    if db_user.email:
        return {
            "id": db_user.id, 
            "role": db_user.role, 
            "nextStep": "otp", 
            "message": "สมัครสมาชิกสำเร็จ เตรียมส่ง OTP"
        }
    else:
        return {
            "id": db_user.id, 
            "role": db_user.role, 
            "nextStep": "completed", 
            "message": "สมัครสมาชิกสำเร็จ (ไม่มีอีเมล)"
        }

# ---------- Login ----------
@router.post("/login", response_model=TokenResponse)
async def login(request: LoginReq, db: Session = Depends(get_db)):
    if not request.username or len(request.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Invalid username")

    # แปลงค่าที่ผู้ใช้กรอกเข้ามาให้เป็นตัวพิมพ์เล็กทั้งหมด และตัดช่องว่าง
    username_clean = request.username.strip().lower()

    # ✅ ค้นหาด้วย func.lower() เพื่อให้เป็น Case-Insensitive ทั้ง 3 ตาราง
    user = db.query(models.User).filter(func.lower(models.User.username) == username_clean).first()
    
    admin = None
    if not user:
        admin = db.query(models.Admin).filter(func.lower(models.Admin.username) == username_clean).first()
        
    doctor = None
    if not (user or admin):
        doctor = db.query(models.Doctors).filter(func.lower(models.Doctors.username) == username_clean).first()

    account = user or admin or doctor
    if not account:
        raise HTTPException(status_code=401, detail="ไม่พบชื่อผู้ใช้นี้ในระบบ")

    stored_password = account.password if user else account.password_hash
    if not verify_password(request.password, stored_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user:
        account_id, role = user.id, user.role
    elif admin:
        account_id, role = admin.admin_id, "admin"
    else:
        account_id, role = doctor.id, "doctor"

    access_token  = create_access_token({"sub": str(account_id), "user_id": str(account_id), "role": role})
    refresh_token = create_refresh_token({"sub": str(account_id), "user_id": str(account_id)})

    db.add(RefreshToken(
        user_id=account_id,
        token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        is_revoked=0,
    ))
    db.commit()

    is_https = os.getenv("APP_ENV", "development") == "production"
    response = JSONResponse(content={
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": 900,
        "role": role,
    })
    response.set_cookie("access_token", access_token, max_age=900, httponly=True,  secure=is_https, samesite="lax", path="/")
    response.set_cookie("user_role",    role,          max_age=900, httponly=False, secure=is_https, samesite="lax", path="/")
    return response


# ---------- Logout ----------
@router.post("/logout")
async def logout(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.is_revoked == 0,
    ).update({"is_revoked": 1})
    db.commit()

    response = JSONResponse({"message": "Logged out successfully"})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("user_role", path="/")
    return response


# ---------- Me ----------
@router.get("/me")
def me(current_user: models.User = Depends(get_current_user)):
    return {
        "id":               current_user.id,
        "username":         current_user.username,
        "email":            current_user.email,
        "firstName":        current_user.firstName,
        "role":             current_user.role,
        "target_calories":  current_user.target_calories,
        "target_carbs":     current_user.target_carbs,
        "target_protein":   current_user.target_protein,
        "target_fat":       current_user.target_fat,
        "age":              current_user.age,
        "weight_kg":        current_user.weight_kg,
        "height_cm":        current_user.height_cm,
        "health_info":      current_user.health_info,
        "bmr":              current_user.bmr,
        "bmi":              current_user.bmi,
        "goal":             current_user.goal,
    }


# ---------- Update Targets ----------
@router.put("/me/targets")
def update_user_targets(
    payload: UserTargetReq,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.target_calories = payload.target_calories
    current_user.target_carbs    = payload.target_carbs
    current_user.target_protein  = payload.target_protein
    current_user.target_fat      = payload.target_fat
    db.commit()
    db.refresh(current_user)
    return {
        "message": "Update targets success",
        "data": {
            "target_calories": current_user.target_calories,
            "target_carbs":     current_user.target_carbs,
            "target_protein":   current_user.target_protein,
            "target_fat":       current_user.target_fat,
        },
    }


# ---------- Reset Password ----------
@router.post("/reset-password")
def reset_password(payload: ResetPasswordReq, db: Session = Depends(get_db)):
    if len(payload.new_password) < 4:
        raise HTTPException(status_code=400, detail="รหัสผ่านใหม่ต้องมีอย่างน้อย 4 ตัวอักษร")

    if payload.is_email:
        search_email = payload.identifier.strip()
        search_citizen_id = None
    else:
        citizen_digits = "".join(ch for ch in payload.identifier if ch.isdigit())
        if len(citizen_digits) != 13:
            raise HTTPException(status_code=400, detail="เลขบัตรประชาชนต้องเป็นตัวเลข 13 หลัก")
        search_email = None
        search_citizen_id = citizen_digits

    first_name = payload.firstName.strip()
    last_name  = payload.lastName.strip()

    def find_account(model_class):
        if hasattr(model_class, "firstName"):
            f_col = model_class.firstName
            l_col = model_class.lastName
        else:
            f_col = model_class.first_name
            l_col = model_class.last_name

        q = db.query(model_class).filter(f_col == first_name, l_col == last_name)
        if payload.is_email:
            q = q.filter(model_class.email == search_email)
        else:
            q = q.filter(model_class.citizen_id == search_citizen_id)
        return q.first()

    account = find_account(models.User)
    is_user = account is not None
    if not account:
        account = find_account(models.Admin)

    if not account:
        raise HTTPException(
            status_code=404,
            detail="ไม่พบข้อมูลที่ตรงกับที่ระบุ (ตรวจสอบอีเมล/บัตรประชาชน และ ชื่อ-นามสกุล)",
        )

    hashed_pw = hash_password(payload.new_password)
    if is_user:
        account.password = hashed_pw
    else:
        account.password_hash = hashed_pw
    db.commit()
    return {"detail": "เปลี่ยนรหัสผ่านเรียบร้อยแล้ว"}


# ---------- Health Records ----------
@router.get("/me/health-records")
def get_my_health_records(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = db.execute(
        text("""
            SELECT id, systolic, diastolic, pulse, recommendation, created_at
            FROM health_records
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """),
        {"user_id": current_user.id},
    ).mappings().all()

    return [
        {
            "id":             row["id"],
            "systolic":       row["systolic"],
            "diastolic":      row["diastolic"],
            "pulse":          row["pulse"],
            "recommendation": row["recommendation"],
            "createdAt":      row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in result
    ]


# ---------- Update Profile ----------
@router.put("/me/profile")
def update_user_profile(
    payload: UserProfileUpdateReq,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.age         = payload.age
    current_user.weight_kg   = payload.weight_kg
    current_user.height_cm   = payload.height_cm
    current_user.health_info = payload.health_info

    w = float(payload.weight_kg or 0)
    h = float(payload.height_cm or 0)
    a = float(payload.age or 0)

    current_user.bmi = round(w / ((h / 100.0) ** 2), 2) if h > 0 and w > 0 else None

    gender_str = str(current_user.gender or "").strip().lower()
    if gender_str in ["หญิง", "female", "f"]:
        bmrHB = 447.593 + (9.274 * w) + (3.098 * h) - (4.330 * a)
    else:
        bmrHB = 88.362 + (13.397 * w) + (4.799 * h) - (5.677 * a)
    bmr = round(bmrHB, 2)
    current_user.bmr = bmr

    multipliers = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725, "very_active": 1.9}
    act_val = multipliers.get(str(getattr(current_user, "activity_level", "") or "").strip().lower(), 1.2)
    maintenance_tdee = round(bmr * act_val)

    goal_str = str(getattr(current_user, "goal", "") or "").strip().lower()
    if goal_str in ["ลดน้ำหนัก", "lose_weight", "ลดไขมัน"]:
        target_calories = max(maintenance_tdee - 500, 1200)
        carb_pct, protein_pct, fat_pct = 0.45, 0.30, 0.25
    elif goal_str in ["เพิ่มน้ำหนัก", "gain_weight", "เพิ่มกล้ามเนื้อ"]:
        target_calories = maintenance_tdee + 300
        carb_pct, protein_pct, fat_pct = 0.55, 0.25, 0.20
    else:
        target_calories = maintenance_tdee
        carb_pct, protein_pct, fat_pct = 0.50, 0.20, 0.30

    fat_gram     = (target_calories * fat_pct) / 9.0
    protein_gram = max((target_calories * protein_pct) / 4.0, w * 0.8)
    carbs_gram   = max(target_calories - (protein_gram * 4.0) - (fat_gram * 9.0), 0.0) / 4.0

    # ✅ แก้ไข: แปลงผลปัดเศษสารอาหารให้เป็น Integer (int) เพื่อให้สอดรับกับฐานข้อมูลและโครงสร้าง Register ด้านบน
    current_user.target_calories = int(round(target_calories))
    current_user.target_carbs    = int(round(carbs_gram))
    current_user.target_protein  = int(round(protein_gram))
    current_user.target_fat      = int(round(fat_gram))

    db.commit()
    db.refresh(current_user)
    return {
        "message": "อัปเดตข้อมูลและเป้าหมายสุขภาพสำเร็จ",
        "data": {
            "bmi":             current_user.bmi,
            "bmr":             current_user.bmr,
            "tdee":            int(round(maintenance_tdee)),
            "target_calories": current_user.target_calories,
            "target_carbs":     current_user.target_carbs,
            "target_protein":   current_user.target_protein,
            "target_fat":       current_user.target_fat,
        },
    }


# ---------- Check Username ----------
@router.get("/check-username")
def check_username(
    username: str = Query(...),
    org_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    username_clean = username.strip()

    def make_filters(model, username_field):
     filters = [
        func.lower(username_field) == username_clean.lower(),
    ]
    if org_code:
        combined = f"{org_code.strip()}{username_clean.lower()}"
        filters += [
            func.lower(username_field) == combined,
        ]
    return filters

    if db.query(models.Admin).filter(or_(*make_filters(models.Admin, models.Admin.username))).first():
        return {"is_available": False, "detail": "Username นี้ถูกใช้งานแล้วในระบบผู้ดูแลระบบ (Admin)"}

    if db.query(models.Doctors).filter(or_(*make_filters(models.Doctors, models.Doctors.username))).first():
        return {"is_available": False, "detail": "Username นี้ถูกใช้งานแล้วในระบบบัญชีแพทย์ (Doctors)"}

    if db.query(models.User).filter(func.lower(models.User.username) == username_clean.lower()).first():
        return {"is_available": False, "detail": "Username นี้ถูกใช้งานแล้วในระบบผู้ใช้งาน"}

    return {"is_available": True, "detail": "Username นี้สามารถใช้งานได้"}