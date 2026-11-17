"""Tests for prescription-based reminders and lab-report data capture / history."""
from datetime import date, timedelta
from io import BytesIO

from reportlab.pdfgen import canvas

from app.parsing import find_date, parse_prescription, parse_prescription_line

TODAY = date.today()
DMY = f"{TODAY:%d/%m/%Y}"


def _pdf(lines):
    buf = BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 18
    c.save()
    return buf.getvalue()


# ---------------- Parser (pure functions) ----------------
def test_prescription_line_formats():
    p = parse_prescription_line("1. Tab Metformin 500 mg 1-0-1 after food x 30 days")
    assert (p["name"], p["times"], p["duration_days"]) == ("Metformin", ["08:00", "21:00"], 30)
    assert "500 mg" in p["dosage"] and "after food" in p["instructions"]
    p = parse_prescription_line("Cap Omeprazole 20mg OD before breakfast for 2 weeks")
    assert p["times"] == ["08:00"] and p["duration_days"] == 14
    p = parse_prescription_line("Tab Amoxicillin 500mg every 8 hours for 7 days")
    assert p["times"] == ["06:00", "14:00", "22:00"]
    p = parse_prescription_line("Vitamin D3 60000 IU once weekly for 8 weeks")
    assert p["frequency"] == "weekly" and p["duration_days"] == 56
    p = parse_prescription_line("Iron + Folic acid 1 tablet twice daily")
    assert p["name"] == "Iron + Folic acid" and p["times"] == ["08:00", "20:00"]


def test_prescription_as_needed_and_unclear_lines_are_not_auto_scheduled():
    p = parse_prescription_line("Tab Paracetamol 650 mg SOS")
    assert p["as_needed"] and p["times"] == []
    p = parse_prescription_line("Tab Mystery 5 mg")
    assert p["needs_review"] and p["times"] == []


def test_prescription_header_and_advice_lines_ignored():
    for line in ("Patient Name: Fake Person Age: 28", "Advice: drink plenty of water", "Follow up after 5 days", "Diagnosis: fever"):
        assert parse_prescription_line(line) is None


def test_parse_prescription_doctor_and_date():
    r = parse_prescription(f"Dr. Neha Kapoor, MBBS\nDate: {DMY}\nRx\n1. Tab Cetirizine 10 mg 0-0-1 x 10 days\n")
    assert r["doctor"] == "Dr. Neha Kapoor" and r["date"] == TODAY.isoformat() and len(r["items"]) == 1


def test_find_date_variants():
    assert find_date("Collected on: 3 Nov 2025") == "2025-11-03"
    assert find_date("Report Date 2025-10-12") == "2025-10-12"
    assert find_date("DOB: 01/01/1990") is None
    assert find_date("no dates here") is None


# ---------------- Prescription API ----------------
RX_TEXT = (f"Dr. Neha Kapoor (sample)\nDate: {DMY}\nRx\n1. Tab Cetirizine 10 mg 0-0-1 after food x 10 days\n"
           "2. Tab Paracetamol 650 mg SOS\n3. Tab Mystery 5 mg\n")


def test_prescription_upload_review_and_create_reminders(client, auth):
    pdf = _pdf(RX_TEXT.splitlines())
    r = client.post("/api/prescriptions", headers=auth, files={"file": ("rx.pdf", pdf, "application/pdf")})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["doctor"] == "Dr. Neha Kapoor" and d["prescribed_on"] == TODAY.isoformat() and "never suggests" in d["review_note"]
    items = {i["name"]: i for i in d["items"]}
    assert items["Cetirizine"]["include"] and items["Cetirizine"]["times"] == ["21:00"]
    assert items["Cetirizine"]["end_date"] == (TODAY + timedelta(days=9)).isoformat()
    assert not items["Paracetamol"]["include"] and items["Paracetamol"]["as_needed"]
    assert not items["Mystery"]["include"] and items["Mystery"]["needs_review"]
    # nothing is scheduled until the user confirms
    assert client.get("/api/medicines", headers=auth).json() == []

    c = items["Cetirizine"]
    body = {"doctor": d["doctor"], "prescribed_on": d["prescribed_on"], "items": [
        {k: c[k] for k in ("name", "dosage", "times", "frequency", "start_date", "end_date", "notes")}]}
    r = client.post(f"/api/prescriptions/{d['id']}/reminders", headers=auth, json=body)
    assert r.status_code == 201 and r.json()["created"] == 1
    meds = client.get("/api/medicines", headers=auth).json()
    assert meds[0]["prescribed_by"] == "Dr. Neha Kapoor" and meds[0]["prescription_id"] == d["id"]
    lst = client.get("/api/prescriptions", headers=auth).json()
    assert lst[0]["medicines"][0]["name"] == "Cetirizine"
    assert "Cetirizine" in client.get(f"/api/prescriptions/{d['id']}", headers=auth).json()["text"]


def test_prescription_pasted_text(client, auth):
    r = client.post("/api/prescriptions", headers=auth, data={"text": "Tab Omeprazole 20 mg OD x 5 days"})
    assert r.status_code == 201 and r.json()["items"][0]["times"] == ["08:00"]
    assert r.json()["prescribed_on"] == TODAY.isoformat() and r.json()["date_detected"] is False


def test_prescription_validation(client, auth):
    assert client.post("/api/prescriptions", headers=auth, data={"text": "  "}).status_code == 422
    assert client.post("/api/prescriptions", headers=auth, files={"file": ("rx.jpg", b"\xff\xd8", "image/jpeg")}).status_code == 415
    blank_pdf = _pdf([])
    assert client.post("/api/prescriptions", headers=auth, files={"file": ("scan.pdf", blank_pdf, "application/pdf")}).status_code == 422
    pid = client.post("/api/prescriptions", headers=auth, data={"text": RX_TEXT}).json()["id"]
    bad = {"doctor": "", "prescribed_on": TODAY.isoformat(), "items": [
        {"name": "X", "dosage": "1", "times": ["08:00"], "start_date": TODAY.isoformat(), "end_date": (TODAY - timedelta(days=1)).isoformat()}]}
    assert client.post(f"/api/prescriptions/{pid}/reminders", headers=auth, json=bad).status_code == 422
    future = {**bad, "prescribed_on": (TODAY + timedelta(days=3)).isoformat(), "items": [{**bad["items"][0], "end_date": None}]}
    assert client.post(f"/api/prescriptions/{pid}/reminders", headers=auth, json=future).status_code == 422
    assert client.post(f"/api/prescriptions/{pid}/reminders", headers=auth, json={**bad, "items": []}).status_code == 422


def test_prescription_delete_keeps_or_removes_reminders(client, auth, register):
    def make():
        pid = client.post("/api/prescriptions", headers=auth, data={"text": "Tab Omeprazole 20 mg OD x 5 days"}).json()["id"]
        client.post(f"/api/prescriptions/{pid}/reminders", headers=auth, json={"prescribed_on": TODAY.isoformat(), "items": [
            {"name": "Omeprazole", "dosage": "20 mg", "times": ["08:00"], "start_date": TODAY.isoformat()}]})
        return pid
    other = register(client, "rx-other@example.com")
    pid = make()
    assert client.delete(f"/api/prescriptions/{pid}", headers=other).status_code == 404
    assert client.delete(f"/api/prescriptions/{pid}", headers=auth).status_code == 200
    meds = client.get("/api/medicines", headers=auth).json()
    assert len(meds) == 1 and meds[0]["prescription_id"] is None  # reminder kept, unlinked
    pid = make()
    assert client.delete(f"/api/prescriptions/{pid}?with_reminders=true", headers=auth).status_code == 200
    assert len(client.get("/api/medicines", headers=auth).json()) == 1  # the new one was removed


# ---------------- Lab capture and history ----------------
def _upload(client, auth, lines, test_date=None, name="lab.pdf"):
    data = {"test_date": test_date} if test_date else {}
    return client.post("/api/records/reports", headers=auth, data=data, files={"file": (name, _pdf(lines), "application/pdf")})


def test_report_values_are_captured_into_dated_history(client, auth):
    d1 = (TODAY - timedelta(days=60)).isoformat()
    r1 = _upload(client, auth, ["Hemoglobin 11.0 g/dL (12.0 - 15.5)", "Glucose 92 mg/dL (70 - 99)"], test_date=d1)
    assert r1.status_code == 201 and r1.json()["test_date"] == d1 and r1.json()["captured"] == 2
    r2 = _upload(client, auth, [f"Collected on: {DMY}", "Hemoglobin 12.6 g/dL (12.0 - 15.5)", "Glucose 104 mg/dL (70 - 99)"])
    b = r2.json()
    assert b["test_date"] == TODAY.isoformat() and b["date_source"].startswith("detected")
    hb = next(x for x in b["results"] if x["name"] == "Hemoglobin")
    assert hb["status"] == "normal" and hb["previous"]["value"] == 11.0 and hb["previous"]["test_date"] == d1

    hist = client.get("/api/records/labs?test=hemoglobin", headers=auth).json()
    assert [h["value"] for h in hist] == [12.6, 11.0] and hist[0]["report_name"] == "lab.pdf"
    tests = {t["test_name"]: t for t in client.get("/api/records/labs/tests", headers=auth).json()}
    assert tests["Glucose"]["latest_status"] == "high" and tests["Glucose"]["previous_value"] == 92 and tests["Glucose"]["count"] == 2
    assert len(client.get("/api/records/labs?status=high", headers=auth).json()) == 1
    assert len(client.get(f"/api/records/labs?start={TODAY.isoformat()}", headers=auth).json()) == 2

    s = client.post(f"/api/records/reports/{b['id']}/summarize", headers=auth).json()["summary"]
    assert "Glucose" in s and "previously 92" in s and "Hemoglobin is now within" in s


def test_report_date_fallback_and_correction(client, auth):
    r = _upload(client, auth, ["TSH 2.4 uIU/mL (0.4 - 4.0)"]).json()
    assert r["test_date"] == TODAY.isoformat() and r["date_source"].startswith("upload date")
    newd = (TODAY - timedelta(days=10)).isoformat()
    p = client.patch(f"/api/records/reports/{r['id']}", headers=auth, json={"test_date": newd})
    assert p.status_code == 200 and p.json()["test_date"] == newd
    assert client.get("/api/records/labs?test=TSH", headers=auth).json()[0]["test_date"] == newd
    future = (TODAY + timedelta(days=5)).isoformat()
    assert client.patch(f"/api/records/reports/{r['id']}", headers=auth, json={"test_date": future}).status_code == 422
    assert _upload(client, auth, ["TSH 2 (0.4 - 4.0)"], test_date=future).status_code == 422


def test_deleting_report_removes_its_captured_values(client, auth):
    r = _upload(client, auth, ["Vitamin D 18 ng/mL (30 - 100)"]).json()
    assert len(client.get("/api/records/labs", headers=auth).json()) == 1
    assert client.delete(f"/api/records/reports/{r['id']}", headers=auth).status_code == 200
    assert client.get("/api/records/labs", headers=auth).json() == []


def test_manual_lab_entry_and_validation(client, auth):
    d = (TODAY - timedelta(days=3)).isoformat()
    r = client.post("/api/records/labs", headers=auth, json={"test_name": "HbA1c", "value": 6.1, "unit": "%", "ref_low": 4.0, "ref_high": 5.6, "test_date": d})
    assert r.status_code == 201 and r.json()["status"] == "high" and r.json()["source"] == "manual"
    bad = [{"test_name": "X", "value": 1, "test_date": d}, {"test_name": "HbA1c", "value": 1, "ref_low": 4, "test_date": d},
           {"test_name": "HbA1c", "value": 1, "ref_low": 6, "ref_high": 4, "test_date": d},
           {"test_name": "HbA1c", "value": 1, "test_date": (TODAY + timedelta(days=1)).isoformat()}]
    for b in bad:
        assert client.post("/api/records/labs", headers=auth, json=b).status_code == 422, b
    assert client.delete(f"/api/records/labs/{r.json()['id']}", headers=auth).status_code == 200


def test_lab_history_is_private_and_deleted_with_data(client, auth, register):
    _upload(client, auth, ["Platelets 265 (150 - 450)"])
    client.post("/api/prescriptions", headers=auth, data={"text": "Tab Omeprazole 20 mg OD"})
    other = register(client, "lab-other@example.com")
    assert client.get("/api/records/labs", headers=other).json() == []
    assert client.get("/api/prescriptions", headers=other).json() == []
    assert client.delete("/api/account/data", headers=auth).status_code == 200
    assert client.get("/api/records/labs", headers=auth).json() == []
    assert client.get("/api/prescriptions", headers=auth).json() == []


def test_demo_account_has_lab_history_and_linked_prescription(client):
    tok = client.post("/api/auth/login", json={"email": "demo@healthmate.ai", "password": "Demo@1234"}).json()["token"]
    h = {"Authorization": "Bearer " + tok}
    tests = client.get("/api/records/labs/tests", headers=h).json()
    assert len(tests) == 5 and all(t["count"] == 3 for t in tests)
    assert all(m["prescribed_by"] for m in client.get("/api/medicines", headers=h).json())


def test_pdf_report_includes_lab_section(client, auth):
    _upload(client, auth, ["Hemoglobin 11.0 g/dL (12.0 - 15.5)"])
    r = client.get("/api/report/pdf", headers=auth)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
