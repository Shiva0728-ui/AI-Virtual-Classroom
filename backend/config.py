"""
Configuration for AI Virtual Classroom
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (parent of backend/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

# Database
if os.getenv("DATABASE_URL") and os.getenv("DATABASE_URL").startswith("postgres"):
    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
elif os.getenv("VERCEL") == "1" or os.getenv("VERCEL_URL") or os.getenv("VERCEL_REGION"):
    DATABASE_URL = "sqlite:////tmp/ai_classroom.db"
else:
    default_db = "sqlite:///./ai_classroom.db"
    DATABASE_URL = os.getenv("DATABASE_URL", default_db)

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# JWT
SECRET_KEY = os.getenv("SECRET_KEY", "ai-virtual-classroom-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# App
APP_NAME = "AI Virtual Classroom"
APP_VERSION = "1.0.0"
