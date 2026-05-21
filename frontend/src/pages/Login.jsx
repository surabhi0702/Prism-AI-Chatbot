import React, { useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { Eye, EyeOff, ArrowLeft } from 'lucide-react'
import toast from 'react-hot-toast'

const COUNTRIES = [
  { code: 'MX', label: 'Mexico 🇲🇽' },
  { code: 'BR', label: 'Brazil 🇧🇷' },
  { code: 'AR', label: 'Argentina 🇦🇷' },
  { code: 'CO', label: 'Colombia 🇨🇴' },
  { code: 'CL', label: 'Chile 🇨🇱' },
  { code: 'PE', label: 'Peru 🇵🇪' },
  { code: 'UY', label: 'Uruguay 🇺🇾' },
  { code: 'VE', label: 'Venezuela 🇻🇪' },
  { code: 'EC', label: 'Ecuador 🇪🇨' },
  { code: 'CR', label: 'Costa Rica 🇨🇷' },
  { code: 'GT', label: 'Guatemala 🇬🇹' },
  { code: 'PA', label: 'Panama 🇵🇦' },
  { code: 'DO', label: 'Dominican Republic 🇩🇴' },
  { code: 'US', label: 'USA 🇺🇸' },
]

export default function Login() {
  const [params]  = useSearchParams()
  const navigate   = useNavigate()
  const location   = window.location
  const { login, register, logout } = useAuthStore()
  const role = params.get('role') || 'patient'
  const from = window.history.state?.usr?.from || (useAuthStore.getState().user?.role === 'admin' ? '/admin-intro' : '/app')
  const [mode, setMode]     = useState(params.get('register') ? 'register' : 'login')
  const [show, setShow]     = useState(false)
  const [loading, setLoading] = useState(false)
  const [form, setForm]     = useState({ email: '', password: '', name: '', country: 'Mexico' })

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      if (mode === 'login') {
        const { user, warning } = await login(form.email, form.password)

        if (warning) {
          toast(warning, { icon: '⚠️', duration: 6000 })
        }
        
        // Role enforcement
        if (role && user.role !== role) {
          logout()
          toast.error(`Authorized ${role} access only.`)
          setLoading(false)
          return
        }

        toast.success(`Welcome back, ${user.name}!`)
        const target = user.role === 'admin' ? (window.history.state?.usr?.from || '/admin-intro') : '/app'
        navigate(target)
      } else {
        const user = await register(form.email, form.name, form.password, form.country)
        toast.success(`Welcome to PRISM, ${user.name}!`)
        navigate('/app')
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-void flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className={`w-14 h-14 rounded-2xl mx-auto flex items-center justify-center font-disp font-bold text-2xl text-white shadow-lg mb-4 transition-all duration-500 bg-[var(--grad-primary)] shadow-[var(--accent)]/30`}>
            {role === 'admin' ? 'A' : 'P'}
          </div>
          <h1 className="font-disp font-bold text-2xl uppercase tracking-tight">
            {role === 'admin' ? 'Admin Console' : 'PRISM Health'}
          </h1>
          <p className="text-ink3 text-sm mt-1">
            {role === 'admin' ? 'Executive Operational Oversight' : 'Patient-centric Health Intelligence'}
          </p>
        </div>

        <div className="card p-8">
          {/* Mode tabs */}
          <div className="flex gap-1 bg-bg3 rounded-xl p-1 mb-6">
            {['login', ...(role === 'admin' ? [] : ['register'])].map(m => (
              <button key={m} onClick={() => setMode(m)}
                className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all capitalize ${mode === m ? 'bg-[var(--accent)] text-white shadow' : 'text-[var(--text-dim)] hover:text-[var(--text-main)]'}`}>
                {m === 'login' ? 'Sign In' : 'Create Account'}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="text-xs text-ink3 font-mono font-semibold uppercase tracking-wider mb-1 block">Full Name</label>
                <input className="input w-full" placeholder="Dr. Maria González" value={form.name}
                  onChange={e => set('name', e.target.value)} required />
              </div>
            )}
            <div>
              <label className="text-xs text-ink3 font-mono font-semibold uppercase tracking-wider mb-1 block">Email</label>
              <input className="input w-full" type="email" placeholder="you@example.com"
                value={form.email} onChange={e => set('email', e.target.value)} required />
            </div>
            <div>
              <label className="text-xs text-ink3 font-mono font-semibold uppercase tracking-wider mb-1 block">Password</label>
              <div className="relative">
                <input className="input w-full pr-10" type={show ? 'text' : 'password'}
                  placeholder="••••••••" value={form.password}
                  onChange={e => set('password', e.target.value)} required minLength={6} />
                <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2 text-ink3 hover:text-ink"
                  onClick={() => setShow(!show)}>
                  {show ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>
            {mode === 'register' && (
              <div>
                <label className="text-xs text-ink3 font-mono font-semibold uppercase tracking-wider mb-1 block">Country (LATAM)</label>
                <select className="input w-full" value={form.country} onChange={e => set('country', e.target.value)}>
                  {COUNTRIES.map(c => <option key={c.code} value={c.label}>{c.label}</option>)}
                </select>
              </div>
            )}

            {/* Demo accounts */}
            <div className="text-xs text-ink3 bg-bg3 rounded-lg p-3 border border-line">
              <div className="font-mono font-semibold mb-1 text-ink2">Demo accounts:</div>
              <div><b className="text-ink">Patient:</b> <span className="text-ink2">patient@prism.ai / demo123</span></div>
              <div><b className="text-ink">Admin:</b> <span className="text-ink2">admin@prism.ai / admin123</span></div>
            </div>

            <button type="submit" disabled={loading} className="bg-[var(--accent)] hover:opacity-90 w-full py-3 text-sm rounded-xl font-bold transition-all text-white shadow-lg shadow-[var(--accent)]/20">
              {loading ? 'Authenticating…' : mode === 'login' ? (role === 'admin' ? 'Secure Admin Login' : 'Sign In to PRISM') : 'Create Account'}
            </button>
          </form>
        </div>

        <Link to="/" className="flex items-center gap-1.5 justify-center mt-4 text-ink3 text-xs hover:text-ink transition-colors">
          <ArrowLeft size={13} /> Back to home
        </Link>
      </div>
    </div>
  )
}
