import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Chat from './pages/Chat'
import Symptoms from './pages/Symptoms'
import Medicines from './pages/Medicines'
import Records from './pages/Records'
import Wellness from './pages/Wellness'
import Appointments from './pages/Appointments'
import Report from './pages/Report'
import SettingsPage from './pages/Settings'

export default function App() {
  const { user, loading } = useAuth()
  if (loading) return <div className="grid min-h-screen place-items-center"><Spinner /></div>
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="chat" element={<Chat />} />
        <Route path="symptoms" element={<Symptoms />} />
        <Route path="medicines" element={<Medicines />} />
        <Route path="records" element={<Records />} />
        <Route path="wellness" element={<Wellness />} />
        <Route path="appointments" element={<Appointments />} />
        <Route path="report" element={<Report />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
