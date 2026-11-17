import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Activity, CalendarClock, Check, ClipboardList, Pill, Send, Sparkles, X } from 'lucide-react'
import { api, nowStr, type Dashboard as Dash, type DoseItem } from '../api'
import { useAuth } from '../auth'
import { Empty, ErrorBox, ModeBadge, Spinner, useAsync } from '../components/ui'

const QUICK_SYMPTOMS = ['Headache', 'Fever', 'Cough', 'Sore throat', 'Fatigue', 'Nausea']

export function Kpi({ icon: Icon, label, value, tone }: { icon: typeof Pill; label: string; value: string | number; tone: string }) {
  return (
    <div className="card flex items-center gap-4">
      <span className={`grid h-12 w-12 place-items-center rounded-2xl ${tone}`}><Icon className="h-6 w-6" /></span>
      <div><div className="text-2xl font-bold">{value}</div><div className="text-xs text-slate-500">{label}</div></div>
    </div>
  )
}

export const statusStyle: Record<DoseItem['status'], string> = {
  pending: 'bg-sky-100 text-sky-800', overdue: 'bg-red-100 text-red-800', taken: 'bg-emerald-100 text-emerald-800', skipped: 'bg-slate-200 text-slate-700',
}

export default function Dashboard() {
  const { user } = useAuth()
  const nav = useNavigate()
  const { data, error, loading, reload } = useAsync(() => api<Dash>(`/api/dashboard?now=${encodeURIComponent(nowStr())}`))
  const [q, setQ] = useState('')
  const [picked, setPicked] = useState<string[]>([])

  async function mark(d: DoseItem, status: 'taken' | 'skipped') {
    await api('/api/medicines/log', { body: { medicine_id: d.medicine_id, scheduled_for: d.scheduled_for, status } })
    reload()
  }
  const ask = (e: FormEvent) => { e.preventDefault(); if (q.trim()) nav(`/chat?q=${encodeURIComponent(q.trim())}`) }

  if (loading && !data) return <Spinner />
  if (!data) return <ErrorBox message={error} />
  const L = data.latest
  const bp = L.systolic && L.diastolic ? `${L.systolic.v}/${L.diastolic.v}` : '-'
  const hr = new Date().getHours()
  const greet = hr < 12 ? 'Good morning' : hr < 17 ? 'Good afternoon' : 'Good evening'

  return (
    <div className="space-y-5">
      <section className="rounded-3xl bg-gradient-to-r from-teal-600 to-sky-500 p-6 text-white shadow">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-2xl font-bold">{greet}, {user?.name.split(' ')[0]} 👋</h1>
          <ModeBadge mode={data.ai.mode} />
        </div>
        <p className="mt-1 text-teal-50">Here is your health overview for today.{data.ai.mode === 'demo' && ' (AI is running in demo mode with pre-written answers.)'}</p>
        <form onSubmit={ask} className="mt-4 flex gap-2">
          <label className="sr-only" htmlFor="ask">Ask the AI health assistant</label>
          <input id="ask" className="input flex-1 border-0" placeholder="Ask the AI Health Assistant: e.g. How can I improve my sleep?" maxLength={300} value={q} onChange={(e) => setQ(e.target.value)} />
          <button className="btn bg-white text-teal-700 hover:bg-teal-50"><Send className="h-4 w-4" /> Ask</button>
        </form>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Key figures">
        <Kpi icon={ClipboardList} label="Total health records" value={data.kpis.health_records} tone="bg-sky-100 text-sky-700" />
        <Kpi icon={Pill} label="Active medicine reminders" value={data.kpis.active_medicines} tone="bg-teal-100 text-teal-700" />
        <Kpi icon={CalendarClock} label="Upcoming appointments" value={data.kpis.upcoming_appointments} tone="bg-violet-100 text-violet-700" />
        <Kpi icon={Activity} label="Today's wellness progress" value={`${data.kpis.wellness_progress}%`} tone="bg-emerald-100 text-emerald-700" />
      </section>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="card">
          <h2 className="mb-1 font-semibold">Quick symptom information checker</h2>
          <p className="mb-3 text-xs text-slate-500">Pick symptoms, then continue for general information. This is not a diagnosis.</p>
          <div className="flex flex-wrap gap-2">
            {QUICK_SYMPTOMS.map((s) => (
              <button key={s} aria-pressed={picked.includes(s)} className={`chip ${picked.includes(s) ? 'chip-on' : ''}`}
                onClick={() => setPicked(picked.includes(s) ? picked.filter((x) => x !== s) : [...picked, s])}>{s}</button>
            ))}
          </div>
          <button className="btn-primary mt-4" disabled={!picked.length} onClick={() => nav(`/symptoms?s=${encodeURIComponent(picked.join(','))}`)}>
            <Sparkles className="h-4 w-4" /> Continue
          </button>
        </section>

        <section className="card">
          <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold">Today's medicine schedule</h2><Link className="text-xs text-teal-700 underline dark:text-teal-300" to="/medicines">Manage</Link></div>
          {data.schedule.length === 0 ? <Empty>No doses scheduled today.</Empty> : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-700">
              {data.schedule.map((d) => (
                <li key={d.scheduled_for + d.medicine_id} className="flex items-center justify-between gap-2 py-2">
                  <div><div className="text-sm font-medium">{d.name}</div><div className="text-xs text-slate-500">{d.time} · {d.dosage}</div></div>
                  {d.status === 'pending' || d.status === 'overdue' ? (
                    <div className="flex items-center gap-1">
                      {d.status === 'overdue' && <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${statusStyle.overdue}`}>OVERDUE</span>}
                      <button className="btn-primary btn-sm" onClick={() => mark(d, 'taken')} aria-label={`Mark ${d.name} taken`}><Check className="h-3 w-3" /> Taken</button>
                      <button className="btn-ghost btn-sm" onClick={() => mark(d, 'skipped')} aria-label={`Mark ${d.name} skipped`}><X className="h-3 w-3" /></button>
                    </div>
                  ) : <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusStyle[d.status]}`}>{d.status}</span>}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold">Health metrics overview</h2><Link className="text-xs text-teal-700 underline dark:text-teal-300" to="/records">All records</Link></div>
          <div className="mb-3 grid grid-cols-3 gap-2 text-center text-sm">
            <div className="rounded-xl bg-slate-50 p-2 dark:bg-slate-700"><div className="font-bold">{L.weight_kg?.v ?? '-'}</div><div className="text-[11px] text-slate-500">Weight kg</div></div>
            <div className="rounded-xl bg-slate-50 p-2 dark:bg-slate-700"><div className="font-bold">{bp}</div><div className="text-[11px] text-slate-500">BP mmHg</div></div>
            <div className="rounded-xl bg-slate-50 p-2 dark:bg-slate-700"><div className="font-bold">{L.glucose_mgdl?.v ?? '-'}</div><div className="text-[11px] text-slate-500">Glucose mg/dL</div></div>
          </div>
          {data.series.length < 2 ? <Empty>Add health records to see trends.</Empty> : (
            <div className="h-44" aria-label="Weight and blood pressure trend chart">
              <ResponsiveContainer>
                <LineChart data={data.series}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="recorded_at" tickFormatter={(v: string) => v.slice(5)} fontSize={10} />
                  <YAxis yAxisId="a" fontSize={10} domain={['auto', 'auto']} /><YAxis yAxisId="b" orientation="right" fontSize={10} domain={['auto', 'auto']} />
                  <Tooltip />
                  <Line yAxisId="a" dataKey="weight_kg" name="Weight kg" stroke="#0d9488" strokeWidth={2} dot={false} connectNulls />
                  <Line yAxisId="b" dataKey="systolic" name="Systolic" stroke="#0ea5e9" strokeWidth={2} dot={false} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>

        <section className="card">
          <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold">Wellness progress (7 days)</h2><Link className="text-xs text-teal-700 underline dark:text-teal-300" to="/wellness">Track</Link></div>
          <div className="h-44" aria-label="Wellness progress chart">
            <ResponsiveContainer>
              <BarChart data={data.wellness_week}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="log_date" tickFormatter={(v: string) => v.slice(5)} fontSize={10} /><YAxis domain={[0, 100]} fontSize={10} />
                <Tooltip formatter={(v) => `${v}%`} /><Bar dataKey="progress" name="Goal progress" fill="#14b8a6" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <section className="card">
        <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold">Upcoming doctor appointments</h2><Link className="text-xs text-teal-700 underline dark:text-teal-300" to="/appointments">Manage</Link></div>
        {data.appointments.length === 0 ? <Empty>No upcoming appointments.</Empty> : (
          <ul className="grid gap-3 md:grid-cols-3">
            {data.appointments.map((a) => (
              <li key={a.id} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                <div className="font-medium">{a.doctor}</div>
                <div className="text-xs text-slate-500">{a.specialization} · {a.clinic}</div>
                <div className="mt-1 text-sm font-semibold text-teal-700 dark:text-teal-300">{a.scheduled_at}</div>
                <div className="text-xs">{a.purpose}</div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
