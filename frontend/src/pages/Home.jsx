import React from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Shield, Activity, Users, Globe, ArrowRight, Lock, Settings, Palette, Smartphone } from 'lucide-react';
import { useAuthStore } from '../store/auth';
import { useThemeStore } from '../store/theme';
import DeviceSwitcher from '../Components/DeviceSwitcher';

export default function Home() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { currentTheme, setTheme } = useThemeStore();

  const themes = [
    { id: 'black-pink', name: 'WOW Factor', color: 'bg-pink-500' },
    { id: 'titanium-gold', name: 'Titanium & Gold', color: 'bg-[#D4AF37]' },
    { id: 'neural-glass', name: 'Natural Glass', color: 'bg-cyan-400' }
  ];

  const stats = [
    { value: '5', label: 'Disease Domains' },
    { value: '30', label: 'Active Agents' },
    { value: '5', label: 'Global Languages' },
    { value: '19-Dim', label: 'Quality Gates' },
  ];

  return (
    <div className="min-h-screen h-full bg-[var(--bg-main)] text-[var(--text-main)] flex flex-col font-sans selection:bg-[var(--accent)]/30 transition-colors duration-500 relative">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-[var(--accent)]/10 blur-[120px] rounded-full" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-[var(--accent)]/5 blur-[120px] rounded-full" />
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay" />
      </div>

      {/* Header */}
      <header className="relative z-20 px-8 py-3 flex justify-between items-center max-w-7xl mx-auto w-full">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-xl bg-[var(--grad-primary)] flex items-center justify-center font-bold shadow-lg shadow-[var(--accent)]/20 text-white">P</div>
          <span className="text-2xl font-bold tracking-tight">PRISM</span>
        </div>
        <div className="flex items-center gap-4">
          {!user ? (
            <Link to="/login" className="px-5 py-2 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 transition-all text-sm font-semibold">
              Sign In
            </Link>
          ) : (
            <div className="flex items-center gap-4">
              <span className="text-sm text-[var(--text-dim)]">Welcome, <b className="text-[var(--text-main)]">{user.name}</b></span>
              <button onClick={() => navigate(user.role === 'admin' ? '/admin-intro' : '/app')} className="px-5 py-2 rounded-full bg-[var(--accent)] hover:opacity-90 transition-all text-sm font-bold shadow-lg shadow-[var(--accent)]/20 text-white">
                Go to Dashboard
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Device & Theme Switcher Overlay */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-30 flex flex-col md:flex-row items-center gap-4">
        {/* Device Switcher */}
        <div className="flex items-center gap-3 px-6 py-2.5 rounded-full bg-white/5 border border-white/10 backdrop-blur-xl shadow-2xl">
          <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-dim)] mr-2 border-r border-white/10 pr-4">
            <Smartphone size={14} className="text-[var(--accent)]" />
            Device Mode
          </div>
          <DeviceSwitcher />
        </div>

        {/* Theme Switcher */}
        <div className="flex items-center gap-3 px-6 py-2.5 rounded-full bg-white/5 border border-white/10 backdrop-blur-xl shadow-2xl">
          <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-[var(--text-dim)] mr-2 border-r border-white/10 pr-4">
            <Palette size={14} className="text-[var(--accent)]" />
            Select Theme
          </div>
          <div className="flex gap-3">
            {themes.map((t) => (
              <button
                key={t.id}
                onClick={() => setTheme(t.id)}
                className={`group relative w-7 h-7 rounded-full border-2 transition-all hover:scale-110 flex items-center justify-center
                  ${currentTheme === t.id ? 'border-[var(--accent)] scale-110 shadow-lg shadow-[var(--accent)]/30' : 'border-transparent hover:border-white/20'}`}
                title={t.name}
              >
                <div className={`w-4 h-4 rounded-full ${t.color}`} />
                <div className="absolute -top-10 left-1/2 -translate-x-1/2 px-3 py-1 rounded-md bg-black text-white text-[9px] font-black opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none uppercase tracking-tighter">
                  {t.name}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Hero */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 py-2 text-center max-w-5xl mx-auto">
        <div className="inline-flex items-center gap-2 px-4 py-1 rounded-full bg-[var(--accent)]/10 border border-[var(--accent)]/20 text-[var(--accent)] text-[10px] font-bold uppercase tracking-[0.2em] mb-2">
          <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
          AI-Powered Healthcare Platform · Latin America
        </div>
        
        <h1 className="text-3xl md:text-5xl font-black mb-1 tracking-tight leading-[0.95] text-[var(--text-main)]">
          One platform.<br />
          <span className="bg-[var(--grad-primary)] bg-clip-text text-transparent">
            Two powerful portals.
          </span>
        </h1>
        
        <p className="text-gray-400 text-sm md:text-base max-w-xl mb-4 leading-relaxed">
          PRISM delivers 24/7 specialist AI health companions for patients and 
          a comprehensive operations console for administrators — all in one unified system.
        </p>

        {/* Portal Cards */}
        <div className="grid md:grid-cols-2 gap-4 w-full max-w-4xl">
          {/* Patient Card */}
          <button 
            onClick={() => navigate('/patient')}
            className="group relative text-left p-4 rounded-[20px] bg-[var(--bg-card)] border border-white/10 hover:border-[var(--accent)]/50 transition-all duration-500 overflow-hidden"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-[var(--accent)]/10 blur-3xl group-hover:bg-[var(--accent)]/20 transition-all" />
            <div className="w-9 h-9 rounded-xl bg-[var(--accent)]/20 flex items-center justify-center text-[var(--accent)] mb-2 group-hover:scale-110 transition-transform duration-500">
              <Activity size={20} />
            </div>
            <div className="uppercase text-[8px] font-black tracking-widest text-[var(--accent)]/60 mb-1">Patient Portal</div>
            <h3 className="text-lg font-bold mb-1 text-[var(--text-main)]">Your Health Companion</h3>
            <p className="text-[var(--text-dim)] text-[12px] leading-relaxed mb-2">
              Access specialist AI care companions for diabetes, cardiovascular, cancer and more. 
              Get evidence-based answers in your language, 24/7.
            </p>
            <div className="flex items-center gap-2 text-[var(--accent)] font-bold text-sm">
              Enter Patient Portal <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
            </div>
          </button>

          {/* Admin Card */}
          <button 
            onClick={() => navigate('/login?role=admin')}
            className="group relative text-left p-4 rounded-[20px] bg-[var(--bg-card)] border border-white/10 hover:border-[var(--accent)]/50 transition-all duration-500 overflow-hidden"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-[var(--accent)]/10 blur-3xl group-hover:bg-[var(--accent)]/20 transition-all" />
            <div className="w-9 h-9 rounded-xl bg-[var(--accent)]/20 flex items-center justify-center text-[var(--accent)] mb-2 group-hover:scale-110 transition-transform duration-500">
              <Shield size={20} />
            </div>
            <div className="uppercase text-[8px] font-black tracking-widest text-[var(--accent)]/60 mb-1">Admin Console</div>
            <h3 className="text-lg font-bold mb-1 text-[var(--text-main)]">Operational Health</h3>
            <p className="text-[var(--text-dim)] text-[12px] leading-relaxed mb-2">
              Command centre for RAG performance, clinical audit trails, 
              agent registry and smart routing thresholds.
            </p>
            <div className="flex items-center gap-2 text-[var(--accent)] font-bold text-sm">
              Enter Admin Portal <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
            </div>
          </button>
        </div>

        {/* Stats Strip */}
        <div className="mt-2 py-2 border-y border-white/5 w-full flex flex-wrap justify-center gap-10 md:gap-16">
          {stats.map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-lg font-black mb-0.5">{s.value}</div>
              <div className="text-[8px] font-bold text-gray-500 uppercase tracking-widest">{s.label}</div>
            </div>
          ))}
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 px-8 py-2 border-t border-white/5 text-center text-gray-500 text-[9px]">
        <div className="flex justify-center gap-4 mb-0.5">
          <span className="hover:text-white transition-colors cursor-pointer">Privacy Policy</span>
          <span className="hover:text-white transition-colors cursor-pointer">Terms of Service</span>
          <span className="hover:text-white transition-colors cursor-pointer">Security</span>
        </div>
        <p>© 2026 PRISM — Feuji AI/ML Data Science Team. Not a substitute for professional medical advice.</p>
      </footer>
    </div>
  );
}
