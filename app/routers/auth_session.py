"""
app/routers/auth_session.py
Login/Logout ด้วย Session Management (Username-based, Fixed password fields)
"""

from fastapi import APIRouter, HTTPException, Request, Response, status, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import timedelta

from app.database import get_db
from app import models
from app.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.session_manager import (
    create_session,
    revoke_session,
    revoke_all_user_sessions,
    generate_csrf_token,
    get_session,
    get_user_sessions
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ===== Pydantic Models =====

class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    role: str
    csrf_token: str
    message: str


# ===== Login =====

@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    credentials: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login endpoint
    ส่ง username + password เพื่อได้ JWT token + session
    """
    
    # ค้นหา user ตามอรรถวิธี (ลองทั้ง user, doctor, admin)
    user = db.query(models.User).filter(
        models.User.username == credentials.username
    ).first()
    
    role = "user"
    
    if not user:
        # ลองหา doctor
        user = db.query(models.Doctors).filter(
            models.Doctors.username == credentials.username
        ).first()
        role = "doctor"
    
    if not user:
        # ลองหา admin
        user = db.query(models.Admin).filter(
            models.Admin.username == credentials.username
        ).first()
        role = "admin"
    
    # ตรวจสอบ user หาไม่เจอ
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # ✅ ตรวจสอบ password ตามประเภท (User ใช้ 'password', อื่น ใช้ 'password_hash')
    if role == "user":
        user_password = user.password
    else:
        user_password = user.password_hash
    
    if not verify_password(credentials.password, user_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # ดึง user_id ตามประเภท
    if role == "admin":
        user_id = str(user.admin_id)
    elif role == "doctor":
        user_id = str(user.id)
    else:
        user_id = str(user.id)
    
    # สร้าง JWT tokens
    access_token = create_access_token(
        data={"sub": user_id, "role": role}
    )
    
    # refresh token ใช้เวลา 7 วัน
    refresh_token = create_refresh_token(
        data={"sub": user_id, "role": role}
    )
    
    # สร้าง session
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent", "unknown")
    
    session_data = create_session(
        user_id=user_id,
        role=role,
        ip_address=client_ip,
        user_agent=user_agent,
        extra_data={
            "username": credentials.username,
            "name": getattr(user, "name", getattr(user, "first_name", "Unknown"))
        }
    )
    
    session_id = session_data["session_id"]
    
    # สร้าง CSRF token
    csrf_token = generate_csrf_token(session_id)
    
    # สร้าง response
    response = JSONResponse(
        content={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": user_id,
            "role": role,
            "csrf_token": csrf_token,
            "message": f"Welcome {credentials.username}!"
        },
        status_code=status.HTTP_200_OK
    )
    
    # ✅ ส่ง session_id เป็น cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        max_age=30 * 60,  # 30 นาที
        secure=True,  # HTTPS only
        httponly=True,  # ป้องกัน JavaScript access
        samesite="strict"  # CSRF protection
    )
    
    # ✅ ส่ง access_token เป็น cookie (optional)
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=15 * 60,  # 15 นาที
        secure=True,
        httponly=True,
        samesite="strict"
    )
    
    return response


# ===== Logout =====

@router.post("/logout")
async def logout(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Logout endpoint
    ปิด session และ revoke token
    """
    
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session not found"
        )
    
    # ปิด session
    if revoke_session(session_id):
        # สร้าง response ที่ลบ cookies
        response = JSONResponse(
            content={"message": "Logged out successfully"},
            status_code=status.HTTP_200_OK
        )
        
        # ลบ cookies
        response.delete_cookie("session_id", secure=True, httponly=True)
        response.delete_cookie("access_token", secure=True, httponly=True)
        
        return response
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to logout"
        )


# ===== Logout from All Devices =====

@router.post("/logout-all")
async def logout_all(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    ปิด session ทั้งหมดของ user (logout from all devices)
    """
    
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session not found"
        )
    
    # ดึง session data เพื่อหา user_id
    session = get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session"
        )
    
    user_id = session.get("user_id")
    
    # ปิด session ทั้งหมด ยกเว้น session ปัจจุบัน
    count = revoke_all_user_sessions(user_id, except_session_id=session_id)
    
    response = JSONResponse(
        content={
            "message": f"Logged out from {count} other device(s)",
            "devices_logged_out": count
        }
    )
    
    # ลบ cookies ปัจจุบัน
    response.delete_cookie("session_id", secure=True, httponly=True)
    response.delete_cookie("access_token", secure=True, httponly=True)
    
    return response


# ===== Get Active Sessions =====

@router.get("/sessions")
async def get_active_sessions(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    ดูรายการ session ทั้งหมดของ user ปัจจุบัน
    """
    
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    current_session = get_session(session_id)
    if not current_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session"
        )
    
    user_id = current_session.get("user_id")
    all_sessions = get_user_sessions(user_id)
    
    return {
        "current_session_id": session_id,
        "total_sessions": len(all_sessions),
        "sessions": [
            {
                "session_id": s.get("session_id"),
                "ip_address": s.get("ip_address"),
                "user_agent": s.get("user_agent"),
                "created_at": s.get("created_at"),
                "last_activity": s.get("last_activity"),
                "is_current": s.get("session_id") == session_id
            }
            for s in all_sessions
        ]
    }