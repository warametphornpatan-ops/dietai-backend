from datetime import datetime
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Header, status
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.config import settings

router = APIRouter(prefix="/food", tags=["Food Logs"])


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


def extract_user_id_from_payload(payload: dict) -> int:
    # 1) ลองหา user_id ก่อน
    user_id = payload.get("user_id")
    if user_id is not None:
        try:
            return int(user_id)
        except (TypeError, ValueError):
            pass

    # 2) ถ้าไม่มี ให้ fallback ไปใช้ sub
    sub = payload.get("sub")
    if sub is not None:
        try:
            return int(sub)
        except (TypeError, ValueError):
            pass

    # 3) เผื่อบางระบบใช้ id
    account_id = payload.get("id")
    if account_id is not None:
        try:
            return int(account_id)
        except (TypeError, ValueError):
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="ไม่พบ user_id ใน token",
    )


def get_current_user_id(authorization: Optional[str] = Header(default=None)) -> int:
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
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token ไม่ถูกต้องหรือหมดอายุ",
        )


@router.get("/summary")
def get_food_summary(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    try:
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

        return {
            "total_calories": int(result["total_calories"]) if result else 0,
            "total_carbs": int(result["total_carbs"]) if result else 0,
            "total_protein": int(result["total_protein"]) if result else 0,
            "total_fat": int(result["total_fat"]) if result else 0,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ดึงข้อมูลสรุปไม่สำเร็จ: {str(e)}",
        )


@router.get("/my-logs")
def get_my_food_logs(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    try:
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

        return [
            {
                "id": row["id"],
                "user_id": row["user_id"],
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ดึงประวัติอาหารไม่สำเร็จ: {str(e)}",
        )