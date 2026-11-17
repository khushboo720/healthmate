# HealthMate AI: REST API

Base URL: `http://127.0.0.1:8000`. Interactive Swagger docs: `/docs`.
All endpoints except register and login need the header `Authorization: Bearer <token>`.
Errors return `{"detail": "..."}` (or a list of validation errors for 422). Statuses: 400 bad request, 401 unauthenticated,
404 not found (including other users' records), 409 duplicate, 413 file too large, 415 unsupported file, 422 validation, 429 too many logins.

## Auth and account
| Method | Path | Body / notes |
|---|---|---|
| POST | `/api/auth/register` | `{name, email, password (8+ chars, letter+digit), age?}` returns `{token, user}` |
| POST | `/api/auth/login` | `{email, password}` returns `{token, user}` (throttled after repeated failures) |
| GET | `/api/auth/me` | current user |
| PUT | `/api/auth/profile` | `{name, age, gender, blood_group, allergies, medical_history, water_goal_ml, sleep_goal_h, activity_goal_min}` |
| POST | `/api/auth/change-password` | `{current_password, new_password}` |
| DELETE | `/api/account/data` | deletes all health data, keeps the account |
| DELETE | `/api/account` | deletes the account and everything |
| GET | `/api/status` | `{mode: "live"\|"demo", model}` |

## Dashboard
`GET /api/dashboard?now=YYYY-MM-DD HH:MM` returns KPIs, today's medicine schedule, latest metrics, metric series, 7-day wellness,
upcoming appointments and notifications.

## Chatbot
| Method | Path | Notes |
|---|---|---|
| GET | `/api/chat/history` | `{welcome, messages[], ai, disclaimer}` |
| POST | `/api/chat` | `{message (1-1000 chars)}` returns `{id, reply, mode: "live"\|"demo"\|"safety", emergency, demo_label, disclaimer}` |
| DELETE | `/api/chat/history` | clears the conversation |
| POST | `/api/chat/explain-term` | `{term}` returns `{term, explanation, mode}` |

`mode: "safety"` means the built-in emergency rule answered and no AI was called.

## Symptom checker
| Method | Path | Notes |
|---|---|---|
| GET | `/api/symptoms/catalog` | `{symptoms[{name, red_flag}], severities}` |
| POST | `/api/symptoms/check` | `{symptoms[], duration_days, severity: mild\|moderate\|severe, notes}` returns `{urgency: self_care\|routine\|soon\|emergency, urgency_text, reasons, emergency_message, explanations, self_care, warning_signs, doctor_summary, mode, disclaimer}` |

## Medicines
| Method | Path | Notes |
|---|---|---|
| GET / POST | `/api/medicines` | `{name, dosage, times["HH:MM"], frequency: daily\|alternate\|weekly, start_date, end_date?, notes, active}` |
| PUT / DELETE | `/api/medicines/{id}` | |
| GET | `/api/medicines/schedule?date=&now=` | doses with status `pending\|overdue\|taken\|skipped` |
| POST | `/api/medicines/log` | `{medicine_id, scheduled_for: "YYYY-MM-DD HH:MM", status: taken\|skipped}` |
| GET | `/api/medicines/history?limit=` | dose log |

## Health records and reports
| Method | Path | Notes |
|---|---|---|
| GET | `/api/records?q=&metric=&start=&end=` | `metric`: weight, height, bp, glucose, temperature |
| POST | `/api/records` | `{recorded_at, weight_kg?, height_cm?, systolic?, diastolic?, glucose_mgdl?, temperature_c?, notes}`; needs at least one value; BP needs both numbers with diastolic below systolic |
| DELETE | `/api/records/{id}` | |
| POST | `/api/records/reports` | multipart field `file` (.pdf or .txt, max 5 MB) returns parsed `results[{name, value, unit, low, high, status}]` |
| GET | `/api/records/reports`, `/api/records/reports/{id}` | list or detail |
| POST | `/api/records/reports/{id}/summarize` | `{summary, mode}` (live AI or demo template) |
| DELETE | `/api/records/reports/{id}` | |

## Wellness
| Method | Path | Notes |
|---|---|---|
| GET | `/api/wellness?days=7` | `{days[], goals}` |
| PUT | `/api/wellness/{YYYY-MM-DD}` | `{water_ml, sleep_hours, activity_min, mood}` (upsert) |
| GET | `/api/wellness/summary` | weekly averages plus text |
| POST | `/api/wellness/suggestions` | `{diet, goal, activity_level: low\|moderate\|high}` returns `{suggestions[], mode}` |

## Appointments
`GET/POST /api/appointments`, `PUT/DELETE /api/appointments/{id}` with
`{doctor, specialization, clinic, scheduled_at: "YYYY-MM-DD HH:MM", purpose, status: upcoming|completed|cancelled}`.

## PDF report
`GET /api/report/pdf` returns `application/pdf` (attachment `healthmate-report.pdf`).
