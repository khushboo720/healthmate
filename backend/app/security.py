"""Password hashing (bcrypt), JWT tokens and the current-user dependency."""
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import JWT_ALGORITHM, JWT_EXPIRE_HOURS, JWT_SECRET
from .db import get_db, row

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    return jwt.encode({"sub": str(user_id), "exp": exp}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorized
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized
    user = row(db, "SELECT * FROM users WHERE id = ?", (user_id,))
    if not user:
        raise unauthorized
    return user


# --- very small in-memory login throttle (per email) ---
_attempts: dict[str, list[float]] = {}
MAX_ATTEMPTS, WINDOW = 8, 300


def check_throttle(key: str) -> None:
    now = time.time()
    recent = [t for t in _attempts.get(key, []) if now - t < WINDOW]
    _attempts[key] = recent
    if len(recent) >= MAX_ATTEMPTS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts. Please wait a few minutes.")


def record_failure(key: str) -> None:
    _attempts.setdefault(key, []).append(time.time())


def clear_failures(key: str) -> None:
    _attempts.pop(key, None)


def public_user(u: dict) -> dict:
    return {k: v for k, v in u.items() if k != "password_hash"}
