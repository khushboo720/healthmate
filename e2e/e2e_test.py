"""End-to-end browser test + screenshot capture (Playwright, Microsoft Edge).
Usage: start the app on http://127.0.0.1:8000 (see README), then run:  python e2e/e2e_test.py
"""
import sys
import tempfile
import traceback
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
SHOTS = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)
SAMPLE_RX = Path(__file__).resolve().parent.parent / "sample_data" / "sample_prescription.pdf"
results: list[tuple[str, bool, str]] = []
console_errors: list[str] = []


def step(name):
    def deco(fn):
        try:
            fn()
            results.append((name, True, ""))
            print(f"PASS  {name}")
        except Exception as e:  # noqa: BLE001
            results.append((name, False, str(e).splitlines()[0][:200]))
            print(f"FAIL  {name}: {str(e).splitlines()[0][:200]}")
            traceback.print_exc(limit=1)
        return fn
    return deco


with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge", headless=True)
    ctx = browser.new_context(viewport={"width": 1366, "height": 900}, accept_downloads=True)
    page = ctx.new_page()
    page.on("console", lambda m: m.type == "error" and console_errors.append(m.text))
    page.on("pageerror", lambda e: console_errors.append(str(e)))
    shot = lambda n: page.screenshot(path=str(SHOTS / f"{n}.png"), full_page=True)

    @step("01 Login page loads and shows demo credentials + disclaimer")
    def _():
        page.goto(BASE)
        expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
        expect(page.get_by_text("demo@healthmate.ai / Demo@1234")).to_be_visible()
        expect(page.get_by_text("not a medical diagnosis", exact=False).first).to_be_visible()
        shot("01-login")

    @step("02 Wrong password shows an error")
    def _():
        page.get_by_label("Email").fill("demo@healthmate.ai")
        page.get_by_label("Password").fill("WrongPass1")
        page.get_by_role("button", name="Log in").click()
        expect(page.get_by_role("alert")).to_contain_text("Incorrect email or password")

    @step("03 Registration validation (weak password) and successful registration")
    def _():
        page.get_by_role("button", name="New here? Create an account").click()
        page.get_by_label("Full name").fill("E2E Tester")
        page.get_by_label("Email").fill(f"e2e{date.today().toordinal()}{id(page) % 9999}@example.com")
        page.get_by_label("Password").fill("weakpass")
        page.get_by_role("button", name="Create account").click()
        expect(page.get_by_role("alert")).to_contain_text("letter and a number")
        page.get_by_label("Password").fill("Strong1234")
        page.get_by_role("button", name="Create account").click()
        expect(page.get_by_text("Good", exact=False).first).to_be_visible()
        expect(page.get_by_text("0%").first).to_be_visible()
        # log out
        page.get_by_role("button", name="Log out").click()
        expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()

    @step("04 Demo login opens dashboard with KPIs, schedule, charts, appointments")
    def _():
        page.get_by_role("button", name="Fill demo credentials").click()
        page.get_by_role("button", name="Log in").click()
        expect(page.get_by_text("Total health records")).to_be_visible()
        expect(page.get_by_text("Today's medicine schedule")).to_be_visible()
        expect(page.get_by_text("Upcoming doctor appointments")).to_be_visible()
        expect(page.get_by_text("Dr. A. Mehta (sample)").first).to_be_visible()
        page.wait_for_timeout(1200)
        shot("02-dashboard")

    @step("05 Dashboard: mark a dose as taken")
    def _():
        btn = page.get_by_role("button", name="Mark", exact=False).filter(has_text="Taken").first
        if btn.count():
            btn.click()
            page.wait_for_timeout(600)

    @step("06 Dashboard 'Ask AI' navigates to chat and gets a labelled demo answer")
    def _():
        page.goto(BASE + "/")
        page.get_by_label("Ask the AI health assistant").fill("How can I improve my sleep?")
        page.get_by_role("button", name="Ask").click()
        expect(page.get_by_text("fixed sleep and wake times", exact=False)).to_be_visible(timeout=10000)
        expect(page.get_by_text("Demo mode: pre-written", exact=False).first).to_be_visible()

    @step("07 Chat: suggested question, welcome message, typing indicator, history")
    def _():
        expect(page.get_by_text("Hello! Welcome to HealthMate AI")).to_be_visible()
        page.get_by_role("button", name="What are common symptoms of dehydration?").click()
        expect(page.get_by_text("Dark yellow urine", exact=False)).to_be_visible(timeout=10000)
        shot("03-chat")

    @step("08 Chat: emergency message short-circuits with emergency numbers")
    def _():
        page.get_by_label("Your health question").fill("I have severe chest pain and can't breathe")
        page.get_by_role("button", name="Send").click()
        expect(page.get_by_text("This may be a medical emergency", exact=False)).to_be_visible(timeout=10000)
        expect(page.get_by_text("Safety rule").first).to_be_visible()
        shot("03b-chat-emergency")

    @step("09 Chat: history persists after reload, clear chat works")
    def _():
        page.reload()
        expect(page.get_by_text("This may be a medical emergency", exact=False)).to_be_visible()
        page.once("dialog", lambda d: d.accept())
        page.get_by_role("button", name="Clear chat").click()
        expect(page.get_by_text("This may be a medical emergency", exact=False)).to_have_count(0)

    @step("10 Symptom checker: mild symptoms -> info, warning signs, doctor summary")
    def _():
        page.get_by_role("link", name="Symptom Info").click()
        page.get_by_role("button", name="Headache", exact=True).click()
        page.get_by_role("button", name="Fatigue", exact=True).click()
        page.get_by_role("button", name="Get information").click()
        expect(page.get_by_text("Possible general explanations")).to_be_visible()
        expect(page.get_by_text("Summary to share with your doctor")).to_be_visible()
        expect(page.get_by_text("Symptoms: Headache, Fatigue")).to_be_visible()
        shot("04-symptoms")

    @step("11 Symptom checker: red-flag symptom shows emergency guidance")
    def _():
        page.get_by_role("button", name="⚠ Chest pain or pressure").click()
        page.get_by_role("button", name="Get information").click()
        expect(page.get_by_text("Emergency guidance")).to_be_visible()
        expect(page.get_by_text("Seek emergency care now").first).to_be_visible()
        shot("04b-symptoms-emergency")

    @step("12 Medicines: add reminder, appears in list and today's schedule; mark taken")
    def _():
        page.get_by_role("link", name="Medicines").click()
        page.get_by_label("Medicine name").fill("E2E Vitamin C")
        page.get_by_label("Dosage (exactly as prescribed)").fill("1 tablet after lunch")
        page.get_by_label("Reminder time 1").fill("00:05")
        page.get_by_role("button", name="Add reminder").click()
        expect(page.get_by_role("cell", name="E2E Vitamin C", exact=True)).to_be_visible()
        expect(page.get_by_text("00:05 · E2E Vitamin C")).to_be_visible()
        page.get_by_role("listitem").filter(has_text="E2E Vitamin C").get_by_role("button", name="Taken").click()
        expect(page.get_by_role("cell", name="taken").first).to_be_visible()
        shot("05-medicines")

    @step("13 Medicines: validation error for end date before start")
    def _():
        page.get_by_label("Medicine name").fill("Bad Dates")
        page.get_by_label("Dosage (exactly as prescribed)").fill("x")
        page.get_by_label("Start date").fill(str(date.today()))
        page.get_by_label("End date (duration)").evaluate("e => e.removeAttribute('min')")
        page.get_by_label("End date (duration)").fill(str(date.today() - timedelta(days=2)))
        page.get_by_role("button", name="Add reminder").click()
        expect(page.get_by_role("alert")).to_contain_text("End date cannot be before start date")

    @step("13b Prescription: upload PDF, review captured medicines, create linked reminders")
    def _():
        page.get_by_label("Choose prescription file").set_input_files(str(SAMPLE_RX))
        page.get_by_role("button", name="Read prescription").click()
        expect(page.get_by_text("never suggests or changes doses", exact=False)).to_be_visible()
        expect(page.get_by_label("Prescribed by")).to_have_value("Dr. Neha Kapoor")
        expect(page.get_by_label("Medicine name 1")).to_have_value("Cetirizine")
        expect(page.get_by_label("Times 1")).to_have_value("21:00")
        expect(page.get_by_text("AS NEEDED · NO FIXED TIME")).to_be_visible()
        shot("05b-prescription-review")
        page.get_by_role("button", name="Create 4 reminder(s)").click()
        expect(page.get_by_text("4 reminder(s) created from the prescription", exact=False)).to_be_visible()
        expect(page.get_by_role("cell", name="Cetirizine", exact=True)).to_be_visible()
        expect(page.get_by_role("listitem").filter(has_text="Dr. Neha Kapoor").first).to_be_visible()

    @step("14 Health records: add record, filter, charts render")
    def _():
        page.get_by_role("link", name="Health Records").click()
        page.get_by_label("Weight (kg)").fill("61.5")
        page.get_by_label("BP systolic").fill("118")
        page.get_by_label("BP diastolic").fill("76")
        page.get_by_label("Notes", exact=True).fill("e2e morning reading")
        page.get_by_role("button", name="Save record").click()
        page.get_by_label("Search notes").fill("e2e morning")
        expect(page.get_by_role("cell", name="e2e morning reading")).to_be_visible()
        page.get_by_label("Search notes").fill("")
        expect(page.locator(".recharts-line").first).to_be_visible()

    @step("15 Health records: invalid BP rejected (diastolic >= systolic)")
    def _():
        page.get_by_label("BP systolic").fill("100")
        page.get_by_label("BP diastolic").fill("120")
        page.get_by_role("button", name="Save record").click()
        expect(page.get_by_role("alert")).to_contain_text("Diastolic")

    @step("16 Health records: explain term + upload report highlights out-of-range")
    def _():
        page.get_by_label("Medical term").fill("hemoglobin")
        page.get_by_role("button", name="Explain", exact=True).click()
        expect(page.get_by_text("carries oxygen", exact=False)).to_be_visible()
        tmp = Path(tempfile.gettempdir()) / "e2e_report.txt"
        collected = (date.today() - timedelta(days=1)).strftime("%d/%m/%Y")
        tmp.write_text(f"Patient Name: Sample Person\nCollected on: {collected}\nHemoglobin 11.2 g/dL (12.0 - 15.5)\nGlucose 92 mg/dL (70 - 99)\n",
                       encoding="utf-8")
        page.get_by_label("Choose report file").set_input_files(str(tmp))
        page.get_by_role("button", name="Upload & capture values").click()
        expect(page.get_by_text("Captured 2 value(s)", exact=False)).to_be_visible()
        expect(page.get_by_text("detected from report", exact=False)).to_be_visible()
        rep = page.locator("section[aria-labelledby=reports-h]")
        expect(rep.get_by_text("LOW", exact=True)).to_be_visible()
        expect(rep.get_by_text("within range").first).to_be_visible()
        expect(rep.get_by_text("11.9 on", exact=False)).to_be_visible()  # previous Hemoglobin value from history
        rep.get_by_role("button", name="Summarize").click()
        expect(rep.get_by_text("not a diagnosis", exact=False).first).to_be_visible()

    @step("16b Lab history: captured values, trend chart with reference band, filters, manual entry")
    def _():
        sec = page.locator("section[aria-labelledby=labs-h]")
        sec.get_by_role("button", name="Hemoglobin").click()
        expect(sec.get_by_role("img", name="Hemoglobin trend chart")).to_be_visible()
        expect(sec.locator("[class*=recharts-reference-area]").first).to_be_visible()
        sec.get_by_label("Filter by test").select_option(label="Hemoglobin")
        expect(sec.locator("tbody tr")).to_have_count(4)  # 3 sample check-ups + the uploaded report
        expect(sec.get_by_role("cell", name="e2e_report.txt")).to_be_visible()
        sec.get_by_label("Filter by test").select_option("")
        sec.get_by_label("Test name").fill("HbA1c")
        sec.get_by_label("Value").fill("6.1")
        sec.get_by_label("Unit").fill("%")
        sec.get_by_label("Range low").fill("4")
        sec.get_by_label("Range high").fill("5.6")
        sec.get_by_role("button", name="Add value").click()
        expect(sec.get_by_role("button", name="HbA1c")).to_be_visible()
        page.wait_for_timeout(800)
        shot("06-records")

    @step("17 Wellness: save today's log, summary, suggestions")
    def _():
        page.get_by_role("link", name="Wellness").click()
        page.get_by_role("button", name="+250 ml water").click()
        page.get_by_role("button", name="Save today").click()
        expect(page.get_by_role("button", name="Saved!")).to_be_visible()
        page.get_by_role("button", name="Get suggestions").click()
        expect(page.get_by_text("Demo mode", exact=False).first).to_be_visible()
        page.wait_for_timeout(800)
        shot("07-wellness")

    @step("18 Appointments: add and see under upcoming; mark completed")
    def _():
        page.get_by_role("link", name="Appointments").click()
        page.get_by_label("Doctor name").fill("Dr. E2E Test")
        page.get_by_label("Specialization").fill("Tester")
        page.get_by_label("Date").fill(str(date.today() + timedelta(days=3)))
        page.get_by_label("Purpose").fill("e2e purpose")
        page.get_by_role("button", name="Add appointment").click()
        expect(page.get_by_text("Dr. E2E Test")).to_be_visible()
        shot("08-appointments")
        page.get_by_role("listitem").filter(has_text="Dr. E2E Test").get_by_role("button", name="Mark completed").click()
        expect(page.get_by_role("cell", name="completed").first).to_be_visible()

    @step("19 Report: PDF downloads and is a valid PDF")
    def _():
        page.get_by_role("link", name="Health Report").click()
        with page.expect_download() as dl:
            page.get_by_role("button", name="Generate & download PDF").click()
        path = Path(dl.value.path())
        assert path.read_bytes().startswith(b"%PDF"), "not a PDF"
        import fitz  # PyMuPDF: check the new sections are really in the PDF
        text = " ".join(" ".join(p.get_text() for p in fitz.open(str(path))).split())  # table cells wrap onto new lines
        for needle in ("Lab test results", "Hemoglobin", "Prescribed by", "Dr. Neha Kapoor", "NOT a medical diagnosis"):
            assert needle in text, f"PDF is missing '{needle}'"
        (SHOTS.parent / "sample-health-report.pdf").write_bytes(path.read_bytes())
        shot("09-report")

    @step("20 Settings: update profile, dark mode, AI mode shown")
    def _():
        page.get_by_role("link", name="Profile & Settings").click()
        page.get_by_label("Allergies").fill("Pollen (e2e)")
        page.get_by_role("button", name="Save profile").click()
        expect(page.get_by_text("Profile saved.")).to_be_visible()
        expect(page.get_by_text("Demo mode").first).to_be_visible()
        page.get_by_role("button", name="Switch to dark").first.click()
        assert page.evaluate("document.documentElement.classList.contains('dark')")
        page.wait_for_timeout(300)
        shot("10-settings-dark")
        page.get_by_role("button", name="Switch to light").first.click()

    @step("21 Settings: wrong current password rejected")
    def _():
        page.get_by_label("Current password").fill("NotRight123")
        page.get_by_label("New password").fill("Another1234")
        page.get_by_role("button", name="Update password").click()
        expect(page.get_by_role("alert")).to_contain_text("incorrect")

    @step("22 Data deletion: 'Delete all my health data' wipes records (throwaway user, demo data is kept)")
    def _():
        page.get_by_role("button", name="Log out").click()
        page.get_by_role("button", name="New here? Create an account").click()
        page.get_by_label("Full name").fill("Throwaway User")
        page.get_by_label("Email").fill(f"throwaway{date.today().toordinal()}{id(page) % 9999}@example.com")
        page.get_by_label("Password").fill("Strong1234")
        page.get_by_role("button", name="Create account").click()
        page.get_by_role("link", name="Health Records").click()
        page.get_by_label("Weight (kg)").fill("70")
        page.get_by_role("button", name="Save record").click()
        expect(page.get_by_role("cell", name="70", exact=True).first).to_be_visible()
        page.get_by_role("link", name="Profile & Settings").click()
        page.once("dialog", lambda d: d.accept())
        page.get_by_role("button", name="Delete all my health data").click()
        expect(page.get_by_text("All your health data was deleted.")).to_be_visible()
        page.get_by_role("link", name="Health Records").click()
        expect(page.get_by_text("No records match.")).to_be_visible()

    @step("23 Mobile layout: hamburger menu opens, navigation works, no horizontal scroll")
    def _():
        page.get_by_role("button", name="Log out").click()
        page.wait_for_timeout(300)
        mobile = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        mp = mobile.new_page()
        mp.on("console", lambda m: m.type == "error" and console_errors.append(m.text))
        mp.goto(BASE)
        mp.get_by_role("button", name="Fill demo credentials").click()
        mp.get_by_role("button", name="Log in").click()
        expect(mp.get_by_text("Total health records")).to_be_visible()
        mp.wait_for_timeout(1200)
        assert mp.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "horizontal overflow on mobile dashboard"
        mp.screenshot(path=str(SHOTS / "11-mobile-dashboard.png"), full_page=True)
        mp.get_by_role("button", name="Open menu").click()
        mp.screenshot(path=str(SHOTS / "12-mobile-menu.png"))
        mp.get_by_role("link", name="AI Health Chat").click()
        expect(mp.get_by_role("heading", name="AI Health Chat")).to_be_visible()
        assert mp.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "horizontal overflow on mobile chat"
        mobile.close()

    @step("24 Unauthenticated access redirects to login")
    def _():
        c2 = browser.new_context()
        p2 = c2.new_page()
        p2.goto(BASE + "/records")
        expect(p2.get_by_role("heading", name="Welcome back")).to_be_visible()
        c2.close()

    browser.close()

real_errors = [e for e in console_errors if "401" not in e and "409" not in e and "422" not in e and "400" not in e and "Failed to load resource" not in e]
print("\nConsole errors (excluding expected HTTP 4xx from negative tests):", real_errors or "none")
failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} steps passed")
sys.exit(1 if failed or real_errors else 0)
