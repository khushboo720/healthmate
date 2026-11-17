"""Symptom information checker. Urgency is decided by deterministic rules, never by the AI."""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import ai
from ..knowledge import SEVERITIES, SYMPTOMS
from ..safety import DISCLAIMER, EMERGENCY_MESSAGE, detect_emergency, redact
from ..security import current_user

router = APIRouter(prefix="/api/symptoms", tags=["symptoms"])

URGENCY_TEXT = {
    "emergency": "Seek emergency care now",
    "soon": "Consider seeing a doctor within 24-48 hours",
    "routine": "Consider a routine appointment with a doctor",
    "self_care": "Self-care and monitoring may be reasonable",
}
LEVELS = ["self_care", "routine", "soon", "emergency"]


class CheckIn(BaseModel):
    symptoms: list[str] = Field(min_length=1, max_length=12)
    duration_days: int = Field(ge=0, le=365)
    severity: str
    notes: str = Field(default="", max_length=500)


@router.get("/catalog")
def catalog(user: dict = Depends(current_user)):
    return {
        "symptoms": [{"name": n, "red_flag": bool(v.get("red"))} for n, v in SYMPTOMS.items()],
        "severities": SEVERITIES,
    }


def decide_urgency(symptoms: list[str], days: int, severity: str, age: int | None, notes: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    red = [s for s in symptoms if SYMPTOMS[s].get("red")]
    note_flags = detect_emergency(notes)
    if red or note_flags:
        return "emergency", red + note_flags
    level = 0
    if severity == "severe":
        level = 2
        reasons.append("severity reported as severe")
    elif severity == "moderate" and days >= 3:
        level = 2
        reasons.append("moderate symptoms lasting 3 or more days")
    elif "Fever" in symptoms and days >= 3:
        level = 2
        reasons.append("fever lasting 3 or more days")
    elif days >= 7 or severity == "moderate":
        level = 1
        reasons.append("symptoms lasting a week or more" if days >= 7 else "moderate severity")
    if age is not None and (age < 5 or age >= 65):
        level = min(level + 1, 2)  # extra caution for very young / older people, but never auto-escalate to emergency
        reasons.append("age group needs extra caution")
    return LEVELS[level], reasons


def _demo_content(symptoms: list[str]) -> dict:
    causes, care, warn = [], [], []
    for s in symptoms:
        info = SYMPTOMS[s]
        causes += [f"{s}: {c}" for c in info.get("causes", [])[:3]]
        care += info.get("care", [])
        warn += info.get("warn", [])
    uniq = lambda xs: list(dict.fromkeys(xs))
    return {"explanations": uniq(causes)[:8], "self_care": uniq(care)[:6], "warning_signs": uniq(warn)[:8]}


def _live_content(symptoms, days, severity, age_band, notes) -> dict:
    prompt = (
        "Provide general educational information about these symptoms. Do NOT diagnose, give probabilities, or recommend medicines.\n"
        f"Symptoms: {', '.join(symptoms)}\nDuration: {days} days\nSeverity: {severity}\nAge group: {age_band}\n"
        f"Extra notes: {redact(notes) or 'none'}\n"
        'Return JSON with keys: "explanations" (list of up to 6 short general possible explanations, phrased as possibilities), '
        '"self_care" (list of up to 5 general comfort tips), "warning_signs" (list of up to 6 signs that need prompt medical care).')
    data = ai.generate_json(prompt)
    out = {}
    for k in ("explanations", "self_care", "warning_signs"):
        v = data.get(k)
        if not isinstance(v, list) or not v:
            raise ai.AIError("missing " + k)
        out[k] = [str(x)[:300] for x in v][:8]
    return out


@router.post("/check")
def check(body: CheckIn, user: dict = Depends(current_user)):
    unknown = [s for s in body.symptoms if s not in SYMPTOMS]
    if unknown:
        raise HTTPException(422, f"Unknown symptom: {unknown[0]}")
    if body.severity not in SEVERITIES:
        raise HTTPException(422, "Severity must be mild, moderate or severe")

    urgency, reasons = decide_urgency(body.symptoms, body.duration_days, body.severity, user.get("age"), body.notes)

    if urgency == "emergency":
        # No AI call, no further questions: emergency guidance first.
        summary = _doctor_summary(user, body, urgency)
        return {"urgency": urgency, "urgency_text": URGENCY_TEXT[urgency], "reasons": reasons, "emergency_message": EMERGENCY_MESSAGE,
                "explanations": [], "self_care": [], "warning_signs": [], "doctor_summary": summary, "mode": "safety", "disclaimer": DISCLAIMER}

    age = user.get("age")
    age_band = "unknown" if age is None else "child" if age < 13 else "teen" if age < 18 else "adult" if age < 65 else "older adult"
    mode, content = "demo", None
    if ai.ai_enabled():
        try:
            content, mode = _live_content(body.symptoms, body.duration_days, body.severity, age_band, body.notes), "live"
        except ai.AIError:
            content = None
    if content is None:
        content, mode = _demo_content(body.symptoms), "demo"

    return {"urgency": urgency, "urgency_text": URGENCY_TEXT[urgency], "reasons": reasons, "emergency_message": None,
            **content, "doctor_summary": _doctor_summary(user, body, urgency), "mode": mode,
            "demo_label": "Demo mode: pre-written general information, not generated by a live AI model." if mode == "demo" else None,
            "disclaimer": DISCLAIMER}


def _doctor_summary(user: dict, body: CheckIn, urgency: str) -> str:
    age = f"{user['age']} years" if user.get("age") is not None else "age not provided"
    lines = [
        "SYMPTOM SUMMARY FOR DOCTOR (self-reported, not a diagnosis)",
        f"Patient: {user['name']} ({age}{', ' + user['gender'] if user.get('gender') else ''})",
        f"Symptoms: {', '.join(body.symptoms)}",
        f"Duration: {body.duration_days} day(s)    Severity: {body.severity}",
        f"Additional observations: {body.notes or 'none'}",
        f"Known allergies: {user.get('allergies') or 'none recorded'}",
        f"Existing history: {user.get('medical_history') or 'none recorded'}",
        f"App guidance level: {URGENCY_TEXT[urgency]}",
        "Generated by HealthMate AI. Informational only; not a medical diagnosis.",
    ]
    return "\n".join(lines)
