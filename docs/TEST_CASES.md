# Test cases and results

Both suites were run against this code. Results are at the bottom.

## A. Automated API tests (`backend/tests/test_api.py`, pytest)

| Area | Test case | Expected |
|---|---|---|
| Auth | Register, login (case-insensitive email), `/me` | 201, token, no password hash returned |
| Auth | Weak password, no digit, bad email, duplicate email | 422 / 422 / 422 / 409 |
| Auth | Wrong password, no token, garbage token | 401 |
| Auth | Demo account seeded | login works, 3 medicines, 12 or more records, 2 or more upcoming appointments |
| Auth | Profile update | allergies saved |
| Safety | Emergency patterns, self-harm, normal question | detected / `self-harm` / none |
| Safety | PII redaction | name, email and phone removed |
| Chat | Normal question in demo mode | `mode=demo`, label shown, disclaimer present |
| Chat | "chest pain and can't breathe" | `mode=safety`, emergency flag, 112 shown, no AI call |
| Chat | Self-harm message | helpline 14416 shown |
| Chat | "What are common causes of chest pain?" | not blocked |
| Chat | History, clear history, empty or oversized message | persisted, cleared, 422 |
| Chat | Explain term "Hemoglobin" | correct explanation |
| Symptoms | Mild headache | `self_care`, warning signs listed, doctor summary |
| Symptoms | Red-flag symptom, or red-flag text in notes | `emergency`, no explanations |
| Symptoms | Fever for 3 days | `soon` |
| Symptoms | Unknown symptom, bad severity, empty list | 422 |
| Medicines | Create, schedule (overdue and pending), log taken and skipped, history, deactivate, delete | all correct |
| Medicines | Bad time, no times, empty name, end date before start | 422 |
| Medicines | Other user's medicine | 404 |
| Records | Create, search, metric filter, delete | correct |
| Records | No value, BP with one number, diastolic above systolic, temp 60, bad date | 422 |
| Reports | Parse formats, flag low, high and normal | correct |
| Reports | Upload PDF, summarize, list, delete | works, summary says "not a diagnosis" |
| Reports | `.exe`, fake PDF, 5 MB or larger | 415 / 415 / 413 |
| Wellness | Upsert, progress %, weekly summary, suggestions, validation | correct |
| Appointments | Create, update, list, delete, validation | correct |
| Dashboard | New user | all zeros, 7 wellness days |
| PDF | Generate | valid `%PDF` file |
| Privacy | Delete data, delete account | data gone, account kept or removed |
| Privacy | Two users | no cross-user data |
| Robustness | 60 concurrent requests | all 200 (regression for the SQLite threading bug) |

## B. Browser end-to-end test (`e2e/e2e_test.py`, Playwright and Edge)

| # | Step | Expected |
|---|---|---|
| 01 | Login page | form, demo credentials and disclaimer visible |
| 02 | Wrong password | error alert |
| 03 | Register with a weak and then a strong password | validation error, then dashboard |
| 04 | Demo login | KPIs, schedule, charts and appointments render |
| 05 | Mark a dose taken | status updates |
| 06 | Dashboard "Ask AI" | opens chat with an answer labelled Demo mode |
| 07 | Chat suggested question | answer appears, welcome message visible |
| 08 | Emergency message | red emergency bubble, "Safety rule" badge |
| 09 | Reload, then Clear chat | history persists, then clears |
| 10 | Symptom checker with mild symptoms | explanations, warning signs, doctor summary |
| 11 | Red-flag symptom | emergency banner |
| 12 | Add medicine, then mark taken | listed, scheduled, history updated |
| 13 | End date before start | validation error |
| 14 | Add record, search, charts | row shown, charts drawn |
| 15 | Invalid BP | error |
| 16 | Explain term, upload report, summarize | LOW flag and "within range" shown |
| 17 | Wellness save and suggestions | "Saved!" and labelled tips |
| 18 | Add and complete an appointment | moves to history |
| 19 | Generate PDF | downloaded file is a valid PDF |
| 20 | Settings: profile, dark mode, AI mode | saved, dark class toggles |
| 21 | Wrong current password | error |
| 22 | Delete all data (throwaway user) | records gone |
| 23 | Mobile 390px | hamburger menu works, no horizontal scroll |
| 24 | Logged-out visit to `/records` | redirected to login |

## C. Results (run on 15 Nov 2026)

* `pytest`: **36 passed**
* Browser e2e: **24 of 24 steps passed**, with no unexpected browser console errors.
* Bugs found by testing and fixed:
  1. Intermittent HTTP 500 on random requests. SQLite connections were bound to one thread but FastAPI used several. Fixed with `check_same_thread=False`, and a concurrency regression test was added.
  2. Mobile header overflowed the screen (418px on a 390px display). Fixed by tightening the header.
  3. Async upload endpoint hit the same threading problem. It is now a sync endpoint.

## D. Not verified

* **Live Gemini responses:** no API key was available. The live path and its fallback to demo mode are implemented but untested against the real service.
* **Browser notifications:** the permission and trigger code is implemented, but headless tests cannot show OS notifications.
* **Voice input and text-to-speech:** depend on the browser and a microphone or speakers, so they were not exercised.
* **Accessibility:** labels, roles and keyboard focus styles were added. Full WCAG validation needs manual testing with assistive technology.
* **Safari, Firefox:** only Microsoft Edge (Chromium) was tested.
