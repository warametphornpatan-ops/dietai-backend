from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from passlib.hash import bcrypt_sha256
from typing import Optional, Dict, List
from pydantic import BaseModel
import os

from ..database import get_db
from .. import models
from .. import schemas
from app.security import create_access_token

# เปิดใช้งาน Supabase Client สำหรับฝั่ง Backend
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

router = APIRouter()

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


# --- 1. ตรวจสอบ Username ซ้ำ (Case-Insensitive ทั่วทั้งระบบ) ---
@router.get("/doctors/check-username")
def check_username_global(
    username: str = Query(...),
    org_code: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> Dict[str, object]:
    username_clean = username.strip().lower()

    # ตรวจสอบในตารางแอดมิน
    if db.query(models.Admin).filter(func.lower(models.Admin.username) == username_clean).first():
        return {"is_available": False, "detail": "Username นี้ถูกใช้งานแล้วในระบบผู้ดูแลระบบ (Admin)"}

    # ตรวจสอบในตารางแพทย์
    if db.query(models.Doctors).filter(func.lower(models.Doctors.username) == username_clean).first():
        return {"is_available": False, "detail": "Username นี้ถูกใช้งานแล้วในระบบบัญชีแพทย์ (Doctors)"}

    return {"is_available": True, "detail": "Username นี้สามารถใช้งานได้"}


# --- 2. API ลงทะเบียนผู้ดูแลระบบ (Case-Insensitive) ---
@router.post("/register")
def register_admin(payload: schemas.AdminCreate, db: Session = Depends(get_db)) -> Dict[str, str]:
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

    hashed_pwd = bcrypt_sha256.hash(payload.password)

    new_admin = models.Admin(
        org_code=payload.org_code,
        citizen_id=payload.citizen_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        username=admin_username,  # บันทึกตามที่ส่งมา แต่เวลาค้นหาจะใช้ lower()
        password_hash=hashed_pwd
    )

    db.add(new_admin)
    db.commit()
    
    return {"message": "ลงทะเบียนผู้ดูแลระบบสำเร็จ!"}


# --- 3. ดึงรายชื่อแพทย์ทั้งหมด ---
@router.get("/doctors")
def get_doctors(org_code: Optional[str] = Query(None), db: Session = Depends(get_db)) -> Dict[str, List[Dict[str, str]]]:
    query = db.query(models.Doctors)
    if org_code:
        query = query.filter(models.Doctors.org_code == org_code)
        
    doctors = query.all()
    result: List[Dict[str, str]] = []
    for doc in doctors:
        result.append({
            "doctor_id": str(doc.id), 
            "org_code": doc.org_code,
            "first_name": doc.first_name,
            "last_name": doc.last_name,
            "username": doc.username,
            "email": doc.email
        })
    return {"doctors": result}


# --- 4. API เพิ่มแพทย์ + ส่งอีเมลคำเชิญไปยังหน้าเว็บใหม่ ---
@router.post("/doctors")
def add_doctor(payload: schemas.DoctorCreate, db: Session = Depends(get_db)) -> Dict[str, str]:
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
        raise HTTPException(status_code=400, detail="Username หรือ อีเมลนี้ ถูกใช้งานโดยแพทย์ท่านอื่นในระบบแล้ว")

    admin_exists = db.query(models.Admin).filter(
        or_(
            func.lower(models.Admin.username) == username_lower,
            func.lower(models.Admin.email) == email_lower
        )
    ).first()
    if admin_exists:
        raise HTTPException(status_code=400, detail="Username หรือ อีเมลนี้ ซ้ำกับระบบผู้ดูแลระบบ ไม่สามารถใช้งานได้")
    
    try:
        redirect_to_url = "https://dietai-admin.vercel.app/set-password" 
        
        supabase.auth.admin.invite_user_by_email(
            email_clean,
            options={
                "redirectTo": redirect_to_url,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"เกิดข้อผิดพลาดในการส่งอีเมลคำเชิญผ่าน Supabase: {str(e)}")

    new_doctor = models.Doctors(
        org_code=payload.org_code,
        first_name=payload.first_name,
        last_name=payload.last_name,
        citizen_id=payload.citizen_id, 
        username=username_clean,
        email=email_clean,
        password_hash="INVITED_BUT_NOT_SET"
    )
    db.add(new_doctor)
    db.commit()
    return {"message": "เพิ่มข้อมูลแพทย์และระบบได้จัดส่งอีเมลเชิญสำหรับตั้งรหัสผ่านเรียบร้อยแล้ว"}


# --- 5. API แก้ไขข้อมูลแพทย์ ---
@router.put("/doctors/{doctor_id}")
def update_doctor(doctor_id: str, payload: DoctorUpdate, db: Session = Depends(get_db)) -> Dict[str, str]:
    doctor = db.query(models.Doctors).filter(models.Doctors.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลแพทย์ในระบบ")

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

    db.commit()
    return {"message": "อัปเดตข้อมูลแพทย์สำเร็จ"}


# --- 6. API ลบแพทย์ ---
@router.delete("/doctors/{doctor_id}")
def delete_doctor(doctor_id: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    doctor = db.query(models.Doctors).filter(models.Doctors.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลแพทย์")
    
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


# --- 7. API ล็อกอินรวม (แก้ไขสมบูรณ์ - เรียงลำดับขั้นตอน Flow ถูกต้อง) ---
@router.post("/login")
def login_staff(payload: LoginReq, db: Session = Depends(get_db)) -> Dict[str, str]:
    input_username: str = payload.username.strip().lower()

    # 1. ตรวจสอบสิทธิ์ฝั่งผู้ดูแลระบบ (Admin) ค้นหาแบบ Case-Insensitive
    admin = db.query(models.Admin).filter(
        func.lower(models.Admin.username) == input_username
    ).first()

    if admin:
        if not bcrypt_sha256.verify(payload.password, admin.password_hash):
            raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านผู้ดูแลระบบไม่ถูกต้อง")
        
        clean_payload_org: str = "".join(filter(str.isdigit, payload.org_code.strip()))
        clean_admin_org: str = "".join(filter(str.isdigit, admin.org_code.strip() if admin.org_code else ""))

        if clean_admin_org != clean_payload_org:
            raise HTTPException(status_code=401, detail="รหัสหน่วยงานไม่ตรงกับสิทธิ์การเข้าใช้งานของผู้ดูแลระบบนี้")
        
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
        
    # 2. ตรวจสอบฝั่งแพทย์ (Doctors) ต่อเนื่อง ค้นหาแบบ Case-Insensitive
    doctor = db.query(models.Doctors).filter(
        or_(
            func.lower(models.Doctors.username) == input_username,
            func.lower(models.Doctors.email) == input_username
        )
    ).first()

    if doctor:
        # เคสที่ 2.1: ตรวจสอบผ่านระบบตาราง DB ภายในหลัก
        if hasattr(doctor, 'password_hash') and doctor.password_hash and doctor.password_hash != "INVITED_BUT_NOT_SET":
            if bcrypt_sha256.verify(payload.password, doctor.password_hash):
                access_token = create_access_token(
                    data={
                        "sub": str(doctor.id), 
                        "role": "doctor",
                        "org_code": doctor.org_code,
                        "first_name": doctor.first_name,
                        "last_name": doctor.last_name
                    }
                )
                return {"access_token": access_token, "token_type": "bearer", "role": "doctor"}
        
        # เคสที่ 2.2: ตรวจสอบสิทธิ์ผ่าน Supabase Auth ตรง ๆ
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
                        "last_name": doctor.last_name
                    }
                )
                return {"access_token": access_token, "token_type": "bearer", "role": "doctor"}
        except Exception:
            pass

    # หากเช็กครบทั้งสองฝั่งแล้วไม่เข้าเงื่อนไขใดเลย
    raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")


# --- 8. API ตรวจสอบความพร้อมใช้งานทั่วไป (แยกฟังก์ชันออกมาให้ถูกต้อง) ---
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