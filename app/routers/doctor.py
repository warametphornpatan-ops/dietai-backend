from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, text, func
from pydantic import BaseModel
from typing import Optional, Dict
from ..database import get_db
from .. import models
from app.security import create_access_token
import logging

try:
    from passlib.hash import bcrypt_sha256
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

logger = logging.getLogger(__name__)

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
# 🔐 Helper: Verify Password (Backward Compatible)
# ==========================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    ตรวจสอบ password - รองรับทั้ง:
    1. bcrypt_sha256 hash (ใหม่)
    2. plain text (ข้อมูลเก่า - backward compatible)
    """
    
    # ✅ ลอง bcrypt_sha256 ก่อน (ถ้าติดตั้ง)
    if BCRYPT_AVAILABLE:
        try:
            # ตรวจสอบว่า hashed_password ดูเหมือน bcrypt hash
            if hashed_password.startswith('$2b$') or hashed_password.startswith('$2a$') or hashed_password.startswith('$2y$'):
                return bcrypt_sha256.verify(plain_password, hashed_password)
        except Exception as e:
            logger.debug(f"bcrypt verification failed: {e}")
    
    # ✅ Fallback: ใช้ plain text comparison (ข้อมูลเก่า)
    return plain_password == hashed_password

# ==========================================
# 🌟 API สำหรับการเข้าสู่ระบบของแพทย์
# ==========================================

@router.post("/login")
def login_doctor(payload: DoctorLoginReq, db: Session = Depends(get_db)) -> Dict[str, str]:
    """
    Doctor Login Endpoint
    
    - ตรวจสอบ username + password + org_code
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
    
    # ✅ Verify password (รองรับทั้ง bcrypt + plain text)
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
            detail=f"❌ บัญชีของคุณยังไม่ได้รับการอนุมัติ"
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
def sync_doctor_password(payload: SyncPasswordReq, db: Session = Depends(get_db)):
    """
    Sync password from Supabase to main database
    
    - ค้นหาแพทย์จากอีเมล
    - Hash รหัสผ่านใหม่
    - บันทึกลงฐานข้อมูล
    """
    
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
        # 2. เข้ารหัสลับรหัสผ่านด้วย bcrypt_sha256
        if BCRYPT_AVAILABLE:
            hashed_password = bcrypt_sha256.hash(payload.new_password)
        else:
            # Fallback: เก็บเป็น plain text (ไม่ปลอดภัย - แนะนำให้ install passlib)
            logger.warning("⚠️ bcrypt_sha256 not available, storing password as plain text")
            hashed_password = payload.new_password
        
        # 3. อัปเดตลงฟิลด์ password_hash
        doctor.password_hash = hashed_password
        
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
    
    # ✅ สร้าง query base ก่อน
    query = db.query(models.User).filter(models.User.role == "user")

    # ✅ Handle ทั้ง citizen_id และ citizenId
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

        # ── Health Records (ตัด blood_sugar ออก) ──
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
    """
    Create health record for a patient
    
    - บันทึก systolic, diastolic, pulse, recommendation
    - ตัด blood_sugar ออกแล้ว
    """
    
    try:
        # ✅ Insert health record (ไม่มี blood_sugar)
        query = text("""
            INSERT INTO health_records (user_id, systolic, diastolic, pulse, recommendation)
            VALUES (:user_id, :systolic, :diastolic, :pulse, :recommendation)
        """)
        
        db.execute(query, {
            "user_id": user_id,
            "systolic": record.systolic,
            "diastolic": record.diastolic,
            "pulse": record.pulse,
            "recommendation": record.recommendation
        })
        
        db.commit()
        
        logger.info(f"✅ Health record created: user_id={user_id}")
        
        return {
            "status": "success",
            "message": "บันทึกข้อมูลสำเร็จ"
        }
    
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
        
        return {
            "code": org.code,
            "name": org.name
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="❌ เกิดข้อผิดพลาดในการดึงข้อมูล"
        )