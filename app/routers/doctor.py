from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import or_, text, func
from pydantic import BaseModel
from typing import Optional, Dict
from ..database import get_db
from .. import models
from app.security import create_access_token, verify_password, hash_password
import logging
import os

logger = logging.getLogger(__name__)


# ==========================================
# 🌟 Pydantic Schemas
# ==========================================

class HealthRecordCreate(BaseModel):
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    pulse: Optional[int] = None
    recommendation: str

class DoctorLoginReq(BaseModel):
    username: str
    password: str
    org_code: str

class SyncPasswordReq(BaseModel):
    email: str
    new_password: str


router = APIRouter(tags=["doctor"])

# 🔐 ตั้ง SYNC_SECRET ใน environment variable เช่น SYNC_SECRET=your-secret-key
SYNC_SECRET = os.getenv("SYNC_SECRET", "")


# ==========================================
# 🌟 API สำหรับการเข้าสู่ระบบของแพทย์
# ==========================================

@router.post("/login")
def login_doctor(payload: DoctorLoginReq, db: Session = Depends(get_db)) -> Dict[str, str]:
    """
    Doctor Login Endpoint

    - ตรวจสอบ username + password (bcrypt) + org_code
    - ส่งกลับ JWT token
    """

    username = payload.username.strip()
    password = payload.password
    org_code = payload.org_code.strip()

    # ✅ ดึงข้อมูลแพทย์จากฐานข้อมูล
    try:
        doctor = db.query(models.Doctors).filter(
            func.lower(models.Doctors.username) == username.lower()
        ).first()
    except Exception as e:
        logger.error(f"Error querying doctor: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="❌ เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล"
        )

    # ✅ ตรวจสอบว่า doctor มีอยู่
    if not doctor:
        logger.warning(f"Doctor not found: username={username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="❌ ไม่พบชื่อผู้ใช้นี้ในระบบ"
        )

    # ✅ Verify password ด้วย bcrypt จาก security.py
    if not verify_password(password, doctor.password_hash):
        logger.warning(f"Invalid password: username={username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="❌ รหัสผ่านไม่ถูกต้อง"
        )

    # ✅ ตรวจสอบรหัสหน่วยงาน (org_code)
    clean_payload_org = "".join(filter(str.isdigit, org_code if org_code else ""))
    clean_doctor_org = "".join(filter(str.isdigit, doctor.org_code.strip() if doctor.org_code else ""))

    if clean_doctor_org != clean_payload_org:
        logger.warning(f"Org code mismatch: username={username}, provided={clean_payload_org}, expected={clean_doctor_org}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="❌ รหัสหน่วยงานไม่ตรงกับสิทธิ์การเข้าใช้งานของแพทย์ท่านนี้"
        )

    # ✅ ตรวจสอบสถานะ doctor (ต้องได้รับการอนุมัติ)
    if hasattr(doctor, 'status') and doctor.status != "approved":
        logger.warning(f"Doctor not approved: username={username}, status={doctor.status}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="❌ บัญชีของคุณยังไม่ได้รับการอนุมัติ"
        )

    # ✅ สร้าง Access Token
    try:
        access_token = create_access_token(
            data={
                "sub": doctor.username,
                "role": "doctor",
                "org_code": doctor.org_code,
                "first_name": doctor.first_name,
                "last_name": doctor.last_name,
                "position": doctor.position,
            }
        )

        logger.info(f"✅ Doctor login successful: username={username}, org_code={org_code}")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "role": "doctor"
        }

    except Exception as e:
        logger.error(f"Error creating token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="❌ เกิดข้อผิดพลาดในการสร้าง token"
        )


# ==========================================
# ✨ API สำหรับซิงค์รหัสผ่านใหม่จากหน้าตั้งรหัสผ่าน (Supabase)
# ==========================================

@router.patch("/sync-password")
def sync_doctor_password(
    payload: SyncPasswordReq,
    db: Session = Depends(get_db),
    x_sync_secret: str = Header(..., alias="X-Sync-Secret")
):
    """
    Sync password from Supabase to main database

    - ต้องส่ง Header: X-Sync-Secret ที่ตรงกับ SYNC_SECRET ใน env
    - ค้นหาแพทย์จากอีเมล
    - Hash รหัสผ่านด้วย bcrypt แล้วบันทึก
    """

    # ✅ ตรวจสอบ secret key ก่อน
    if not SYNC_SECRET or x_sync_secret != SYNC_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="❌ ไม่มีสิทธิ์เข้าถึง endpoint นี้"
        )

    # 1. ค้นหาแพทย์ในตารางด้วยอีเมล
    doctor = db.query(models.Doctors).filter(
        models.Doctors.email == payload.email
    ).first()

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="❌ ไม่พบข้อมูลแพทย์ที่มีอีเมลนี้ในระบบหลัก"
        )

    try:
        # 2. Hash รหัสผ่านด้วย bcrypt ก่อนบันทึก
        doctor.password_hash = hash_password(payload.new_password)
        db.commit()

        logger.info(f"✅ Doctor password synced: email={payload.email}")

        return {
            "status": "success",
            "message": "บันทึกรหัสผ่านเข้าฐานข้อมูลหลักสำเร็จ"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error syncing password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Database Error: {str(e)}"
        )


# ==========================================
# 🌟 API ดึงข้อมูลคนไข้ (รวมประวัติโภชนาการและสุขภาพ)
# ==========================================

@router.get("/patients")
def get_patients(name: str = "", citizenId: str = "", db: Session = Depends(get_db)):
    """
    Get patients by name or citizen ID

    - ค้นหาคนไข้จากชื่อหรือเลขบัตรประชาชน
    - ส่งกลับข้อมูลสมบูรณ์รวม health records, food logs, etc.
    """

    if not name and not citizenId:
        return []

    query = db.query(models.User).filter(models.User.role == "user")

    # ✅ Build filters แบบ safe ไม่ส่ง None เข้า or_()
    if citizenId:
        filters = []
        if hasattr(models.User, 'citizen_id'):
            filters.append(models.User.citizen_id.like(f"%{citizenId}%"))
        if hasattr(models.User, 'citizenId'):
            filters.append(models.User.citizenId.like(f"%{citizenId}%"))
        if filters:
            query = query.filter(or_(*filters))
        else:
            return []
    elif name:
        filters = []
        if hasattr(models.User, 'firstName'):
            filters.append(models.User.firstName.like(f"%{name}%"))
        if hasattr(models.User, 'lastName'):
            filters.append(models.User.lastName.like(f"%{name}%"))
        if filters:
            query = query.filter(or_(*filters))
        else:
            return []

    users = query.all()
    if not users:
        return []

    # ✅ Batch query แทน N+1
    user_ids = [u.id for u in users]
    user_ids_tuple = tuple(user_ids) if len(user_ids) > 1 else f"({user_ids[0]})"

    # ── โภชนาการรายวัน (batch) ──
    daily_rows = db.execute(text("""
        SELECT 
            user_id,
            DATE(created_at) as log_date,
            SUM(calories) as total_cal,
            SUM(carbs) as total_carb
        FROM food_logs
        WHERE user_id IN :user_ids
        GROUP BY user_id, DATE(created_at)
        ORDER BY user_id, log_date DESC
    """), {"user_ids": user_ids_tuple}).mappings().all()

    daily_map: Dict = {}
    for row in daily_rows:
        daily_map.setdefault(row["user_id"], []).append({
            "date": str(row["log_date"]),
            "totalCal": float(row["total_cal"] or 0),
            "totalCarb": float(row["total_carb"] or 0),
        })

    # ── ประวัติอาหารรายมื้อ (batch) ──
    food_rows = db.execute(text("""
        SELECT id, user_id, food_name, calories, carbs, protein, created_at
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) as rn
            FROM food_logs
            WHERE user_id IN :user_ids
        ) ranked
        WHERE rn <= 50
    """), {"user_ids": user_ids_tuple}).mappings().all()

    food_map: Dict = {}
    for row in food_rows:
        food_map.setdefault(row["user_id"], []).append({
            "id": row["id"],
            "foodName": row["food_name"],
            "calories": float(row["calories"] or 0),
            "carbs": float(row["carbs"] or 0),
            "protein": float(row["protein"] or 0),
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        })

    # ── Health Records (batch) ──
    hr_rows = db.execute(text("""
        SELECT id, user_id, systolic, diastolic, pulse, recommendation, created_at
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) as rn
            FROM health_records
            WHERE user_id IN :user_ids
        ) ranked
        WHERE rn <= 30
    """), {"user_ids": user_ids_tuple}).mappings().all()

    hr_map: Dict = {}
    for row in hr_rows:
        hr_map.setdefault(row["user_id"], []).append({
            "id": row["id"],
            "systolic": row["systolic"],
            "diastolic": row["diastolic"],
            "pulse": row["pulse"],
            "recommendation": row["recommendation"],
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        })

    # ── Build results ──
    results = []
    for u in users:
        height = getattr(u, "height_cm", getattr(u, "heightCm", None))
        weight = getattr(u, "weight_kg", getattr(u, "weightKg", None))
        bmi = None
        if height and weight:
            h = height / 100
            bmi = round(weight / (h * h), 2)

        health_info_val = getattr(u, "healthInfo", getattr(u, "health_info", None))
        allergies_list = [item.strip() for item in health_info_val.split(",") if item.strip()] if health_info_val else []

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
            "dailyNutrition": daily_map.get(u.id, []),
            "foodLogs": food_map.get(u.id, []),
            "healthRecords": hr_map.get(u.id, []),
            "allergies": allergies_list,
        })

    return results


# ==========================================
# 🌟 API บันทึกคำแนะนำและข้อมูลสุขภาพ
# ==========================================

@router.post("/patients/{user_id}/health-records")
def create_health_record(user_id: str, record: HealthRecordCreate, db: Session = Depends(get_db)):
    """
    Create health record for a patient

    - บันทึก systolic, diastolic, pulse, recommendation
    """

    try:
        db.execute(text("""
            INSERT INTO health_records (user_id, systolic, diastolic, pulse, recommendation)
            VALUES (:user_id, :systolic, :diastolic, :pulse, :recommendation)
        """), {
            "user_id": user_id,
            "systolic": record.systolic,
            "diastolic": record.diastolic,
            "pulse": record.pulse,
            "recommendation": record.recommendation
        })

        db.commit()
        logger.info(f"✅ Health record created: user_id={user_id}")

        return {"status": "success", "message": "บันทึกข้อมูลสำเร็จ"}

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating health record: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Database Error: {str(e)}"
        )
    
    @router.post("/migrate-passwords")
    def migrate_passwords(db: Session = Depends(get_db)):
     migrated = 0
    doctors = db.query(models.Doctors).all()
    for doctor in doctors:
        if doctor.password_hash and not doctor.password_hash.startswith("$2b$"):
            doctor.password_hash = hash_password(doctor.password_hash)
            migrated += 1
    db.commit()
    return {"migrated": migrated}


# ==========================================
# 🌟 API ค้นหาโรงพยาบาลจากรหัส
# ==========================================

@router.get("/organizations/{org_code}")
def get_organization_by_code(org_code: str, db: Session = Depends(get_db)):
    """
    Get organization by code

    - ค้นหาข้อมูลโรงพยาบาล
    - ส่งกลับชื่อและรหัส
    """

    try:
        org = db.query(models.Organizations).filter(
            models.Organizations.code == org_code
        ).first()

        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"❌ ไม่พบข้อมูลสถานพยาบาลรหัส {org_code}"
            )

        return {"code": org.code, "name": org.name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="❌ เกิดข้อผิดพลาดในการดึงข้อมูล"
        )