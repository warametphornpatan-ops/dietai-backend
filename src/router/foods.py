from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import FoodItem

router = APIRouter(prefix="/foods", tags=["Foods"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/")
def get_foods(category: str = Query(None), db: Session = Depends(get_db)):
    query = db.query(FoodItem)
    if category:
        query = query.filter(FoodItem.category == category.upper())
    foods = query.order_by(FoodItem.category).all()
    return {
        "count": len(foods),
        "items": foods
    }
