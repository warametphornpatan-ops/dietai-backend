from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from app.services.email_service import send_password_reset_notification

# ปรับ path import ให้ตรงกับโครงสร้างโฟลเดอร์ของแอป
from app.database import get_db
from app.schemas import ResetPassword
from app.models import User

router = APIRouter()
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 📝 1. สร้าง Pydantic Model สำหรับรับค่าเลขบัตรประชาชนจากหน้าบ้าน
class IdCardCheck(BaseModel):
    id_card: str = Field(..., max_length=13, min_length=13)


# 🔍 2. Endpoint สำหรับตรวจสอบเลขบัตรประชาชนของ User
@router.post("/users/check-id-card")
def check_user_idcard(payload: IdCardCheck, db: Session = Depends(get_db)):
    # ดึงมาเฉพาะตัวเลขเพื่อความถูกต้อง ป้องกันอักขระแปลกปลอม
    citizen_digits = "".join(ch for ch in payload.id_card if ch.isdigit())
    
    if len(citizen_digits) != 13:
        raise HTTPException(status_code=422, detail="เลขบัตรประชาชนต้องเป็นตัวเลข 13 หลัก")

    # ค้นหาในตาราง User ด้วย citizen_id
    user_account = db.query(User).filter(User.citizen_id == citizen_digits).first()

    # ถ้าหาไม่เจอในตาราง ให้โยน Error 404
    if not user_account:
        raise HTTPException(
            status_code=404, 
            detail="ไม่พบเลขบัตรประชาชนนี้ในระบบผู้ใช้งาน"
        )

    # ส่งชื่อและนามสกุลกลับไปแสดงผลที่หน้าบ้าน
    # (อย่าลืมตรวจสอบชื่อฟิลด์ใน Model User ของคุณด้วยนะครับ เช่น first_name / last_name)
    return {
        "first_name": getattr(user_account, "firstName", ""),
        "last_name": getattr(user_account, "lastName", "")
    }


# 🔐 3. Endpoint รีเซ็ตรหัสผ่านเดิมของคุณ
@router.post("/users/reset-password")
def reset_user_password(payload: ResetPassword, db: Session = Depends(get_db)):
    
    # 1. สร้าง Query ตั้งต้น ค้นหาจาก username (ตัดช่องว่างซ้าย-ขวาให้เรียบร้อย)
    query = db.query(User).filter(
        User.username == payload.username.strip()
    )

    # 2. เช็กว่าผู้ใช้ส่งอีเมลหรือเลขบัตรประชาชนมา
    if payload.is_email:
        # ถ้าเป็นอีเมล ก็ค้นหาจากคอลัมน์ email
        query = query.filter(User.email == payload.identifier.strip())
    else:
        # ถ้าไม่ใช่ ให้ดึงมาเฉพาะตัวเลข แล้วค้นหาจากคอลัมน์ citizen_id
        citizen_digits = "".join(ch for ch in payload.identifier if ch.isdigit())
        query = query.filter(User.citizen_id == citizen_digits)
        
    # ดึงข้อมูลผู้ใช้งานคนแรกที่ตรงเงื่อนไข
    account = query.first()

    # 3. ถ้าหาไม่เจอ ให้โยน Error 404 กลับไปให้หน้าบ้านแจ้งเตือน
    if not account:
        raise HTTPException(
            status_code=404, 
            detail="ไม่พบข้อมูลผู้ใช้ที่ตรงกับข้อมูลที่ระบุ"
        )

    # 4. ถ้าเจอข้อมูล ให้อัปเดตรหัสผ่าน (เข้ารหัสก่อนเซฟลงฐานข้อมูล)
    account.password = pwd.hash(payload.new_password)
    db.commit()

    notify_email = getattr(account, "email", None)
    if notify_email:
        full_name = f"{getattr(account, 'firstName', '')} {getattr(account, 'lastName', '')}".strip()
        send_password_reset_notification(to_email=notify_email, full_name=full_name)

    return {"message": "เปลี่ยนรหัสผ่านผู้ใช้งานสำเร็จ"}