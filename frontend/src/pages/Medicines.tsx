import { useState, type FormEvent } from 'react'
import { BellRing, Check, Plus, Trash2, X } from 'lucide-react'
import { api, nowStr, todayStr, type DoseItem, type Medicine } from '../api'
import { ConfirmButton, Disclaimer, Empty, ErrorBox, Field, PageHeader, Spinner, useAsync } from '../components/ui'
import { statusStyle } from './Dashboard'
import { PrescriptionImport, PrescriptionList } from '../components/PrescriptionImport'

interface HistoryRow { id: number; scheduled_for: string; status: string; name: string; dosage: string }
const blank = { name: '', dosage: '', times: ['08:00'], frequency: 'daily', start_date: todayStr(), end_date: '', notes: '' }

export default function Medicines() {
  const meds = useAsync(() => api<Medicine[]>('/api/medicines'))
  const sched = useAsync(() => api<DoseItem[]>(`/api/medicines/schedule?date=${todayStr()}&now=${encodeURIComponent(nowStr())}`))
  const hist = useAsync(() => api<HistoryRow[]>('/api/medicines/history?limit=30'))
  const [f, setF] = useState(blank)
  const [error, setError] = useState<string | null>(null)
  const [perm, setPerm] = useState<string>('Notification' in window ? Notification.permission : 'unsupported')
  const [rxVersion, setRxVersion] = useState(0)
  const reloadAll = () => { meds.reload(); sched.reload(); hist.reload(); setRxVersion((v) => v + 1) }

  async function add(e: FormEvent) {
    e.preventDefault(); setError(null)
    try {
      await api('/api/medicines', { body: { ...f, end_date: f.end_date || null } })
      setF({ ...blank, start_date: todayStr() }); reloadAll()
    } catch (err) { setError((err as Error).message) }
  }
  const act = async (fn: () => Promise<unknown>) => { try { await fn(); reloadAll() } catch (err) { setError((err as Error).message) } }
  const log = (d: DoseItem, status: string) => act(() => api('/api/medicines/log', { body: { medicine_id: d.medicine_id, scheduled_for: d.scheduled_for, status } }))
  const toggleActive = (m: Medicine) => act(() => api(`/api/medicines/${m.id}`, { method: 'PUT', body: { ...m, end_date: m.end_date, active: !m.active } }))
  const remove = (m: Medicine) => act(() => api(`/api/medicines/${m.id}`, { method: 'DELETE' }))
  const setTime = (i: number, v: string) => setF({ ...f, times: f.times.map((t, k) => (k === i ? v : t)) })

  async function enableNotifications() {
    if (!('Notification' in window)) return
    setPerm(await Notification.requestPermission())
  }

  return (
    <div className="space-y-5">
      <PageHeader title="Medicine Reminder" subtitle="Track the medicines your doctor prescribed. This app never suggests doses."
        action={perm !== 'unsupported' && perm !== 'granted' ? (
          <button className="btn-ghost" onClick={enableNotifications}><BellRing className="h-4 w-4" /> Enable browser notifications</button>
        ) : <span className="text-xs text-slate-500">{perm === 'granted' ? 'Browser notifications are on' : 'Notifications not supported in this browser'}</span>} />
      <ErrorBox message={error} />

      <PrescriptionImport onCreated={reloadAll} />

      <div className="grid gap-5 lg:grid-cols-2">
        <form onSubmit={add} className="card space-y-3">
          <h2 className="font-semibold">Or add a medicine reminder manually</h2>
          <Field label="Medicine name"><input className="input" required maxLength={80} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="e.g. Vitamin D3" /></Field>
          <Field label="Dosage (exactly as prescribed)" hint="Copy it from your prescription. HealthMate AI never recommends or changes doses."><input className="input" required maxLength={80} value={f.dosage} onChange={(e) => setF({ ...f, dosage: e.target.value })} placeholder="e.g. 1 tablet after meals" /></Field>
          <div>
            <span className="label">Reminder times</span>
            <div className="flex flex-wrap gap-2">
              {f.times.map((t, i) => (
                <span key={i} className="flex items-center gap-1">
                  <input aria-label={`Reminder time ${i + 1}`} type="time" required className="input w-auto" value={t} onChange={(e) => setTime(i, e.target.value)} />
                  {f.times.length > 1 && <button type="button" className="btn-ghost btn-sm" aria-label="Remove time" onClick={() => setF({ ...f, times: f.times.filter((_, k) => k !== i) })}><X className="h-3 w-3" /></button>}
                </span>
              ))}
              {f.times.length < 6 && <button type="button" className="btn-ghost btn-sm" onClick={() => setF({ ...f, times: [...f.times, '12:00'] })}><Plus className="h-3 w-3" /> Add time</button>}
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Frequency">
              <select className="input" value={f.frequency} onChange={(e) => setF({ ...f, frequency: e.target.value })}>
                <option value="daily">Every day</option><option value="alternate">Alternate days</option><option value="weekly">Once a week</option>
              </select>
            </Field>
            <Field label="Start date"><input className="input" type="date" required value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} /></Field>
            <Field label="End date (duration)"><input className="input" type="date" min={f.start_date} value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} /></Field>
          </div>
          <Field label="Notes (optional)"><input className="input" maxLength={300} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
          <button className="btn-primary"><Plus className="h-4 w-4" /> Add reminder</button>
        </form>

        <section className="card">
          <h2 className="mb-2 font-semibold">Today's schedule</h2>
          {sched.loading && !sched.data ? <Spinner /> : !sched.data?.length ? <Empty>No doses scheduled today.</Empty> : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-700">
              {sched.data.map((d) => (
                <li key={d.scheduled_for + d.medicine_id} className="flex items-center justify-between gap-2 py-2">
                  <div><div className="text-sm font-medium">{d.time} · {d.name}</div><div className="text-xs text-slate-500">{d.dosage}</div></div>
                  {d.status === 'pending' || d.status === 'overdue' ? (
                    <div className="flex items-center gap-1">
                      {d.status === 'overdue' && <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${statusStyle.overdue}`}>OVERDUE</span>}
                      <button className="btn-primary btn-sm" onClick={() => log(d, 'taken')}><Check className="h-3 w-3" /> Taken</button>
                      <button className="btn-ghost btn-sm" onClick={() => log(d, 'skipped')}>Skip</button>
                    </div>
                  ) : <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusStyle[d.status]}`}>{d.status}</span>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="card overflow-x-auto">
        <h2 className="mb-2 font-semibold">My medicines</h2>
        {!meds.data?.length ? <Empty>No medicines added yet.</Empty> : (
          <table className="w-full"><thead><tr><th className="th">Medicine</th><th className="th">Dosage</th><th className="th">Times</th><th className="th">Schedule</th><th className="th">Prescribed by</th><th className="th">Status</th><th className="th" /></tr></thead>
            <tbody>{meds.data.map((m) => (
              <tr key={m.id} className="border-t border-slate-100 dark:border-slate-700">
                <td className="td font-medium">{m.name}</td><td className="td">{m.dosage}</td><td className="td">{m.times.join(', ')}</td>
                <td className="td text-xs">{m.frequency}<br />{m.start_date} → {m.end_date ?? 'ongoing'}</td>
                <td className="td text-xs">{m.prescribed_by ? <><span className="rounded-full bg-sky-100 px-2 py-0.5 font-bold text-sky-800">Rx</span> {m.prescribed_by}<br /><span className="text-slate-500">{m.prescribed_on}</span></> : <span className="text-slate-400">Added manually</span>}</td>
                <td className="td"><button className="chip" onClick={() => toggleActive(m)}>{m.active ? 'Active' : 'Paused'}</button></td>
                <td className="td text-right"><ConfirmButton message={`Delete ${m.name}?`} onConfirm={() => remove(m)}><Trash2 className="h-3.5 w-3.5" /><span className="sr-only">Delete {m.name}</span></ConfirmButton></td>
              </tr>))}</tbody></table>
        )}
      </section>

      <PrescriptionList version={rxVersion} onChanged={() => { meds.reload(); sched.reload(); hist.reload() }} />

      <section className="card overflow-x-auto">
        <h2 className="mb-2 font-semibold">Medicine history</h2>
        {!hist.data?.length ? <Empty>No doses logged yet.</Empty> : (
          <table className="w-full"><thead><tr><th className="th">Scheduled</th><th className="th">Medicine</th><th className="th">Result</th></tr></thead>
            <tbody>{hist.data.map((h) => (
              <tr key={h.id} className="border-t border-slate-100 dark:border-slate-700"><td className="td">{h.scheduled_for}</td><td className="td">{h.name} <span className="text-xs text-slate-500">({h.dosage})</span></td>
                <td className="td"><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusStyle[h.status as DoseItem['status']]}`}>{h.status}</span></td></tr>))}</tbody></table>
        )}
      </section>
      <Disclaimer text="Never change, stop or adjust prescribed medicines without your doctor's advice. Reminders are a convenience and may not fire if your browser is closed." />
    </div>
  )
}
