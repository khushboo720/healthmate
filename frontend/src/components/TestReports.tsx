import { useRef, useState } from 'react'
import { Calendar, FileUp, Sparkles, Trash2 } from 'lucide-react'
import { api, todayStr, type LabReport } from '../api'
import { flagClass, flagText, Trend } from './LabHistory'
import { ConfirmButton, Empty, ErrorBox, Field, Markdown, ModeBadge, Spinner, useAsync } from './ui'

/** Upload test reports (PDF/TXT). Values with printed reference ranges are captured into the lab history. */
export default function TestReports({ version, onChanged }: { version: number; onChanged: () => void }) {
  const reports = useAsync(() => api<LabReport[]>('/api/records/reports'), [version])
  const fileRef = useRef<HTMLInputElement>(null)
  const [testDate, setTestDate] = useState('')
  const [busy, setBusy] = useState(false)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [editDate, setEditDate] = useState<Record<number, string>>({})

  async function upload() {
    const file = fileRef.current?.files?.[0]
    setError(null); setNotice(null)
    if (!file) return setError('Choose a test report file (PDF or TXT).')
    const form = new FormData(); form.append('file', file)
    if (testDate) form.append('test_date', testDate)
    setBusy(true)
    try {
      const r = await api<LabReport>('/api/records/reports', { form })
      setNotice(`Captured ${r.captured} value(s) from ${r.filename}. Test date ${r.test_date} (${r.date_source}). Check the date and values below.`)
      if (fileRef.current) fileRef.current.value = ''
      setTestDate(''); onChanged()
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }
  const act = async (id: number, fn: () => Promise<unknown>) => {
    setBusyId(id); setError(null)
    try { await fn(); onChanged() } catch (err) { setError((err as Error).message) } finally { setBusyId(null) }
  }
  const saveDate = (id: number) => act(id, async () => {
    await api(`/api/records/reports/${id}`, { method: 'PATCH', body: { test_date: editDate[id] } })
    setEditDate(({ [id]: _, ...rest }) => rest)
  })

  return (
    <section className="card" aria-labelledby="reports-h">
      <h2 id="reports-h" className="mb-1 flex items-center gap-2 font-semibold"><FileUp className="h-4 w-4" /> Upload test reports</h2>
      <p className="mb-3 text-xs text-slate-500">Values with a printed reference range (e.g. <i>Hemoglobin 11.2 g/dL (12.0 - 15.5)</i>) are captured and saved to your lab history.
        The test date is read from the report (e.g. "Collected on"), or you can set it. Text is read on the server; only parsed test values are sent to an AI service, and only when you press Summarize.</p>
      <ErrorBox message={error} />
      {notice && <div role="status" className="mb-3 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Report file (PDF or TXT)"><input ref={fileRef} aria-label="Choose report file" type="file" accept=".pdf,.txt,application/pdf,text/plain" className="input max-w-sm" /></Field>
        <Field label="Test date (optional)"><input aria-label="Report test date" type="date" max={todayStr()} className="input w-auto" value={testDate} onChange={(e) => setTestDate(e.target.value)} /></Field>
        <button className="btn-primary" disabled={busy} onClick={upload}><FileUp className="h-4 w-4" /> {busy ? 'Reading…' : 'Upload & capture values'}</button>
      </div>

      <div className="mt-4 space-y-4">
        {reports.loading && !reports.data ? <Spinner /> : reports.data?.length === 0 ? <Empty>No reports uploaded yet. Try <code>sample_data/sample_lab_report.pdf</code>.</Empty> : null}
        {reports.data?.map((r) => (
          <div key={r.id} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-sm font-semibold">{r.filename}</div>
                <div className="flex items-center gap-1 text-xs text-slate-500"><Calendar className="h-3 w-3" /> Test date {r.test_date} · uploaded {r.created_at.slice(0, 10)}</div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {editDate[r.id] !== undefined ? (
                  <>
                    <input aria-label={`New test date for ${r.filename}`} type="date" max={todayStr()} className="input w-auto py-1" value={editDate[r.id]} onChange={(e) => setEditDate({ ...editDate, [r.id]: e.target.value })} />
                    <button className="btn-primary btn-sm" disabled={busyId === r.id || !editDate[r.id]} onClick={() => saveDate(r.id)}>Save date</button>
                    <button className="btn-ghost btn-sm" onClick={() => setEditDate(({ [r.id]: _, ...rest }) => rest)}>Cancel</button>
                  </>
                ) : <button className="btn-ghost btn-sm" onClick={() => setEditDate({ ...editDate, [r.id]: r.test_date })}>Change date</button>}
                <button className="btn-ghost btn-sm" disabled={busyId === r.id} onClick={() => act(r.id, () => api(`/api/records/reports/${r.id}/summarize`, { method: 'POST', body: {} }))}>
                  <Sparkles className="h-3.5 w-3.5" /> {busyId === r.id ? 'Working…' : 'Summarize'}
                </button>
                <ConfirmButton message="Delete this report and the values captured from it?" onConfirm={() => act(r.id, () => api(`/api/records/reports/${r.id}`, { method: 'DELETE' }))}>
                  <Trash2 className="h-3.5 w-3.5" /><span className="sr-only">Delete report</span>
                </ConfirmButton>
              </div>
            </div>
            {r.results.length === 0 ? <p className="mt-2 text-xs text-slate-500">No values with printed reference ranges were found, so nothing was captured.</p> : (
              <div className="overflow-x-auto">
                <table className="mt-2 w-full"><thead><tr><th className="th">Test</th><th className="th">Value</th><th className="th">Report range</th><th className="th">Flag</th><th className="th">Previous</th></tr></thead>
                  <tbody>{r.results.map((x, i) => (
                    <tr key={i} className="border-t border-slate-100 dark:border-slate-700">
                      <td className="td">{x.name}</td><td className="td">{x.value} {x.unit}</td><td className="td">{x.low} - {x.high}</td>
                      <td className="td"><span className={`rounded-full px-2 py-0.5 text-xs font-bold ${flagClass(x.status)}`}>{flagText(x.status)}</span></td>
                      <td className="td text-xs">{x.previous ? <>{x.previous.value} on {x.previous.test_date} <Trend now={x.value} before={x.previous.value} /></> : <span className="text-slate-400">first result</span>}</td>
                    </tr>))}</tbody></table>
              </div>
            )}
            {r.summary && <div className="mt-3 rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-900"><ModeBadge mode={r.summary_mode} /><Markdown text={r.summary} /></div>}
          </div>
        ))}
      </div>
    </section>
  )
}
