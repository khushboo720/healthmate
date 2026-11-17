"""Prescription upload -> user-reviewed medicine reminders.

The app COPIES what is written on the prescription (rule-based parser, runs locally, no AI).
It never suggests, calculates or changes doses. Every item must be reviewed and confirmed by the user.
"""
import json
import sqlite3
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from ..db import get_db, row, rows
from ..files import extract_text, read_upload, remove_file, store_file
from ..parsing import parse_prescription
from ..security import current_user
from .medicines import MedicineIn, _out, _validate_range

router = APIRouter(prefix="/api/prescriptions", tags=["prescriptions"])
DATE_RX = r"^\d{4}-\d{2}-\d{2}$"
REVIEW_NOTE = ("Captured automatically from your prescription. Check every medicine, dose, time and duration against the original "
               "before saving. HealthMate AI copies what is written; it never suggests or changes doses.")


def _start_date(prescribed_on: str) -> str:
    """Reminders start on the prescription date if it is recent, otherwise today."""
    p = date.fromisoformat(prescribed_on)
    return prescribed_on if (date.today() - p).days <= 7 and p <= date.today() else date.today().isoformat()


def _drafts(items: list[dict], start: str) -> list[dict]:
    out = []
    for it in items:
        end = None
        if it["duration_days"]:
            end = (date.fromisoformat(start) + timedelta(days=it["duration_days"] - 1)).isoformat()
        out.append({"name": it["name"], "dosage": it["dosage"], "times": it["times"], "frequency": it["frequency"],
                    "start_date": start, "end_date": end, "notes": it["instructions"], "raw": it["raw"],
                    "as_needed": it["as_needed"], "needs_review": it["needs_review"],
                    "include": bool(it["times"]) and not it["as_needed"]})
    return out


def _get(db, pid: int, uid: int) -> dict:
    p = row(db, "SELECT * FROM prescriptions WHERE id=? AND user_id=?", (pid, uid))
    if not p:
        raise HTTPException(404, "Prescription not found")
    return p


@router.post("", status_code=201)
def upload(file: UploadFile | None = File(default=None), text: str = Form(default="", max_length=20000),
           user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    """Upload a prescription (PDF/TXT) or paste its text. Returns draft reminders for review; nothing is scheduled yet."""
    if file is None and not text.strip():
        raise HTTPException(422, "Upload a prescription file or paste its text")
    name, stored, raw = "", "", text
    if file is not None:
        name, data = read_upload(file)
        raw = extract_text(data, name)
        stored = str(store_file(user["id"], name, data))
    parsed = parse_prescription(raw)
    prescribed_on = parsed["date"] or date.today().isoformat()
    cur = db.execute("INSERT INTO prescriptions (user_id, doctor, prescribed_on, filename, stored_path, extracted_text) VALUES (?,?,?,?,?,?)",
                     (user["id"], parsed["doctor"] or "", prescribed_on, name, stored, raw))
    db.commit()
    return {"id": cur.lastrowid, "doctor": parsed["doctor"] or "", "prescribed_on": prescribed_on, "date_detected": bool(parsed["date"]),
            "filename": name, "items": _drafts(parsed["items"], _start_date(prescribed_on)), "text": raw[:4000], "review_note": REVIEW_NOTE}


class ConfirmIn(BaseModel):
    doctor: str = Field(default="", max_length=80)
    prescribed_on: str = Field(pattern=DATE_RX)
    notes: str = Field(default="", max_length=300)
    items: list[MedicineIn] = Field(min_length=1, max_length=20)


@router.post("/{pid}/reminders", status_code=201)
def create_reminders(pid: int, body: ConfirmIn, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    _get(db, pid, user["id"])
    if date.fromisoformat(body.prescribed_on) > date.today():
        raise HTTPException(422, "Prescription date cannot be in the future")
    for it in body.items:
        _validate_range(it)
    db.execute("UPDATE prescriptions SET doctor=?, prescribed_on=?, notes=? WHERE id=?",
               (body.doctor.strip(), body.prescribed_on, body.notes, pid))
    ids = []
    for it in body.items:
        cur = db.execute(
            "INSERT INTO medicines (user_id,name,dosage,times,frequency,start_date,end_date,notes,active,prescription_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (user["id"], it.name.strip(), it.dosage.strip(), json.dumps(it.times), it.frequency, it.start_date, it.end_date,
             it.notes, int(it.active), pid))
        ids.append(cur.lastrowid)
    db.commit()
    meds = [_out(m) for m in rows(db, f"SELECT * FROM medicines WHERE id IN ({','.join('?' * len(ids))})", ids)]
    return {"created": len(ids), "medicines": meds}


@router.get("")
def list_prescriptions(user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    out = []
    for p in rows(db, "SELECT id, doctor, prescribed_on, notes, filename, created_at FROM prescriptions WHERE user_id=? ORDER BY prescribed_on DESC, id DESC",
                  (user["id"],)):
        meds = rows(db, "SELECT id, name, dosage, times, frequency, start_date, end_date, active FROM medicines WHERE prescription_id=? AND user_id=? ORDER BY name",
                    (p["id"], user["id"]))
        for m in meds:
            m["times"], m["active"] = json.loads(m["times"]), bool(m["active"])
        out.append({**p, "medicines": meds})
    return out


@router.get("/{pid}")
def get_prescription(pid: int, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    p = _get(db, pid, user["id"])
    return {k: p[k] for k in ("id", "doctor", "prescribed_on", "notes", "filename", "created_at")} | {"text": p["extracted_text"]}


@router.delete("/{pid}")
def delete_prescription(pid: int, with_reminders: bool = Query(default=False), user: dict = Depends(current_user),
                        db: sqlite3.Connection = Depends(get_db)):
    p = _get(db, pid, user["id"])
    if with_reminders:
        db.execute("DELETE FROM medicines WHERE prescription_id=? AND user_id=?", (pid, user["id"]))
    else:
        db.execute("UPDATE medicines SET prescription_id=NULL WHERE prescription_id=? AND user_id=?", (pid, user["id"]))
    db.execute("DELETE FROM prescriptions WHERE id=?", (pid,))
    db.commit()
    if p["stored_path"]:
        remove_file(user["id"], p["stored_path"])
    return {"ok": True}
