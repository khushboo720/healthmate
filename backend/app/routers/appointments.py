"""Doctor appointment management."""
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..db import get_db, row, rows
from ..security import current_user

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


class AppointmentIn(BaseModel):
    doctor: str = Field(min_length=2, max_length=80)
    specialization: str = Field(default="", max_length=60)
    clinic: str = Field(default="", max_length=100)
    scheduled_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
    purpose: str = Field(default="", max_length=200)
    status: str = Field(default="upcoming", pattern=r"^(upcoming|completed|cancelled)$")

    @field_validator("scheduled_at")
    @classmethod
    def _dt(cls, v):
        datetime.strptime(v, "%Y-%m-%d %H:%M")
        return v


@router.get("")
def list_appointments(user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    return rows(db, "SELECT * FROM appointments WHERE user_id=? ORDER BY scheduled_at DESC", (user["id"],))


@router.post("", status_code=201)
def create(body: AppointmentIn, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute(
        "INSERT INTO appointments (user_id, doctor, specialization, clinic, scheduled_at, purpose, status) VALUES (?,?,?,?,?,?,?)",
        (user["id"], body.doctor.strip(), body.specialization, body.clinic, body.scheduled_at, body.purpose, body.status))
    db.commit()
    return row(db, "SELECT * FROM appointments WHERE id=?", (cur.lastrowid,))


@router.put("/{aid}")
def update(aid: int, body: AppointmentIn, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute(
        "UPDATE appointments SET doctor=?, specialization=?, clinic=?, scheduled_at=?, purpose=?, status=? WHERE id=? AND user_id=?",
        (body.doctor.strip(), body.specialization, body.clinic, body.scheduled_at, body.purpose, body.status, aid, user["id"]))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "Appointment not found")
    return row(db, "SELECT * FROM appointments WHERE id=?", (aid,))


@router.delete("/{aid}")
def delete(aid: int, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("DELETE FROM appointments WHERE id=? AND user_id=?", (aid, user["id"]))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "Appointment not found")
    return {"ok": True}
