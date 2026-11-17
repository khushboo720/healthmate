"""API test cases (see docs/TEST_CASES.md). Run: pytest -q"""
from datetime import date, timedelta
from io import BytesIO

from reportlab.pdfgen import canvas

from app.routers.records import parse_results
from app.safety import detect_emergency, redact

TODAY = date.today().isoformat()


# ---------------- Auth ----------------
def test_register_login_me(client):
    r = client.post("/api/auth/register", json={"name": "Asha K", "email": "asha@example.com", "password": "Strong123", "age": 25})
    assert r.status_code == 201 and "password_hash" not in r.json()["user"]
    r = client.post("/api/auth/login", json={"email": "ASHA@example.com", "password": "Strong123"})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + r.json()["token"]})
    assert me.json()["email"] == "asha@example.com"


def test_register_validation_and_duplicate(client):
    base = {"name": "Bob", "email": "bob@example.com", "password": "Strong123"}
    assert client.post("/api/auth/register", json={**base, "password": "short"}).status_code == 422
    assert client.post("/api/auth/register", json={**base, "password": "onlyletters"}).status_code == 422
    assert client.post("/api/auth/register", json={**base, "email": "not-an-email"}).status_code == 422
    assert client.post("/api/auth/register", json=base).status_code == 201
    assert client.post("/api/auth/register", json=base).status_code == 409


def test_wrong_password_and_protected_routes(client):
    assert client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"}).status_code == 401
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_demo_account_seeded(client):
    r = client.post("/api/auth/login", json={"email": "demo@healthmate.ai", "password": "Demo@1234"})
    assert r.status_code == 200
    h = {"Authorization": "Bearer " + r.json()["token"]}
    d = client.get("/api/dashboard", headers=h).json()
    assert d["kpis"]["health_records"] >= 10 and d["kpis"]["active_medicines"] == 3 and d["kpis"]["upcoming_appointments"] >= 2


def test_profile_update(client, auth):
    r = client.put("/api/auth/profile", headers=auth, json={"name": "New Name", "age": 41, "gender": "Male", "allergies": "Peanuts"})
    assert r.status_code == 200 and r.json()["allergies"] == "Peanuts"


# ---------------- Safety ----------------
def test_detect_emergency_patterns():
    assert detect_emergency("I have severe chest pain")
    assert detect_emergency("my father has slurred speech")
    assert detect_emergency("I want to kill myself") == ["self-harm"]
    assert not detect_emergency("How can I improve my sleep?")


def test_redact_removes_identifiers():
    out = redact("Name: John Doe\nEmail a@b.com\nPhone 9876543210\nHb 12")
    assert "John" not in out and "a@b.com" not in out and "9876543210" not in out and "Hb 12" in out


# ---------------- Chat ----------------
def test_chat_demo_mode_is_labelled(client, auth):
    r = client.post("/api/chat", headers=auth, json={"message": "Why do people experience headaches?"}).json()
    assert r["mode"] == "demo" and "Demo mode" in r["demo_label"] and "doctor" in r["reply"].lower()
    assert "does not provide" in r["disclaimer"]


def test_chat_emergency_short_circuits(client, auth):
    r = client.post("/api/chat", headers=auth, json={"message": "I have chest pain and can't breathe"}).json()
    assert r["emergency"] and r["mode"] == "safety" and "112" in r["reply"]


def test_chat_self_harm_gets_helpline(client, auth):
    r = client.post("/api/chat", headers=auth, json={"message": "I want to kill myself"}).json()
    assert r["emergency"] and "14416" in r["reply"]


def test_chat_general_question_about_red_flag_not_blocked(client, auth):
    r = client.post("/api/chat", headers=auth, json={"message": "What are common causes of chest pain?"}).json()
    assert r["mode"] != "safety"


def test_chat_history_and_clear(client, auth):
    client.post("/api/chat", headers=auth, json={"message": "How can I improve my sleep?"})
    h = client.get("/api/chat/history", headers=auth).json()
    assert len(h["messages"]) == 2 and h["ai"]["mode"] == "demo"
    assert client.delete("/api/chat/history", headers=auth).status_code == 200
    assert client.get("/api/chat/history", headers=auth).json()["messages"] == []


def test_chat_validation(client, auth):
    assert client.post("/api/chat", headers=auth, json={"message": ""}).status_code == 422
    assert client.post("/api/chat", headers=auth, json={"message": "x" * 1001}).status_code == 422


def test_explain_term(client, auth):
    r = client.post("/api/chat/explain-term", headers=auth, json={"term": "Hemoglobin"}).json()
    assert "oxygen" in r["explanation"]


# ---------------- Symptoms ----------------
def check(client, auth, **kw):
    body = {"symptoms": ["Headache"], "duration_days": 1, "severity": "mild", "notes": ""}
    body.update(kw)
    return client.post("/api/symptoms/check", headers=auth, json=body)


def test_symptom_mild_self_care(client, auth):
    r = check(client, auth).json()
    assert r["urgency"] == "self_care" and r["warning_signs"] and "diagnos" in r["disclaimer"].lower()
    assert r["mode"] == "demo" and "Symptoms: Headache" in r["doctor_summary"]


def test_symptom_red_flag_is_emergency(client, auth):
    r = check(client, auth, symptoms=["Headache", "Chest pain or pressure"]).json()
    assert r["urgency"] == "emergency" and "112" in r["emergency_message"] and r["explanations"] == []


def test_symptom_emergency_from_notes(client, auth):
    assert check(client, auth, notes="my lips are swelling of the throat").json()["urgency"] == "emergency"


def test_symptom_fever_three_days_is_soon(client, auth):
    assert check(client, auth, symptoms=["Fever"], duration_days=3, severity="mild").json()["urgency"] == "soon"


def test_symptom_validation(client, auth):
    assert check(client, auth, symptoms=["Made up"]).status_code == 422
    assert check(client, auth, severity="extreme").status_code == 422
    assert check(client, auth, symptoms=[]).status_code == 422


# ---------------- Medicines ----------------
def med(**kw):
    b = {"name": "Vitamin C", "dosage": "1 tablet (as prescribed)", "times": ["08:00", "20:00"], "frequency": "daily", "start_date": TODAY}
    b.update(kw)
    return b


def test_medicine_lifecycle(client, auth):
    r = client.post("/api/medicines", headers=auth, json=med())
    assert r.status_code == 201
    mid = r.json()["id"]
    sched = client.get(f"/api/medicines/schedule?date={TODAY}&now={TODAY}%2012:00", headers=auth).json()
    assert [s["status"] for s in sched] == ["overdue", "pending"]
    log = client.post("/api/medicines/log", headers=auth, json={"medicine_id": mid, "scheduled_for": f"{TODAY} 08:00", "status": "taken"})
    assert log.status_code == 200
    client.post("/api/medicines/log", headers=auth, json={"medicine_id": mid, "scheduled_for": f"{TODAY} 20:00", "status": "skipped"})
    sched = client.get(f"/api/medicines/schedule?date={TODAY}", headers=auth).json()
    assert [s["status"] for s in sched] == ["taken", "skipped"]
    hist = client.get("/api/medicines/history", headers=auth).json()
    assert len(hist) == 2 and hist[0]["name"] == "Vitamin C"
    assert client.put(f"/api/medicines/{mid}", headers=auth, json=med(active=False)).json()["active"] is False
    assert client.delete(f"/api/medicines/{mid}", headers=auth).status_code == 200


def test_medicine_validation(client, auth):
    assert client.post("/api/medicines", headers=auth, json=med(times=["25:99"])).status_code == 422
    assert client.post("/api/medicines", headers=auth, json=med(times=[])).status_code == 422
    assert client.post("/api/medicines", headers=auth, json=med(name="")).status_code == 422
    past = (date.today() - timedelta(days=3)).isoformat()
    assert client.post("/api/medicines", headers=auth, json=med(end_date=past)).status_code == 422


def test_cannot_log_other_users_medicine(client, auth, register):
    mid = client.post("/api/medicines", headers=auth, json=med()).json()["id"]
    other = register(client, "other1@example.com")
    r = client.post("/api/medicines/log", headers=other, json={"medicine_id": mid, "scheduled_for": f"{TODAY} 08:00", "status": "taken"})
    assert r.status_code == 404
    assert client.delete(f"/api/medicines/{mid}", headers=other).status_code == 404


# ---------------- Records ----------------
def test_records_crud_and_filter(client, auth):
    r = client.post("/api/records", headers=auth, json={"recorded_at": TODAY, "weight_kg": 70.5, "systolic": 120, "diastolic": 80, "notes": "morning check"})
    assert r.status_code == 201
    client.post("/api/records", headers=auth, json={"recorded_at": TODAY, "glucose_mgdl": 95})
    assert len(client.get("/api/records", headers=auth).json()) == 2
    assert len(client.get("/api/records?q=morning", headers=auth).json()) == 1
    assert len(client.get("/api/records?metric=glucose", headers=auth).json()) == 1
    assert client.delete(f"/api/records/{r.json()['id']}", headers=auth).status_code == 200


def test_records_validation(client, auth):
    bad = [{"recorded_at": TODAY}, {"recorded_at": TODAY, "systolic": 120}, {"recorded_at": TODAY, "systolic": 80, "diastolic": 120},
           {"recorded_at": TODAY, "temperature_c": 60}, {"recorded_at": "2024-13-45", "weight_kg": 60}]
    for b in bad:
        assert client.post("/api/records", headers=auth, json=b).status_code == 422, b


def test_parse_results_formats():
    text = "Hemoglobin: 11.2 g/dL (12.0 - 15.5)\nGlucose 130 mg/dL Ref: 70-99\nWBC 7.1 4.0 - 11.0 x10^3\nRandom text 5"
    res = {r["name"]: r for r in parse_results(text)}
    assert res["Hemoglobin"]["status"] == "low"
    assert res["Glucose"]["status"] == "high"
    assert res["WBC"]["status"] == "normal"
    assert len(res) == 3


def _pdf(lines):
    buf = BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 18
    c.save()
    return buf.getvalue()


def test_report_upload_pdf_and_summarize(client, auth):
    pdf = _pdf(["Patient Name: Fake Person", "Hemoglobin 11.2 g/dL (12.0 - 15.5)", "Cholesterol 180 mg/dL (0 - 200)"])
    r = client.post("/api/records/reports", headers=auth, files={"file": ("lab.pdf", pdf, "application/pdf")})
    assert r.status_code == 201, r.text
    body = r.json()
    assert {x["name"]: x["status"] for x in body["results"]} == {"Hemoglobin": "low", "Cholesterol": "normal"}
    s = client.post(f"/api/records/reports/{body['id']}/summarize", headers=auth).json()
    assert s["mode"] == "demo" and "not a diagnosis" in s["summary"].lower()
    assert len(client.get("/api/records/reports", headers=auth).json()) == 1
    assert client.delete(f"/api/records/reports/{body['id']}", headers=auth).status_code == 200


def test_report_upload_rejects_bad_files(client, auth):
    assert client.post("/api/records/reports", headers=auth, files={"file": ("x.exe", b"abc", "application/octet-stream")}).status_code == 415
    assert client.post("/api/records/reports", headers=auth, files={"file": ("fake.pdf", b"not a pdf", "application/pdf")}).status_code == 415
    big = b"%PDF" + b"0" * (5 * 1024 * 1024 + 10)
    assert client.post("/api/records/reports", headers=auth, files={"file": ("big.pdf", big, "application/pdf")}).status_code == 413


# ---------------- Wellness ----------------
def test_wellness_upsert_summary_suggestions(client, auth):
    r = client.put(f"/api/wellness/{TODAY}", headers=auth, json={"water_ml": 2500, "sleep_hours": 8, "activity_min": 30, "mood": "Good"})
    assert r.json()["progress"] == 100
    client.put(f"/api/wellness/{TODAY}", headers=auth, json={"water_ml": 1250, "sleep_hours": 4, "activity_min": 15})
    w = client.get("/api/wellness?days=7", headers=auth).json()
    assert len(w["days"]) == 7 and w["days"][-1]["water_ml"] == 1250 and w["days"][-1]["progress"] == 50
    s = client.get("/api/wellness/summary", headers=auth).json()
    assert s["days_logged"] == 1 and s["mode"] == "demo"
    sug = client.post("/api/wellness/suggestions", headers=auth, json={"diet": "vegetarian", "goal": "more energy", "activity_level": "low"}).json()
    assert len(sug["suggestions"]) >= 4 and sug["demo_label"]


def test_wellness_validation(client, auth):
    assert client.put(f"/api/wellness/{TODAY}", headers=auth, json={"water_ml": -5, "sleep_hours": 8, "activity_min": 1}).status_code == 422
    assert client.put("/api/wellness/not-a-date", headers=auth, json={"water_ml": 1, "sleep_hours": 8, "activity_min": 1}).status_code == 422


# ---------------- Appointments ----------------
def test_appointments_crud(client, auth):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    b = {"doctor": "Dr. Test", "specialization": "GP", "clinic": "Clinic", "scheduled_at": f"{tomorrow} 10:30", "purpose": "Check-up"}
    r = client.post("/api/appointments", headers=auth, json=b)
    assert r.status_code == 201
    aid = r.json()["id"]
    assert client.put(f"/api/appointments/{aid}", headers=auth, json={**b, "status": "completed"}).json()["status"] == "completed"
    assert len(client.get("/api/appointments", headers=auth).json()) == 1
    assert client.delete(f"/api/appointments/{aid}", headers=auth).status_code == 200
    assert client.delete(f"/api/appointments/{aid}", headers=auth).status_code == 404


def test_appointment_validation(client, auth):
    assert client.post("/api/appointments", headers=auth, json={"doctor": "D", "scheduled_at": "2025-01-01 10:00"}).status_code == 422
    assert client.post("/api/appointments", headers=auth, json={"doctor": "Dr. X", "scheduled_at": "tomorrow"}).status_code == 422


# ---------------- Dashboard, PDF, deletion ----------------
def test_dashboard_for_new_user_is_empty_but_valid(client, auth):
    d = client.get("/api/dashboard", headers=auth).json()
    assert d["kpis"] == {"health_records": 0, "active_medicines": 0, "upcoming_appointments": 0, "wellness_progress": 0}
    assert len(d["wellness_week"]) == 7


def test_pdf_report(client, auth):
    client.post("/api/records", headers=auth, json={"recorded_at": TODAY, "weight_kg": 65})
    r = client.get("/api/report/pdf", headers=auth)
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and r.headers["content-type"] == "application/pdf"
    assert b"Demo" in r.content or len(r.content) > 1000


def test_delete_data_and_account(client, register):
    h = register(client, "gone@example.com")
    client.post("/api/records", headers=h, json={"recorded_at": TODAY, "weight_kg": 65})
    client.post("/api/chat", headers=h, json={"message": "hello"})
    assert client.delete("/api/account/data", headers=h).status_code == 200
    assert client.get("/api/records", headers=h).json() == []
    assert client.get("/api/chat/history", headers=h).json()["messages"] == []
    assert client.get("/api/auth/me", headers=h).status_code == 200  # account remains
    assert client.delete("/api/account", headers=h).status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_security_headers_and_no_store_on_api(client, auth):
    r = client.get("/api/dashboard", headers=auth)
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


def test_security_headers_and_no_store_on_api(client, auth):
    r = client.get("/api/dashboard", headers=auth)
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


def test_concurrent_requests_do_not_hit_sqlite_thread_errors(client, auth):
    """Regression: dependencies/endpoint may run on different worker threads."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=16) as ex:
        codes = list(ex.map(lambda _: client.get("/api/dashboard", headers=auth).status_code, range(60)))
    assert set(codes) == {200}


def test_users_cannot_see_each_others_data(client, auth, register):
    client.post("/api/records", headers=auth, json={"recorded_at": TODAY, "weight_kg": 65})
    other = register(client, "spy@example.com")
    assert client.get("/api/records", headers=other).json() == []
