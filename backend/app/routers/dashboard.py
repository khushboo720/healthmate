"""Dashboard aggregate endpoint."""
import sqlite3
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query

from .. import ai
from ..db import get_db, row, rows
from ..security import current_user
from .medicines import schedule_for
from .wellness import last_days

router = APIRouter(prefix="/api", tags=["dashboard"])

METRICS = ("weight_kg", "height_cm", "systolic", "diastolic", "glucose_mgdl", "temperature_c")


def latest_metrics(db, uid: int) -> dict:
    out = {}
    for col in METRICS:
        r = row(db, f"SELECT {col} AS v, recorded_at FROM health_records WHERE user_id=? AND {col} IS NOT NULL ORDER BY recorded_at DESC, id DESC LIMIT 1", (uid,))  # col from constant tuple
        out[col] = r
    return out


@router.get("/status")
def app_status():
    return ai.status()


@router.get("/dashboard")
def dashboard(now: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$"),
              user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    n = datetime.strptime(now, "%Y-%m-%d %H:%M") if now else datetime.now()
    uid = user["id"]
    today = n.date()
    now_s = n.strftime("%Y-%m-%d %H:%M")

    schedule = schedule_for(db, uid, today, n)
    upcoming = rows(db, "SELECT * FROM appointments WHERE user_id=? AND status='upcoming' AND scheduled_at>=? ORDER BY scheduled_at LIMIT 5", (uid, now_s))
    n_upcoming = row(db, "SELECT COUNT(*) c FROM appointments WHERE user_id=? AND status='upcoming' AND scheduled_at>=?", (uid, now_s))["c"]
    week = last_days(db, user, 7)
    series = rows(db, "SELECT recorded_at, weight_kg, systolic, diastolic, glucose_mgdl, temperature_c FROM health_records "
                      "WHERE user_id=? ORDER BY recorded_at DESC, id DESC LIMIT 12", (uid,))[::-1]

    notifications = []
    for s in schedule:
        if s["status"] == "overdue":
            notifications.append({"type": "medicine", "title": f"Overdue: {s['name']}", "detail": f"Scheduled at {s['time']}"})
        elif s["status"] == "pending":
            due = datetime.strptime(s["scheduled_for"], "%Y-%m-%d %H:%M")
            if due - n <= timedelta(minutes=60):
                notifications.append({"type": "medicine", "title": f"Upcoming: {s['name']}", "detail": f"At {s['time']}"})
    for a in upcoming:
        if datetime.strptime(a["scheduled_at"], "%Y-%m-%d %H:%M") - n <= timedelta(hours=24):
            notifications.append({"type": "appointment", "title": f"Appointment with {a['doctor']}", "detail": a["scheduled_at"]})

    return {
        "user": {"name": user["name"]},
        "kpis": {
            "health_records": row(db, "SELECT COUNT(*) c FROM health_records WHERE user_id=?", (uid,))["c"],
            "active_medicines": row(db, "SELECT COUNT(*) c FROM medicines WHERE user_id=? AND active=1 AND (end_date IS NULL OR end_date>=?)", (uid, today.isoformat()))["c"],
            "upcoming_appointments": n_upcoming,
            "wellness_progress": week[-1]["progress"],
        },
        "schedule": schedule,
        "latest": latest_metrics(db, uid),
        "series": series,
        "wellness_week": week,
        "appointments": upcoming[:3],
        "notifications": notifications,
        "ai": ai.status(),
    }
