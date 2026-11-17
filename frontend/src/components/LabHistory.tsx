import { useEffect, useState, type FormEvent } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ArrowDownRight, ArrowRight, ArrowUpRight, FlaskConical, Plus, Trash2 } from 'lucide-react'
import { api, todayStr, type LabEntry, type LabStatus, type LabTest } from '../api'
import { ConfirmButton, Empty, ErrorBox, Field, Spinner, useAsync } from './ui'

export const flagClass = (s: LabStatus) => (s === 'normal' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800')
export const flagText = (s: LabStatus) => (s === 'normal' ? 'within range' : s.toUpperCase())
const DOT = { low: '#dc2626', high: '#dc2626', normal: '#0d9488' }

export function Trend({ now, before }: { now: number; before: number | null | undefined }) {
  if (before == null) return null
  const d = Math.round((now - before) * 100) / 100
  const Icon = d > 0 ? ArrowUpRight : d < 0 ? ArrowDownRight : ArrowRight
  return <span className="inline-flex items-center text-[11px] text-slate-500" title={`Previous: ${before}`}><Icon className="h-3 w-3" />{d > 0 ? '+' : ''}{d}</span>
}

const sourceLabel = (e: LabEntry) => (e.source === 'report' ? e.report_name ?? 'Report' : e.source === 'manual' ? 'Entered manually' : 'Sample data')

/** Lab values captured from uploaded test reports (or typed in), with per-test trend charts and a filterable history. */
export default function LabHistory({ version, onChanged }: { version: number; onChanged: () => void }) {
  const tests = useAsync(() => api<LabTest[]>('/api/records/labs/tests'), [version])
  const [sel, setSel] = useState<string>('')
  const [status, setStatus] = useState(''); const [start, setStart] = useState(''); const [end, setEnd] = useState(''); const [filterTest, setFilterTest] = useState('')
  const qs = new URLSearchParams({ ...(filterTest && { test: filterTest }), ...(status && { status }), ...(start && { start }), ...(end && { end }) }).toString()
  const table = useAsync(() => api<LabEntry[]>(`/api/records/labs?${qs}`), [qs, version])
  const series = useAsync(() => (sel ? api<LabEntry[]>(`/api/records/labs?test=${encodeURIComponent(sel)}`) : Promise.resolve([] as LabEntry[])), [sel, version])
  const [f, setF] = useState({ test_name: '', value: '', unit: '', ref_low: '', ref_high: '', test_date: todayStr() })
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (tests.data?.length && !tests.data.some((t) => t.test_key === sel)) setSel(tests.data[0].test_key)
  }, [tests.data, sel])

  async function addManual(e: FormEvent) {
    e.preventDefault(); setError(null)
    const n = (v: string) => (v === '' ? null : Number(v))
    try {
      await api('/api/records/labs', { body: { test_name: f.test_name, value: Number(f.value), unit: f.unit, ref_low: n(f.ref_low), ref_high: n(f.ref_high), test_date: f.test_date } })
      setF({ ...f, value: '' }); onChanged()
    } catch (err) { setError((err as Error).message) }
  }
  const del = async (id: number) => { await api(`/api/records/labs/${id}`, { method: 'DELETE' }); onChanged() }

  const current = tests.data?.find((t) => t.test_key === sel)
  const points = (series.data ?? []).slice().reverse()

  return (
    <section className="card space-y-4" aria-labelledby="labs-h">
      <div>
        <h2 id="labs-h" className="flex items-center gap-2 font-semibold"><FlaskConical className="h-4 w-4" /> Lab test history</h2>
        <p className="text-xs text-slate-500">Values captured from your uploaded test reports, dated by the test date. Select a test to see its trend against the report's reference range.</p>
      </div>

      {tests.loading && !tests.data ? <Spinner /> : !tests.data?.length ? <Empty>No lab values yet. Upload a test report below or add a value manually.</Empty> : (
        <>
          <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5" aria-label="Tests">
            {tests.data.map((t) => (
              <li key={t.test_key}>
              <button aria-pressed={sel === t.test_key} onClick={() => setSel(t.test_key)}
                className={`w-full rounded-xl border p-3 text-left transition ${sel === t.test_key ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/30' : 'border-slate-200 hover:border-teal-300 dark:border-slate-700'}`}>
                <div className="truncate text-xs font-semibold text-slate-500">{t.test_name}</div>
                <div className="flex items-baseline gap-1"><span className="text-lg font-bold">{t.latest_value}</span><span className="text-xs text-slate-500">{t.unit}</span> <Trend now={t.latest_value} before={t.previous_value} /></div>
                <div className="mt-1 flex items-center justify-between gap-1">
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${flagClass(t.latest_status)}`}>{flagText(t.latest_status)}</span>
                  <span className="text-[10px] text-slate-500">{t.latest_date} · {t.count}×</span>
                </div>
              </button>
              </li>
            ))}
          </ul>

          {current && (
            <div>
              <h3 className="mb-1 text-sm font-semibold">{current.test_name} over time {current.ref_low != null && <span className="font-normal text-slate-500">(shaded band = report range {current.ref_low}–{current.ref_high} {current.unit})</span>}</h3>
              <div className="h-56" role="img" aria-label={`${current.test_name} trend chart`}>
                <ResponsiveContainer>
                  <LineChart data={points} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                    <XAxis dataKey="test_date" fontSize={10} />
                    <YAxis fontSize={10} domain={[(min: number) => Math.floor(Math.min(min, current.ref_low ?? min) * 0.9), (max: number) => Math.ceil(Math.max(max, current.ref_high ?? max) * 1.05)]} />
                    {current.ref_low != null && current.ref_high != null && <ReferenceArea y1={current.ref_low} y2={current.ref_high} fill="#10b981" fillOpacity={0.12} />}
                    <Tooltip formatter={(v) => [`${v} ${current.unit}`, current.test_name]} />
                    <Line dataKey="value" stroke="#0d9488" strokeWidth={2} isAnimationActive={false}
                      dot={(props: unknown) => {
                        const p = props as { cx?: number; cy?: number; index?: number; payload?: LabEntry }
                        return <circle key={p.index} cx={p.cx} cy={p.cy} r={5} fill={DOT[p.payload?.status ?? 'normal']} stroke="white" strokeWidth={1.5} />
                      }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </>
      )}

      <div className="overflow-x-auto">
        <h3 className="mb-2 text-sm font-semibold">All captured values</h3>
        <div className="mb-2 grid gap-2 sm:grid-cols-4">
          <select aria-label="Filter by test" className="input" value={filterTest} onChange={(e) => setFilterTest(e.target.value)}>
            <option value="">All tests</option>{tests.data?.map((t) => <option key={t.test_key} value={t.test_key}>{t.test_name}</option>)}
          </select>
          <select aria-label="Filter by flag" className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All flags</option><option value="low">Low</option><option value="high">High</option><option value="normal">Within range</option>
          </select>
          <input aria-label="Lab from date" type="date" className="input" value={start} onChange={(e) => setStart(e.target.value)} />
          <input aria-label="Lab to date" type="date" className="input" value={end} onChange={(e) => setEnd(e.target.value)} />
        </div>
        {!table.data?.length ? <Empty>No values match.</Empty> : (
          <table className="w-full"><thead><tr><th className="th">Test date</th><th className="th">Test</th><th className="th">Value</th><th className="th">Report range</th><th className="th">Flag</th><th className="th">Source</th><th className="th" /></tr></thead>
            <tbody>{table.data.map((e) => (
              <tr key={e.id} className="border-t border-slate-100 dark:border-slate-700">
                <td className="td">{e.test_date}</td><td className="td">{e.test_name}</td><td className="td">{e.value} {e.unit}</td>
                <td className="td">{e.ref_low != null ? `${e.ref_low} - ${e.ref_high}` : '-'}</td>
                <td className="td"><span className={`rounded-full px-2 py-0.5 text-xs font-bold ${flagClass(e.status)}`}>{flagText(e.status)}</span></td>
                <td className="td text-xs">{sourceLabel(e)}</td>
                <td className="td text-right"><ConfirmButton message="Delete this value?" onConfirm={() => del(e.id)}><Trash2 className="h-3.5 w-3.5" /><span className="sr-only">Delete value</span></ConfirmButton></td>
              </tr>))}</tbody></table>
        )}
      </div>

      <form onSubmit={addManual} className="space-y-2 rounded-xl border border-dashed border-slate-300 p-3 dark:border-slate-600">
        <h3 className="text-sm font-semibold">Add a lab value manually</h3>
        <ErrorBox message={error} />
        <datalist id="lab-tests">{tests.data?.map((t) => <option key={t.test_key} value={t.test_name} />)}</datalist>
        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <Field label="Test name"><input className="input" list="lab-tests" required minLength={2} maxLength={60} value={f.test_name} onChange={(e) => setF({ ...f, test_name: e.target.value })} placeholder="e.g. HbA1c" /></Field>
          <Field label="Value"><input className="input" type="number" step="any" min={0} required value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} /></Field>
          <Field label="Unit"><input className="input" maxLength={20} value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })} placeholder="%" /></Field>
          <Field label="Range low"><input className="input" type="number" step="any" min={0} value={f.ref_low} onChange={(e) => setF({ ...f, ref_low: e.target.value })} /></Field>
          <Field label="Range high"><input className="input" type="number" step="any" min={0} value={f.ref_high} onChange={(e) => setF({ ...f, ref_high: e.target.value })} /></Field>
          <Field label="Test date"><input className="input" type="date" required max={todayStr()} value={f.test_date} onChange={(e) => setF({ ...f, test_date: e.target.value })} /></Field>
        </div>
        <button className="btn-ghost btn-sm"><Plus className="h-3.5 w-3.5" /> Add value</button>
      </form>
    </section>
  )
}
