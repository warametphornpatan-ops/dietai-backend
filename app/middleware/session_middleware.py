from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.session_manager import validate_session, update_session_activity, get_session
import logging

logger = logging.getLogger(__name__)


class SessionValidationMiddleware(BaseHTTPMiddleware):
    """Middleware ที่ validate session ในทุก request"""
    
    SKIP_PATHS = [
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/favicon.ico",
        "/health",
    ]
    
    async def dispatch(self, request: Request, call_next):
        # Skip public endpoints
        if any(request.url.path.startswith(path) for path in self.SKIP_PATHS):
            return await call_next(request)
        
        # ดึง session_id
        session_id = request.cookies.get("session_id")
        
        # ถ้าไม่มี session ให้ผ่านไป
        if not session_id:
            return await call_next(request)
        
        try:
            # ตรวจสอบ session
            session = get_session(session_id)
            
            if not session or not session.get("is_active"):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Session expired or invalid"}
                )
            
            # ดึง client info
            client_ip = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("User-Agent", "unknown")
            user_id = session.get("user_id")
            
            # Validate session
            is_valid, error_msg = validate_session(
                session_id=session_id,
                user_id=user_id,
                ip_address=client_ip,
                user_agent=user_agent
            )
            
            if not is_valid:
                logger.warning(f"Invalid session for user {user_id}: {error_msg}")
                return JSONResponse(
                    status_code=401,
                    content={"detail": error_msg or "Invalid session"}
                )
            
            # อัพเดต activity
            update_session_activity(session_id)
            
            # เพิ่ม session data ลง request.state
            request.state.session_id = session_id
            request.state.user_id = user_id
            request.state.role = session.get("role", "user")
            
        except Exception as e:
            logger.error(f"Session validation error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
        
        response = await call_next(request)
        return response