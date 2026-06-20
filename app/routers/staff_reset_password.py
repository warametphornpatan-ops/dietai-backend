from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from passlib.handlers.bcrypt import bcrypt_sha256
from pydantic import BaseModel, Field

# Import ให้ตรงกับโฟลเดอร์ของแอป
from app.database import get_db
from app.schemas import ResetPassword  # ใช้ Schema เดียวกันกับฝั่ง User ที่เพิ่มฟิลด์ username
from app.models import Doctors, Admin

router = APIRouter()

# 📝 1. สร้าง Pydantic Model สำหรับรับค่าเลขบัตรประชาชนจากหน้าบ้าน
class IdCardCheck(BaseModel):
    id_card: str = Field(..., max_length=13, min_length=13)


# 🔍 2. Endpoint สำหรับตรวจสอบเลขบัตรประชาชนของ Staff (Admin / Doctors)
@router.post("/staff/check-id-card")
def check_staff_idcard(payload: IdCardCheck, db: Session = Depends(get_db)):
    # ดึงมาเฉพาะตัวเลขเพื่อความชัวร์ ป้องกันอักขระแปลกปลอม
    citizen_digits = "".join(ch for ch in payload.id_card if ch.isdigit())
    
    if len(citizen_digits) != 13:
        raise HTTPException(status_code=422, detail="เลขบัตรประชาชนต้องเป็นตัวเลข 13 หลัก")

    # ฟังก์ชันช่วยค้นหาด้วย citizen_id
    def find_by_citizen_id(model_class):
        return db.query(model_class).filter(model_class.citizen_id == citizen_digits).first()

    # ลองค้นหาในตาราง Admin ก่อน
    staff_account = find_by_citizen_id(Admin)
    
    # ถ้าไม่เจอใน Admin ให้ค้นหาในตาราง Doctors ต่อ
    if not staff_account:
        staff_account = find_by_citizen_id(Doctors)

    # ถ้าหาไม่เจอเลยทั้งสองตาราง ให้โยน Error 404
    if not staff_account:
        raise HTTPException(
            status_code=404, 
            detail="ไม่พบเลขบัตรประชาชนนี้ในระบบเจ้าหน้าที่"
        )

    # ส่งชื่อและนามสกุลกลับไปแสดงผลที่หน้าบ้าน
    # (หมายเหตุ: ตรวจสอบชื่อฟิลด์ใน Model ของคุณด้วยนะครับ เช่น first_name / last_name หรือ name)
    return {
        "first_name": getattr(staff_account, "first_name", ""),
        "last_name": getattr(staff_account, "last_name", "")
    }


# 🔐 3. Endpoint รีเซ็ตรหัสผ่านเดิมของคุณ
@router.post("/staff/reset-password")
def reset_password_staff(payload: ResetPassword, db: Session = Depends(get_db)):
    
    # ฟังก์ชันค้นหาที่ใช้ได้ทั้ง Admin และ Doctors
    def search_staff(model_class):
        query = db.query(model_class).filter(
            model_class.username == payload.username.strip()
        )

        if payload.is_email:
            query = query.filter(model_class.email == payload.identifier.strip())
        else:
            citizen_digits = "".join(ch for ch in payload.identifier if ch.isdigit())
            query = query.filter(model_class.citizen_id == citizen_digits)
            
        return query.first()

    # ค้นหาในตาราง Admin 
    account = search_staff(Admin)

    # ถ้าไม่เจอใน Admin ให้หาในตาราง Doctors ต่อ
    if not account:
        account = search_staff(Doctors)

    # ถ้าหาไม่เจอทั้ง 2 ตาราง
    if not account:
        raise HTTPException(
            status_code=404, 
            detail="ไม่พบข้อมูลเจ้าหน้าที่ที่ตรงกับข้อมูลที่ระบุ"
        )

    # เจอแล้ว! ทำการอัปเดตรหัสผ่านใหม่
    account.password_hash = bcrypt_sha256.hash(payload.new_password)
    
    # บันทึกลงฐานข้อมูล
    db.add(account)
    db.commit()

    return {"message": "เปลี่ยนรหัสผ่านเจ้าหน้าที่สำเร็จ"}