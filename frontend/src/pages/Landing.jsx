import React from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Shield, Brain, Zap, Globe, Star, CheckCircle } from 'lucide-react'

const DISEASES = [
  { code: 'CA', icon: '🎗', name: 'Cancer Care',    color: '#A78BFA', agents: ['Screening','Treatment','Supportive','Survivorship','Genetics'] },
  { code: 'DM', icon: '🩺', name: 'Diabetes',       color: '#60A5FA', agents: ['Monitoring','Medication','Nutrition','Complications','Gestational'] },
  { code: 'CV', icon: '❤️', name: 'Cardiovascular', color: '#F472B6', agents: ['Clinical','Emergency','Medications','Rehab','Nutrition'] },
  { code: 'MH', icon: '🧠', name: 'Mental Health',  color: '#34D399', agents: ['Depression','Anxiety','Sleep','Trauma','Crisis'] },
  { code: 'RS', icon: '🫁', name: 'Respiratory',    color: '#F5C842', agents: ['Asthma','COPD','Therapy','Medications','Sleep Apnea'] },
]

const FEATURES = [
  { icon: <Brain size={20} />, title: '25 Specialised AI Agents', desc: '5 agents per disease — Primary, Specialist & Human Escalation' },
  { icon: <Shield size={20} />, title: 'Evidence-Based Answers', desc: 'Grade A/B/C citations from WHO, ADA, ASCO, ACC/AHA, PAHO' },
  { icon: <Globe size={20} />, title: '5-Language Support', desc: 'English, हिंदी, తెలుగు, Español, ਪੰਜਾਬੀ' },
  { icon: <Zap size={20} />, title: 'Multimodal AI', desc: 'Upload prescriptions, lab reports, or talk via audio' },
]

export default function Landing() {
  return (
    <div className="min-h-screen bg-void text-ink">
      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-void/90 backdrop-blur border-b border-line px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-gold to-ora flex items-center justify-center font-disp font-bold text-void text-sm shadow-lg shadow-gold/30">P</div>
          <span className="font-disp font-bold text-lg">PRISM</span>
          <span className="text-xs text-ink3 font-mono bg-bg3 px-2 py-0.5 rounded border border-line">v2.0</span>
        </div>
        <div className="flex gap-3">
          <Link to="/login" className="btn-ghost text-sm">Sign In</Link>
          <Link to="/login?register=1" className="btn-primary text-sm">Get Started</Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative px-6 py-24 max-w-6xl mx-auto text-center overflow-hidden">
        <div className="absolute inset-0 bg-gradient-radial from-gold/5 via-transparent to-transparent pointer-events-none" />
        <div className="inline-flex items-center gap-2 bg-goldL border border-gold/20 px-4 py-1.5 rounded-full text-gold text-xs font-mono font-semibold mb-6">
          <div className="w-1.5 h-1.5 rounded-full bg-gold animate-pulse" />
          AI-Powered Tele Medicine Platform
        </div>
        <h1 className="font-disp font-bold text-5xl md:text-7xl mb-6 leading-tight">
          Your AI Health <br />
          <span className="bg-gradient-to-r from-gold via-ora to-pink bg-clip-text text-transparent">Intelligence System</span>
        </h1>
        <p className="text-ink2 text-lg md:text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
          Evidence-based AI health guidance for Cancer, Diabetes, Cardiovascular, Mental Health & Respiratory diseases. 25 specialised agents. Multilingual. Multimodal.
        </p>
        <div className="flex gap-4 justify-center flex-wrap">
          <Link to="/login?register=1" className="btn-primary flex items-center gap-2 text-base px-6 py-3">
            Start Free <ArrowRight size={18} />
          </Link>
          <Link to="/login" className="btn-ghost flex items-center gap-2 text-base px-6 py-3">
            Sign In
          </Link>
        </div>
        {/* Stats bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-16">
          {[['5', 'Disease Domains'],['25', 'AI Agents'],['5', 'Languages'],['19-Dim', 'Quality Gate']].map(([v,l]) => (
            <div key={l} className="card p-4 text-center">
              <div className="font-disp font-bold text-2xl text-gold">{v}</div>
              <div className="text-ink3 text-xs mt-1">{l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Disease Cards */}
      <section className="px-6 py-16 max-w-6xl mx-auto">
        <h2 className="font-disp font-bold text-3xl mb-2">5 Disease Domains</h2>
        <p className="text-ink3 mb-8">Each with 5 specialised agents + expert escalation + human coordinator</p>
        <div className="grid md:grid-cols-3 lg:grid-cols-5 gap-4">
          {DISEASES.map((d) => (
            <div key={d.code} className="card p-5 hover:border-line2 transition-all cursor-pointer group"
              style={{ borderLeftColor: d.color, borderLeftWidth: 3 }}>
              <div className="text-3xl mb-3">{d.icon}</div>
              <div className="font-disp font-bold text-sm mb-2" style={{ color: d.color }}>{d.name}</div>
              <div className="space-y-1">
                {d.agents.map(a => (
                  <div key={a} className="flex items-center gap-1.5 text-xs text-ink3">
                    <CheckCircle size={10} style={{ color: d.color }} />{a}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="px-6 py-16 max-w-6xl mx-auto">
        <h2 className="font-disp font-bold text-3xl mb-8">Platform Features</h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {FEATURES.map((f) => (
            <div key={f.title} className="card p-5">
              <div className="w-9 h-9 rounded-lg bg-goldL flex items-center justify-center text-gold mb-3">{f.icon}</div>
              <div className="font-semibold text-sm mb-1">{f.title}</div>
              <div className="text-xs text-ink3 leading-relaxed">{f.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-line px-6 py-8 text-center text-ink3 text-xs">
        <p>© 2025 PRISM — Feuji AI/ML Data Science Team. Not a substitute for professional medical advice.</p>
      </footer>
    </div>
  )
}
