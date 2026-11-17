import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, getToken, setToken, type User } from './api'

interface AuthCtx {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string, age?: number) => Promise<void>
  logout: () => void
  setUser: (u: User) => void
}
const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(!!getToken())

  useEffect(() => {
    if (!getToken()) return
    api<User>('/api/auth/me').then(setUser).catch(() => setToken(null)).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const h = () => setUser(null)
    window.addEventListener('hm-unauthorized', h)
    return () => window.removeEventListener('hm-unauthorized', h)
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const r = await api<{ token: string; user: User }>('/api/auth/login', { body: { email, password } })
    setToken(r.token); setUser(r.user)
  }, [])
  const register = useCallback(async (name: string, email: string, password: string, age?: number) => {
    const r = await api<{ token: string; user: User }>('/api/auth/register', { body: { name, email, password, age: age ?? null } })
    setToken(r.token); setUser(r.user)
  }, [])
  const logout = useCallback(() => { setToken(null); setUser(null) }, [])

  return <Ctx.Provider value={{ user, loading, login, register, logout, setUser }}>{children}</Ctx.Provider>
}
