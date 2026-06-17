import json
import uuid
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from redis import Redis
import hashlib

# ===== Redis Configuration =====
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

try:
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    redis_client.ping()
    print("✅ Connected to Redis successfully")
except Exception as e:
    print(f"⚠️ Redis connection error: {e}")
    redis_client = None

SESSION_EXPIRY_MINUTES = 30
SESSION_PREFIX = "session:"
CSRF_PREFIX = "csrf:"


# ===== Session Creation =====

def create_session(
    user_id: str,
    role: str,
    ip_address: str,
    user_agent: str,
    extra_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """สร้าง session ใหม่"""
    if redis_client is None:
        raise Exception("Redis service not available")
    
    session_id = str(uuid.uuid4())
    
    session_data = {
        "session_id": session_id,
        "user_id": user_id,
        "role": role,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_activity": datetime.now(timezone.utc).isoformat(),
        "is_active": True,
        **(extra_data or {})
    }
    
    redis_client.setex(
        f"{SESSION_PREFIX}{session_id}",
        SESSION_EXPIRY_MINUTES * 60,
        json.dumps(session_data)
    )
    
    return session_data


# ===== Session Retrieval =====

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """ดึง session data"""
    if redis_client is None:
        return None
    
    data = redis_client.get(f"{SESSION_PREFIX}{session_id}")
    return json.loads(data) if data else None


def get_user_sessions(user_id: str) -> list:
    """ดึง session ทั้งหมดของ user"""
    if redis_client is None:
        return []
    
    sessions = []
    for key in redis_client.scan_iter(f"{SESSION_PREFIX}*"):
        data = redis_client.get(key)
        if data:
            session_data = json.loads(data)
            if session_data.get("user_id") == user_id:
                sessions.append(session_data)
    return sessions


# ===== Session Update =====

def update_session_activity(session_id: str) -> bool:
    """อัพเดต last_activity"""
    if redis_client is None:
        return False
    
    session = get_session(session_id)
    if not session:
        return False
    
    session["last_activity"] = datetime.now(timezone.utc).isoformat()
    redis_client.setex(
        f"{SESSION_PREFIX}{session_id}",
        SESSION_EXPIRY_MINUTES * 60,
        json.dumps(session)
    )
    return True


def validate_session(
    session_id: str,
    user_id: str,
    ip_address: str,
    user_agent: str
) -> tuple:
    """ตรวจสอบ session ว่า valid หรือไม่"""
    if redis_client is None:
        return False, "Redis service not available"
    
    session = get_session(session_id)
    
    if not session:
        return False, "Session not found or expired"
    
    if not session.get("is_active"):
        return False, "Session has been terminated"
    
    if session.get("user_id") != user_id:
        return False, "User ID mismatch"
    
    return True, None


# ===== Session Termination =====

def revoke_session(session_id: str) -> bool:
    """ปิด session เดียว"""
    if redis_client is None:
        return False
    
    session = get_session(session_id)
    if session:
        session["is_active"] = False
        redis_client.setex(
            f"{SESSION_PREFIX}{session_id}",
            60,
            json.dumps(session)
        )
        return True
    return False


def revoke_all_user_sessions(user_id: str, except_session_id: Optional[str] = None) -> int:
    """ปิด session ทั้งหมดของ user"""
    if redis_client is None:
        return 0
    
    sessions = get_user_sessions(user_id)
    count = 0
    
    for session in sessions:
        session_id = session.get("session_id")
        if except_session_id and session_id == except_session_id:
            continue
        if revoke_session(session_id):
            count += 1
    
    return count


# ===== CSRF Token =====

def generate_csrf_token(session_id: str) -> str:
    """สร้าง CSRF token"""
    if redis_client is None:
        raise Exception("Redis service not available")
    
    csrf_token = hashlib.sha256(
        (session_id + str(uuid.uuid4())).encode()
    ).hexdigest()
    
    redis_client.setex(
        f"{CSRF_PREFIX}{csrf_token}",
        60 * 60,
        session_id
    )
    
    return csrf_token


def verify_csrf_token(csrf_token: str, session_id: str) -> bool:
    """ตรวจสอบ CSRF token"""
    if redis_client is None:
        return False
    
    stored_session_id = redis_client.get(f"{CSRF_PREFIX}{csrf_token}")
    if not stored_session_id:
        return False
    return stored_session_id == session_id