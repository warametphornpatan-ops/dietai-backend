from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, text, func
from pydantic import BaseModel
from typing import Optional
from ..database import get_db
from .. import models
from app.security import verify_password, create_access_token
from passlib.hash import bcrypt_sha256
from typing import Dict

# ==========================================
# 🌟 Pydantic Schemas
# ==========================================

# Schema สำหรับสร้าง record (ตัด blood_sugar ออกถาวร)
class HealthRecordCreate(BaseModel):
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    pulse: Optional[int] = None
    recommendation: str

# Schema สำหรับ Login
class DoctorLoginReq(BaseModel):
    username: str
    password: str
    org_code: str

# ✨ Schema สำหรับรับข้อมูลซิงค์รหัสผ่านใหม่
class SyncPasswordReq(BaseModel):
    email: str
    new_password: str

router = APIRouter(
    tags=["doctor"]
)

# ==========================================
# 🌟 API สำหรับการเข้าสู่ระบบของแพทย์
# ==========================================
@router.post("/login")
def login_doctor(payload: DoctorLoginReq, db: Session = Depends(get_db)) -> Dict[str, str]:
    # ดึงข้อมูลแพทย์จากฐานข้อมูลด้วย username
    doctor = db.query(models.Doctors).filter(func.lower(models.Doctors.username) == payload.username.strip().lower()).first()
    
    if not doctor:
        raise HTTPException(status_code=401, detail="ไม่พบชื่อผู้ใช้นี้")

    # ✅ เพิ่ม try/except ดัก hash format ผิด ไม่ให้ 500
    try:
        valid: bool = bcrypt_sha256.verify(payload.password, doctor.password_hash)
    except Exception:
        raise HTTPException(status_code=401, detail="รหัสผ่านไม่ถูกต้อง")

    if not valid:
        raise HTTPException(status_code=401, detail="รหัสผ่านไม่ถูกต้อง")

    # 🧩 ----------------------------------------------------
    # เพิ่มส่วนการตรวจสอบรหัสหน่วยงาน (org_code) ของแพทย์ตรงนี้
    # ----------------------------------------------------
    # ล้างเครื่องหมายหรือช่องว่าง และกรองให้เหลือเฉพาะตัวเลขตามมาตรฐาน
    clean_payload_org: str = "".join(filter(str.isdigit, payload.org_code.strip() if payload.org_code else ""))
    clean_doctor_org: str = "".join(filter(str.isdigit, doctor.org_code.strip() if doctor.org_code else ""))

    # หากรหัสหน่วยงานที่กรอกมา ไม่ตรงกับรหัสหน่วยงานของแพทย์ในฐานข้อมูล
    if clean_doctor_org != clean_payload_org:
        raise HTTPException(
            status_code=401, 
            detail="รหัสหน่วยงานไม่ตรงกับสิทธิ์การเข้าใช้งานของแพทย์ท่านนี้"
        )
    # ----------------------------------------------------

    # สร้าง Access Token เมื่อข้อมูลถูกต้องทั้งหมด
    access_token: str = create_access_token(
        data={
            "sub": doctor.username, 
            "role": "doctor",
            "org_code": doctor.org_code,
            "first_name": doctor.first_name,
            "last_name": doctor.last_name,
            "position": doctor.position,
        } 
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": "doctor"
    }

# ==========================================
# ✨ API สำหรับซิงค์รหัสผ่านใหม่จากหน้าตั้งรหัสผ่าน (Supabase)
# ==========================================
@router.patch("/sync-password")
def sync_doctor_password(payload: SyncPasswordReq, db: Session = Depends(get_db)):
    # 1. ค้นหาแพทย์ในตารางด้วยอีเมล
    doctor = db.query(models.Doctors).filter(models.Doctors.email == payload.email).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="ไม่พบข้อมูลแพทย์ที่มีอีเมลนี้ในระบบหลัก"
        )
        
    # 2. เข้ารหัสลับรหัสผ่านด้วย bcrypt_sha256 (ให้ตรงกับระบบ Login)
    hashed_password = bcrypt_sha256.hash(payload.new_password)
    
    # 3. อัปเดตลงฟิลด์ password_hash
    doctor.password_hash = hashed_password
    
    try:
        db.commit()
        return {"status": "success", "message": "บันทึกรหัสผ่านเข้าฐานข้อมูลหลักสำเร็จ"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Database Error: {str(e)}"
        )

# ==========================================
# 🌟 API ดึงข้อมูลคนไข้ (รวมประวัติโภชนาการและสุขภาพ)
# ==========================================
@router.get("/patients")
def get_patients(name: str = "", citizenId: str = "", db: Session = Depends(get_db)):
    # ✅ สร้าง query base ก่อน
    query = db.query(models.User).filter(models.User.role == "user")

    # ✅ แก้ logic ค้นหา — handle ทั้ง citizen_id และ citizenId
    if citizenId:
        query = query.filter(
            or_(
                models.User.citizen_id.like(f"%{citizenId}%") if hasattr(models.User, 'citizen_id') else None,
                models.User.citizenId.like(f"%{citizenId}%") if hasattr(models.User, 'citizenId') else None,
            )
        )
    elif name:
        query = query.filter(
            or_(
                models.User.firstName.like(f"%{name}%"),
                models.User.lastName.like(f"%{name}%"),
            )
        )
    else:
        return []

    users = query.all()
    results = []

    for u in users:
        bmi = None
        height = getattr(u, "height_cm", getattr(u, "heightCm", None))
        weight = getattr(u, "weight_kg", getattr(u, "weightKg", None))
        
        if height and weight:
            h = height / 100
            bmi = round(weight / (h * h), 2)

        # ── โภชนาการรายวัน ──
        daily_nutrition_query = text("""
            SELECT 
                DATE(created_at) as log_date,
                SUM(calories) as total_cal,
                SUM(carbs) as total_carb
            FROM food_logs
            WHERE user_id = :user_id
            GROUP BY DATE(created_at)
            ORDER BY log_date DESC
        """)
        daily_result = db.execute(daily_nutrition_query, {"user_id": u.id}).mappings().all()
        daily_nutrition_list = [
            {
                "date": str(row["log_date"]),
                "totalCal": float(row["total_cal"] or 0),
                "totalCarb": float(row["total_carb"] or 0)
            }
            for row in daily_result
        ]

        # ── ประวัติอาหารรายมื้อ ──
        food_logs_query = text("""
            SELECT id, food_name, calories, carbs, protein, created_at
            FROM food_logs 
            WHERE user_id = :user_id 
            ORDER BY created_at DESC
            LIMIT 50
        """)
        food_logs_result = db.execute(food_logs_query, {"user_id": u.id}).mappings().all()
        food_logs_list = [
            {
                "id": row["id"],
                "foodName": row["food_name"],
                "calories": float(row["calories"] or 0),
                "carbs": float(row["carbs"] or 0),
                "protein": float(row["protein"] or 0),
                "createdAt": row["created_at"].isoformat() if row["created_at"] else None
            }
            for row in food_logs_result
        ]

        # ── Health Records ──
        health_records_query = text("""
            SELECT 
                id, systolic, diastolic, pulse, recommendation, created_at
            FROM health_records
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 30
        """)
        hr_result = db.execute(health_records_query, {"user_id": u.id}).mappings().all()
        health_records_list = [
            {
                "id": hr["id"],
                "bloodPressure": hr["systolic"],
                "bloodSugar": None,
                "systolic": hr["systolic"],
                "diastolic": hr["diastolic"],
                "pulse": hr["pulse"],
                "recommendation": hr["recommendation"],
                "createdAt": hr["created_at"].isoformat() if hr["created_at"] else None
            }
            for hr in hr_result
        ]

        # ── Allergies ──
        allergies_list = []
        health_info_val = getattr(u, "healthInfo", getattr(u, "health_info", None))
        if health_info_val:
            allergies_list = [item.strip() for item in health_info_val.split(",") if item.strip()]

        results.append({
            "userId": u.id,
            "citizenId": getattr(u, "citizen_id", getattr(u, "citizenId", None)),
            "firstName": getattr(u, "firstName", getattr(u, "first_name", None)),
            "lastName": getattr(u, "lastName", getattr(u, "last_name", None)),
            "heightCm": height,
            "weightKg": weight,
            "bmi": bmi,
            "targetCalories": getattr(u, "target_calories", getattr(u, "targetCalories", None)),
            "targetCarbs": getattr(u, "target_carbs", getattr(u, "targetCarbs", None)),
            "dailyNutrition": daily_nutrition_list,
            "foodLogs": food_logs_list,
            "healthRecords": health_records_list,
            "allergies": allergies_list,
        })
        
    return results

# ==========================================
# 🌟 API บันทึกคำแนะนำและข้อมูลสุขภาพ
# ==========================================
@router.post("/patients/{user_id}/health-records")
def create_health_record(user_id: str, record: HealthRecordCreate, db: Session = Depends(get_db)):
    try:
        # ✅ แก้ไข SQL: เอา blood_sugar ออกจากทั้ง Columns และ Values
        query = text("""
            INSERT INTO health_records (user_id, systolic, diastolic, pulse, recommendation)
            VALUES (:user_id, :systolic, :diastolic, :pulse, :recommendation)
        """)
        
        # ✅ แก้ไข Parameter: ลบ "blood_sugar": record.blood_sugar ออก
        db.execute(query, {
            "user_id": user_id,
            "systolic": record.systolic,
            "diastolic": record.diastolic,
            "pulse": record.pulse,
            "recommendation": record.recommendation
        })
        
        db.commit()
        return {"status": "success", "message": "บันทึกข้อมูลสำเร็จ"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    
@router.get("/organizations/{org_code}")
def get_organization_by_code(org_code: str, db: Session = Depends(get_db)):
    # 💡 ค้นหาข้อมูลโรงพยาบาลจากตารางชื่อ Organizations (หรือชื่อโมเดลตารางโรงพยาบาลของคุณ)
    # สมมติว่าใน models.py มีโมเดลชื่อ Organizations และมีฟิลด์ code กับ name
    org = db.query(models.Organizations).filter(models.Organizations.code == org_code).first()
    
    if not org:
        raise HTTPException(
            status_code=404, 
            detail=f"ไม่พบข้อมูลสถานพยาบาลรหัส {org_code}"
        )
        
    # ส่งค่ากลับไปในรูปแบบ Object ที่มี Key ชื่อ "name" เพื่อให้ตรงกับที่หน้าบ้านแกะค่าไปใช้
    return {
        "code": org.code,
        "name": org.name  # 👈 ชื่อโรงพยาบาลที่จะไปแสดงบนหน้าจอ
    }