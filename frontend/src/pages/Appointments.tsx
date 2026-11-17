import { useState, type FormEvent } from 'react'
import { CalendarPlus, Trash2 } from 'lucide-react'
import { api, nowStr, type Appointment } from '../api'
import { ConfirmButton, Empty, ErrorBox, Field, PageHeader, Spinner, useAsync } from '../components/ui'

const blank = { doctor: '', specialization: '', clinic: '', date: '', time: '10:00', purpose: '' }
const tone: Record<string, string> = { upcoming: 'bg-sky-100 text-sky-800', completed: 'bg-emerald-100 text-emerald-800', cancelled: 'bg-slate-200 text-slate-700' }

export default function Appointments() {
  const { data, error: loadErr, loading, reload } = useAsync(() => api<Appointment[]>('/api/appointments'))
  const [f, setF] = useState(blank)
  const [error, setError] = useState<string | null>(null)
  const now = nowStr()

  async function add(e: FormEvent) {
    e.preventDefault(); setError(null)
    try {
      await api('/api/appointments', { body: { doctor: f.doctor, specialization: f.specialization, clinic: f.clinic, scheduled_at: `${f.date} ${f.time}`, purpose: f.purpose } })
      setF(blank); reload()
    } catch (err) { setError((err as Error).message) }
  }
  const setStatus = async (a: Appointment, status: string) => {
    try { await api(`/api/appointments/${a.id}`, { method: 'PUT', body: { ...a, status } }); reload() } catch (err) { setError((err as Error).message) }
  }
  const del = async (a: Appointment) => { await api(`/api/appointments/${a.id}`, { method: 'DELETE' }); reload() }

  const upcoming = (data ?? []).filter((a) => a.status === 'upcoming' && a.scheduled_at >= now).sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at))
  const history = (data ?? []).filter((a) => !upcoming.includes(a))
  const soon = (a: Appointment) => (new Date(a.scheduled_at.replace(' ', 'T')).getTime() - Date.now()) / 36e5 <= 24

  return (
    <div className="space-y-5">
      <PageHeader title="Doctor Appointments" subtitle="Keep track of upcoming visits and your appointment history." />
      <ErrorBox message={error ?? loadErr} />
      <form onSubmit={add} className="card space-y-3">
        <h2 className="font-semibold">Add appointment</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Doctor name"><input className="input" required minLength={2} maxLength={80} value={f.doctor} onChange={(e) => setF({ ...f, doctor: e.target.value })} placeholder="Dr. Name" /></Field>
          <Field label="Specialization"><input className="input" maxLength={60} value={f.specialization} onChange={(e) => setF({ ...f, specialization: e.target.value })} placeholder="e.g. Cardiologist" /></Field>
          <Field label="Hospital / clinic"><input className="input" maxLength={100} value={f.clinic} onChange={(e) => setF({ ...f, clinic: e.target.value })} /></Field>
          <Field label="Date"><input className="input" type="date" required value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></Field>
          <Field label="Time"><input className="input" type="time" required value={f.time} onChange={(e) => setF({ ...f, time: e.target.value })} /></Field>
          <Field label="Purpose"><input className="input" maxLength={200} value={f.purpose} onChange={(e) => setF({ ...f, purpose: e.target.value })} placeholder="e.g. Routine check-up" /></Field>
        </div>
        <button className="btn-primary"><CalendarPlus className="h-4 w-4" /> Add appointment</button>
      </form>

      {loading && !data ? <Spinner /> : (
        <>
          <section>
            <h2 className="mb-2 font-semibold">Upcoming</h2>
            {upcoming.length === 0 ? <div className="card"><Empty>No upcoming appointments.</Empty></div> : (
              <ul className="grid gap-3 md:grid-cols-2">
                {upcoming.map((a) => (
                  <li key={a.id} className="card">
                    <div className="flex items-start justify-between gap-2">
                      <div><div className="font-semibold">{a.doctor}</div><div className="text-xs text-slate-500">{a.specialization} · {a.clinic}</div></div>
                      {soon(a) && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-800">WITHIN 24H</span>}
                    </div>
                    <div className="mt-2 text-sm font-semibold text-teal-700 dark:text-teal-300">{a.scheduled_at}</div>
                    <div className="text-sm">{a.purpose}</div>
                    <div className="mt-3 flex gap-2">
                      <button className="btn-primary btn-sm" onClick={() => setStatus(a, 'completed')}>Mark completed</button>
                      <button className="btn-ghost btn-sm" onClick={() => setStatus(a, 'cancelled')}>Cancel</button>
                      <ConfirmButton message="Delete this appointment?" onConfirm={() => del(a)}><Trash2 className="h-3.5 w-3.5" /><span className="sr-only">Delete</span></ConfirmButton>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="card overflow-x-auto">
            <h2 className="mb-2 font-semibold">History</h2>
            {history.length === 0 ? <Empty>No past appointments.</Empty> : (
              <table className="w-full"><thead><tr><th className="th">Date</th><th className="th">Doctor</th><th className="th">Clinic</th><th className="th">Purpose</th><th className="th">Status</th><th className="th" /></tr></thead>
                <tbody>{history.map((a) => (
                  <tr key={a.id} className="border-t border-slate-100 dark:border-slate-700">
                    <td className="td">{a.scheduled_at}</td><td className="td">{a.doctor}<div className="text-xs text-slate-500">{a.specialization}</div></td><td className="td">{a.clinic}</td><td className="td">{a.purpose}</td>
                    <td className="td"><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${tone[a.status]}`}>{a.status}</span></td>
                    <td className="td text-right"><ConfirmButton message="Delete this appointment?" onConfirm={() => del(a)}><Trash2 className="h-3.5 w-3.5" /><span className="sr-only">Delete</span></ConfirmButton></td>
                  </tr>))}</tbody></table>
            )}
          </section>
        </>
      )}
    </div>
  )
}
