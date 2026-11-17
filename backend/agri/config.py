"""Settings, read once from the environment (see .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DATA_DIR = Path(__file__).resolve().parent / "data"
MODELS_DIR = BACKEND_DIR / "models"
APP_DATA_DIR = Path(os.getenv("AGRI_DATA_DIR", BACKEND_DIR / "app_data"))


class Config:
    JWT_SECRET = os.getenv("JWT_SECRET", "")
    TOKEN_DAYS = int(os.getenv("TOKEN_DAYS", "30"))

    # mongo  = a MongoDB server (MONGO_URI)
    # local  = no server needed; data is kept in app_data/local_db.json
    # memory = nothing is saved (used by the tests)
    DB_MODE = os.getenv("AGRI_DB", "local").lower()
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB = os.getenv("MONGO_DB", "agriexpert")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip()
    DATA_GOV_API_KEY = os.getenv("DATA_GOV_API_KEY", "").strip()

    # live = ask Open-Meteo for the forecast; offline = never call out, use rainfall normals
    WEATHER_MODE = os.getenv("WEATHER_MODE", "live").lower()

    PORT = int(os.getenv("PORT", "5050"))
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "12"))
    FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"
