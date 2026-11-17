"""Medicine reminders. The app stores the dosage text the user types (as prescribed); it never suggests doses."""
import json
import sqlite3
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from ..db import get_db, row, rows
from ..security import current_user

router = APIRouter(prefix="/api/medicines", tags=["medicines"])
TIME_RX = r"^([01]\d|2[0-3]):[0-5]\d$"
DATE_RX = r"^\d{4}-\d{2}-\d{2}$"


class MedicineIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    dosage: str = Field(min_length=1, max_length=80, description="As prescribed by your doctor")
    times: list[str] = Field(min_length=1, max_length=6)
    frequency: str = Field(default="daily", pattern=r"^(daily|alternate|weekly)$")
    start_date: str = Field(pattern=DATE_RX)
    end_date: str | None = Field(default=None, pattern=DATE_RX)
    notes: str = Field(default="", max_length=300)
    active: bool = True

    @field_validator("times")
    @classmethod
    def _times(cls, v: list[str]) -> list[str]:
        import re
        for t in v:
            if not re.match(TIME_RX, t):
                raise ValueError("Times must be HH:MM (24 hour)")
        return sorted(set(v))

    @field_validator("start_date", "end_date")
    @classmethod
    def _dates(cls, v):
        if v:
            datetime.strptime(v, "%Y-%m-%d")
        return v


class LogIn(BaseModel):
    medicine_id: int
    scheduled_for: str = Field(pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
    status: str = Field(pattern=r"^(taken|skipped)$")


def _out(m: dict) -> dict:
    m = dict(m)
    m["times"] = json.loads(m["times"])
    m["active"] = bool(m["active"])
    return m


def _occurs(m: dict, day: date) -> bool:
    start = datetime.strptime(m["start_date"], "%Y-%m-%d").date()
    if day < start:
        return False
    if m["end_date"] and day > datetime.strptime(m["end_date"], "%Y-%m-%d").date():
        return False
    delta = (day - start).days
    return {"daily": True, "alternate": delta % 2 == 0, "weekly": delta % 7 == 0}[m["frequency"]]


def schedule_for(db: sqlite3.Connection, user_id: int, day: date, now: datetime | None = None) -> list[dict]:
    """Doses scheduled for `day` with status pending | overdue | taken | skipped."""
    now = now or datetime.now()
    items = []
    for m in rows(db, "SELECT * FROM medicines WHERE user_id=? AND active=1", (user_id,)):
        if not _occurs(m, day):
            continue
        for t in json.loads(m["times"]):
            sched = f"{day.isoformat()} {t}"
            log = row(db, "SELECT status FROM medicine_logs WHERE medicine_id=? AND scheduled_for=?", (m["id"], sched))
            if log:
                status = log["status"]
            else:
                status = "overdue" if datetime.strptime(sched, "%Y-%m-%d %H:%M") < now else "pending"
            items.append({"medicine_id": m["id"], "name": m["name"], "dosage": m["dosage"], "time": t,
                          "scheduled_for": sched, "status": status})
    return sorted(items, key=lambda i: i["scheduled_for"])


@router.get("")
def list_medicines(user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    return [_out(m) for m in rows(db, """SELECT m.*, p.doctor AS prescribed_by, p.prescribed_on FROM medicines m
                                         LEFT JOIN prescriptions p ON p.id = m.prescription_id
                                         WHERE m.user_id=? ORDER BY m.active DESC, m.name""", (user["id"],))]


def _validate_range(b: MedicineIn) -> None:
    if b.end_date and b.end_date < b.start_date:
        raise HTTPException(422, "End date cannot be before start date")


@router.post("", status_code=201)
def create(body: MedicineIn, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    _validate_range(body)
    cur = db.execute(
        "INSERT INTO medicines (user_id,name,dosage,times,frequency,start_date,end_date,notes,active) VALUES (?,?,?,?,?,?,?,?,?)",
        (user["id"], body.name.strip(), body.dosage.strip(), json.dumps(body.times), body.frequency,
         body.start_date, body.end_date, body.notes, int(body.active)))
    db.commit()
    return _out(row(db, "SELECT * FROM medicines WHERE id=?", (cur.lastrowid,)))


@router.put("/{mid}")
def update(mid: int, body: MedicineIn, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    _validate_range(body)
    if not row(db, "SELECT id FROM medicines WHERE id=? AND user_id=?", (mid, user["id"])):
        raise HTTPException(404, "Medicine not found")
    db.execute(
        "UPDATE medicines SET name=?,dosage=?,times=?,frequency=?,start_date=?,end_date=?,notes=?,active=? WHERE id=?",
        (body.name.strip(), body.dosage.strip(), json.dumps(body.times), body.frequency, body.start_date,
         body.end_date, body.notes, int(body.active), mid))
    db.commit()
    return _out(row(db, "SELECT * FROM medicines WHERE id=?", (mid,)))


@router.delete("/{mid}")
def delete(mid: int, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("DELETE FROM medicines WHERE id=? AND user_id=?", (mid, user["id"]))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "Medicine not found")
    return {"ok": True}


@router.get("/schedule")
def schedule(day: str | None = Query(default=None, alias="date", pattern=DATE_RX),
             now: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$"),
             user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    d = datetime.strptime(day, "%Y-%m-%d").date() if day else date.today()
    n = datetime.strptime(now, "%Y-%m-%d %H:%M") if now else None
    return schedule_for(db, user["id"], d, n)


@router.post("/log")
def log_dose(body: LogIn, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    if not row(db, "SELECT id FROM medicines WHERE id=? AND user_id=?", (body.medicine_id, user["id"])):
        raise HTTPException(404, "Medicine not found")
    db.execute(
        """INSERT INTO medicine_logs (user_id, medicine_id, scheduled_for, status) VALUES (?,?,?,?)
           ON CONFLICT(medicine_id, scheduled_for) DO UPDATE SET status=excluded.status, logged_at=CURRENT_TIMESTAMP""",
        (user["id"], body.medicine_id, body.scheduled_for, body.status))
    db.commit()
    return {"ok": True}


@router.get("/history")
def history(limit: int = Query(default=50, ge=1, le=500), user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    return rows(db, """SELECT l.id, l.scheduled_for, l.status, l.logged_at, m.name, m.dosage
                       FROM medicine_logs l JOIN medicines m ON m.id = l.medicine_id
                       WHERE l.user_id=? ORDER BY l.scheduled_for DESC LIMIT ?""", (user["id"], limit))
