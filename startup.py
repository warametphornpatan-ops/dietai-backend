#!/usr/bin/env python3
"""
Smart Carb Analyzer - Production Startup Script
Ensures proper environment loading before application startup
"""

import os
import sys
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Load environment variables FIRST
try:
    from dotenv import load_dotenv
    env_path = current_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print("✅ Environment variables loaded from .env")
    else:
        print("⚠️  No .env file found, using system environment variables")
except ImportError:
    print("⚠️  python-dotenv not installed, using system environment variables")

# Validate critical environment variables
required_vars = ["DATABASE_URL", "SECRET_KEY"]
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
    print("   Please set these in your .env file or environment")
    sys.exit(1)

# Now import and run the application
try:
    from app.main import app
    from app.config import settings

    # แก้ไข: เติมวงเล็บปิดและแยกบรรทัดให้ถูกต้อง
    print("🚀 Starting Smart Carb Analyzer API")
    print(f"   Environment: {settings.environment}")
    print(f"   Debug: {settings.debug}")
    print(f"   Database: {'✅ Configured' if settings.database_url else '❌ Missing'}")
    print(f"   CORS Origins: {', '.join(settings.allowed_origins)}")

    if __name__ == "__main__":
        import uvicorn
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=settings.debug,
            log_level=settings.log_level.lower()
        )

except Exception as e:
    print(f"❌ Failed to start application: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)