"""Application configuration. All secrets come from environment variables / .env."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "healthmate.db"))

# --- AI provider (Google Gemini). Key stays on the server only. ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "30"))

# --- Auth ---
def _jwt_secret() -> str:
    env = os.getenv("JWT_SECRET", "").strip()
    if env:
        return env
    # No secret configured: generate one once and persist it locally (dev convenience).
    f = DATA_DIR / ".jwt_secret"
    if not f.exists():
        f.write_text(secrets.token_urlsafe(48))
    return f.read_text().strip()


JWT_SECRET = _jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "8"))

SEED_DEMO = os.getenv("SEED_DEMO", "true").lower() == "true"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

DEMO_EMAIL = "demo@healthmate.ai"
DEMO_PASSWORD = "Demo@1234"
