import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { BookOpen, Plus, Search, Trash2 } from 'lucide-react'
import { api, todayStr, type HealthRecord } from '../api'
import { useAuth } from '../auth'
import LabHistory from '../components/LabHistory'
import TestReports from '../components/TestReports'
import { ConfirmButton, Disclaimer, Empty, ErrorBox, Field, Markdown, ModeBadge, PageHeader, Spinner, useAsync } from '../components/ui'

const blank = { recorded_at: todayStr(), weight_kg: '', height_cm: '', systolic: '', diastolic: '', glucose_mgdl: '', temperature_c: '', notes: '' }
const num = (v: string) => (v === '' ? null : Number(v))

function Chart({ title, data, lines }: { title: string; data: Record<string, unknown>[]; lines: { key: string; name: string; color: string }[] }) {
  const has = data.some((d) => lines.some((l) => d[l.key] != null))
  return (
    <div className="card">
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      {!has ? <Empty>No data yet.</Empty> : (
        <div className="h-48" role="img" aria-label={`${title} chart`}>
          <ResponsiveContainer>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="recorded_at" tickFormatter={(v: string) => v.slice(5)} fontSize={10} />
              <YAxis fontSize={10} domain={['auto', 'auto']} /><Tooltip />{lines.length > 1 && <Legend />}
              {lines.map((l) => <Line key={l.key} dataKey={l.key} name={l.name} stroke={l.color} strokeWidth={2} connectNulls dot={{ r: 2 }} />)}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

export default function Records() {
  const { user } = useAuth()
  const [q, setQ] = useState(''); const [metric, setMetric] = useState(''); const [start, setStart] = useState(''); const [end, setEnd] = useState('')
  const qs = new URLSearchParams({ q, metric, ...(start && { start }), ...(end && { end }) }).toString()
  const recs = useAsync(() => api<HealthRecord[]>(`/api/records?${qs}`), [qs])
  const all = useAsync(() => api<HealthRecord[]>('/api/records'))
  const [f, setF] = useState(blank)
  const [error, setError] = useState<string | null>(null)
  const [term, setTerm] = useState(''); const [termRes, setTermRes] = useState<{ explanation: string; mode: string } | null>(null)
  const [labVersion, setLabVersion] = useState(0)
  const bumpLabs = () => setLabVersion((v) => v + 1)
  const reload = () => { recs.reload(); all.reload() }

  async function add(e: FormEvent) {
    e.preventDefault(); setError(null)
    try {
      await api('/api/records', { body: {
        recorded_at: f.recorded_at, weight_kg: num(f.weight_kg), height_cm: num(f.height_cm), systolic: num(f.systolic), diastolic: num(f.diastolic),
        glucose_mgdl: num(f.glucose_mgdl), temperature_c: num(f.temperature_c), notes: f.notes } })
      setF({ ...blank, recorded_at: todayStr() }); reload()
    } catch (err) { setError((err as Error).message) }
  }
  const del = async (id: number) => { await api(`/api/records/${id}`, { method: 'DELETE' }); reload() }

  async function explain(e: FormEvent) {
    e.preventDefault()
    try { setTermRes(await api('/api/chat/explain-term', { body: { term } })) } catch (err) { setError((err as Error).message) }
  }

  const series = (all.data ?? []).slice().reverse().map((r) => ({ ...r }))

  return (
    <div className="space-y-5">
      <PageHeader title="Health Records" subtitle="Record measurements, upload test reports to capture lab values, and follow your history over time." />
      <ErrorBox message={error} />

      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">Allergies & medical history</h2>
          <Link className="text-xs text-teal-700 underline dark:text-teal-300" to="/settings">Edit in profile</Link>
        </div>
        <p className="mt-1 text-sm"><b>Allergies:</b> {user?.allergies || 'none recorded'}</p>
        <p className="text-sm"><b>History:</b> {user?.medical_history || 'none recorded'}</p>
      </div>

      <form onSubmit={add} className="card space-y-3">
        <h2 className="font-semibold">Add a record</h2>
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <Field label="Date"><input className="input" type="date" required max={todayStr()} value={f.recorded_at} onChange={(e) => setF({ ...f, recorded_at: e.target.value })} /></Field>
          <Field label="Weight (kg)"><input className="input" type="number" step="0.1" min={1} max={500} value={f.weight_kg} onChange={(e) => setF({ ...f, weight_kg: e.target.value })} /></Field>
          <Field label="Height (cm)"><input className="input" type="number" step="0.1" min={30} max={272} value={f.height_cm} onChange={(e) => setF({ ...f, height_cm: e.target.value })} /></Field>
          <Field label="Temperature (°C)"><input className="input" type="number" step="0.1" min={30} max={45} value={f.temperature_c} onChange={(e) => setF({ ...f, temperature_c: e.target.value })} /></Field>
          <Field label="BP systolic"><input className="input" type="number" min={50} max={260} value={f.systolic} onChange={(e) => setF({ ...f, systolic: e.target.value })} /></Field>
          <Field label="BP diastolic"><input className="input" type="number" min={30} max={180} value={f.diastolic} onChange={(e) => setF({ ...f, diastolic: e.target.value })} /></Field>
          <Field label="Blood glucose (mg/dL)"><input className="input" type="number" step="0.1" min={20} max={800} value={f.glucose_mgdl} onChange={(e) => setF({ ...f, glucose_mgdl: e.target.value })} /></Field>
          <Field label="Notes"><input className="input" maxLength={300} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
        </div>
        <button className="btn-primary"><Plus className="h-4 w-4" /> Save record</button>
      </form>

      <section className="grid gap-4 md:grid-cols-2" aria-label="Charts">
        <Chart title="Weight (kg)" data={series} lines={[{ key: 'weight_kg', name: 'Weight', color: '#0d9488' }]} />
        <Chart title="Blood pressure (mmHg)" data={series} lines={[{ key: 'systolic', name: 'Systolic', color: '#0ea5e9' }, { key: 'diastolic', name: 'Diastolic', color: '#8b5cf6' }]} />
        <Chart title="Blood glucose (mg/dL)" data={series} lines={[{ key: 'glucose_mgdl', name: 'Glucose', color: '#f59e0b' }]} />
        <Chart title="Temperature (°C)" data={series} lines={[{ key: 'temperature_c', name: 'Temperature', color: '#ef4444' }]} />
      </section>

      <section className="card overflow-x-auto">
        <h2 className="mb-3 font-semibold">Record history</h2>
        <div className="mb-3 grid gap-2 sm:grid-cols-4">
          <div className="relative sm:col-span-1"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" /><input aria-label="Search notes" className="input pl-8" placeholder="Search notes" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <select aria-label="Filter by metric" className="input" value={metric} onChange={(e) => setMetric(e.target.value)}>
            <option value="">All metrics</option><option value="weight">Weight</option><option value="height">Height</option><option value="bp">Blood pressure</option><option value="glucose">Glucose</option><option value="temperature">Temperature</option>
          </select>
          <input aria-label="From date" type="date" className="input" value={start} onChange={(e) => setStart(e.target.value)} />
          <input aria-label="To date" type="date" className="input" value={end} onChange={(e) => setEnd(e.target.value)} />
        </div>
        {recs.loading && !recs.data ? <Spinner /> : !recs.data?.length ? <Empty>No records match.</Empty> : (
          <table className="w-full"><thead><tr><th className="th">Date</th><th className="th">Weight</th><th className="th">BP</th><th className="th">Glucose</th><th className="th">Temp</th><th className="th">Notes</th><th className="th" /></tr></thead>
            <tbody>{recs.data.map((r) => (
              <tr key={r.id} className="border-t border-slate-100 dark:border-slate-700">
                <td className="td">{r.recorded_at}</td><td className="td">{r.weight_kg ?? '-'}</td><td className="td">{r.systolic ? `${r.systolic}/${r.diastolic}` : '-'}</td>
                <td className="td">{r.glucose_mgdl ?? '-'}</td><td className="td">{r.temperature_c ?? '-'}</td><td className="td text-xs">{r.notes}</td>
                <td className="td text-right"><ConfirmButton message="Delete this record?" onConfirm={() => del(r.id)}><Trash2 className="h-3.5 w-3.5" /><span className="sr-only">Delete record</span></ConfirmButton></td>
              </tr>))}</tbody></table>
        )}
      </section>

      <TestReports version={labVersion} onChanged={bumpLabs} />
      <LabHistory version={labVersion} onChanged={bumpLabs} />

      <section className="card">
        <h2 className="mb-2 flex items-center gap-2 font-semibold"><BookOpen className="h-4 w-4" /> Explain a medical term</h2>
        <form onSubmit={explain} className="flex gap-2">
          <input aria-label="Medical term" className="input" required minLength={2} maxLength={80} placeholder="e.g. hemoglobin, hypertension, BMI" value={term} onChange={(e) => setTerm(e.target.value)} />
          <button className="btn-primary">Explain</button>
        </form>
        {termRes && <div className="mt-3 rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-900"><ModeBadge mode={termRes.mode} /> <Markdown text={termRes.explanation} /></div>}
      </section>

      <Disclaimer text="Flags only compare numbers against the ranges printed in your report. They are not a diagnosis. Please review all results with your doctor." />
    </div>
  )
}
