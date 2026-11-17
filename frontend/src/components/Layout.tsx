import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Bell, CalendarClock, ClipboardList, FileText, HeartPulse, LayoutDashboard, LogOut, Menu, MessageCircle,
  Moon, Pill, Settings, Stethoscope, Sun, X, Droplets,
} from 'lucide-react'
import { api, nowStr, type Dashboard, type Notice } from '../api'
import { useAuth } from '../auth'
import { useTheme } from '../theme'
import { DISCLAIMER_SHORT } from './ui'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/chat', label: 'AI Health Chat', icon: MessageCircle },
  { to: '/symptoms', label: 'Symptom Info', icon: Stethoscope },
  { to: '/medicines', label: 'Medicines', icon: Pill },
  { to: '/records', label: 'Health Records', icon: ClipboardList },
  { to: '/wellness', label: 'Wellness', icon: Droplets },
  { to: '/appointments', label: 'Appointments', icon: CalendarClock },
  { to: '/report', label: 'Health Report', icon: FileText },
  { to: '/settings', label: 'Profile & Settings', icon: Settings },
]

const NOTIFIED_KEY = 'hm_notified'

export default function Layout() {
  const { user, logout } = useAuth()
  const { dark, toggle } = useTheme()
  const nav = useNavigate()
  const loc = useLocation()
  const [open, setOpen] = useState(false)
  const [bell, setBell] = useState(false)
  const [notices, setNotices] = useState<Notice[]>([])
  const bellRef = useRef<HTMLDivElement>(null)

  useEffect(() => setOpen(false), [loc.pathname])

  // Poll for reminders; fire browser notifications for recently due doses (once each).
  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const d = await api<Dashboard>(`/api/dashboard?now=${encodeURIComponent(nowStr())}`)
        if (!alive) return
        setNotices(d.notifications)
        if ('Notification' in window && Notification.permission === 'granted') {
          const done: string[] = JSON.parse(localStorage.getItem(NOTIFIED_KEY) || '[]')
          const cutoff = Date.now() - 90 * 60 * 1000
          d.schedule.filter((s) => s.status === 'overdue' && new Date(s.scheduled_for.replace(' ', 'T')).getTime() > cutoff).forEach((s) => {
            const key = `${s.medicine_id}|${s.scheduled_for}`
            if (!done.includes(key)) {
              new Notification('Medicine reminder', { body: `${s.name} (${s.dosage}) was due at ${s.time}` })
              done.push(key)
            }
          })
          localStorage.setItem(NOTIFIED_KEY, JSON.stringify(done.slice(-100)))
        }
      } catch { /* ignore polling errors */ }
    }
    tick()
    const id = setInterval(tick, 30000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  useEffect(() => {
    const h = (e: MouseEvent) => bellRef.current && !bellRef.current.contains(e.target as Node) && setBell(false)
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  const links = (
    <nav aria-label="Main navigation" className="flex flex-col gap-1 p-3">
      {NAV.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={to} end={to === '/'}
          className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
            isActive ? 'bg-teal-600 text-white shadow' : 'text-slate-600 hover:bg-teal-50 dark:text-slate-300 dark:hover:bg-slate-700'}`}>
          <Icon className="h-4 w-4" /> {label}
        </NavLink>
      ))}
    </nav>
  )

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white/90 px-3 backdrop-blur dark:border-slate-700 dark:bg-slate-800/90 md:px-5">
        <div className="flex items-center gap-2">
          <button className="btn-ghost btn-sm md:hidden" aria-label="Open menu" onClick={() => setOpen(true)}><Menu className="h-5 w-5" /></button>
          <button onClick={() => nav('/')} className="flex items-center gap-2 text-base font-bold text-teal-700 dark:text-teal-300 sm:text-lg" aria-label="HealthMate AI home">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-teal-500 to-sky-500 text-white"><HeartPulse className="h-5 w-5" /></span>
            HealthMate <span className="text-sky-500">AI</span>
          </button>
        </div>
        <div className="flex items-center gap-1 sm:gap-1.5 [&_.btn-sm]:px-2">
          <button className="btn-ghost btn-sm" onClick={toggle} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}>
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <div className="relative" ref={bellRef}>
            <button className="btn-ghost btn-sm relative" aria-label={`Notifications (${notices.length})`} aria-expanded={bell} onClick={() => setBell((b) => !b)}>
              <Bell className="h-4 w-4" />
              {notices.length > 0 && <span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">{notices.length}</span>}
            </button>
            {bell && (
              <div className="card absolute right-0 mt-2 w-72 p-3" role="menu">
                <p className="mb-2 text-sm font-semibold">Notifications</p>
                {notices.length === 0 ? <p className="text-xs text-slate-500">You are all caught up.</p> : (
                  <ul className="space-y-2">{notices.map((n, i) => (
                    <li key={i} className="rounded-lg bg-slate-50 p-2 text-xs dark:bg-slate-700"><b>{n.title}</b><br />{n.detail}</li>))}</ul>)}
              </div>
            )}
          </div>
          <button className="btn-ghost btn-sm" onClick={() => nav('/settings')} aria-label="Settings"><Settings className="h-4 w-4" /></button>
          <div className="ml-1 hidden items-center gap-2 sm:flex">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-sky-100 text-sm font-bold text-sky-700">{user?.name.charAt(0).toUpperCase()}</span>
            <span className="max-w-32 truncate text-sm font-medium">{user?.name}</span>
          </div>
          <button className="btn-ghost btn-sm" onClick={() => { logout(); nav('/login') }} aria-label="Log out"><LogOut className="h-4 w-4" /></button>
        </div>
      </header>

      <div className="mx-auto flex max-w-7xl">
        <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-60 shrink-0 overflow-y-auto border-r border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800 md:block">{links}</aside>

        {open && (
          <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Menu">
            <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
            <div className="relative h-full w-64 overflow-y-auto bg-white dark:bg-slate-800">
              <div className="flex justify-end p-2"><button className="btn-ghost btn-sm" aria-label="Close menu" onClick={() => setOpen(false)}><X className="h-4 w-4" /></button></div>
              {links}
            </div>
          </div>
        )}

        <main className="min-w-0 flex-1 p-4 pb-24 md:p-6 md:pb-6">
          <Outlet />
          <p className="mt-8 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
            <b>Medical disclaimer:</b> {DISCLAIMER_SHORT}
          </p>
        </main>
      </div>
    </div>
  )
}
