# app/database.py
from sqlalchemy import create_engine, event, pool
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Generator
from contextlib import contextmanager
import logging
from .config import settings

logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = settings.database_url.replace("mysql://", "mysql+pymysql://")

# Database engine with production settings
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,

    # Connection pooling
    poolclass=pool.QueuePool,
    pool_size=20,                    # Max connections
    max_overflow=40,                 # Additional connections when pool exhausted
    pool_pre_ping=True,              # Verify connections before use
    pool_recycle=3600,               # Recycle connections after 1 hour

    # Performance
    echo=settings.debug,             # SQL logging in development only
    connect_args={
        "charset": "utf8mb4",        # Proper character encoding
        "read_timeout": 30,          # Connection timeout
        "write_timeout": 30,
        "connect_timeout": 10,
    },
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

Base = declarative_base()

# Connection pool health check
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Enable foreign key constraints"""
    cursor = dbapi_conn.cursor()
    cursor.execute("SET FOREIGN_KEY_CHECKS=1")
    cursor.close()

# Session management with context manager
@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database sessions"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {str(e)}")
        raise
    finally:
        db.close()

# FastAPI dependency
def get_db() -> Generator[Session, None, None]:
    """Database session dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error: {str(e)}")
        raise
    finally:
        db.close()

# Create tables
Base.metadata.create_all(bind=engine)

# Health check function
def check_db_health() -> bool:
    """Verify database connection"""
    try:
        with get_db_context() as db:
            db.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

# ⬇⬇⬇ import models ที่ "ท้ายไฟล์" หลังจากมี Base และ engine แล้ว
from . import models  # ไม่ต้อง import User ตรง ๆ ก็ได้

# ให้ SQLAlchemy สร้างตารางจาก models ทั้งหมด
Base.metadata.create_all(bind=engine)
