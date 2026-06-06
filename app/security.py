from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import unquote
import jwt
import uuid  # 🌟 เพิ่มเข้ามาเพื่อใช้สร้าง jti
from passlib.context import CryptContext

from app.database import get_db
from app import models
from app.models import TokenBlacklist
from .config import settings

# Security Configuration
SECRET_KEY = settings.secret_key
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = settings.refresh_token_expire_days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

# Password hashing
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# JWT Token generation
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    # 🌟 เพิ่ม jti (JWT ID) เพื่อให้ระบบ Blacklist ทำงานได้
    to_encode.update({"exp": expire, "type": "access", "jti": str(uuid.uuid4())})
    
    # 🌟 ถ้าไม่ได้ส่ง role มา ให้ถือว่าเป็น user ปกติ
    if "role" not in to_encode:
        to_encode["role"] = "user"
        
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "type": "refresh", "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def extract_user_id(payload: dict) -> Optional[str]:
    candidate_keys = ["user_id", "sub", "id", "userId", "uid"]
    for key in candidate_keys:
        value = payload.get(key)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None

# Token verification
# 🌟 เปลี่ยนให้ return payload ทั้งก้อน เพื่อเอาไปดึง Role ต่อได้
def verify_token(token: str, token_type: str = "access", db: Session = Depends(get_db)) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        user_id = extract_user_id(payload)

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="ไม่พบ user_id ใน token"
            )

        jti = payload.get("jti")
        if jti:
            blacklisted = db.query(TokenBlacklist).filter(
                TokenBlacklist.jti == jti
            ).first()
            if blacklisted:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked"
                )

        return payload  # 🌟 คืนค่า payload แทนที่จะคืนแค่ user_id

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

# Dependency for current user
async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
):
    token = None

    if credentials and credentials.credentials:
        token = credentials.credentials.strip()

    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "", 1).strip()

    if not token:
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            token = unquote(cookie_token).strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    # 🌟 ดึงข้อมูลจาก Token
    payload = verify_token(token, "access", db)
    user_id = extract_user_id(payload)
    role = payload.get("role", "user")  # ดึง role ออกมา ถ้าไม่มีให้เป็น user

    # 🌟 ค้นหาตารางตาม Role
    if role == "admin":
        user = db.query(models.Admin).filter(models.Admin.admin_id == user_id).first()
    elif role == "doctor":
        user = db.query(models.Doctors).filter(models.Doctors.id == user_id).first()
    else:
        user = db.query(models.User).filter(models.User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # เราสามารถแนบ role ไปกับ object user ได้เผื่อต้องการใช้ใน API
    user.current_role = role 

    return user

def revoke_token(jti: str, expires_at: datetime, db: Session = Depends(get_db)):
    blacklist_entry = TokenBlacklist(jti=jti, expires_at=expires_at)
    db.add(blacklist_entry)
    db.commit()