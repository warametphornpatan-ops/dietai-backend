from datetime import datetime
from typing import Optional, Any
import logging

from fastapi import APIRouter, Depends, HTTPException, Header, status
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import text, func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.config import settings
from app import models

router = APIRouter(tags=["Food Logs"])  # ✅ ลบ prefix="/food" ออก

logger = logging.getLogger(__name__)


class FoodEntryCreate(BaseModel):
    food_name: str
    calories: int
    carbs: int
    protein: int = 0
    fat: int = 0
    image_url: Optional[str] = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ไม่พบ Authorization header",
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="รูปแบบ Authorization ไม่ถูกต้อง",
        )

    return parts[1]


def extract_user_id_from_payload(payload: dict) -> str:
    """✅ แก้: คืนค่า UUID (str) แทน int"""
    # 1) ลองหา user_id ก่อน
    user_id = payload.get("user_id")
    if user_id is not None:
        return str(user_id)

    # 2) ถ้าไม่มี ให้ fallback ไปใช้ sub (UUID)
    sub = payload.get("sub")
    if sub is not None:
        return str(sub)

    # 3) เผื่อบางระบบใช้ id
    account_id = payload.get("id")
    if account_id is not None:
        return str(account_id)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="ไม่พบ user_id ใน token",
    )


def get_current_user_id(authorization: Optional[str] = Header(default=None)) -> str:
    """✅ แก้: คืนค่า UUID (str) แทน int"""
    token = get_bearer_token(authorization)

    secret_key = getattr(settings, "secret_key", None)
    algorithm = getattr(settings, "jwt_algorithm", "HS256")

    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="เซิร์ฟเวอร์ยังไม่ได้ตั้งค่า secret_key",
        )

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return extract_user_id_from_payload(payload)
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token ไม่ถูกต้องหรือหมดอายุ",
        )


# ✅ เพิ่ม POST /add endpoint (path จะเป็น /foods/add เมื่อ include ใน main.py)
@router.post("/add")
def create_food_log(
    data: FoodEntryCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """บันทึกอาหารใหม่ที่ผู้ใช้กินเข้าไป"""
    try:
        logger.info(f"📤 Creating food log for user {user_id}")
        logger.info(f"📋 Data: {data.dict()}")

        # ✅ ตรวจสอบข้อมูล
        if data.calories < 0 or data.carbs < 0 or data.protein < 0 or data.fat < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ค่าสารอาหารต้องไม่เป็นลบ"
            )

        if not data.food_name or len(data.food_name.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ชื่ออาหารต้องไม่ว่าง"
            )

        # ✅ บันทึกลง database ด้วย SQLAlchemy
        new_log = models.FoodLog(
            user_id=user_id,
            food_name=data.food_name.strip(),
            calories=data.calories,
            carbs=data.carbs,
            protein=data.protein,
            fat=data.fat,
            image_url=data.image_url,
            created_at=datetime.now(),
        )

        db.add(new_log)
        db.commit()
        db.refresh(new_log)

        logger.info(f"✅ Food log created: {new_log.id}")

        return {
            "status": "success",
            "message": "บันทึกอาหารสำเร็จ",
            "data": {
                "id": str(new_log.id),
                "food_name": new_log.food_name,
                "calories": new_log.calories,
                "carbs": new_log.carbs,
                "protein": new_log.protein,
                "fat": new_log.fat,
                "created_at": new_log.created_at.isoformat() if new_log.created_at else None,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Create food log error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"บันทึกอาหารไม่สำเร็จ: {str(e)}"
        )


# ✅ แก้: endpoint path เป็น /foods/summary (ลบ /food prefix)
@router.get("/summary")
def get_food_summary(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """ดึงสรุปอาหารประจำวันนี้"""
    try:
        logger.info(f"📊 Getting food summary for user {user_id}")

        query = text("""
            SELECT
                COALESCE(SUM(calories), 0) AS total_calories,
                COALESCE(SUM(carbs), 0) AS total_carbs,
                COALESCE(SUM(protein), 0) AS total_protein,
                COALESCE(SUM(fat), 0) AS total_fat
            FROM food_logs
            WHERE user_id = :user_id
              AND DATE(created_at) = CURDATE()
        """)

        result = db.execute(query, {"user_id": user_id}).mappings().first()

        summary = {
            "user_id": user_id,
            "date": datetime.now().date().isoformat(),
            "total_calories": int(result["total_calories"]) if result else 0,
            "total_carbs": int(result["total_carbs"]) if result else 0,
            "total_protein": int(result["total_protein"]) if result else 0,
            "total_fat": int(result["total_fat"]) if result else 0,
        }

        logger.info(f"✅ Summary: {summary}")
        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Get food summary error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ดึงข้อมูลสรุปไม่สำเร็จ: {str(e)}",
        )


# ✅ แก้: endpoint path เป็น /foods/my-logs (ลบ /food prefix)
@router.get("/my-logs")
def get_my_food_logs(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """ดึงประวัติอาหารทั้งหมด"""
    try:
        logger.info(f"📝 Getting food logs for user {user_id}")

        query = text("""
            SELECT
                id,
                user_id,
                food_name,
                calories,
                carbs,
                protein,
                fat,
                image_url,
                created_at
            FROM food_logs
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """)

        rows = db.execute(query, {"user_id": user_id}).mappings().all()

        logs = [
            {
                "id": str(row["id"]),
                "user_id": str(row["user_id"]),
                "food_name": row["food_name"],
                "calories": row["calories"],
                "carbs": row["carbs"],
                "protein": row["protein"],
                "fat": row["fat"],
                "image_url": row["image_url"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]

        logger.info(f"✅ Found {len(logs)} food logs")
        return logs

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Get food logs error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ดึงประวัติอาหารไม่สำเร็จ: {str(e)}",
        )


# ✅ เพิ่ม DELETE endpoint (เพิ่มเติม)
@router.delete("/{log_id}")
def delete_food_log(
    log_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """ลบอาหารเฉพาะของตัวเอง"""
    try:
        logger.info(f"🗑️ Deleting food log {log_id} for user {user_id}")

        # ✅ ตรวจสอบว่าเป็นของผู้ใช้คนนี้
        log = db.query(models.FoodLog).filter(
            models.FoodLog.id == log_id,
            models.FoodLog.user_id == user_id
        ).first()

        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ไม่พบอาหารนี้"
            )

        db.delete(log)
        db.commit()

        logger.info(f"✅ Food log deleted: {log_id}")

        return {
            "status": "success",
            "message": "ลบอาหารสำเร็จ"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Delete food log error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ลบอาหารไม่สำเร็จ: {str(e)}"
        )