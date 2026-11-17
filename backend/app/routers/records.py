"""Personal health records, uploaded test reports and the lab-result history captured from them."""
import json
import sqlite3
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, model_validator

from .. import ai
from ..db import get_db, row, rows
from ..files import extract_text, read_upload, remove_file, store_file
from ..parsing import find_date, parse_results, test_key  # parse_results is re-exported for tests
from ..safety import DISCLAIMER, redact
from ..security import current_user

router = APIRouter(prefix="/api/records", tags=["records"])
DATE_RX = r"^\d{4}-\d{2}-\d{2}$"


class RecordIn(BaseModel):
    recorded_at: str = Field(pattern=DATE_RX)
    weight_kg: float | None = Field(default=None, ge=1, le=500)
    height_cm: float | None = Field(default=None, ge=30, le=272)
    systolic: int | None = Field(default=None, ge=50, le=260)
    diastolic: int | None = Field(default=None, ge=30, le=180)
    glucose_mgdl: float | None = Field(default=None, ge=20, le=800)
    temperature_c: float | None = Field(default=None, ge=30, le=45)
    notes: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def _check(self):
        datetime.strptime(self.recorded_at, "%Y-%m-%d")
        if (self.systolic is None) != (self.diastolic is None):
            raise ValueError("Enter both systolic and diastolic blood pressure")
        if self.systolic and self.diastolic and self.diastolic >= self.systolic:
            raise ValueError("Diastolic pressure must be lower than systolic")
        if all(v is None for v in (self.weight_kg, self.height_cm, self.systolic, self.glucose_mgdl, self.temperature_c)):
            raise ValueError("Enter at least one measurement")
        return self


METRIC_COLUMNS = {"weight": "weight_kg", "height": "height_cm", "bp": "systolic", "glucose": "glucose_mgdl", "temperature": "temperature_c"}


def _check_date(value: str, label: str = "Test date") -> str:
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(422, f"{label} must be YYYY-MM-DD")
    if d > date.today():
        raise HTTPException(422, f"{label} cannot be in the future")
    return value


@router.get("")
def list_records(q: str = Query(default="", max_length=100), metric: str = Query(default="", pattern=r"^(weight|height|bp|glucose|temperature)?$"),
                 start: str | None = Query(default=None, pattern=DATE_RX), end: str | None = Query(default=None, pattern=DATE_RX),
                 user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    sql, params = "SELECT * FROM health_records WHERE user_id=?", [user["id"]]
    if q:
        sql += " AND notes LIKE ?"
        params.append(f"%{q}%")
    if metric:
        sql += f" AND {METRIC_COLUMNS[metric]} IS NOT NULL"  # column comes from a fixed whitelist
    if start:
        sql += " AND recorded_at >= ?"
        params.append(start)
    if end:
        sql += " AND recorded_at <= ?"
        params.append(end)
    return rows(db, sql + " ORDER BY recorded_at DESC, id DESC", params)


@router.post("", status_code=201)
def add_record(body: RecordIn, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute(
        """INSERT INTO health_records (user_id, recorded_at, weight_kg, height_cm, systolic, diastolic, glucose_mgdl, temperature_c, notes)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (user["id"], body.recorded_at, body.weight_kg, body.height_cm, body.systolic, body.diastolic,
         body.glucose_mgdl, body.temperature_c, body.notes))
    db.commit()
    return row(db, "SELECT * FROM health_records WHERE id=?", (cur.lastrowid,))


@router.delete("/{rid}")
def delete_record(rid: int, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("DELETE FROM health_records WHERE id=? AND user_id=?", (rid, user["id"]))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "Record not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Lab result history: values captured from uploaded reports, or typed in manually
# ---------------------------------------------------------------------------
class LabIn(BaseModel):
    test_name: str = Field(min_length=2, max_length=60)
    value: float = Field(ge=0, le=1e7)
    unit: str = Field(default="", max_length=20)
    ref_low: float | None = Field(default=None, ge=0, le=1e7)
    ref_high: float | None = Field(default=None, ge=0, le=1e7)
    test_date: str = Field(pattern=DATE_RX)

    @model_validator(mode="after")
    def _check(self):
        if datetime.strptime(self.test_date, "%Y-%m-%d").date() > date.today():
            raise ValueError("Test date cannot be in the future")
        if (self.ref_low is None) != (self.ref_high is None):
            raise ValueError("Enter both reference limits or leave both empty")
        if self.ref_low is not None and self.ref_low >= self.ref_high:
            raise ValueError("Reference low must be below reference high")
        return self


def _status(value: float, lo: float | None, hi: float | None) -> str:
    if lo is None or hi is None:
        return "normal"
    return "low" if value < lo else "high" if value > hi else "normal"


def _save_labs(db, user_id: int, report_id: int | None, results: list[dict], test_date: str, source: str) -> None:
    for r in results:
        db.execute(
            """INSERT INTO lab_results (user_id, report_id, test_name, test_key, value, unit, ref_low, ref_high, status, test_date, source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, report_id, r["name"], test_key(r["name"]), r["value"], r["unit"], r["low"], r["high"], r["status"], test_date, source))


def _previous(db, user_id: int, key: str, before: str, exclude_report: int | None) -> dict | None:
    """Most recent earlier value of the same test (for 'compared with last time')."""
    return row(db, """SELECT value, unit, test_date, status FROM lab_results
                      WHERE user_id=? AND test_key=? AND test_date<? AND (report_id IS NULL OR report_id<>?)
                      ORDER BY test_date DESC, id DESC LIMIT 1""", (user_id, key, before, exclude_report or -1))


@router.get("/labs")
def lab_history(test: str = Query(default="", max_length=60), status: str = Query(default="", pattern=r"^(low|high|normal)?$"),
                start: str | None = Query(default=None, pattern=DATE_RX), end: str | None = Query(default=None, pattern=DATE_RX),
                user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    sql = "SELECT l.*, r.filename AS report_name FROM lab_results l LEFT JOIN reports r ON r.id = l.report_id WHERE l.user_id=?"
    params: list = [user["id"]]
    if test:
        sql += " AND l.test_key = ?"
        params.append(test_key(test))
    if status:
        sql += " AND l.status = ?"
        params.append(status)
    if start:
        sql += " AND l.test_date >= ?"
        params.append(start)
    if end:
        sql += " AND l.test_date <= ?"
        params.append(end)
    return rows(db, sql + " ORDER BY l.test_date DESC, l.id DESC", params)


@router.get("/labs/tests")
def lab_tests(user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    """One entry per distinct test: latest value, status, count and change from the previous measurement."""
    out: dict[str, dict] = {}
    for r in rows(db, "SELECT * FROM lab_results WHERE user_id=? ORDER BY test_date DESC, id DESC", (user["id"],)):
        t = out.get(r["test_key"])
        if t is None:
            out[r["test_key"]] = {"test_key": r["test_key"], "test_name": r["test_name"], "unit": r["unit"], "count": 1,
                                  "latest_value": r["value"], "latest_date": r["test_date"], "latest_status": r["status"],
                                  "ref_low": r["ref_low"], "ref_high": r["ref_high"], "previous_value": None, "previous_date": None}
        else:
            t["count"] += 1
            if t["previous_value"] is None:
                t["previous_value"], t["previous_date"] = r["value"], r["test_date"]
    return sorted(out.values(), key=lambda t: (t["latest_status"] == "normal", t["test_name"].lower()))


@router.post("/labs", status_code=201)
def add_lab(body: LabIn, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute(
        """INSERT INTO lab_results (user_id, report_id, test_name, test_key, value, unit, ref_low, ref_high, status, test_date, source)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (user["id"], None, body.test_name.strip(), test_key(body.test_name), body.value, body.unit.strip(), body.ref_low, body.ref_high,
         _status(body.value, body.ref_low, body.ref_high), body.test_date, "manual"))
    db.commit()
    return row(db, "SELECT * FROM lab_results WHERE id=?", (cur.lastrowid,))


@router.delete("/labs/{lid}")
def delete_lab(lid: int, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("DELETE FROM lab_results WHERE id=? AND user_id=?", (lid, user["id"]))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "Lab result not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Uploaded test reports
# ---------------------------------------------------------------------------
def _report_out(db, r: dict, full: bool = False) -> dict:
    out = {k: r[k] for k in ("id", "filename", "summary", "summary_mode", "created_at", "test_date")}
    results = json.loads(r["flagged"])
    for x in results:
        prev = _previous(db, r["user_id"], test_key(x["name"]), r["test_date"], r["id"])
        x["previous"] = prev
    out["results"] = results
    if full:
        out["text"] = r["extracted_text"]
    return out


def _get_report(db, rid, uid) -> dict:
    r = row(db, "SELECT * FROM reports WHERE id=? AND user_id=?", (rid, uid))
    if not r:
        raise HTTPException(404, "Report not found")
    return r


@router.post("/reports", status_code=201)
def upload_report(file: UploadFile = File(...), test_date: str = Form(default=""),
                  user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    if test_date:
        _check_date(test_date)
    name, data = read_upload(file)
    text = extract_text(data, name)
    results = parse_results(text)
    detected = find_date(text)
    when = test_date or detected or date.today().isoformat()
    date_source = "entered" if test_date else "detected from report" if detected else "upload date (no date found in report)"
    stored = store_file(user["id"], name, data)
    cur = db.execute("INSERT INTO reports (user_id, filename, stored_path, extracted_text, flagged, test_date) VALUES (?,?,?,?,?,?)",
                     (user["id"], name, str(stored), text, json.dumps(results), when))
    _save_labs(db, user["id"], cur.lastrowid, results, when, "report")
    db.commit()
    out = _report_out(db, _get_report(db, cur.lastrowid, user["id"]), full=True)
    out["date_source"] = date_source
    out["captured"] = len(results)
    return out


@router.get("/reports")
def list_reports(user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    return [_report_out(db, r) for r in rows(db, "SELECT * FROM reports WHERE user_id=? ORDER BY test_date DESC, id DESC", (user["id"],))]


@router.get("/reports/{rid}")
def get_report(rid: int, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    return _report_out(db, _get_report(db, rid, user["id"]), full=True)


class ReportDateIn(BaseModel):
    test_date: str = Field(pattern=DATE_RX)


@router.patch("/reports/{rid}")
def update_report_date(rid: int, body: ReportDateIn, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    """Correct the test date of a report; the captured lab values move with it."""
    _get_report(db, rid, user["id"])
    _check_date(body.test_date)
    db.execute("UPDATE reports SET test_date=? WHERE id=?", (body.test_date, rid))
    db.execute("UPDATE lab_results SET test_date=? WHERE report_id=? AND user_id=?", (body.test_date, rid, user["id"]))
    db.commit()
    return _report_out(db, _get_report(db, rid, user["id"]))


@router.delete("/reports/{rid}")
def delete_report(rid: int, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    r = _get_report(db, rid, user["id"])
    db.execute("DELETE FROM lab_results WHERE report_id=? AND user_id=?", (rid, user["id"]))
    db.execute("DELETE FROM reports WHERE id=?", (rid,))
    db.commit()
    remove_file(user["id"], r["stored_path"])
    return {"ok": True}


def _trend_text(x: dict) -> str:
    p = x.get("previous")
    if not p:
        return ""
    diff = x["value"] - p["value"]
    word = "up" if diff > 0 else "down" if diff < 0 else "unchanged"
    return f" (previously {p['value']} on {p['test_date']}, {word})"


def demo_summary(results: list[dict]) -> str:
    if not results:
        return "No lab values with printed reference ranges were found in this report, so nothing could be compared. Please discuss the report with your doctor."
    abnormal = [r for r in results if r["status"] != "normal"]
    lines = [f"{len(results)} value(s) with reference ranges were found; {len(abnormal)} fall outside the range printed in the report."]
    for r in abnormal:
        lines.append(f"- {r['name']}: {r['value']} {r['unit']} is {r['status']} (report range {r['low']}-{r['high']}){_trend_text(r)}.")
    changed = [r for r in results if r["status"] == "normal" and r.get("previous") and r["previous"]["status"] != "normal"]
    for r in changed:
        lines.append(f"- {r['name']} is now within the report range{_trend_text(r)}.")
    lines.append("This only compares numbers with the ranges printed in your report. It is not a diagnosis. Please review the report with your doctor.")
    return "\n".join(lines)


@router.post("/reports/{rid}/summarize")
def summarize(rid: int, user: dict = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    r = _get_report(db, rid, user["id"])
    results = _report_out(db, r)["results"]
    summary, mode = None, "demo"
    if ai.ai_enabled() and results:
        # Privacy: only parsed test names, values, ranges and previous values are sent. Never the raw report (names, IDs).
        table = "\n".join(f"{x['name']}: {x['value']} {x['unit']} (report range {x['low']}-{x['high']}, {x['status']}){_trend_text(x)}"
                          for x in results[:60])
        try:
            summary = ai.generate([{"role": "user", "content":
                "Summarise these lab values in plain language for a patient in under 150 words. Mention which are outside the report's "
                "own reference range and any change from the previous value. Do NOT diagnose or suggest medicines; recommend "
                "discussing with a doctor.\n" + redact(table)}], max_tokens=500)
            mode = "live"
        except ai.AIError:
            summary = None
    if summary is None:
        summary, mode = demo_summary(results), "demo"
    db.execute("UPDATE reports SET summary=?, summary_mode=? WHERE id=?", (summary, mode, rid))
    db.commit()
    return {"summary": summary, "mode": mode, "disclaimer": DISCLAIMER}
