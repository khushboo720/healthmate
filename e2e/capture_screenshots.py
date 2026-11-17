"""Captures clean screenshots of every page with the seeded demo account (used in docs and the presentation).
Run on a freshly seeded database with the app on :8000:  python e2e/capture_screenshots.py"""
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
SAMPLE_LAB = ROOT / "sample_data" / "sample_lab_report.pdf"
SAMPLE_RX = ROOT / "sample_data" / "sample_prescription.pdf"
# Full-page stitching renders sticky bars mid-image; make them static just for capture.
FLAT = "header.sticky{position:static!important} aside.sticky{position:static!important;height:auto!important}"

with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge", headless=True)

    def snap(page, name, **kw):
        page.add_style_tag(content=FLAT)
        page.screenshot(path=str(OUT / f"{name}.png"), **kw)

    def part(page, selector, name):
        page.add_style_tag(content=FLAT)
        page.locator(selector).first.screenshot(path=str(OUT / f"{name}.png"))

    def login(ctx, shot_login=False):
        p = ctx.new_page()
        p.goto(BASE)
        expect(p.get_by_role("button", name="Fill demo credentials")).to_be_visible()
        if shot_login:
            p.screenshot(path=str(OUT / "01-login.png"))
        p.get_by_role("button", name="Fill demo credentials").click()
        p.get_by_role("button", name="Log in").click()
        expect(p.get_by_text("Total health records")).to_be_visible()
        return p

    ctx = b.new_context(viewport={"width": 1366, "height": 768})
    p = login(ctx, shot_login=True)
    p.wait_for_timeout(1500)
    snap(p, "02-dashboard", full_page=True)

    p.goto(BASE + "/chat")
    p.get_by_role("button", name="How can I improve my sleep?").click()
    expect(p.get_by_text("fixed sleep and wake times", exact=False)).to_be_visible(timeout=10000)
    p.get_by_label("Your health question").fill("I have severe chest pain and can't breathe")
    p.get_by_role("button", name="Send").click()
    expect(p.get_by_text("This may be a medical emergency", exact=False)).to_be_visible()
    snap(p, "03-chat", full_page=True)

    p.goto(BASE + "/symptoms")
    for s in ("Headache", "Fever", "Fatigue"):
        p.get_by_role("button", name=s, exact=True).click()
    p.get_by_label("How long (days)?").fill("3")
    p.get_by_role("button", name="Get information").click()
    expect(p.get_by_text("Summary to share with your doctor")).to_be_visible()
    snap(p, "04-symptoms", full_page=True)

    p.goto(BASE + "/medicines")
    p.wait_for_timeout(800)
    snap(p, "05-medicines", full_page=True)
    p.get_by_label("Choose prescription file").set_input_files(str(SAMPLE_RX))
    p.get_by_role("button", name="Read prescription").click()
    expect(p.get_by_text("never suggests or changes doses", exact=False)).to_be_visible()
    part(p, "section[aria-labelledby=rx-h]", "05b-prescription-review")
    p.get_by_role("button", name="Cancel", exact=True).click()  # discard the draft so demo data stays clean

    p.goto(BASE + "/records")
    p.wait_for_timeout(1000)
    p.get_by_label("Choose report file").set_input_files(str(SAMPLE_LAB))
    p.get_by_role("button", name="Upload & capture values").click()
    expect(p.get_by_text("Captured", exact=False).first).to_be_visible()
    rep = p.locator("section[aria-labelledby=reports-h]")
    rep.get_by_role("button", name="Summarize").click()
    expect(rep.get_by_text("not a diagnosis", exact=False).first).to_be_visible()
    p.locator("section[aria-labelledby=labs-h]").get_by_role("button", name="Vitamin D").click()
    p.wait_for_timeout(1200)
    part(p, "section[aria-labelledby=reports-h]", "06b-test-report")
    part(p, "section[aria-labelledby=labs-h]", "06c-lab-history")
    snap(p, "06-records", full_page=True)

    for name, path, wait in (("07-wellness", "/wellness", 1500), ("08-appointments", "/appointments", 500),
                             ("09-report", "/report", 300), ("10-settings", "/settings", 300)):
        p.goto(BASE + path)
        p.wait_for_timeout(wait)
        snap(p, name, full_page=True)

    p.get_by_role("button", name="Switch to dark mode").first.click()
    p.goto(BASE + "/")
    p.wait_for_timeout(1500)
    snap(p, "13-dashboard-dark", full_page=True)
    ctx.close()

    m = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    mp = login(m)
    mp.wait_for_timeout(1500)
    snap(mp, "11-mobile-dashboard", full_page=True)
    mp.get_by_role("button", name="Open menu").click()
    mp.screenshot(path=str(OUT / "12-mobile-menu.png"))
    b.close()
print("screenshots saved to", OUT)
