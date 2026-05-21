import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import './index.css'
import { useAuthStore } from './store/auth'
import { useThemeStore } from './store/theme'
import { LanguageProvider } from './Context/LanguageContext'

// Components
import PortalLayout from './Components/PortalLayout'

// Lazy load pages
const Home           = React.lazy(() => import('./pages/Home'))
const Login         = React.lazy(() => import('./pages/Login'))
const PatientLanding = React.lazy(() => import('./pages/PatientLanding'))
const PatientApp    = React.lazy(() => import('./pages/PatientApp_voice_integration'))
const AdminPortal   = React.lazy(() => import('./pages/AdminPortal'))
const AdminIntro    = React.lazy(() => import('./pages/AdminIntro'))
const PatientDashboard = React.lazy(() => import('./pages/PatientDashboard'))

function ProtectedRoute({ children, adminOnly = false }) {
  const { user, token } = useAuthStore()
  const location = window.location;
  
  if (!token || !user) {
    const roleParam = adminOnly ? '?role=admin' : '?role=patient';
    return <Navigate to={`/login${roleParam}`} state={{ from: location.pathname }} replace />
  }
  if (adminOnly && user.role !== 'admin') {
    return <Navigate to="/login?role=admin" state={{ from: location.pathname }} replace />
  }
  return children
}

function App() {
  const { hydrate, user, token } = useAuthStore()
  const { currentTheme } = useThemeStore()
  
  React.useEffect(() => { hydrate() }, [])

  // Apply theme class to body and html for global style inheritance
  React.useEffect(() => {
    const themeClasses = ['theme-black-pink', 'theme-titanium-gold', 'theme-neural-glass'];
    document.documentElement.classList.remove(...themeClasses);
    document.body.classList.remove(...themeClasses);
    document.documentElement.classList.add(`theme-${currentTheme}`);
    document.body.classList.add(`theme-${currentTheme}`);
  }, [currentTheme]);

  const isAdminMode = import.meta.env.MODE === 'admin'

  return (
    <div className="min-h-screen bg-[var(--bg-main)] text-[var(--text-main)] transition-colors duration-500">
      <BrowserRouter>
      <PortalLayout>
        <React.Suspense fallback={<div className="min-h-screen bg-[var(--bg-main)] flex items-center justify-center"><div className="text-[var(--accent)] font-bold text-xl animate-pulse">PRISM Loading…</div></div>}>
          <Routes>
            <Route path="/"        element={<Home />} />
            <Route path="/login"   element={<Login />} />
            
            {/* Patient Flow */}
            <Route path="/patient" element={<PatientLanding />} />
            <Route path="/dashboard" element={<ProtectedRoute><PatientDashboard /></ProtectedRoute>} />
            <Route path="/app/*"   element={<ProtectedRoute><PatientApp /></ProtectedRoute>} />
            
            {/* Admin Flow */}
            <Route path="/admin-intro" element={<ProtectedRoute adminOnly><AdminIntro /></ProtectedRoute>} />
            <Route path="/admin/*" element={<ProtectedRoute adminOnly><AdminPortal /></ProtectedRoute>} />
            
            <Route path="*"        element={<Navigate to="/" replace />} />
          </Routes>
        </React.Suspense>
      </PortalLayout>
      <Toaster position="top-right" toastOptions={{ style: { background: 'var(--bg-card)', color: 'var(--text-main)', border: '1px solid var(--border)' } }} />
      </BrowserRouter>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <LanguageProvider>
    <App />
  </LanguageProvider>
)
