import { useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Copy, Printer, Stethoscope } from 'lucide-react'
import { api } from '../api'
import { Disclaimer, EmergencyBanner, ErrorBox, Field, Markdown, ModeBadge, PageHeader, Spinner, useAsync } from '../components/ui'

interface Catalog { symptoms: { name: string; red_flag: boolean }[]; severities: string[] }
interface Result {
  urgency: 'self_care' | 'routine' | 'soon' | 'emergency'; urgency_text: string; reasons: string[]; emergency_message: string | null
  explanations: string[]; self_care: string[]; warning_signs: string[]; doctor_summary: string; mode: string; demo_label?: string | null; disclaimer: string
}
const TONE: Record<Result['urgency'], string> = {
  self_care: 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100',
  routine: 'border-sky-300 bg-sky-50 text-sky-900 dark:bg-sky-950/40 dark:text-sky-100',
  soon: 'border-amber-400 bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-100',
  emergency: 'border-red-500 bg-red-50 text-red-900',
}

export default function Symptoms() {
  const [params] = useSearchParams()
  const { data: cat, error: catErr } = useAsync(() => api<Catalog>('/api/symptoms/catalog'))
  const [sel, setSel] = useState<string[]>([])
  const [days, setDays] = useState('2')
  const [severity, setSeverity] = useState('mild')
  const [notes, setNotes] = useState('')
  const [res, setRes] = useState<Result | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => { const s = params.get('s'); if (s) setSel(s.split(',').filter(Boolean)) }, [params])

  const toggle = (n: string) => setSel((s) => (s.includes(n) ? s.filter((x) => x !== n) : [...s, n]))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null); setRes(null)
    if (!sel.length) return setError('Please select at least one symptom.')
    setBusy(true)
    try {
      setRes(await api<Result>('/api/symptoms/check', { body: { symptoms: sel, duration_days: Number(days), severity, notes } }))
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }

  const copy = async () => { await navigator.clipboard.writeText(res!.doctor_summary); setCopied(true); setTimeout(() => setCopied(false), 1800) }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Symptom Information Checker" subtitle="General information only. This tool cannot diagnose a condition." />
      <ErrorBox message={catErr} />
      <form onSubmit={submit} className="card space-y-4">
        <ErrorBox message={error} />
        {!cat ? <Spinner /> : (
          <>
            <fieldset>
              <legend className="label">1. Select your symptoms</legend>
              <div className="flex flex-wrap gap-2">
                {cat.symptoms.map((s) => (
                  <button type="button" key={s.name} aria-pressed={sel.includes(s.name)} onClick={() => toggle(s.name)}
                    className={`chip ${sel.includes(s.name) ? (s.red_flag ? 'border-red-500 bg-red-50 text-red-700' : 'chip-on') : s.red_flag ? 'border-red-300 text-red-700' : ''}`}>
                    {s.red_flag && '⚠ '}{s.name}
                  </button>
                ))}
              </div>
              <p className="mt-1 text-[11px] text-slate-500">⚠ marks warning-sign symptoms that need urgent attention.</p>
            </fieldset>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="2. How long (days)?"><input className="input" type="number" min={0} max={365} required value={days} onChange={(e) => setDays(e.target.value)} /></Field>
              <Field label="3. Severity">
                <select className="input" value={severity} onChange={(e) => setSeverity(e.target.value)}>
                  {cat.severities.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </Field>
              <Field label="4. Other observations (optional)"><input className="input" maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. worse at night" /></Field>
            </div>
            <button className="btn-primary" disabled={busy}><Stethoscope className="h-4 w-4" /> {busy ? 'Checking…' : 'Get information'}</button>
          </>
        )}
      </form>

      {res && (
        <div className="mt-5 space-y-4" aria-live="polite">
          {res.urgency === 'emergency' && res.emergency_message && (
            <EmergencyBanner><Markdown text={res.emergency_message} /></EmergencyBanner>
          )}
          <div className={`rounded-2xl border-2 p-4 ${TONE[res.urgency]}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="font-bold">{res.urgency_text}</div><ModeBadge mode={res.mode} />
            </div>
            {res.reasons.length > 0 && <p className="mt-1 text-xs">Based on: {res.reasons.join(', ')}</p>}
            {res.demo_label && <p className="mt-1 text-xs">{res.demo_label}</p>}
          </div>

          {res.urgency !== 'emergency' && (
            <div className="grid gap-4 md:grid-cols-3">
              <Block title="Possible general explanations" items={res.explanations} note="These are possibilities only, not a diagnosis." />
              <Block title="General self-care ideas" items={res.self_care} />
              <Block title="Warning signs: seek care if you notice" items={res.warning_signs} danger />
            </div>
          )}

          <div className="card">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">Summary to share with your doctor</h2>
              <div className="flex gap-2">
                <button className="btn-ghost btn-sm" onClick={copy}><Copy className="h-3.5 w-3.5" /> {copied ? 'Copied!' : 'Copy'}</button>
                <button className="btn-ghost btn-sm" onClick={() => window.print()}><Printer className="h-3.5 w-3.5" /> Print</button>
              </div>
            </div>
            <pre className="whitespace-pre-wrap rounded-xl bg-slate-50 p-3 font-sans text-xs dark:bg-slate-900">{res.doctor_summary}</pre>
          </div>
          <Disclaimer text={res.disclaimer} />
        </div>
      )}
    </div>
  )
}

function Block({ title, items, note, danger }: { title: string; items: string[]; note?: string; danger?: boolean }) {
  return (
    <div className={`card ${danger ? 'border-red-200 dark:border-red-900' : ''}`}>
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      <ul className="list-disc space-y-1 pl-5 text-sm">{items.map((i, k) => <li key={k}>{i}</li>)}</ul>
      {note && <p className="mt-2 text-[11px] text-slate-500">{note}</p>}
    </div>
  )
}
