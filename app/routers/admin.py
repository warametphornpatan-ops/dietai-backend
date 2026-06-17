from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, text   # ✅ เพิ่ม text
from passlib.hash import bcrypt_sha256
from typing import Optional, Dict, List
from pydantic import BaseModel
import os

from ..database import get_db
from .. import models
from .. import schemas
# 🔐 นำเข้า get_current_user เพื่อใช้ล็อกสิทธิ์ API
from app.security import create_access_token, get_current_user

from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

router = APIRouter()

# ---------- Dependency สำหรับล็อกเฉพาะสิทธิ์ Admin ----------
def get_current_admin(current_user: models.User = Depends(get_current_user)):
    """
    ✅ FIX: ตรวจสิทธิ์ admin แบบยืดหยุ่น
    - ผ่านถ้า role == "admin"
    - หรือผ่านถ้า object มี attribute admin_id (เป็นแถวจากตาราง admins)
      กันกรณีโมเดล Admin ไม่มีคอลัมน์ role ซึ่งทำให้ getattr คืน None → 403
    """
    role = getattr(current_user, "role", None)
    is_admin = (role == "admin") or hasattr(current_user, "admin_id")
    if not is_admin:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์เข้าถึงข้อมูลนี้ (เฉพาะแอดมินเท่านั้น)")
    return current_user


# ---------- Schemas ----------
class LoginReq(BaseModel):
    username: str
    password: str
    org_code: str

class DoctorUpdate(BaseModel):
    org_code: str
    first_name: str
    last_name: str
    username: str
    email: str
    citizen_id: Optional[str] = None
    position: Optional[str] = None

class SyncPasswordReq(BaseModel):
    email: str
    new_password: str

class AdminProfileUpdate(BaseModel):
    first_name: str
    last_name: str
    email: str
    position: Optional[str] = None


# --- 1. ตรวจสอบ Username ซ้ำ (Case-Insensitive ทั่วทั้งระบบ) ---
@router.get("/doctors/check-username")
def check_username_global(
    username: str = Query(...),
    org_code: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> Dict[str, object]:
    username_clean = username.strip().lower()

    if db.query(models.Admin).filter(func.lower(models.Admin.username) == username_clean).first():
        return {"is_available": False, "detail": "Username นี้ถูกใช้งานแล้วในระบบผู้ดูแลระบบ (Admin)"}

    if db.query(models.Doctors).filter(func.lower(models.Doctors.username) == username_clean).first():
        return {"is_available": False, "detail": "Username นี้ถูกใช้งานแล้วในระบบบัญชีแพทย์ (Doctors)"}

    return {"is_available": True, "detail": "Username นี้สามารถใช้งานได้"}


# --- 2. API ลงทะเบียนผู้ดูแลระบบ (ล็อกสิทธิ์เฉพาะแอดมินเดิมทำได้) ---
@router.post("/register")
def register_admin(
    payload: schemas.AdminCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
) -> Dict[str, str]:
    admin_username = payload.username.strip()
    admin_username_lower = admin_username.lower()
    email_clean_lower = payload.email.strip().lower()

    existing_admin = db.query(models.Admin).filter(
        or_(
            models.Admin.citizen_id == payload.citizen_id,
            func.lower(models.Admin.email) == email_clean_lower,
            func.lower(models.Admin.username) == admin_username_lower
        )
    ).first()

    if existing_admin:
        raise HTTPException(status_code=400, detail="เลขบัตรประชาชน, อีเมล หรือ ชื่อผู้ใช้นี้ มีในระบบแอดมินแล้ว")

    existing_doctor_user = db.query(models.Doctors).filter(
        func.lower(models.Doctors.username) == admin_username_lower
    ).first()

    if existing_doctor_user:
        raise HTTPException(status_code=400, detail="ชื่อผู้ใช้นี้ถูกใช้งานแล้วในระบบบัญชีแพทย์ผู้ใช้งาน")

    try:
        supabase.auth.admin.invite_user_by_email(
            payload.email.strip(),
            options={"redirectTo": "https://dietai-admin.vercel.app/set-password"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ส่งอีเมลคำเชิญไม่สำเร็จ: {str(e)}")

    new_admin = models.Admin(
        org_code=payload.org_code,
        citizen_id=payload.citizen_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email.strip(),
        username=admin_username,
        password_hash="INVITED_BUT_NOT_SET"
    )

    db.add(new_admin)
    db.commit()

    return {"message": "เพิ่มผู้ดูแลระบบและส่งอีเมลคำเชิญเรียบร้อยแล้ว"}


# --- 3. ดึงรายชื่อแอดมินในหน่วยงาน (🔒 ล็อก org_code ตามแอดมินที่ล็อกอิน) ---
@router.get("/list")
def get_admins(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
) -> Dict[str, List[Dict[str, str]]]:
    admins = db.query(models.Admin).filter(models.Admin.org_code == current_admin.org_code).all()

    result: List[Dict[str, str]] = []
    for a in admins:
        result.append({
            "id": str(a.admin_id),
            "org_code": a.org_code,
            "first_name": a.first_name,
            "last_name": a.last_name,
            "username": a.username,
            "email": a.email or "",
            "position": "ผู้ดูแลระบบ",
            "role": "admin"
        })
    return {"admins": result}


# --- 4. ดึงรายชื่อแพทย์ทั้งหมด (🔒 ล็อก org_code ตามแอดมินที่ล็อกอิน) ---
@router.get("/doctors")
def get_doctors(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
) -> Dict[str, List[Dict[str, str]]]:
    doctors = db.query(models.Doctors).filter(models.Doctors.org_code == current_admin.org_code).all()

    result: List[Dict[str, str]] = []
    for doc in doctors:
        result.append({
            "doctor_id": str(doc.id),
            "org_code": doc.org_code,
            "first_name": doc.first_name,
            "last_name": doc.last_name,
            "position": doc.position or "",
            "username": doc.username,
            "email": doc.email or ""
        })
    return {"doctors": result}


# --- 5. API ลงทะเบียนบุคลากรทางการแพทย์ (🔒 ล็อกสิทธิ์) ---
@router.post("/doctors")
def add_doctor(
    payload: schemas.DoctorCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
) -> Dict[str, str]:
    username_clean = payload.username.strip()
    username_lower = username_clean.lower()
    email_clean = payload.email.strip()
    email_lower = email_clean.lower()

    doc_exists = db.query(models.Doctors).filter(
        or_(
            func.lower(models.Doctors.username) == username_lower,
            func.lower(models.Doctors.email) == email_lower
        )
    ).first()
    if doc_exists:
        raise HTTPException(status_code=400, detail="Username หรือ อีเมลนี้ ถูกใช้งานโดยบุคลากรท่านอื่นในระบบแล้ว")

    admin_exists = db.query(models.Admin).filter(
        or_(
            func.lower(models.Admin.username) == username_lower,
            func.lower(models.Admin.email) == email_lower
        )
    ).first()
    if admin_exists:
        raise HTTPException(status_code=400, detail="Username หรือ อีเมลนี้ ซ้ำกับระบบผู้ดูแลระบบ ไม่สามารถใช้งานได้")

    hashed_pwd = bcrypt_sha256.hash(payload.password)

    new_doctor = models.Doctors(
        org_code=current_admin.org_code,
        citizen_id=payload.citizen_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        position=payload.position,
        username=username_clean,
        email=email_clean,
        password_hash=hashed_pwd,
    )
    db.add(new_doctor)
    db.commit()
    return {"message": "ลงทะเบียนบุคลากรทางการแพทย์สำเร็จ"}


# --- 6. API แก้ไขข้อมูลแพทย์ ---
@router.put("/doctors/{doctor_id}")
def update_doctor(
    doctor_id: str,
    payload: DoctorUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
) -> Dict[str, str]:
    doctor = db.query(models.Doctors).filter(
        models.Doctors.id == doctor_id,
        models.Doctors.org_code == current_admin.org_code
    ).first()

    if not doctor:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลแพทย์ในระบบของคุณ")

    username_clean = payload.username.strip()
    username_lower = username_clean.lower()

    if username_lower != doctor.username.lower():
        doc_exists = db.query(models.Doctors).filter(
            models.Doctors.id != doctor_id,
            func.lower(models.Doctors.username) == username_lower
        ).first()
        if doc_exists:
            raise HTTPException(status_code=400, detail="Username นี้ถูกใช้งานโดยแพทย์ท่านอื่นในระบบแล้ว")

        admin_exists = db.query(models.Admin).filter(
            func.lower(models.Admin.username) == username_lower
        ).first()
        if admin_exists:
            raise HTTPException(status_code=400, detail="Username นี้ซ้ำกับระบบผู้ดูแลระบบ ไม่สามารถใช้งานได้")

    doctor.org_code = payload.org_code
    doctor.first_name = payload.first_name
    doctor.last_name = payload.last_name
    doctor.username = username_clean

    if payload.email is not None:
        doctor.email = payload.email

    if payload.citizen_id:
        doctor.citizen_id = payload.citizen_id

    if payload.position is not None:
        doctor.position = payload.position

    db.commit()
    return {"message": "อัปเดตข้อมูลแพทย์สำเร็จ"}


# --- 7. API ลบแพทย์ ---
@router.delete("/doctors/{doctor_id}")
def delete_doctor(
    doctor_id: str,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
) -> Dict[str, str]:
    doctor = db.query(models.Doctors).filter(
        models.Doctors.id == doctor_id,
        models.Doctors.org_code == current_admin.org_code
    ).first()

    if not doctor:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลแพทย์ในหน่วยงานของคุณ")

    try:
        db.delete(doctor)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="ไม่สามารถลบข้อมูลแพทย์ได้เนื่องจากมีข้อมูลอื่นอ้างอิงอยู่ แนะนำให้ทำ Soft Delete แทน"
        )
    return {"message": "ลบข้อมูลสำเร็จ"}


# --- 8. API ล็อกอินรวม ---
@router.post("/login")
def login_staff(payload: LoginReq, db: Session = Depends(get_db)) -> Dict[str, str]:
    input_username: str = payload.username.strip().lower()

    admin = db.query(models.Admin).filter(
        func.lower(models.Admin.username) == input_username
    ).first()

    if admin:
        if not bcrypt_sha256.verify(payload.password, admin.password_hash):
            raise HTTPException(status_code=401, detail="❌ รหัสผ่านไม่ถูกต้อง")

        clean_payload_org: str = "".join(filter(str.isdigit, payload.org_code.strip()))
        clean_admin_org: str = "".join(filter(str.isdigit, admin.org_code.strip() if admin.org_code else ""))

        if clean_admin_org != clean_payload_org:
            raise HTTPException(status_code=401, detail="❌ รหัสหน่วยงานไม่ตรงกับสิทธิ์การเข้าใช้งาน")

        access_token: str = create_access_token(
            data={
                "sub": str(admin.admin_id),
                "role": "admin",
                "org_code": admin.org_code,
                "first_name": admin.first_name,
                "last_name": admin.last_name
            }
        )
        return {"access_token": access_token, "token_type": "bearer", "role": "admin"}

    doctor = db.query(models.Doctors).filter(
        or_(
            func.lower(models.Doctors.username) == input_username,
            func.lower(models.Doctors.email) == input_username
        )
    ).first()

    if doctor:
        if hasattr(doctor, 'password_hash') and doctor.password_hash and doctor.password_hash != "INVITED_BUT_NOT_SET":
            if bcrypt_sha256.verify(payload.password, doctor.password_hash):
                access_token = create_access_token(
                    data={
                        "sub": str(doctor.id),
                        "role": "doctor",
                        "org_code": doctor.org_code,
                        "first_name": doctor.first_name,
                        "last_name": doctor.last_name,
                        "position": doctor.position,
                    }
                )
                return {"access_token": access_token, "token_type": "bearer", "role": "doctor"}
            else:
                raise HTTPException(status_code=401, detail="❌ รหัสผ่านไม่ถูกต้อง")

        try:
            supabase_auth = supabase.auth.sign_in_with_password({
                "email": doctor.email,
                "password": payload.password
            })
            if supabase_auth.user:
                access_token = create_access_token(
                    data={
                        "sub": str(doctor.id),
                        "role": "doctor",
                        "org_code": doctor.org_code,
                        "first_name": doctor.first_name,
                        "last_name": doctor.last_name,
                        "position": doctor.position,
                    }
                )
                return {"access_token": access_token, "token_type": "bearer", "role": "doctor"}
        except Exception:
            raise HTTPException(status_code=401, detail="❌ รหัสผ่านไม่ถูกต้อง")

    raise HTTPException(status_code=401, detail="❌ ไม่พบชื่อผู้ใช้นี้ในระบบ")


# --- 9. API ตรวจสอบ Username (Admin) ---
@router.get("/check-username")
def check_admin_username(username: str, db: Session = Depends(get_db)) -> Dict[str, bool]:
    username_clean = username.strip().lower()

    existing = db.query(models.Admin).filter(
        func.lower(models.Admin.username) == username_clean
    ).first()

    existing_doctor = db.query(models.Doctors).filter(
        func.lower(models.Doctors.username) == username_clean
    ).first()

    is_available = existing is None and existing_doctor is None
    return {"is_available": is_available}


# --- 10. API ตรวจสอบ Email ---
@router.get("/check-email")
def check_admin_email(email: str, db: Session = Depends(get_db)) -> Dict[str, bool]:
    em = email.strip().lower()

    existing_admin = db.query(models.Admin).filter(
        func.lower(models.Admin.email) == em
    ).first()

    existing_doctor = db.query(models.Doctors).filter(
        func.lower(models.Doctors.email) == em
    ).first()

    is_available = existing_admin is None and existing_doctor is None
    return {"is_available": is_available}


# --- 11. API sync-password สำหรับแอดมิน ---
@router.patch("/sync-password")
def sync_admin_password(payload: SyncPasswordReq, db: Session = Depends(get_db)):
    admin = db.query(models.Admin).filter(
        func.lower(models.Admin.email) == payload.email.strip().lower()
    ).first()
    if not admin:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลแอดมินที่มีอีเมลนี้")

    admin.password_hash = bcrypt_sha256.hash(payload.new_password)
    try:
        db.commit()
        return {"status": "success", "message": "บันทึกรหัสผ่านสำเร็จ"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")


# --- 12. API แก้ไขข้อมูล Admin Profile (ตัวเอง) ---
@router.patch("/profile/{admin_id}")
def update_admin_profile(
    admin_id: str,
    payload: AdminProfileUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
) -> Dict[str, str]:

    if str(current_admin.admin_id) != admin_id:
         raise HTTPException(status_code=403, detail="คุณไม่มีสิทธิ์แก้ไขโปรไฟล์ของผู้อื่น")

    admin = db.query(models.Admin).filter(models.Admin.admin_id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลแอดมิน")

    email_lower = payload.email.strip().lower()
    if email_lower != admin.email.lower():
        existing_admin = db.query(models.Admin).filter(
            models.Admin.admin_id != admin_id,
            func.lower(models.Admin.email) == email_lower
        ).first()
        if existing_admin:
            raise HTTPException(status_code=400, detail="อีเมลนี้ถูกใช้งานแล้ว")

        existing_doctor = db.query(models.Doctors).filter(
            func.lower(models.Doctors.email) == email_lower
        ).first()
        if existing_doctor:
            raise HTTPException(status_code=400, detail="อีเมลนี้ซ้ำกับระบบแพทย์")

    admin.first_name = payload.first_name.strip()
    admin.last_name = payload.last_name.strip()
    admin.email = payload.email.strip()
    if payload.position:
        admin.position = payload.position.strip()

    try:
        db.commit()
        db.refresh(admin)
        return {
            "message": "แก้ไขข้อมูลสำเร็จ",
            "admin_id": str(admin.admin_id),
            "first_name": admin.first_name,
            "last_name": admin.last_name,
            "email": admin.email
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")


# --- 13. API ลบแอดมิน ---
@router.delete("/{admin_id}")
def delete_admin(
    admin_id: str,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
) -> Dict[str, str]:
    admin = db.query(models.Admin).filter(models.Admin.admin_id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลผู้ดูแลระบบ")

    if admin.org_code != current_admin.org_code:
        raise HTTPException(status_code=403, detail="คุณไม่มีสิทธิ์ลบผู้ดูแลระบบของหน่วยงานอื่น")

    admin_count = db.query(models.Admin).filter(
        models.Admin.org_code == admin.org_code
    ).count()
    if admin_count <= 1:
        raise HTTPException(
            status_code=400,
            detail="ไม่สามารถลบได้ เนื่องจากเป็นผู้ดูแลระบบคนสุดท้ายของหน่วยงาน"
        )

    try:
        db.delete(admin)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="ไม่สามารถลบผู้ดูแลระบบได้เนื่องจากมีข้อมูลอื่นอ้างอิงอยู่"
        )
    return {"message": "ลบแอดมินสำเร็จ"}


# ============================================================
# ✅ FIX 2: เพิ่ม endpoint สำหรับ "รายการแจ้งปัญหา" (Support Requests)
# ============================================================
# ตาราง support_requests มีคอลัมน์: id, email, name, request_type,
#   description, status, created_at
# frontend อ่านชื่อ contact_info / details จึงต้อง map ให้ตรง

# --- 14. ดึงรายการแจ้งปัญหาที่ยังค้างอยู่ ---
@router.get("/support-requests")
def get_support_requests(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    rows = db.execute(text("""
        SELECT id, email, name, request_type, description, status, created_at
        FROM support_requests
        WHERE status = 'pending' OR status IS NULL
        ORDER BY created_at DESC
    """)).fetchall()

    requests = []
    for r in rows:
        requests.append({
            "id": r.id,
            "contact_info": r.email,            # map email → contact_info
            "name": r.name or "",                # ✅ ตอนนี้ select มาแล้ว เข้าถึงได้จริง
            "details": r.description or "",      # map description → details
            "request_type": r.request_type,
            "status": r.status or "pending",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {"requests": requests}


# --- 15. กด "ติดต่อแล้ว" → เปลี่ยน status เป็น resolved ---
@router.patch("/support-requests/{request_id}/resolve")
def resolve_support_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
) -> Dict[str, str]:
    result = db.execute(
        text("UPDATE support_requests SET status = 'resolved' WHERE id = :id"),
        {"id": request_id},
    )
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="ไม่พบคำร้องนี้ในระบบ")

    return {"message": "อัปเดตสถานะคำร้องเรียนสำเร็จ"}


@router.get("/list-all-users")
def get_all_users(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    """
    ดึง user ทั้งหมดในระบบ คืนเฉพาะ name / username / email
    ถ้าส่ง ?search= มา จะกรองด้วยชื่อ/username/email
    """
    users = db.query(models.User).all()

    result = []
    for u in users:
        # ยืดหยุ่นกับชื่อคอลัมน์ (first_name หรือ firstName)
        first = getattr(u, "first_name", None) or getattr(u, "firstName", None) or ""
        last = getattr(u, "last_name", None) or getattr(u, "lastName", None) or ""
        full_name = f"{first} {last}".strip()

        result.append({
            "id": str(getattr(u, "id", "")),
            "name": full_name or "—",
            "username": getattr(u, "username", "") or "",
            "email": getattr(u, "email", "") or "",
        })

    # กรองตามคำค้นหา (ถ้ามี)
    if search:
        s = search.strip().lower()
        result = [
            r for r in result
            if s in r["name"].lower()
            or s in r["username"].lower()
            or s in r["email"].lower()
        ]

    return {"users": result, "total": len(result)}