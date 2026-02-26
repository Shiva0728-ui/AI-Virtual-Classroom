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
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ai_classroom.db")

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
