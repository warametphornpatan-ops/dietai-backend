from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text
import jwt
import logging
import os

from app.database import get_db
from .routers import (
    user,
    foods,
    meals,
    alerts,
    food_images,
    user_reset_password,
    staff_reset_password,
    doctor,
    admin,
    food_logs,
    organization,
    support_router,
)
# ✅ เพิ่มบรรทัดนี้
from app.routers.doctor_approval import router as doctor_approval_router

from app.routers.multi_detect import router as detect_router
from .middleware import RateLimitMiddleware, ErrorHandlingMiddleware
from .config import settings

# ===== App =====
app = FastAPI(
    title="Smart Carb Analyzer API",
    version="1.0.0",
    debug=settings.debug,
)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

security = HTTPBearer()

# ===== CORS ✅ สมบูรณ์ =====
allowed_origins = [
    # Development
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",  # Vite dev
    "http://127.0.0.1:5173",
    
    # Production Frontend
    "https://dietai-frontend.vercel.app",
    "https://dietai-frontend-5tcrd7ufw-warametphornpatan-ops-projects.vercel.app",
    "https://dietai-frontend-git-main-warametphornpatan-ops-projects.vercel.app",
    
    # Admin Frontend
    "https://dietai-admin.vercel.app",
]

# ✅ เพิ่ม Environment variable สำหรับ dynamic origins
extra_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
for origin in extra_origins:
    if origin.strip() and origin.strip() not in allowed_origins:
        allowed_origins.append(origin.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # ✅ Allow all configured origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],  # ✅ รวม OPTIONS สำหรับ preflight
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-CSRF-Token",
        "Access-Control-Allow-Origin",
    ],
    max_age=3600,  # ✅ Cache preflight response 1 hour
)

# ✅ Log CORS config ตอน startup
logger.info(f"CORS configured with origins: {allowed_origins}")

#app.add_middleware(RateLimitMiddleware, requests_per_hour=settings.rate_limit_requests)
#app.add_middleware(ErrorHandlingMiddleware)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# ===== Health Check =====
@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """ตรวจสอบสถานะ API และ Database"""
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "message": "API and Database are healthy",
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "version": "1.0.0"
        }, 500


# ===== Routers =====
app.include_router(user.router,                prefix="/user",   tags=["users"])
app.include_router(foods.router,               prefix="/foods",   tags=["foods"])
app.include_router(detect_router)
app.include_router(food_logs.router,           prefix="/foods")
app.include_router(meals.router,               prefix="/meals",   tags=["meals"])
app.include_router(alerts.router,              prefix="/alerts",  tags=["alerts"])
app.include_router(food_images.router)
app.include_router(user_reset_password.router)
app.include_router(staff_reset_password.router)
app.include_router(doctor.router,              prefix="/doctors", tags=["doctor"])
app.include_router(admin.router,               prefix="/admins",  tags=["admin"])
app.include_router(organization.router)
app.include_router(support_router.router)

# ✅ เพิ่มบรรทัดนี้
app.include_router(doctor_approval_router)


# ===== Auth: ดึงโปรไฟล์แอดมินจาก JWT =====
@app.get("/auth/me", tags=["Authentication"])
async def get_current_user_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials

    # 1. ถอดรหัส JWT
    try:
        secret = getattr(settings, "secret_key", getattr(settings, "jwt_secret", "YOUR_SECRET_KEY"))
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        # sub เก็บ admin_id (UUID) ไม่ใช่ username
        user_id = payload.get("sub")
    except Exception as e:
        logger.error(f"Token decode failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ไม่ถูกต้อง หรือหมดอายุแล้ว")

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ไม่พบข้อมูลผู้ใช้ใน Token")

    # 2. ค้นหาใน admins
    # ✅ แก้ไข: ใช้ first_name/last_name ให้ตรงกับ schema ตาราง admins จริง
    result = db.execute(
        text("""
            SELECT admin_id, org_code, first_name, last_name, email, username
            FROM admins
            WHERE admin_id = :uid OR username = :uid
            LIMIT 1
        """),
        {"uid": user_id},
    ).mappings().first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ไม่พบข้อมูลบัญชีแอดมินนี้ในฐานข้อมูลหน่วยงาน",
        )

    # 3. ส่งข้อมูลกลับ
    return {
        "admin_id":   str(result["admin_id"]),
        "org_code":   result["org_code"],
        "first_name": result["first_name"],   # ✅ ตรงกับ AdminResponse schema
        "last_name":  result["last_name"],
        "email":      result["email"],
        "username":   result["username"],
    }

@app.get("/")
def root():
    return {"message": "🚀 Smart Carb Analyzer API Ready"}