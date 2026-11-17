import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Moon, Save, Sun, Trash2 } from 'lucide-react'
import { api, type AiStatus, type User } from '../api'
import { useAuth } from '../auth'
import { useTheme } from '../theme'
import { ConfirmButton, ErrorBox, Field, ModeBadge, PageHeader, useAsync } from '../components/ui'

export default function SettingsPage() {
  const { user, setUser, logout } = useAuth()
  const { dark, toggle } = useTheme()
  const nav = useNavigate()
  const status = useAsync(() => api<AiStatus>('/api/status'))
  const [p, setP] = useState<User>(user!)
  const [pw, setPw] = useState({ current_password: '', new_password: '' })
  const [msg, setMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const set = <K extends keyof User>(k: K, v: User[K]) => setP({ ...p, [k]: v })

  async function saveProfile(e: FormEvent) {
    e.preventDefault(); setError(null); setMsg(null)
    try {
      const u = await api<User>('/api/auth/profile', { method: 'PUT', body: { ...p, age: p.age === null || (p.age as unknown) === '' ? null : Number(p.age) } })
      setUser(u); setP(u); setMsg('Profile saved.')
    } catch (err) { setError((err as Error).message) }
  }
  async function changePw(e: FormEvent) {
    e.preventDefault(); setError(null); setMsg(null)
    try { await api('/api/auth/change-password', { body: pw }); setPw({ current_password: '', new_password: '' }); setMsg('Password changed.') }
    catch (err) { setError((err as Error).message) }
  }
  async function wipe() {
    try { await api('/api/account/data', { method: 'DELETE' }); setMsg('All your health data was deleted.'); setP({ ...p, allergies: '', medical_history: '', blood_group: '' }) }
    catch (err) { setError((err as Error).message) }
  }
  async function deleteAccount() {
    try { await api('/api/account', { method: 'DELETE' }); logout(); nav('/login') } catch (err) { setError((err as Error).message) }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageHeader title="Profile & Settings" subtitle="Manage your profile, goals, appearance and privacy." />
      <ErrorBox message={error} />
      {msg && <div role="status" className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800">{msg}</div>}

      <form onSubmit={saveProfile} className="card space-y-3">
        <h2 className="font-semibold">Profile</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Full name"><input className="input" required minLength={2} maxLength={80} value={p.name} onChange={(e) => set('name', e.target.value)} /></Field>
          <Field label="Email"><input className="input" value={p.email} disabled /></Field>
          <Field label="Age"><input className="input" type="number" min={0} max={120} value={p.age ?? ''} onChange={(e) => set('age', e.target.value === '' ? null : Number(e.target.value))} /></Field>
          <Field label="Gender"><select className="input" value={p.gender} onChange={(e) => set('gender', e.target.value)}>{['', 'Female', 'Male', 'Other', 'Prefer not to say'].map((g) => <option key={g} value={g}>{g || '-'}</option>)}</select></Field>
          <Field label="Blood group"><select className="input" value={p.blood_group} onChange={(e) => set('blood_group', e.target.value)}>{['', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map((g) => <option key={g} value={g}>{g || '-'}</option>)}</select></Field>
        </div>
        <Field label="Allergies"><textarea className="input" rows={2} maxLength={500} value={p.allergies} onChange={(e) => set('allergies', e.target.value)} /></Field>
        <Field label="Existing medical history"><textarea className="input" rows={2} maxLength={1000} value={p.medical_history} onChange={(e) => set('medical_history', e.target.value)} /></Field>
        <h3 className="pt-2 text-sm font-semibold">Daily wellness goals</h3>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Water (ml)"><input className="input" type="number" min={500} max={6000} step={100} value={p.water_goal_ml} onChange={(e) => set('water_goal_ml', Number(e.target.value))} /></Field>
          <Field label="Sleep (hours)"><input className="input" type="number" min={3} max={12} step={0.5} value={p.sleep_goal_h} onChange={(e) => set('sleep_goal_h', Number(e.target.value))} /></Field>
          <Field label="Activity (minutes)"><input className="input" type="number" min={5} max={300} step={5} value={p.activity_goal_min} onChange={(e) => set('activity_goal_min', Number(e.target.value))} /></Field>
        </div>
        <button className="btn-primary"><Save className="h-4 w-4" /> Save profile</button>
      </form>

      <section className="card flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="font-semibold">Appearance</h2><p className="text-xs text-slate-500">Choose light or dark mode.</p></div>
        <button className="btn-ghost" onClick={toggle}>{dark ? <><Sun className="h-4 w-4" /> Switch to light</> : <><Moon className="h-4 w-4" /> Switch to dark</>}</button>
      </section>

      <section className="card">
        <h2 className="mb-1 font-semibold">AI service</h2>
        <p className="text-sm">Current mode: <ModeBadge mode={status.data?.mode} /> {status.data?.model && <span className="text-xs text-slate-500">({status.data.model})</span>}</p>
        <p className="mt-1 text-xs text-slate-500">
          {status.data?.mode === 'live' ? 'Questions are sent to the configured AI provider without your name or contact details.'
            : 'No API key is configured, so pre-written demo answers are used. Add GEMINI_API_KEY to backend/.env to enable live AI.'}
        </p>
      </section>

      <form onSubmit={changePw} className="card space-y-3">
        <h2 className="font-semibold">Change password</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Current password"><input className="input" type="password" required autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
          <Field label="New password" hint="8+ characters with a letter and a number"><input className="input" type="password" required minLength={8} autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
        </div>
        <button className="btn-ghost">Update password</button>
      </form>

      <section className="card border-red-200 dark:border-red-900">
        <h2 className="font-semibold text-red-700 dark:text-red-300">Privacy & data deletion</h2>
        <p className="mb-3 text-xs text-slate-500">You control your data. Deleting is permanent and cannot be undone.</p>
        <div className="flex flex-wrap gap-2">
          <ConfirmButton className="btn-ghost" message="Delete ALL your records, medicines, appointments, chats, wellness logs and uploaded reports? Your account will remain." onConfirm={wipe}><Trash2 className="h-4 w-4" /> Delete all my health data</ConfirmButton>
          <ConfirmButton className="btn-danger" message="Permanently delete your account and all data?" onConfirm={deleteAccount}><Trash2 className="h-4 w-4" /> Delete my account</ConfirmButton>
        </div>
      </section>
    </div>
  )
}
