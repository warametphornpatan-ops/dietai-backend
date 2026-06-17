from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import or_, text, func
from sqlalchemy import bindparam
from pydantic import BaseModel
from typing import Optional, Dict, List
from ..database import get_db
from .. import models
from app.security import create_access_token, verify_password, hash_password
import logging
import os

logger = logging.getLogger(__name__)


# ==========================================
# 🌟 Pydantic Schemas
# ==========================================

class UserProfileHistoryResponse(BaseModel):
    id: int
    weightKg: Optional[float] = None
    heightCm: Optional[float] = None
    healthInfo: Optional[str] = None
    createdAt: Optional[str] = None

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

SYNC_SECRET = os.getenv("SYNC_SECRET", "")


# ==========================================
# 🌟 API สำหรับการเข้าสู่ระบบของแพทย์
# ==========================================

@router.post("/login")
def login_doctor(payload: DoctorLoginReq, db: Session = Depends(get_db)) -> Dict[str, str]:
    username = payload.username.strip()
    password = payload.password
    org_code = payload.org_code.strip()

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

    if not doctor:
        logger.warning(f"Doctor not found: username={username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="❌ ไม่พบชื่อผู้ใช้นี้ในระบบ"
        )

    if not verify_password(password, doctor.password_hash):
        logger.warning(f"Invalid password: username={username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="❌ รหัสผ่านไม่ถูกต้อง"
        )

    clean_payload_org = "".join(filter(str.isdigit, org_code if org_code else ""))
    clean_doctor_org = "".join(filter(str.isdigit, doctor.org_code.strip() if doctor.org_code else ""))

    if clean_doctor_org != clean_payload_org:
        logger.warning(f"Org code mismatch: username={username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="❌ รหัสหน่วยงานไม่ตรงกับสิทธิ์การเข้าใช้งานของแพทย์ท่านนี้"
        )

    if hasattr(doctor, 'status') and doctor.status != "approved":
        logger.warning(f"Doctor not approved: username={username}, status={doctor.status}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="❌ บัญชีของคุณยังไม่ได้รับการอนุมัติ"
        )

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
        logger.info(f"✅ Doctor login successful: username={username}")
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
# ✨ API ซิงค์รหัสผ่านจาก Supabase
# ==========================================

@router.patch("/sync-password")
def sync_doctor_password(
    payload: SyncPasswordReq,
    db: Session = Depends(get_db),
    x_sync_secret: str = Header(..., alias="X-Sync-Secret")
):
    if not SYNC_SECRET or x_sync_secret != SYNC_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="❌ ไม่มีสิทธิ์เข้าถึง endpoint นี้"
        )

    doctor = db.query(models.Doctors).filter(
        models.Doctors.email == payload.email
    ).first()

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="❌ ไม่พบข้อมูลแพทย์ที่มีอีเมลนี้ในระบบหลัก"
        )

    try:
        doctor.password_hash = hash_password(payload.new_password)
        db.commit()
        logger.info(f"✅ Doctor password synced: email={payload.email}")
        return {"status": "success", "message": "บันทึกรหัสผ่านเข้าฐานข้อมูลหลักสำเร็จ"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error syncing password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Database Error: {str(e)}"
        )


# ==========================================
# 🌟 Helper: batch query ด้วย user_ids list
# ==========================================

def _fetch_batch(db: Session, sql: str, user_ids: List) -> list:
    """
    ✅ รองรับทั้ง 1 user และหลาย user
    ใช้ string interpolation แบบปลอดภัยด้วย ANY + ARRAY
    """
    return db.execute(
        text(sql),
        {"user_ids": list(user_ids)}
    ).mappings().all()


# ==========================================
# 🌟 API ดึงข้อมูลคนไข้ (Updated with BMR, TDEE, Weight History)
# ==========================================

@router.get("/patients")
def get_patients(name: str = "", citizenId: str = "", db: Session = Depends(get_db)):
    if not name and not citizenId:
        return []

    query = db.query(models.User).filter(models.User.role == "user")

    if citizenId:
        filters = []
        if hasattr(models.User, 'citizen_id'):
            filters.append(models.User.citizen_id.like(f"%{citizenId}%"))
        if hasattr(models.User, 'citizenId'):
            filters.append(models.User.citizenId.like(f"%{citizenId}%"))
        if not filters:
            return []
        query = query.filter(or_(*filters))
    elif name:
        filters = []
        if hasattr(models.User, 'firstName'):
            filters.append(models.User.firstName.like(f"%{name}%"))
        if hasattr(models.User, 'lastName'):
            filters.append(models.User.lastName.like(f"%{name}%"))
        if not filters:
            return []
        query = query.filter(or_(*filters))

    users = query.all()
    if not users:
        return []

    user_ids = [str(u.id) for u in users]

    # ✅ ดึง Daily Nutrition
    daily_rows = _fetch_batch(db, """
        SELECT
            user_id,
            DATE(created_at) as log_date,
            SUM(calories) as total_cal,
            SUM(carbs) as total_carb
        FROM food_logs
        WHERE user_id = ANY(:user_ids)
        GROUP BY user_id, DATE(created_at)
        ORDER BY user_id, log_date DESC
    """, user_ids)

    daily_map: Dict = {}
    for row in daily_rows:
        daily_map.setdefault(str(row["user_id"]), []).append({
            "date": str(row["log_date"]),
            "totalCal": float(row["total_cal"] or 0),
            "totalCarb": float(row["total_carb"] or 0),
        })

    # ✅ ดึง Food Logs
    food_rows = _fetch_batch(db, """
        SELECT id, user_id, food_name, calories, carbs, protein, created_at
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) as rn
            FROM food_logs
            WHERE user_id = ANY(:user_ids)
        ) ranked
        WHERE rn <= 50
    """, user_ids)

    food_map: Dict = {}
    for row in food_rows:
        food_map.setdefault(str(row["user_id"]), []).append({
            "id": row["id"],
            "foodName": row["food_name"],
            "calories": float(row["calories"] or 0),
            "carbs": float(row["carbs"] or 0),
            "protein": float(row["protein"] or 0),
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        })

    # ✅ ดึง Health Records
    hr_rows = _fetch_batch(db, """
        SELECT id, user_id, systolic, diastolic, pulse, recommendation, created_at
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) as rn
            FROM health_records
            WHERE user_id = ANY(:user_ids)
        ) ranked
        WHERE rn <= 30
    """, user_ids)

    hr_map: Dict = {}
    for row in hr_rows:
        hr_map.setdefault(str(row["user_id"]), []).append({
            "id": row["id"],
            "systolic": row["systolic"],
            "diastolic": row["diastolic"],
            "pulse": row["pulse"],
            "recommendation": row["recommendation"],
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        })

    # ✅ ดึง Weight History (NEW)
    weight_rows = _fetch_batch(db, """
        SELECT user_id, weight_kg, created_at
        FROM user_profile_history
        WHERE user_id = ANY(:user_ids)
        ORDER BY user_id, created_at ASC
    """, user_ids)

    weight_map: Dict = {}
    for row in weight_rows:
        weight_map.setdefault(str(row["user_id"]), []).append({
            "date": row["created_at"].isoformat() if row["created_at"] else None,
            "weightKg": float(row["weight_kg"]) if row["weight_kg"] is not None else None,
        })

    results = []
    for u in users:
        uid = str(u.id)
        height = getattr(u, "height_cm", getattr(u, "heightCm", None))
        weight = getattr(u, "weight_kg", getattr(u, "weightKg", None))
        bmi = None
        if height and weight:
            h = height / 100
            bmi = round(weight / (h * h), 2)

        health_info_val = getattr(u, "healthInfo", getattr(u, "health_info", None))
        allergies_list = [i.strip() for i in health_info_val.split(",") if i.strip()] if health_info_val else []

        # ✅ เพิ่มค่า BMR, TDEE, Target Calories, Target Carbs, Target Protein, Target Fat
        results.append({
            "userId": u.id,
            "citizenId": getattr(u, "citizen_id", getattr(u, "citizenId", None)),
            "firstName": getattr(u, "firstName", getattr(u, "first_name", None)),
            "lastName": getattr(u, "lastName", getattr(u, "last_name", None)),
            "heightCm": height,
            "weightKg": weight,
            "targetWeightKg": getattr(u, "targetWeightKg", getattr(u, "target_weight_kg", None)),
            "bmi": bmi,
            "bmr": getattr(u, "bmr", None),  # ✅ NEW
            "targetCalories": getattr(u, "target_calories", getattr(u, "targetCalories", None)),  # ✅ NEW
            "targetCarbs": getattr(u, "target_carbs", getattr(u, "targetCarbs", None)),  # ✅ NEW
            "targetProtein": getattr(u, "target_protein", getattr(u, "targetProtein", None)),  # ✅ NEW
            "targetFat": getattr(u, "target_fat", getattr(u, "targetFat", None)),  # ✅ NEW
            "dailyNutrition": daily_map.get(uid, []),
            "foodLogs": food_map.get(uid, []),
            "healthRecords": hr_map.get(uid, []),
            "weightHistory": weight_map.get(uid, []),  # ✅ NEW
            "allergies": allergies_list,
        })

    return results


# ==========================================
# 🌟 API บันทึกข้อมูลสุขภาพ
# ==========================================

@router.post("/patients/{user_id}/health-records")
def create_health_record(user_id: str, record: HealthRecordCreate, db: Session = Depends(get_db)):
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


# ==========================================
# 🌟 API ค้นหาโรงพยาบาลจากรหัส
# ==========================================

@router.get("/organizations/{org_code}")
def get_organization_by_code(org_code: str, db: Session = Depends(get_db)):
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


# ==========================================
# 🌟 API ดึงประวัติการเปลี่ยนแปลงน้ำหนัก
# ==========================================

@router.get("/patients/{user_id}/profile-history", response_model=List[UserProfileHistoryResponse])
def get_patient_profile_history(user_id: str, db: Session = Depends(get_db)):
    try:
        # ดึงข้อมูลจากตาราง user_profile_history เรียงตามเวลาล่าสุดลงไป
        rows = db.execute(text("""
            SELECT id, weight_kg, height_cm, health_info, created_at
            FROM user_profile_history
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """), {"user_id": user_id}).mappings().all()
        
        # จัดรูปแบบข้อมูลเพื่อส่งกลับไปให้หน้าบ้าน (Frontend)
        history_list = []
        for row in rows:
            history_list.append({
                "id": row["id"],
                "weightKg": float(row["weight_kg"]) if row["weight_kg"] is not None else None,
                "heightCm": float(row["height_cm"]) if row["height_cm"] is not None else None,
                "healthInfo": row["health_info"],
                "createdAt": row["created_at"].isoformat() if row["created_at"] else None
            })
            
        return history_list

    except Exception as e:
        logger.error(f"Error fetching user profile history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ เกิดข้อผิดพลาดในการดึงข้อมูลประวัติ: {str(e)}"
        )