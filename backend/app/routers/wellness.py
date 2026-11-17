"""Wellness tracker: hydration, sleep, activity, weekly summary and general suggestions."""
import sqlite3
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .. import ai
from ..db import get_db, row, rows
from ..knowledge import DEMO_WELLNESS_TIPS
from ..safety import DISCLAIMER
from ..security import current_user

router = APIRouter(prefix="/api/wellness", tags=["wellness"])


class WellnessIn(BaseModel):
    water_ml: int = Field(ge=0, le=10000)
    sleep_hours: float = Field(ge=0, le=24)
    activity_min: int = Field(ge=0, le=1440)
    mood: str = Field(default="", max_length=20)


class PrefsIn(BaseModel):
    diet: str = Field(default="no preference", max_length=40)
    goal: str = Field(default="general wellbeing", max_length=60)
    activity_level: str = Field(default="moderate", pattern=r"^(low|moderate|high)$")


def progress(user: dict, log: dict | None) -> int:
    """Average of capped goal ratios (0-100)."""
    if not log:
        return 0
    parts = [min(log["water_ml"] / user["water_goal_ml"], 1), min(log["sleep_hours"] / user["sleep_goal_h"], 1),
             min(log["activity_min"] / user["activity_goal_min"], 1)]
    return round(sum(parts) / 3 * 100)


def last_days(db, user: dict, days: int) -> list[dict]:
    today = date.today()
    start = (today - timedelta(days=days - 1)).isoformat()
    existing = {r["log_date"]: r for r in rows(db, "SELECT * FROM wellness_logs WHERE user_id=? AND log_date>=? ORDER BY log_date", (user["id"], start))}
    out = []
    for i in range(days):
        d = (today - timedelta(days=days - 1 - i)).isoformat()
        r = existing.get(d)
        out.append({"log_date": d, "water_ml": r["water_ml"] if r else 0, "sleep_hours": r["sleep_hours"] if r else 0,
                    "activity_min": r["activity_min"] if r else 0, "mood": r["mood"] if r else "",
                    "progress": progress(user, r), "logged": bool(r)})
    return out


@router.get("")
def get_logs(days: int = Query(default=7, ge=1, le=90), user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    return {"days": last_days(db, user, days),
            "goals": {"water_ml": user["water_goal_ml"], "sleep_h": user["sleep_goal_h"], "activity_min": user["activity_goal_min"]}}


@router.put("/{day}")
def put_log(day: str, body: WellnessIn, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    try:
        date.fromisoformat(day)
    except ValueError:
        raise HTTPException(422, "Date must be YYYY-MM-DD")
    db.execute(
        """INSERT INTO wellness_logs (user_id, log_date, water_ml, sleep_hours, activity_min, mood) VALUES (?,?,?,?,?,?)
           ON CONFLICT(user_id, log_date) DO UPDATE SET water_ml=excluded.water_ml, sleep_hours=excluded.sleep_hours,
           activity_min=excluded.activity_min, mood=excluded.mood""",
        (user["id"], day, body.water_ml, body.sleep_hours, body.activity_min, body.mood))
    db.commit()
    return {"ok": True, "progress": progress(user, row(db, "SELECT * FROM wellness_logs WHERE user_id=? AND log_date=?", (user["id"], day)))}


def weekly_stats(db, user: dict) -> dict:
    days = last_days(db, user, 7)
    logged = [d for d in days if d["logged"]] or []
    n = max(len(logged), 1)
    return {
        "days_logged": len(logged),
        "avg_water_ml": round(sum(d["water_ml"] for d in logged) / n),
        "avg_sleep_h": round(sum(d["sleep_hours"] for d in logged) / n, 1),
        "avg_activity_min": round(sum(d["activity_min"] for d in logged) / n),
        "avg_progress": round(sum(d["progress"] for d in days) / 7),
    }


def demo_weekly_text(s: dict, user: dict) -> str:
    if s["days_logged"] == 0:
        return "No wellness entries this week yet. Log water, sleep and activity daily to see a summary."
    notes = []
    notes.append("Hydration is close to your goal." if s["avg_water_ml"] >= 0.85 * user["water_goal_ml"] else DEMO_WELLNESS_TIPS["hydration"])
    notes.append("Sleep is on track." if s["avg_sleep_h"] >= 0.9 * user["sleep_goal_h"] else DEMO_WELLNESS_TIPS["sleep"])
    notes.append("Activity goal is being met." if s["avg_activity_min"] >= user["activity_goal_min"] else DEMO_WELLNESS_TIPS["activity"])
    return " ".join(notes)


@router.get("/summary")
def summary(user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    s = weekly_stats(db, user)
    text, mode = None, "demo"
    if ai.ai_enabled() and s["days_logged"]:
        try:
            text = ai.generate([{"role": "user", "content":
                f"Write a friendly 70-word weekly wellness summary with 2 general tips. Averages: water {s['avg_water_ml']} ml (goal {user['water_goal_ml']}), "
                f"sleep {s['avg_sleep_h']} h (goal {user['sleep_goal_h']}), activity {s['avg_activity_min']} min (goal {user['activity_goal_min']}). General advice only."}], max_tokens=300)
            mode = "live"
        except ai.AIError:
            text = None
    if text is None:
        text, mode = demo_weekly_text(s, user), "demo"
    return {**s, "text": text, "mode": mode, "disclaimer": DISCLAIMER}


@router.post("/suggestions")
def suggestions(body: PrefsIn, user: dict = Depends(current_user)):
    tips, mode = None, "demo"
    if ai.ai_enabled():
        try:
            data = ai.generate_json(
                f'Give 5 general, safe wellness habit suggestions (no medicines, no supplements doses). Diet preference: {body.diet}. '
                f'Goal: {body.goal}. Activity level: {body.activity_level}. Return JSON {{"suggestions": ["..."]}}.', max_tokens=500)
            tips = [str(t)[:250] for t in data.get("suggestions", [])][:6] or None
            mode = "live" if tips else "demo"
        except ai.AIError:
            tips = None
    if tips is None:
        mode = "demo"
        tips = [DEMO_WELLNESS_TIPS["hydration"], DEMO_WELLNESS_TIPS["sleep"], DEMO_WELLNESS_TIPS["nutrition"],
                DEMO_WELLNESS_TIPS["activity"] if body.activity_level != "high" else "Include rest days and stretching to help recovery.",
                DEMO_WELLNESS_TIPS["stress"]]
        if body.diet.lower().startswith("veg"):
            tips[2] = "Combine pulses, dairy or tofu, nuts and seeds to cover protein needs on a vegetarian diet."
    return {"suggestions": tips, "mode": mode, "disclaimer": DISCLAIMER,
            "demo_label": "Demo mode: pre-written general tips, not generated by a live AI model." if mode == "demo" else None}
