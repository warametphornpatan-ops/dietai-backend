# app/routers/meals.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db

router = APIRouter(prefix="/meals", tags=["meals"])


@router.get("/")
def list_meals(db: Session = Depends(get_db)):
    # ตอนนี้ยังไม่ดึงจาก DB เลยส่ง [] ไปก่อน
    return {"meals": []}
