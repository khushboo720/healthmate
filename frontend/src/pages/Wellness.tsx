import { useEffect, useState, type FormEvent } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Droplets, Dumbbell, Moon, Save, Sparkles } from 'lucide-react'
import { api, todayStr, type WellnessDay } from '../api'
import { Disclaimer, ErrorBox, Field, Markdown, ModeBadge, PageHeader, Spinner, useAsync } from '../components/ui'

interface Wellness { days: WellnessDay[]; goals: { water_ml: number; sleep_h: number; activity_min: number } }
interface Summary { days_logged: number; avg_water_ml: number; avg_sleep_h: number; avg_activity_min: number; avg_progress: number; text: string; mode: string }
interface Suggest { suggestions: string[]; mode: string; demo_label?: string | null; disclaimer: string }
const MOODS = ['', 'Happy', 'Calm', 'Good', 'Tired', 'Stressed']

function Bar1({ value, goal, label, unit, icon: Icon, color }: { value: number; goal: number; label: string; unit: string; icon: typeof Droplets; color: string }) {
  const pct = Math.min(100, Math.round((value / goal) * 100))
  return (
    <div className="card">
      <div className="mb-2 flex items-center justify-between text-sm"><span className="flex items-center gap-2 font-semibold"><Icon className="h-4 w-4" /> {label}</span><span>{value} / {goal} {unit}</span></div>
      <div className="h-3 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${label} progress`}>
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function Mini({ title, data, k, color }: { title: string; data: WellnessDay[]; k: keyof WellnessDay; color: string }) {
  return (
    <div className="card"><h3 className="mb-2 text-sm font-semibold">{title}</h3>
      <div className="h-36" role="img" aria-label={`${title} chart`}><ResponsiveContainer><BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="log_date" tickFormatter={(v: string) => v.slice(8)} fontSize={10} /><YAxis fontSize={10} /><Tooltip />
        <Bar dataKey={k as string} fill={color} radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></div>
  )
}

export default function Wellness() {
  const w = useAsync(() => api<Wellness>('/api/wellness?days=7'))
  const sum = useAsync(() => api<Summary>('/api/wellness/summary'))
  const [water, setWater] = useState(0); const [sleep, setSleep] = useState(0); const [act, setAct] = useState(0); const [mood, setMood] = useState('')
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [prefs, setPrefs] = useState({ diet: 'no preference', goal: 'general wellbeing', activity_level: 'moderate' })
  const [sug, setSug] = useState<Suggest | null>(null)
  const [sugBusy, setSugBusy] = useState(false)

  useEffect(() => {
    const t = w.data?.days.at(-1)
    if (t) { setWater(t.water_ml); setSleep(t.sleep_hours); setAct(t.activity_min); setMood(t.mood) }
  }, [w.data])

  async function save(e?: FormEvent) {
    e?.preventDefault(); setError(null)
    try {
      await api(`/api/wellness/${todayStr()}`, { method: 'PUT', body: { water_ml: water, sleep_hours: sleep, activity_min: act, mood } })
      setSaved(true); setTimeout(() => setSaved(false), 1800); w.reload(); sum.reload()
    } catch (err) { setError((err as Error).message) }
  }
  async function suggest(e: FormEvent) {
    e.preventDefault(); setSugBusy(true); setError(null)
    try { setSug(await api<Suggest>('/api/wellness/suggestions', { body: prefs })) } catch (err) { setError((err as Error).message) } finally { setSugBusy(false) }
  }

  if (!w.data) return w.error ? <ErrorBox message={w.error} /> : <Spinner />
  const g = w.data.goals
  return (
    <div className="space-y-5">
      <PageHeader title="Wellness Tracker" subtitle="Track hydration, sleep and activity. Goals can be changed in your profile." />
      <ErrorBox message={error} />

      <div className="grid gap-4 md:grid-cols-3">
        <Bar1 value={water} goal={g.water_ml} label="Hydration" unit="ml" icon={Droplets} color="bg-sky-500" />
        <Bar1 value={sleep} goal={g.sleep_h} label="Sleep" unit="h" icon={Moon} color="bg-violet-500" />
        <Bar1 value={act} goal={g.activity_min} label="Activity" unit="min" icon={Dumbbell} color="bg-emerald-500" />
      </div>

      <form onSubmit={save} className="card space-y-3">
        <h2 className="font-semibold">Today's log</h2>
        <div className="grid gap-3 sm:grid-cols-4">
          <Field label="Water (ml)"><input className="input" type="number" min={0} max={10000} value={water} onChange={(e) => setWater(Number(e.target.value))} /></Field>
          <Field label="Sleep (hours)"><input className="input" type="number" min={0} max={24} step={0.5} value={sleep} onChange={(e) => setSleep(Number(e.target.value))} /></Field>
          <Field label="Activity (minutes)"><input className="input" type="number" min={0} max={1440} value={act} onChange={(e) => setAct(Number(e.target.value))} /></Field>
          <Field label="Mood"><select className="input" value={mood} onChange={(e) => setMood(e.target.value)}>{MOODS.map((m) => <option key={m} value={m}>{m || '-'}</option>)}</select></Field>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="btn-ghost btn-sm" onClick={() => setWater(water + 250)}>+250 ml water</button>
          <button type="button" className="btn-ghost btn-sm" onClick={() => setAct(act + 10)}>+10 min activity</button>
          <button className="btn-primary ml-auto"><Save className="h-4 w-4" /> {saved ? 'Saved!' : 'Save today'}</button>
        </div>
      </form>

      <section className="grid gap-4 md:grid-cols-3" aria-label="Weekly charts">
        <Mini title="Water (ml), last 7 days" data={w.data.days} k="water_ml" color="#0ea5e9" />
        <Mini title="Sleep (hours)" data={w.data.days} k="sleep_hours" color="#8b5cf6" />
        <Mini title="Activity (minutes)" data={w.data.days} k="activity_min" color="#10b981" />
      </section>

      <section className="card">
        <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold">Weekly wellness summary</h2><ModeBadge mode={sum.data?.mode} /></div>
        {sum.data && (
          <>
            <div className="mb-3 grid grid-cols-2 gap-2 text-center text-sm sm:grid-cols-4">
              {[[`${sum.data.avg_water_ml} ml`, 'Avg water'], [`${sum.data.avg_sleep_h} h`, 'Avg sleep'], [`${sum.data.avg_activity_min} min`, 'Avg activity'], [`${sum.data.avg_progress}%`, 'Avg goal progress']].map(([v, l]) => (
                <div key={l} className="rounded-xl bg-slate-50 p-2 dark:bg-slate-700"><div className="font-bold">{v}</div><div className="text-[11px] text-slate-500">{l}</div></div>))}
            </div>
            <p className="text-sm"><Markdown text={sum.data.text} /></p>
          </>
        )}
      </section>

      <form onSubmit={suggest} className="card space-y-3">
        <h2 className="flex items-center gap-2 font-semibold"><Sparkles className="h-4 w-4" /> Healthy habit suggestions</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Diet preference"><select className="input" value={prefs.diet} onChange={(e) => setPrefs({ ...prefs, diet: e.target.value })}>
            {['no preference', 'vegetarian', 'vegan', 'non-vegetarian', 'eggetarian'].map((d) => <option key={d}>{d}</option>)}</select></Field>
          <Field label="Goal"><select className="input" value={prefs.goal} onChange={(e) => setPrefs({ ...prefs, goal: e.target.value })}>
            {['general wellbeing', 'more energy', 'better sleep', 'stay active', 'stress management'].map((d) => <option key={d}>{d}</option>)}</select></Field>
          <Field label="Activity level"><select className="input" value={prefs.activity_level} onChange={(e) => setPrefs({ ...prefs, activity_level: e.target.value })}>
            {['low', 'moderate', 'high'].map((d) => <option key={d}>{d}</option>)}</select></Field>
        </div>
        <button className="btn-primary" disabled={sugBusy}>{sugBusy ? 'Thinking…' : 'Get suggestions'}</button>
        {sug && (
          <div aria-live="polite">
            <div className="mb-1 flex items-center gap-2"><ModeBadge mode={sug.mode} />{sug.demo_label && <span className="text-xs text-slate-500">{sug.demo_label}</span>}</div>
            <ul className="list-disc space-y-1 pl-5 text-sm">{sug.suggestions.map((s, i) => <li key={i}>{s}</li>)}</ul>
          </div>
        )}
      </form>
      <Disclaimer text="Suggestions are general wellness ideas, not medical or dietary prescriptions. Ask a doctor or dietitian about your personal needs." />
    </div>
  )
}
