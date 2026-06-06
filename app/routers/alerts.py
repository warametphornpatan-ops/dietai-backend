# app/routers/alerts.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.get("/")
def list_alerts(db: Session = Depends(get_db)):
    return {"alerts": []}
