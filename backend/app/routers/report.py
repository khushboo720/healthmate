"""Downloadable PDF health report."""
import json
import sqlite3
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .. import ai
from ..db import get_db, rows
from ..safety import DISCLAIMER
from ..security import current_user
from .dashboard import latest_metrics
from .wellness import weekly_stats

router = APIRouter(prefix="/api/report", tags=["report"])
TEAL = colors.HexColor("#0d9488")


def _summary(user: dict, latest: dict, stats: dict, adherence: dict, abnormal_labs: int = 0) -> tuple[str, str]:
    """General summary built from numbers only (no name/contact details go to the AI)."""
    facts = (f"Weight {latest['weight_kg']['v'] if latest['weight_kg'] else 'n/a'} kg; BP "
             f"{latest['systolic']['v'] if latest['systolic'] else 'n/a'}/{latest['diastolic']['v'] if latest['diastolic'] else 'n/a'}; "
             f"avg water {stats['avg_water_ml']} ml, sleep {stats['avg_sleep_h']} h, activity {stats['avg_activity_min']} min; "
             f"medicine doses taken {adherence['taken']} of {adherence['total']} logged; "
             f"{abnormal_labs} lab test(s) had a value outside the report's reference range at some point.")
    if ai.ai_enabled():
        try:
            text = ai.generate([{"role": "user", "content":
                "Write a short (about 90 words) general, non-diagnostic health summary and 3 healthy-habit suggestions from these figures. "
                "Do not diagnose or mention medicines doses. Figures: " + facts}], max_tokens=400)
            return text, "AI-generated (live model)"
        except ai.AIError:
            pass
    text = (f"Template-based summary (demo mode, not written by an AI model). Recent figures: {facts} "
            "Keep tracking regularly, aim for your hydration, sleep and activity goals, and share this report with your doctor for interpretation.")
    return text, "Demo-mode template"


def _table(data, widths=None):
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdfa")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


@router.get("/pdf")
def pdf(user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    uid = user["id"]
    ss = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=ss["Heading2"], textColor=TEAL, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12)
    warn = ParagraphStyle("w", parent=body, textColor=colors.HexColor("#92400e"), backColor=colors.HexColor("#fef3c7"), borderPadding=5)
    P = lambda s, st=body: Paragraph(escape(str(s)).replace("\n", "<br/>"), st)

    latest = latest_metrics(db, uid)
    stats = weekly_stats(db, user)
    logs = rows(db, "SELECT l.scheduled_for, l.status, m.name, m.dosage FROM medicine_logs l JOIN medicines m ON m.id=l.medicine_id "
                    "WHERE l.user_id=? ORDER BY l.scheduled_for DESC LIMIT 25", (uid,))
    taken = rows(db, "SELECT status, COUNT(*) c FROM medicine_logs WHERE user_id=? GROUP BY status", (uid,))
    adherence = {"taken": next((r["c"] for r in taken if r["status"] == "taken"), 0), "total": sum(r["c"] for r in taken)}
    meds = rows(db, "SELECT m.*, p.doctor AS prescribed_by FROM medicines m LEFT JOIN prescriptions p ON p.id=m.prescription_id "
                    "WHERE m.user_id=? ORDER BY m.name", (uid,))
    labs = rows(db, "SELECT * FROM lab_results WHERE user_id=? ORDER BY test_date DESC, id DESC", (uid,))
    abnormal = len({l["test_key"] for l in labs if l["status"] != "normal"})
    appts = rows(db, "SELECT * FROM appointments WHERE user_id=? ORDER BY scheduled_at DESC LIMIT 15", (uid,))
    records = rows(db, "SELECT * FROM health_records WHERE user_id=? ORDER BY recorded_at DESC LIMIT 10", (uid,))
    summary, summary_src = _summary(user, latest, stats, adherence, abnormal)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            title="HealthMate AI Health Report", author="HealthMate AI")
    s: list = [Paragraph("HealthMate AI - Personal Health Report", ParagraphStyle("t", parent=ss["Title"], textColor=TEAL)),
               P(f"Generated on {datetime.now():%d %b %Y, %H:%M}"), Spacer(1, 6), P(DISCLAIMER, warn)]

    s += [Paragraph("1. Profile", h), _table([["Field", "Value"], ["Name", user["name"]], ["Email", user["email"]],
          ["Age", user["age"] if user["age"] is not None else "-"], ["Gender", user["gender"] or "-"], ["Blood group", user["blood_group"] or "-"],
          ["Allergies", user["allergies"] or "-"], ["Existing medical history", user["medical_history"] or "-"]], [5 * cm, 12 * cm])]

    rec_rows = [["Date", "Weight kg", "BP", "Glucose", "Temp C", "Notes"]]
    for r in records:
        bp = f"{r['systolic']}/{r['diastolic']}" if r["systolic"] else "-"
        rec_rows.append([r["recorded_at"], r["weight_kg"] or "-", bp, r["glucose_mgdl"] or "-", r["temperature_c"] or "-", P(r["notes"] or "")])
    s += [Paragraph("2. Recorded health metrics (latest 10)", h), _table(rec_rows if len(rec_rows) > 1 else [["No records yet"]])]

    # Lab results captured from uploaded test reports: latest value per test plus the previous one.
    lab_rows = [["Test", "Latest", "Report range", "Flag", "Date", "Previous"]]
    seen: dict[str, dict] = {}
    for l in labs:
        if l["test_key"] not in seen:
            seen[l["test_key"]] = {**l, "prev": None}
        elif seen[l["test_key"]]["prev"] is None:
            seen[l["test_key"]]["prev"] = l
    for l in seen.values():
        rng = f"{l['ref_low']:g} - {l['ref_high']:g}" if l["ref_low"] is not None else "-"
        prev = f"{l['prev']['value']:g} ({l['prev']['test_date']})" if l["prev"] else "-"
        lab_rows.append([l["test_name"], f"{l['value']:g} {l['unit']}", rng, "within range" if l["status"] == "normal" else l["status"].upper(),
                         l["test_date"], prev])
    s += [Paragraph("3. Lab test results (captured from uploaded reports)", h),
          _table(lab_rows if len(lab_rows) > 1 else [["No lab results yet"]]),
          Spacer(1, 3), P("Flags compare each value with the reference range printed on the report. They are not a diagnosis.")]

    med_rows = [["Medicine", "Dosage (as prescribed)", "Times", "Frequency", "Prescribed by", "Active"]]
    for m in meds:
        med_rows.append([m["name"], P(m["dosage"]), ", ".join(json.loads(m["times"])), m["frequency"], P(m["prescribed_by"] or "-"),
                         "yes" if m["active"] else "no"])
    s += [Paragraph("4. Medicines and reminder history", h), _table(med_rows if len(med_rows) > 1 else [["No medicines added"]]),
          Spacer(1, 4), P(f"Adherence: {adherence['taken']} dose(s) taken out of {adherence['total']} logged.")]
    log_rows = [["Scheduled", "Medicine", "Status"]] + [[l["scheduled_for"], l["name"], l["status"]] for l in logs]
    if len(log_rows) > 1:
        s += [Spacer(1, 4), _table(log_rows, [5 * cm, 8 * cm, 4 * cm])]

    s += [Paragraph("5. Wellness activity (last 7 days)", h),
          _table([["Days logged", "Avg water (ml)", "Avg sleep (h)", "Avg activity (min)", "Avg goal progress"],
                  [stats["days_logged"], stats["avg_water_ml"], stats["avg_sleep_h"], stats["avg_activity_min"], f"{stats['avg_progress']}%"]])]

    ap_rows = [["Date/time", "Doctor", "Specialization", "Clinic", "Purpose", "Status"]]
    for a in appts:
        ap_rows.append([a["scheduled_at"], a["doctor"], a["specialization"], a["clinic"], P(a["purpose"]), a["status"]])
    s += [Paragraph("6. Doctor appointments", h), _table(ap_rows if len(ap_rows) > 1 else [["No appointments"]])]

    s += [Paragraph("7. General health summary", h), P(f"Source: {summary_src}"), P(summary), Spacer(1, 6),
          P("This summary is informational only and is NOT a medical diagnosis. It does not replace advice from a qualified doctor.", warn)]
    doc.build(s)
    return Response(buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="healthmate-report.pdf"'})
