# ============================================================
# support_router.py
# ============================================================
# Public endpoint สำหรับรับคำร้อง "แจ้งปัญหาการเข้าสู่ระบบ"
# จากหน้า Login (ไม่ต้อง login ก็ส่งได้)
#
# วิธีติดตั้ง:
#   1. วางไฟล์นี้ใน app/routers/support_router.py
#   2. ใน main.py เพิ่ม:
#        from app.routers import support_router
#        app.include_router(support_router.router)
# ============================================================

from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import Session

# ⚠️ ปรับ import ให้ตรงกับโปรเจกต์ของคุณ
from app.database import Base, get_db


# ============================================================
# 1. MODEL (ตาราง support_requests)
# ============================================================
class SupportRequest(Base):
    __tablename__ = "support_requests"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False)          # ช่องทางติดต่อกลับ (เบอร์/อีเมล)
    request_type = Column(String(50), nullable=False)    # forgot_username / forgot_password / other
    description = Column(Text, nullable=False)           # รายละเอียด + ชื่อจริง
    org_code = Column(String(20), nullable=True)         # (option) ถ้าระบุหน่วยงาน
    is_resolved = Column(Boolean, default=False)         # แอดมินกดแก้ไขแล้วหรือยัง
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# 2. SCHEMAS (Pydantic)
# ============================================================
class RequestTypeEnum(str, Enum):
    forgot_username = "forgot_username"
    forgot_password = "forgot_password"
    other = "other"


class SupportRequestCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=255, description="เบอร์โทรหรืออีเมลติดต่อกลับ")
    request_type: RequestTypeEnum = RequestTypeEnum.other
    description: str = Field(..., min_length=1, max_length=2000)
    org_code: Optional[str] = Field(None, max_length=20)


class SupportRequestResponse(BaseModel):
    success: bool
    message: str
    request_id: int


# ============================================================
# 3. ROUTER
# ============================================================
router = APIRouter(prefix="/support-requests", tags=["Support"])


@router.post("", response_model=SupportRequestResponse)
@router.post("/", response_model=SupportRequestResponse)  # รองรับทั้งมี/ไม่มี slash
def create_support_request(
    payload: SupportRequestCreate,
    db: Session = Depends(get_db),
):
    """
    รับคำร้องแจ้งปัญหาจากหน้า Login (public — ไม่ต้อง auth)
    """
    contact = payload.email.strip()
    description = payload.description.strip()

    if not contact or not description:
        raise HTTPException(
            status_code=400,
            detail="กรุณากรอกข้อมูลติดต่อกลับและรายละเอียดให้ครบถ้วน",
        )

    new_request = SupportRequest(
        email=contact,
        request_type=payload.request_type.value,
        description=description,
        org_code=payload.org_code.strip() if payload.org_code else None,
        is_resolved=False,
        created_at=datetime.utcnow(),
    )

    db.add(new_request)
    db.commit()
    db.refresh(new_request)

    return SupportRequestResponse(
        success=True,
        message="ส่งคำร้องสำเร็จ เจ้าหน้าที่จะติดต่อกลับโดยเร็วที่สุด",
        request_id=new_request.id,
    )