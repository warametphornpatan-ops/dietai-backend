# routers/doctor_approval.py
# ✅ Endpoint อนุมัติแพทย์เข้าระบบ - ใช้ Supabase Service Role

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
import jwt
import logging
import os
from supabase import create_client

from app.database import get_db
from app.models import DoctorApplication, Doctors
from app.config import settings

from app.services.email_service import (
    send_doctor_approved_notification,
    send_doctor_rejected_notification,
)

router = APIRouter(prefix="/admins/doctors", tags=["doctors"])
security = HTTPBearer()
logger = logging.getLogger(__name__)

# ✅ Supabase Admin Client (Service Role Key)
supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# ⚠️ ตรวจสอบ environment variables
if not supabase_url:
    logger.warning("⚠️ NEXT_PUBLIC_SUPABASE_URL is not set!")
if not supabase_service_key:
    logger.warning("⚠️ SUPABASE_SERVICE_ROLE_KEY is not set!")

# ✅ สร้าง Supabase Admin Client
supabase_admin = None
if supabase_url and supabase_service_key:
    try:
        supabase_admin = create_client(supabase_url, supabase_service_key)
        logger.info("✅ Supabase Admin Client initialized successfully")
    except Exception as e:
        logger.error(f"❌ Supabase Admin Client initialization failed: {e}")
else:
    logger.error("❌ Missing Supabase environment variables")

# ============================================================
# 📝 REQUEST/RESPONSE MODELS
# ============================================================

class ApproveDoctorRequest(BaseModel):
    status: str  # "approved" or "rejected"

class ApproveDoctorResponse(BaseModel):
    message: str
    doctor_id: int | None = None
    status: str

class DoctorEmailNotifyRequest(BaseModel):
    email: str
    full_name: str
    result: str 

# ============================================================
# 🔐 Helper: ดึงข้อมูล Admin จาก JWT Token
# ============================================================

async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """ถอดรหัส JWT และดึงข้อมูล Admin"""
    token = credentials.credentials
    
    try:
        secret = getattr(settings, "secret_key", getattr(settings, "jwt_secret", "YOUR_SECRET_KEY"))
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        admin_id = payload.get("sub")
    except Exception as e:
        logger.error(f"Token decode failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ไม่ถูกต้อง หรือหมดอายุแล้ว"
        )
    
    if not admin_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ไม่พบข้อมูลผู้ใช้ใน Token"
        )
    
    # ค้นหา admin ในฐานข้อมูล
    result = db.execute(
        text("""
            SELECT admin_id, org_code, first_name, last_name, email, username
            FROM admins
            WHERE admin_id = :uid OR username = :uid
            LIMIT 1
        """),
        {"uid": admin_id},
    ).mappings().first()
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ไม่พบข้อมูลแอดมินนี้"
        )
    
    return {
        "admin_id": str(result["admin_id"]),
        "org_code": result["org_code"],
        "first_name": result["first_name"],
        "last_name": result["last_name"],
        "email": result["email"],
        "username": result["username"],
    }

# ============================================================
# 🔐 PATCH /admins/doctors/{application_id}/approve
# ============================================================

@router.patch("/{application_id}/approve", response_model=ApproveDoctorResponse)
async def approve_doctor_application(
    application_id: int,
    request: ApproveDoctorRequest,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Admin อนุมัติหรือปฏิเสธ Doctor Application
    
    - application_id: ID ใน doctor_applications table
    - status: "approved" หรือ "rejected"
    """
    
    # ❌ ตรวจสอบ supabase_admin มี ค่า
    if not supabase_admin:
        raise HTTPException(
            status_code=500,
            detail="Supabase ยังไม่พร้อม - ลองใหม่ในอีกสักครู่"
        )
    
    # ✅ ตรวจสอบ status ถูกต้อง
    if request.status not in ["approved", "rejected"]:
        raise HTTPException(
            status_code=400,
            detail="status ต้องเป็น 'approved' หรือ 'rejected'"
        )
    
    # ✅ ดึง application จาก Supabase
    try:
        app_result = supabase_admin.table("doctor_applications").select("*").eq("id", application_id).execute()
        if not app_result.data or len(app_result.data) == 0:
            raise HTTPException(
                status_code=404,
                detail="ไม่พบการลงทะเบียนนี้"
            )
        app = app_result.data[0]
    except Exception as e:
        logger.error(f"Error fetching application: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาดในการดึงข้อมูล: {str(e)}"
        )
    
    # ✅ ตรวจสอบ org_code
    if app["org_code"] != current_admin["org_code"]:
        raise HTTPException(
            status_code=403,
            detail="คุณไม่มีสิทธิ์อนุมัติแพทย์นี้"
        )
    
    # ✅ ตรวจสอบ email ยืนยันแล้ว
    if not app.get("email_verified"):
        raise HTTPException(
            status_code=400,
            detail="ต้องยืนยันอีเมลเสียก่อน"
        )
    
    # ✅ ตรวจสอบสถานะ
    if app.get("status") != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"ไม่สามารถจัดการได้ (สถานะปัจจุบัน: {app.get('status')})"
        )
    
    try:
        if request.status == "approved":
            # ✅ APPROVE: บันทึกเข้า doctors table ผ่าน Supabase Service Role
            doctor_data = {
                "org_code": app["org_code"],
                "citizen_id": app["citizen_id"],
                "first_name": app["first_name"],
                "last_name": app["last_name"],
                "email": app["email"],
                "username": app["username"],
                "password_hash": app["password_hash"],
                "position": app["position"],
                "status": "approved",
                "user_id": app.get("user_id"),
                "created_at": datetime.utcnow().isoformat(),
            }
            
            # ✅ INSERT ลง doctors table
            insert_result = supabase_admin.table("doctors").insert(doctor_data).execute()
            
            if not insert_result.data or len(insert_result.data) == 0:
                raise Exception("Failed to insert doctor")
            
            doctor_id = insert_result.data[0]["id"]
            
            # ✅ ลบจาก doctor_applications
            supabase_admin.table("doctor_applications").delete().eq("id", application_id).execute()
            
            logger.info(f"✅ Doctor approved: {app['first_name']} {app['last_name']} (ID: {doctor_id})")
            
            # ✅ ส่งอีเมลแจ้งเตือนอนุมัติ
            doctor_email = app.get("email")
            if doctor_email:
                full_name = f"{app.get('first_name', '')} {app.get('last_name', '')}".strip()
                send_doctor_approved_notification(to_email=doctor_email, full_name=full_name)
            
            return ApproveDoctorResponse(
                message=f"✅ อนุมัติ {app['first_name']} {app['last_name']} สำเร็จ",
                doctor_id=doctor_id,
                status="approved"
            )
        
        else:  # rejected
            # ❌ REJECT: ลบออก
            supabase_admin.table("doctor_applications").delete().eq("id", application_id).execute()
            
            logger.info(f"❌ Doctor rejected: {app['first_name']} {app['last_name']}")
            
            # ✅ ส่งอีเมลแจ้งเตือนปฏิเสธ
            doctor_email = app.get("email")
            if doctor_email:
                full_name = f"{app.get('first_name', '')} {app.get('last_name', '')}".strip()
                send_doctor_rejected_notification(to_email=doctor_email, full_name=full_name)
            
            return ApproveDoctorResponse(
                message=f"❌ ปฏิเสธ {app['first_name']} {app['last_name']} สำเร็จ",
                status="rejected"
            )
    
    except Exception as e:
        logger.error(f"Error approving doctor: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"เกิดข้อผิดพลาด: {str(e)}"
        )
    
@router.post("/notify-email")
async def notify_doctor_email(payload: DoctorEmailNotifyRequest):
    """
    Endpoint เบาๆ สำหรับให้ frontend เรียกหลังจาก Supabase update สำเร็จแล้ว
    ใช้แค่ส่งอีเมลแจ้งเตือนเท่านั้น ไม่แตะ logic อนุมัติ/ปฏิเสธ
    """
    if payload.result == "approved":
        sent = send_doctor_approved_notification(to_email=payload.email, full_name=payload.full_name)
    elif payload.result == "rejected":
        sent = send_doctor_rejected_notification(to_email=payload.email, full_name=payload.full_name)
    else:
        raise HTTPException(status_code=400, detail="result ต้องเป็น 'approved' หรือ 'rejected'")

    return {"email_sent": sent}