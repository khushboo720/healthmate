// Thin typed API client. The JWT is kept in localStorage; API keys never reach the browser.
const TOKEN_KEY = 'hm_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t: string | null) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY))

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

function errorMessage(data: unknown, status: number): string {
  const d = (data as { detail?: unknown })?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) {
    return d
      .map((e: { msg?: string; loc?: (string | number)[] }) => {
        const field = e.loc?.filter((x) => x !== 'body').join('.')
        const msg = (e.msg ?? 'Invalid value').replace(/^Value error, /, '')
        return field ? `${field}: ${msg}` : msg
      })
      .join('; ')
  }
  return status === 0 ? 'Cannot reach the server. Is the backend running?' : `Request failed (${status})`
}

export async function api<T = unknown>(path: string, opts: { method?: string; body?: unknown; form?: FormData; raw?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let body: BodyInit | undefined
  if (opts.form) body = opts.form
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.body)
  }
  let res: Response
  try {
    res = await fetch(path, { method: opts.method ?? (body ? 'POST' : 'GET'), headers, body })
  } catch {
    throw new ApiError(errorMessage(null, 0), 0)
  }
  if (res.status === 401 && token && !path.startsWith('/api/auth/login')) {
    setToken(null)
    window.dispatchEvent(new Event('hm-unauthorized'))
  }
  if (!res.ok) {
    let data: unknown = null
    try { data = await res.json() } catch { /* not JSON */ }
    throw new ApiError(errorMessage(data, res.status), res.status)
  }
  if (opts.raw) return (await res.blob()) as unknown as T
  return (await res.json()) as T
}

// ---------- date helpers (browser-local time) ----------
const p = (n: number) => String(n).padStart(2, '0')
export const todayStr = (d = new Date()) => `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
export const nowStr = (d = new Date()) => `${todayStr(d)} ${p(d.getHours())}:${p(d.getMinutes())}`

// ---------- types ----------
export interface User {
  id: number; email: string; name: string; age: number | null; gender: string; blood_group: string
  allergies: string; medical_history: string; water_goal_ml: number; sleep_goal_h: number; activity_goal_min: number
}
export interface AiStatus { mode: 'live' | 'demo'; model: string | null }
export interface DoseItem { medicine_id: number; name: string; dosage: string; time: string; scheduled_for: string; status: 'pending' | 'overdue' | 'taken' | 'skipped' }
export interface Medicine {
  id: number; name: string; dosage: string; times: string[]; frequency: string; start_date: string; end_date: string | null; notes: string; active: boolean
  prescription_id?: number | null; prescribed_by?: string | null; prescribed_on?: string | null
}
export interface DraftItem {
  name: string; dosage: string; times: string[]; frequency: string; start_date: string; end_date: string | null; notes: string
  raw: string; as_needed: boolean; needs_review: boolean; include: boolean
}
export interface RxDraft { id: number; doctor: string; prescribed_on: string; date_detected: boolean; filename: string; items: DraftItem[]; text: string; review_note: string }
export interface Prescription {
  id: number; doctor: string; prescribed_on: string; notes: string; filename: string; created_at: string
  medicines: { id: number; name: string; dosage: string; times: string[]; frequency: string; start_date: string; end_date: string | null; active: boolean }[]
}
export type LabStatus = 'low' | 'high' | 'normal'
export interface LabEntry {
  id: number; report_id: number | null; test_name: string; test_key: string; value: number; unit: string
  ref_low: number | null; ref_high: number | null; status: LabStatus; test_date: string; source: 'report' | 'manual' | 'sample'; report_name: string | null
}
export interface LabTest {
  test_key: string; test_name: string; unit: string; count: number; latest_value: number; latest_date: string; latest_status: LabStatus
  ref_low: number | null; ref_high: number | null; previous_value: number | null; previous_date: string | null
}
export interface HealthRecord { id: number; recorded_at: string; weight_kg: number | null; height_cm: number | null; systolic: number | null; diastolic: number | null; glucose_mgdl: number | null; temperature_c: number | null; notes: string }
export interface Appointment { id: number; doctor: string; specialization: string; clinic: string; scheduled_at: string; purpose: string; status: 'upcoming' | 'completed' | 'cancelled' }
export interface WellnessDay { log_date: string; water_ml: number; sleep_hours: number; activity_min: number; mood: string; progress: number; logged: boolean }
export interface Notice { type: string; title: string; detail: string }
export interface Dashboard {
  user: { name: string }
  kpis: { health_records: number; active_medicines: number; upcoming_appointments: number; wellness_progress: number }
  schedule: DoseItem[]
  latest: Record<string, { v: number; recorded_at: string } | null>
  series: Omit<HealthRecord, 'id' | 'height_cm' | 'notes'>[]
  wellness_week: WellnessDay[]
  appointments: Appointment[]
  notifications: Notice[]
  ai: AiStatus
}
export interface ChatMsg { id: number; role: 'user' | 'assistant'; content: string; mode: string; emergency: number }
export interface LabResult {
  name: string; value: number; unit: string; low: number; high: number; status: LabStatus
  previous?: { value: number; unit: string; test_date: string; status: LabStatus } | null
}
export interface LabReport {
  id: number; filename: string; results: LabResult[]; summary: string; summary_mode: string; created_at: string; test_date: string
  date_source?: string; captured?: number
}
