# workflowos/backend/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if exists
load_dotenv(BASE_DIR / ".." / ".env")

# Database URL
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")

# AI Provider configuration (optional)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
