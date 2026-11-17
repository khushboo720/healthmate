"""Registration, login, profile and account/data deletion."""
import shutil
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..config import UPLOAD_DIR
from ..db import get_db, row
from ..security import (check_throttle, clear_failures, create_token, current_user, hash_password,
                        public_user, record_failure, verify_password)

router = APIRouter(prefix="/api", tags=["auth"])
EMAIL_RX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _check_password(p: str) -> str:
    if len(p) < 8 or not any(c.isalpha() for c in p) or not any(c.isdigit() for c in p):
        raise ValueError("Password must be at least 8 characters and include a letter and a number")
    return p


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(pattern=EMAIL_RX, max_length=120)
    password: str = Field(max_length=64)
    age: int | None = Field(default=None, ge=0, le=120)

    _pw = field_validator("password")(_check_password)


class LoginIn(BaseModel):
    email: str = Field(max_length=120)
    password: str = Field(max_length=64)


class ProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    age: int | None = Field(default=None, ge=0, le=120)
    gender: str = Field(default="", max_length=20)
    blood_group: str = Field(default="", max_length=5)
    allergies: str = Field(default="", max_length=500)
    medical_history: str = Field(default="", max_length=1000)
    water_goal_ml: int = Field(default=2500, ge=500, le=6000)
    sleep_goal_h: float = Field(default=8, ge=3, le=12)
    activity_goal_min: int = Field(default=30, ge=5, le=300)


class PasswordIn(BaseModel):
    current_password: str = Field(max_length=64)
    new_password: str = Field(max_length=64)

    _pw = field_validator("new_password")(_check_password)


@router.post("/auth/register", status_code=201)
def register(body: RegisterIn, db: sqlite3.Connection = Depends(get_db)):
    email = body.email.lower()
    if row(db, "SELECT id FROM users WHERE email = ?", (email,)):
        raise HTTPException(409, "An account with this email already exists")
    cur = db.execute(
        "INSERT INTO users (email, name, password_hash, age) VALUES (?,?,?,?)",
        (email, body.name.strip(), hash_password(body.password), body.age))
    db.commit()
    user = row(db, "SELECT * FROM users WHERE id = ?", (cur.lastrowid,))
    return {"token": create_token(user["id"]), "user": public_user(user)}


@router.post("/auth/login")
def login(body: LoginIn, db: sqlite3.Connection = Depends(get_db)):
    email = body.email.lower().strip()
    check_throttle(email)
    user = row(db, "SELECT * FROM users WHERE email = ?", (email,))
    if not user or not verify_password(body.password, user["password_hash"]):
        record_failure(email)
        raise HTTPException(401, "Incorrect email or password")
    clear_failures(email)
    return {"token": create_token(user["id"]), "user": public_user(user)}


@router.get("/auth/me")
def me(user: dict = Depends(current_user)):
    return public_user(user)


@router.put("/auth/profile")
def update_profile(body: ProfileIn, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    db.execute(
        """UPDATE users SET name=?, age=?, gender=?, blood_group=?, allergies=?, medical_history=?,
           water_goal_ml=?, sleep_goal_h=?, activity_goal_min=? WHERE id=?""",
        (body.name.strip(), body.age, body.gender, body.blood_group, body.allergies, body.medical_history,
         body.water_goal_ml, body.sleep_goal_h, body.activity_goal_min, user["id"]))
    db.commit()
    return public_user(row(db, "SELECT * FROM users WHERE id = ?", (user["id"],)))


@router.post("/auth/change-password")
def change_password(body: PasswordIn, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(body.new_password), user["id"]))
    db.commit()
    return {"ok": True}


def _wipe_uploads(user_id: int) -> None:
    shutil.rmtree(UPLOAD_DIR / str(user_id), ignore_errors=True)


@router.delete("/account/data")
def delete_my_data(user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    """Delete all health data but keep the account and profile name/email."""
    uid = user["id"]
    for table in ("lab_results", "medicine_logs", "medicines", "prescriptions", "health_records", "wellness_logs",
                  "appointments", "chat_messages", "reports"):
        db.execute(f"DELETE FROM {table} WHERE user_id = ?", (uid,))  # table names are constants
    db.execute("UPDATE users SET allergies='', medical_history='', blood_group='' WHERE id=?", (uid,))
    db.commit()
    _wipe_uploads(uid)
    return {"ok": True}


@router.delete("/account")
def delete_account(user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    db.execute("DELETE FROM users WHERE id = ?", (user["id"],))  # cascades to all child tables
    db.commit()
    _wipe_uploads(user["id"])
    return {"ok": True}
