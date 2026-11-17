import { useState } from 'react'
import { Download, FileText } from 'lucide-react'
import { api } from '../api'
import { Disclaimer, ErrorBox, PageHeader } from '../components/ui'

export default function Report() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  async function download() {
    setBusy(true); setError(null); setDone(false)
    try {
      const blob = await api<Blob>('/api/report/pdf', { raw: true })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `healthmate-report-${new Date().toISOString().slice(0, 10)}.pdf`
      a.click(); URL.revokeObjectURL(url); setDone(true)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Health Report Generator" subtitle="Create a PDF you can keep or share with your doctor." />
      <ErrorBox message={error} />
      <div className="card">
        <div className="mb-4 flex items-center gap-3"><span className="grid h-12 w-12 place-items-center rounded-2xl bg-teal-100 text-teal-700"><FileText className="h-6 w-6" /></span>
          <div><h2 className="font-semibold">Personal health report (PDF)</h2><p className="text-xs text-slate-500">Generated from your saved data.</p></div></div>
        <ul className="mb-4 list-disc space-y-1 pl-5 text-sm">
          <li>User profile, allergies and medical history</li><li>Recorded health metrics</li><li>Medicine list and reminder history with adherence</li>
          <li>Wellness activity summary (last 7 days)</li><li>Doctor appointment details</li><li>General health summary (clearly labelled as AI-generated or demo template)</li>
        </ul>
        <button className="btn-primary" onClick={download} disabled={busy}><Download className="h-4 w-4" /> {busy ? 'Generating…' : 'Generate & download PDF'}</button>
        {done && <p role="status" className="mt-3 text-sm text-emerald-700">Report downloaded.</p>}
        <p className="mt-3 text-xs text-slate-500">Your report is built on the server from your own data. The PDF contains personal health information, so store and share it carefully.</p>
      </div>
      <Disclaimer text="The report is informational and is NOT a medical diagnosis. AI-generated text is labelled as such. Always discuss your health with a qualified doctor." />
    </div>
  )
}
