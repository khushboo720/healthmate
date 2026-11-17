import { useRef, useState, type FormEvent } from 'react'
import { AlertTriangle, ClipboardPaste, FileText, FileUp, Trash2, X } from 'lucide-react'
import { api, type DraftItem, type Prescription, type RxDraft } from '../api'
import { ConfirmButton, Empty, ErrorBox, Field, Spinner, useAsync } from './ui'

const TIME_RX = /^([01]\d|2[0-3]):[0-5]\d$/
type Row = DraftItem & { timesText: string }

/** Upload or paste a prescription, review what was captured, then create linked reminders. */
export function PrescriptionImport({ onCreated }: { onCreated: () => void }) {
  const [tab, setTab] = useState<'file' | 'text'>('file')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const [draft, setDraft] = useState<RxDraft | null>(null)
  const [rowsState, setRows] = useState<Row[]>([])
  const [doctor, setDoctor] = useState('')
  const [rxDate, setRxDate] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  async function read(e: FormEvent) {
    e.preventDefault(); setError(null); setDone(null)
    const form = new FormData()
    if (tab === 'file') {
      const f = fileRef.current?.files?.[0]
      if (!f) return setError('Choose a prescription file (PDF or TXT).')
      form.append('file', f)
    } else {
      if (!text.trim()) return setError('Paste the prescription text first.')
      form.append('text', text)
    }
    setBusy(true)
    try {
      const d = await api<RxDraft>('/api/prescriptions', { form })
      setDraft(d); setDoctor(d.doctor); setRxDate(d.prescribed_on)
      setRows(d.items.map((i) => ({ ...i, timesText: i.times.join(', ') })))
      if (fileRef.current) fileRef.current.value = ''
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }

  const update = (i: number, patch: Partial<Row>) => setRows((r) => r.map((x, k) => (k === i ? { ...x, ...patch } : x)))
  const addRow = () => setRows((r) => [...r, { name: '', dosage: '', times: [], timesText: '08:00', frequency: 'daily', start_date: rxDate, end_date: null, notes: '', raw: 'Added manually', as_needed: false, needs_review: false, include: true }])

  async function cancel() {
    if (draft) await api(`/api/prescriptions/${draft.id}`, { method: 'DELETE' }).catch(() => undefined)
    setDraft(null); setRows([])
  }

  async function save() {
    setError(null)
    const chosen = rowsState.filter((r) => r.include)
    if (!chosen.length) return setError('Tick at least one medicine to create reminders.')
    const items = []
    for (const r of chosen) {
      const times = r.timesText.split(/[,\s]+/).filter(Boolean)
      if (!r.name.trim() || !r.dosage.trim()) return setError('Every ticked medicine needs a name and the dosage written on the prescription.')
      if (!times.length || !times.every((t) => TIME_RX.test(t))) return setError(`Enter reminder times for ${r.name || 'each medicine'} as HH:MM, e.g. 08:00, 20:00.`)
      if (r.end_date && r.end_date < r.start_date) return setError(`End date is before start date for ${r.name}.`)
      items.push({ name: r.name, dosage: r.dosage, times, frequency: r.frequency, start_date: r.start_date, end_date: r.end_date || null, notes: r.notes })
    }
    setBusy(true)
    try {
      const res = await api<{ created: number }>(`/api/prescriptions/${draft!.id}/reminders`, { body: { doctor, prescribed_on: rxDate, items } })
      setDone(`${res.created} reminder(s) created from the prescription${doctor ? ` by ${doctor}` : ''}.`)
      setDraft(null); setRows([]); setText(''); onCreated()
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }

  return (
    <section className="card space-y-3" aria-labelledby="rx-h">
      <h2 id="rx-h" className="flex items-center gap-2 font-semibold"><FileText className="h-4 w-4" /> Add reminders from a doctor's prescription</h2>
      <p className="text-xs text-slate-500">Upload a text-based PDF or TXT, or paste the prescription. Medicines, timings (e.g. 1-0-1, OD, BD, TDS) and duration are captured on this device. You review everything before any reminder is created.</p>
      <ErrorBox message={error} />
      {done && <div role="status" className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800">{done}</div>}

      {!draft && (
        <form onSubmit={read} className="space-y-3">
          <div className="flex gap-2" role="tablist" aria-label="Prescription input">
            <button type="button" role="tab" aria-selected={tab === 'file'} className={`chip ${tab === 'file' ? 'chip-on' : ''}`} onClick={() => setTab('file')}><FileUp className="mr-1 h-3 w-3" /> Upload file</button>
            <button type="button" role="tab" aria-selected={tab === 'text'} className={`chip ${tab === 'text' ? 'chip-on' : ''}`} onClick={() => setTab('text')}><ClipboardPaste className="mr-1 h-3 w-3" /> Paste text</button>
          </div>
          {tab === 'file'
            ? <input ref={fileRef} aria-label="Choose prescription file" type="file" accept=".pdf,.txt,application/pdf,text/plain" className="input max-w-md" />
            : <textarea aria-label="Prescription text" className="input font-mono text-xs" rows={6} maxLength={20000} value={text} onChange={(e) => setText(e.target.value)}
                placeholder={'Dr. Name\nDate: 15/11/2026\n1. Tab Cetirizine 10 mg 0-0-1 x 10 days\n2. Cap Omeprazole 20 mg OD before breakfast for 14 days'} />}
          <button className="btn-primary" disabled={busy}><FileUp className="h-4 w-4" /> {busy ? 'Reading…' : 'Read prescription'}</button>
          <p className="text-[11px] text-slate-500">Photos and scanned images are not supported (no OCR). For a demo, use <code>sample_data/sample_prescription.pdf</code>.</p>
        </form>
      )}

      {draft && (
        <div className="space-y-3">
          <div role="note" className="flex items-start gap-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {draft.review_note}
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Prescribed by"><input className="input" maxLength={80} value={doctor} onChange={(e) => setDoctor(e.target.value)} placeholder="Doctor name" /></Field>
            <Field label="Prescription date" hint={draft.date_detected ? 'Detected from the prescription' : 'Not found on the prescription; please check'}>
              <input className="input" type="date" required value={rxDate} onChange={(e) => setRxDate(e.target.value)} />
            </Field>
            <Field label="Source"><input className="input" disabled value={draft.filename || 'Pasted text'} /></Field>
          </div>

          {rowsState.length === 0 && <Empty>No medicine lines were recognised. Add them manually below, copying from your prescription.</Empty>}
          <ul className="space-y-3">
            {rowsState.map((r, i) => (
              <li key={i} className={`rounded-xl border p-3 ${r.include ? 'border-teal-300 dark:border-teal-800' : 'border-slate-200 opacity-80 dark:border-slate-700'}`}>
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <label className="flex items-center gap-2 text-sm font-semibold">
                    <input type="checkbox" className="h-4 w-4 accent-teal-600" checked={r.include} onChange={(e) => update(i, { include: e.target.checked })} />
                    Create reminder
                  </label>
                  {r.as_needed && <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-bold text-slate-700">AS NEEDED · NO FIXED TIME</span>}
                  {r.needs_review && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-800">TIMING NOT FOUND · PLEASE ENTER</span>}
                  <span className="ml-auto truncate text-[11px] text-slate-500" title={r.raw}>From prescription: “{r.raw}”</span>
                  <button type="button" className="btn-ghost btn-sm" aria-label={`Remove ${r.name || 'row'}`} onClick={() => setRows((x) => x.filter((_, k) => k !== i))}><X className="h-3 w-3" /></button>
                </div>
                <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
                  <Field label="Medicine"><input aria-label={`Medicine name ${i + 1}`} className="input" maxLength={80} value={r.name} onChange={(e) => update(i, { name: e.target.value })} /></Field>
                  <Field label="Dosage (as written)"><input aria-label={`Dosage ${i + 1}`} className="input" maxLength={80} value={r.dosage} onChange={(e) => update(i, { dosage: e.target.value })} /></Field>
                  <Field label="Times (HH:MM)"><input aria-label={`Times ${i + 1}`} className="input" value={r.timesText} onChange={(e) => update(i, { timesText: e.target.value })} placeholder="08:00, 20:00" /></Field>
                  <Field label="Frequency">
                    <select aria-label={`Frequency ${i + 1}`} className="input" value={r.frequency} onChange={(e) => update(i, { frequency: e.target.value })}>
                      <option value="daily">Every day</option><option value="alternate">Alternate days</option><option value="weekly">Once a week</option>
                    </select>
                  </Field>
                  <Field label="Start"><input aria-label={`Start date ${i + 1}`} className="input" type="date" value={r.start_date} onChange={(e) => update(i, { start_date: e.target.value })} /></Field>
                  <Field label="End (duration)"><input aria-label={`End date ${i + 1}`} className="input" type="date" value={r.end_date ?? ''} onChange={(e) => update(i, { end_date: e.target.value || null })} /></Field>
                </div>
                {r.notes && <p className="mt-1 text-xs text-slate-500">Instructions: {r.notes}</p>}
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-primary" disabled={busy} onClick={save}>{busy ? 'Saving…' : `Create ${rowsState.filter((r) => r.include).length} reminder(s)`}</button>
            <button type="button" className="btn-ghost" onClick={addRow}>+ Add a medicine manually</button>
            <button type="button" className="btn-ghost" onClick={cancel}>Cancel</button>
          </div>
        </div>
      )}
    </section>
  )
}

/** Saved prescriptions with the reminders created from each one. */
export function PrescriptionList({ version, onChanged }: { version: number; onChanged: () => void }) {
  const list = useAsync(() => api<Prescription[]>('/api/prescriptions'), [version])
  const [open, setOpen] = useState<Record<number, string>>({})

  async function toggle(id: number) {
    if (open[id] !== undefined) return setOpen(({ [id]: _, ...rest }) => rest)
    const p = await api<{ text: string }>(`/api/prescriptions/${id}`)
    setOpen((o) => ({ ...o, [id]: p.text || '(no text stored)' }))
  }
  const del = async (id: number, withReminders: boolean) => {
    await api(`/api/prescriptions/${id}${withReminders ? '?with_reminders=true' : ''}`, { method: 'DELETE' })
    list.reload(); onChanged()
  }

  return (
    <section className="card">
      <h2 className="mb-2 font-semibold">My prescriptions</h2>
      {list.loading && !list.data ? <Spinner /> : !list.data?.length ? <Empty>No prescriptions saved yet.</Empty> : (
        <ul className="space-y-3">
          {list.data.map((p) => (
            <li key={p.id} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-medium">{p.doctor || 'Doctor not recorded'}</div>
                  <div className="text-xs text-slate-500">Prescribed {p.prescribed_on}{p.filename ? ` · ${p.filename}` : ''}{p.notes ? ` · ${p.notes}` : ''}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button className="btn-ghost btn-sm" onClick={() => toggle(p.id)} aria-expanded={open[p.id] !== undefined}>{open[p.id] !== undefined ? 'Hide text' : 'View text'}</button>
                  <ConfirmButton message="Delete this prescription? Its reminders will be kept." onConfirm={() => del(p.id, false)}><Trash2 className="h-3.5 w-3.5" /> Delete</ConfirmButton>
                  {p.medicines.length > 0 && <ConfirmButton className="btn-ghost btn-sm text-red-600" message="Delete this prescription AND all reminders created from it?" onConfirm={() => del(p.id, true)}>Delete with reminders</ConfirmButton>}
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {p.medicines.length === 0 ? <span className="text-xs text-slate-500">No reminders created from this prescription.</span>
                  : p.medicines.map((m) => <span key={m.id} className={`chip ${m.active ? 'chip-on' : ''}`}>{m.name} · {m.times.join(', ')}</span>)}
              </div>
              {open[p.id] !== undefined && <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-2 text-[11px] dark:bg-slate-900">{open[p.id]}</pre>}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
