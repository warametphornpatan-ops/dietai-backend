# ============================================================
# support_router.py  (แก้ให้ตรงกับตารางจริงใน Supabase)
# ============================================================
# ตารางจริงมีคอลัมน์: id, email, name, request_type, description,
#                      status, created_at
# ============================================================

import logging
import traceback
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import Session

# ⚠️ ปรับ import ให้ตรงกับโปรเจกต์ของคุณ
from app.database import Base, get_db

logger = logging.getLogger(__name__)


# ============================================================
# 1. MODEL — เพิ่ม column name
# ============================================================
class SupportRequest(Base):
    __tablename__ = "support_requests"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    email = Column(Text, nullable=False)           # ช่องทางติดต่อกลับ
    name = Column(Text, nullable=True)             # ✅ เพิ่ม ชื่อ-นามสกุล
    request_type = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Text, default="pending")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


# ============================================================
# 2. SCHEMAS — เพิ่ม name field
# ============================================================
class RequestTypeEnum(str, Enum):
    forgot_username = "forgot_username"
    forgot_password = "forgot_password"
    other = "other"


class SupportRequestCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)   # ✅ เพิ่ม
    request_type: RequestTypeEnum = RequestTypeEnum.other
    description: str = Field(..., min_length=1, max_length=2000)


class SupportRequestResponse(BaseModel):
    success: bool
    message: str
    request_id: int


# ============================================================
# 3. ROUTER
# ============================================================
router = APIRouter(prefix="/support-requests", tags=["Support"])


@router.post("", response_model=SupportRequestResponse)
@router.post("/", response_model=SupportRequestResponse)
def create_support_request(
    payload: SupportRequestCreate,
    db: Session = Depends(get_db),
):
    """รับคำร้องแจ้งปัญหาจากหน้า Login (public — ไม่ต้อง auth)"""
    contact = payload.email.strip()
    name = payload.name.strip()                    # ✅ รับ name
    description = payload.description.strip()

    if not contact or not name or not description:
        raise HTTPException(
            status_code=400,
            detail="กรุณากรอกข้อมูลติดต่อกลับ ชื่อ-นามสกุล และรายละเอียดให้ครบถ้วน",
        )

    try:
        new_request = SupportRequest(
            email=contact,
            name=name,                             # ✅ บันทึก name
            request_type=payload.request_type.value,
            description=description,
            status="pending",
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

    except Exception as e:
        db.rollback()
        logger.error(f"❌ บันทึก support request ไม่สำเร็จ: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"ไม่สามารถบันทึกคำร้องได้: {str(e)}",
        )