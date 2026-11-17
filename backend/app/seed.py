"""Synthetic demo data (fictional person). Dates are relative to today so the demo always looks fresh."""
import json
import random
from datetime import date, datetime, timedelta

from .config import DEMO_EMAIL, DEMO_PASSWORD
from .db import connect, row
from .security import hash_password


def seed_demo() -> None:
    db = connect()
    try:
        if row(db, "SELECT id FROM users WHERE email=?", (DEMO_EMAIL,)):
            return
        rnd = random.Random(42)
        today = date.today()
        cur = db.execute(
            """INSERT INTO users (email, name, password_hash, age, gender, blood_group, allergies, medical_history)
               VALUES (?,?,?,?,?,?,?,?)""",
            (DEMO_EMAIL, "Demo User (Sample Data)", hash_password(DEMO_PASSWORD), 28, "Female", "B+",
             "Dust (sample data)", "Seasonal allergic rhinitis (sample data)"))
        uid = cur.lastrowid

        for i in range(12):  # about 3 months of readings, oldest first
            d = today - timedelta(days=(11 - i) * 7)
            db.execute(
                """INSERT INTO health_records (user_id, recorded_at, weight_kg, height_cm, systolic, diastolic, glucose_mgdl, temperature_c, notes)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (uid, d.isoformat(), round(63.5 - i * 0.2 + rnd.uniform(-0.3, 0.3), 1), 165,
                 118 + rnd.randint(-6, 8), 78 + rnd.randint(-4, 5), round(92 + rnd.uniform(-8, 12), 1),
                 round(36.6 + rnd.uniform(-0.2, 0.4), 1), "Morning reading (sample)" if i % 3 == 0 else ""))

        meds = [("Vitamin D3", "1 capsule (as prescribed)", ["09:00"], "weekly"),
                ("Iron + Folic acid", "1 tablet (as prescribed)", ["08:30", "20:30"], "daily"),
                ("Antihistamine (sample)", "1 tablet (as prescribed)", ["21:30"], "daily")]
        start = (today - timedelta(days=14)).isoformat()
        # A synthetic typed prescription that the demo reminders are linked to.
        rx_text = (f"Dr. A. Mehta (sample)\nCity Care Clinic (sample)\nDate: {start}\nRx\n"
                   "1. Vitamin D3 60000 IU once weekly for 8 weeks\n2. Iron + Folic acid 1 tablet twice daily after food\n"
                   "3. Tab Antihistamine 10 mg at night for 2 months\n")
        rx_id = db.execute("INSERT INTO prescriptions (user_id, doctor, prescribed_on, notes, extracted_text) VALUES (?,?,?,?,?)",
                           (uid, "Dr. A. Mehta (sample)", start, "Sample prescription (synthetic data)", rx_text)).lastrowid
        med_ids = []
        for name, dose, times, freq in meds:
            c = db.execute("INSERT INTO medicines (user_id,name,dosage,times,frequency,start_date,end_date,notes,active,prescription_id) VALUES (?,?,?,?,?,?,?,?,1,?)",
                           (uid, name, dose, json.dumps(times), freq, start, (today + timedelta(days=45)).isoformat(), "Sample data", rx_id))
            med_ids.append((c.lastrowid, times, freq))

        # Lab history from three earlier (synthetic) check-ups, so trends are visible straight away.
        labs = [("Hemoglobin", "g/dL", 12.0, 15.5, [10.9, 11.4, 11.9]), ("Fasting Glucose", "mg/dL", 70, 99, [97, 103, 95]),
                ("Vitamin D", "ng/mL", 30, 100, [15, 21, 27]), ("Total Cholesterol", "mg/dL", 0, 200, [196, 188, 179]),
                ("TSH", "uIU/mL", 0.4, 4.0, [2.1, 2.6, 2.3])]
        for i, back in enumerate((150, 95, 40)):
            d = (today - timedelta(days=back)).isoformat()
            for name, unit, lo, hi, values in labs:
                v = values[i]
                status = "low" if v < lo else "high" if v > hi else "normal"
                db.execute("""INSERT INTO lab_results (user_id, report_id, test_name, test_key, value, unit, ref_low, ref_high, status, test_date, source)
                              VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (uid, None, name, name.lower(), v, unit, lo, hi, status, d, "sample"))
        for back in range(1, 8):  # past 7 days of dose logs
            day = today - timedelta(days=back)
            delta = (day - (today - timedelta(days=14))).days
            for mid, times, freq in med_ids:
                if freq == "weekly" and delta % 7 != 0:
                    continue
                for t in times:
                    status = "taken" if rnd.random() > 0.15 else "skipped"
                    db.execute("INSERT OR IGNORE INTO medicine_logs (user_id, medicine_id, scheduled_for, status) VALUES (?,?,?,?)",
                               (uid, mid, f"{day.isoformat()} {t}", status))

        for back in range(0, 14):
            d = today - timedelta(days=back)
            db.execute("INSERT INTO wellness_logs (user_id, log_date, water_ml, sleep_hours, activity_min, mood) VALUES (?,?,?,?,?,?)",
                       (uid, d.isoformat(), rnd.randint(1400, 2800), round(rnd.uniform(5.8, 8.4), 1), rnd.randint(10, 55),
                        rnd.choice(["Happy", "Calm", "Tired", "Good"])))

        def at(days: int, hhmm: str) -> str:
            return f"{(today + timedelta(days=days)).isoformat()} {hhmm}"
        appts = [("Dr. A. Mehta (sample)", "General Physician", "City Care Clinic (sample)", at(2, "10:30"), "Routine check-up", "upcoming"),
                 ("Dr. S. Rao (sample)", "Dermatologist", "Green Valley Hospital (sample)", at(9, "16:00"), "Skin allergy review", "upcoming"),
                 ("Dr. K. Iyer (sample)", "Dentist", "SmileCare Dental (sample)", at(-20, "11:00"), "Dental cleaning", "completed")]
        for doc, spec, clinic, when, purpose, status in appts:
            db.execute("INSERT INTO appointments (user_id,doctor,specialization,clinic,scheduled_at,purpose,status) VALUES (?,?,?,?,?,?,?)",
                       (uid, doc, spec, clinic, when, purpose, status))
        db.commit()
    finally:
        db.close()
