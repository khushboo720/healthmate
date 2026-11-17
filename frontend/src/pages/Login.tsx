import { useState, type FormEvent } from 'react'
import { HeartPulse, ShieldCheck } from 'lucide-react'
import { useAuth } from '../auth'
import { Disclaimer, ErrorBox, Field } from '../components/ui'

export default function Login() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [f, setF] = useState({ name: '', email: '', password: '', age: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (mode === 'login') await login(f.email, f.password)
      else await register(f.name, f.email, f.password, f.age ? Number(f.age) : undefined)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <section className="hidden flex-col justify-center bg-gradient-to-br from-teal-600 via-teal-500 to-sky-500 p-12 text-white lg:flex">
        <HeartPulse className="mb-6 h-14 w-14" />
        <h1 className="text-4xl font-bold">HealthMate AI</h1>
        <p className="mt-2 text-xl text-teal-50">Your Personal Health Assistant</p>
        <ul className="mt-8 space-y-3 text-teal-50">
          <li>• Understand general health information with an AI chatbot</li>
          <li>• Track medicines, records, hydration, sleep and activity</li>
          <li>• Manage doctor appointments and download a health report</li>
        </ul>
        <p className="mt-10 flex items-center gap-2 text-sm text-teal-100"><ShieldCheck className="h-4 w-4" /> Educational tool. Never a replacement for a doctor.</p>
      </section>

      <section className="flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <div className="mb-6 flex items-center gap-2 text-2xl font-bold text-teal-700 lg:hidden dark:text-teal-300"><HeartPulse /> HealthMate AI</div>
          <h2 className="text-2xl font-bold">{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2>
          <p className="mb-5 text-sm text-slate-500">{mode === 'login' ? 'Log in to your health dashboard.' : 'Register to start tracking your health.'}</p>

          <form onSubmit={submit} className="card space-y-3">
            <ErrorBox message={error} />
            {mode === 'register' && (
              <>
                <Field label="Full name"><input className="input" required minLength={2} maxLength={80} value={f.name} onChange={set('name')} autoComplete="name" /></Field>
                <Field label="Age (optional)"><input className="input" type="number" min={0} max={120} value={f.age} onChange={set('age')} /></Field>
              </>
            )}
            <Field label="Email"><input className="input" type="email" required value={f.email} onChange={set('email')} autoComplete="email" /></Field>
            <Field label="Password" hint={mode === 'register' ? 'At least 8 characters with a letter and a number.' : undefined}>
              <input className="input" type="password" required value={f.password} onChange={set('password')} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
            </Field>
            <button className="btn-primary w-full" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}</button>
            <button type="button" className="w-full text-sm text-teal-700 underline dark:text-teal-300"
              onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null) }}>
              {mode === 'login' ? 'New here? Create an account' : 'Already registered? Log in'}
            </button>
          </form>

          {mode === 'login' && (
            <div className="mt-4 rounded-2xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-900 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-100">
              <b>Demo account (synthetic data)</b>
              <div className="mt-1 font-mono text-xs">demo@healthmate.ai / Demo@1234</div>
              <button type="button" className="btn-ghost btn-sm mt-2" onClick={() => setF({ ...f, email: 'demo@healthmate.ai', password: 'Demo@1234' })}>Fill demo credentials</button>
            </div>
          )}
          <Disclaimer />
        </div>
      </section>
    </div>
  )
}
