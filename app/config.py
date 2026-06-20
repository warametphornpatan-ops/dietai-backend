# app/config.py
"""
Centralized configuration management for Smart Carb Analyzer
Loads environment variables securely and provides validated configuration
"""

import os
import secrets
from typing import List, Optional
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv

# สั่งให้โหลดค่าตัวแปรจากไฟล์ .env ทันที
load_dotenv()

class Settings(BaseModel):
    """Application settings with validation"""

    # Environment
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Database
    database_url: str

    # Security
    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # API Keys (should be rotated regularly)
    roboflow_api_key: Optional[str] = None
    secret_org_code: str

    # ✅ เพิ่มตรงนี้ — Email (Gmail SMTP)
    gmail_address: str = ""
    gmail_app_password: str = ""

    # CORS
    allowed_origins: List[str] = []

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_period: int = 3600  # per hour

    @classmethod
    @field_validator("secret_key", mode="before")
    def validate_secret_key(cls, v):
        """Ensure secret key is properly set and secure"""
        if not v or v == "your_256_bit_generated_key_here":
            # Generate a secure key if not set
            v = secrets.token_urlsafe(32)
            print(f"⚠️  WARNING: Generated new SECRET_KEY: {v}")
            print("   Add this to your .env file for production!")

        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 256 bits (32 characters)")

        return v

    @classmethod
    @field_validator("database_url")
    def validate_database_url(cls, v):
        """Validate and normalize database URL"""
        if not v:
            raise ValueError("DATABASE_URL is required")

        # Convert mysql:// to mysql+pymysql://
        if v.startswith("mysql://"):
            v = v.replace("mysql://", "mysql+pymysql://", 1)

        # Check for insecure defaults
        if "GeneratedSecurePassword123!" in v:
            print("⚠️  WARNING: Using placeholder database password!")
            print("   Update DATABASE_URL in .env with secure credentials")

        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment.lower() == "development"


def load_settings() -> Settings:
    """Load settings from environment variables"""
    origins_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    allowed_origins = [origin.strip() for origin in origins_raw.split(",")]

    return Settings(
        environment=os.getenv("ENVIRONMENT", "development"),
        debug=os.getenv("DEBUG", "true").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        database_url=os.getenv("DATABASE_URL", ""),
        secret_key=os.getenv("SECRET_KEY", ""),
        roboflow_api_key=os.getenv("ROBOFLOW_API_KEY"),
        secret_org_code=os.getenv("SECRET_ORG_CODE", ""),
        gmail_address=os.getenv("GMAIL_ADDRESS", ""),               # ✅ เพิ่มบรรทัดนี้
        gmail_app_password=os.getenv("GMAIL_APP_PASSWORD", ""),     # ✅ เพิ่มบรรทัดนี้
        allowed_origins=allowed_origins,
        rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "100")),
        rate_limit_period=int(os.getenv("RATE_LIMIT_PERIOD", "3600")),
    )


# Global settings instance
settings = load_settings()