from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from datetime import datetime, timedelta
import logging
import json
from collections import defaultdict
import time
from .config import settings
from typing import Optional

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting with per-user tracking"""

    def __init__(self, app, requests_per_hour: Optional[int] = None):
        super().__init__(app)
        self.requests_per_hour = requests_per_hour or settings.rate_limit_requests
        self.rate_limit_period = settings.rate_limit_period
        self.request_log = defaultdict(list)  # user_id -> [timestamps]

    async def dispatch(self, request: Request, call_next):
        # Get user identifier (IP or user ID from token)
        user_id = request.headers.get("authorization", request.client.host)

        # Clean old requests (older than rate limit period)
        now = datetime.now()
        period_seconds = self.rate_limit_period
        self.request_log[user_id] = [
            ts for ts in self.request_log[user_id]
            if (now - ts).total_seconds() < period_seconds
        ]

        # Check rate limit
        if len(self.request_log[user_id]) >= self.requests_per_hour:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.requests_per_hour} requests per {self.rate_limit_period // 3600} hour(s)."
            )

        # Record request
        self.request_log[user_id].append(now)

        # Log request
        logger.info(
            f"API Request: {request.method} {request.url.path} "
            f"from {request.client.host}",
            extra={"user_id": user_id, "timestamp": now.isoformat()}
        )

        response = await call_next(request)

        # Log response
        logger.info(
            f"API Response: {response.status_code} "
            f"for {request.method} {request.url.path}",
            extra={"duration_ms": (datetime.now() - now).total_seconds() * 1000}
        )

        return response

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Consistent error response format"""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            logger.error(f"Unhandled error: {str(exc)}", exc_info=True)

            # Never expose sensitive error details
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal server error",
                    "message": "An error occurred processing your request",
                    "request_id": request.headers.get("x-request-id", "unknown")
                }
            )