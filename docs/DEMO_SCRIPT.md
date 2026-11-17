# Live demo script (about 8 minutes)

1. **Start:** `cd backend; python -m uvicorn app.main:app --port 8000`, then open http://127.0.0.1:8000
2. **Login page:** point out the demo credentials and disclaimer. Click *Fill demo credentials*, then *Log in*.
3. **Dashboard:** KPIs, today's medicine schedule (press *Taken*), charts, appointments. Toggle dark mode.
4. **AI Health Chat:** click *How can I improve my sleep?*. Note the **Demo mode** badge (honest labelling). Press *Listen* for text-to-speech.
   Then type *I have severe chest pain and can't breathe* to show the **emergency safety rule** answering instantly.
5. **Symptom Info:** select Headache + Fever, 3 days, mild. Show the urgency level, warning signs and the doctor summary (Copy). Add
   *Chest pain or pressure* to show the emergency banner.
6. **Medicines:** add a reminder, mark it taken, show history and *Enable browser notifications*.
7. **Health Records:** add a record, show charts and search. Upload `sample_data/sample_lab_report.pdf`, show **LOW/HIGH flags**
   compared with the report's own ranges, then press *Summarize*. Try the term explainer ("hemoglobin").
8. **Wellness:** log water, sleep and activity, show the weekly summary and habit suggestions.
9. **Appointments:** add one and mark it completed.
10. **Health Report:** download the PDF and open it.
11. **Settings:** edit profile and goals. Show *AI service: Demo mode* and the data-deletion buttons.
12. **Mobile:** resize the browser narrow (or use device mode) to show the responsive menu.

**Talking points:** safety rules run before the AI; urgency is rule-based; no doses are ever recommended; the API key stays on the server;
only redacted question text is sent to the AI; demo mode is labelled, not disguised as AI.

**If asked about live AI:** put `GEMINI_API_KEY` in `backend/.env`, restart, and the badges change to *Live AI*.
