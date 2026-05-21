import React from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  TrendingUp, ShieldCheck, Layers, MessageSquare, 
  UploadCloud, Brain, Users, Zap, Bell, 
  Activity, LifeBuoy, CheckCircle, ArrowRight 
} from 'lucide-react';

const metrics = [
  {
    title: "RAGAS Metrics",
    description: "Retrieval-Augmented Generation Assessment Scoring to evaluate faithfulness, answer relevance, and context recall.",
    icon: <TrendingUp className="text-pink-500" size={24} />,
    color: "from-pink-500/20 to-transparent"
  },
  {
    title: "Governance & Security",
    description: "RBAC protocols and clinical disclaimer compliance monitoring",
    icon: <ShieldCheck className="text-[var(--accent)]" size={24} />,
    color: "from-[var(--accent)]/20 to-transparent"
  },
  {
    title: "Pre-RAG Readiness",
    description: "A 19-dimension document quality scoring system ensuring data integrity before indexing.",
    icon: <Layers className="text-orange-500" size={24} />,
    color: "from-orange-500/20 to-transparent"
  },
  {
    title: "Patient Feedback",
    description: "Aggregated patient sentiment, ratings, and qualitative feedback for continuous improvement.",
    icon: <MessageSquare className="text-green-500" size={24} />,
    color: "from-green-500/20 to-transparent"
  },
  {
    title: "Upload & Crawl",
    description: "Dynamic ingestion pipeline for medical documents and automated web crawling from PubMed and CDC.",
    icon: <UploadCloud className="text-purple-500" size={24} />,
    color: "from-purple-500/20 to-transparent"
  },
  {
    title: "Agent Performance",
    description: "Comparative analysis of performance metrics across all 25 disease-specific primary agents.",
    icon: <Brain className="text-pink-400" size={24} />,
    color: "from-pink-400/20 to-transparent"
  },
  {
    title: "Agent Registry",
    description: "Detailed hierarchy and management of primary agents, specialists, and human escalation paths.",
    icon: <Users className="text-indigo-500" size={24} />,
    color: "from-indigo-500/20 to-transparent"
  },
  {
    title: "LLM Calls",
    description: "Real-time telemetry and logging for every large language model interaction and token usage.",
    icon: <Zap className="text-yellow-500" size={24} />,
    color: "from-yellow-500/20 to-transparent"
  },
  {
    title: "Alerts",
    description: "Proactive system monitoring and critical alerts for immediate operational response.",
    icon: <Bell className="text-red-500" size={24} />,
    color: "from-red-500/20 to-transparent"
  },
  {
    title: "PRISM Health",
    description: "Real-time infrastructure health monitoring for APIs, databases, and model providers.",
    icon: <Activity className="text-teal-500" size={24} />,
    color: "from-teal-500/20 to-transparent"
  },
  {
    title: "Escalation Summary",
    description: "Tracking and analysis of patient escalations to human specialists and medical teams.",
    icon: <LifeBuoy className="text-orange-400" size={24} />,
    color: "from-orange-400/20 to-transparent"
  },
  {
    title: "Quality Score",
    description: "Advanced metrics evaluating the clinical accuracy and empathy of patient interactions.",
    icon: <CheckCircle className="text-emerald-500" size={24} />,
    color: "from-emerald-500/20 to-transparent"
  }
];

export default function AdminIntro() {
  const navigate = useNavigate();

  return (
    <div className="h-screen overflow-hidden bg-[var(--bg-main)] text-[var(--text-main)] flex flex-col font-sans selection:bg-[var(--accent)]/30 relative transition-colors duration-500">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] right-[-10%] w-[40%] h-[40%] bg-[var(--accent)]/10 blur-[150px] rounded-full" />
        <div className="absolute bottom-[-10%] left-[-10%] w-[40%] h-[40%] bg-[var(--accent)]/5 blur-[150px] rounded-full" />
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay" />
      </div>

      {/* Header - Ultralight */}
      <header className="relative z-20 px-6 py-2 flex justify-between items-center w-full border-b border-white/5 bg-[var(--bg-main)]/80 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center font-bold text-lg text-[var(--text-main)]">P</div>
          <div>
            <h1 className="text-lg font-black tracking-tight text-[var(--text-main)] uppercase">PRISM Intelligence</h1>
            <p className="text-[7px] text-[var(--text-dim)] uppercase tracking-[0.2em] font-bold">Executive Suite</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[var(--accent)]/10 border border-[var(--accent)]/20 text-[8px] text-[var(--accent)] font-black uppercase">
            <div className="w-1 h-1 rounded-full bg-[var(--accent)] animate-pulse" />
            Active
          </div>
          <button 
            onClick={() => navigate('/admin')}
            className="px-4 py-1.5 rounded-full bg-[var(--text-main)] text-[var(--bg-main)] text-[10px] font-black hover:bg-[var(--accent)] hover:text-white transition-all shadow-md"
          >
            Enter Dashboard
          </button>
        </div>
      </header>

      {/* Main Content - Tightened for zero-scroll */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 w-full scale-[0.92] md:scale-100">
        <div className="max-w-6xl w-full flex flex-col items-center">
          <div className="text-center mb-4">
            <h2 className="text-4xl md:text-5xl lg:text-6xl font-black mb-1 tracking-tighter uppercase flex flex-wrap justify-center gap-x-4 text-[var(--text-main)]">
              <span>PRISM</span> 
              <span className="text-[var(--accent)]">Intelligence</span>
            </h2>
            <p className="text-[var(--text-dim)] text-sm md:text-base max-w-2xl mx-auto leading-tight font-medium">
              Real-time governance oversight for the PRISM clinical platform. 
              Access dimension-level metrics and system control via the Command Centre.
            </p>
          </div>

          {/* Metrics Grid - Minimalist cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 w-full">
            {metrics.map((metric, index) => (
              <div 
                key={index}
                className="group relative p-3.5 rounded-xl bg-white/[0.02] border border-white/5 hover:border-[var(--accent)]/50 transition-all duration-300 backdrop-blur-md overflow-hidden"
              >
                <div className={`absolute inset-0 bg-gradient-to-br ${metric.color} opacity-0 group-hover:opacity-100 transition-opacity duration-300`} />
                
                <div className="relative z-10">
                  <div className="w-9 h-9 rounded-lg bg-white/5 flex items-center justify-center mb-2 group-hover:scale-105 transition-transform duration-300 border border-white/5 shadow-inner">
                    {React.cloneElement(metric.icon, { size: 20, className: 'text-[var(--accent)]' })}
                  </div>
                  <h3 className="text-[13px] font-black uppercase tracking-wider mb-1 group-hover:text-[var(--accent)] transition-colors text-[var(--text-main)]">{metric.title}</h3>
                  <p className="text-[var(--text-dim)] text-[11px] leading-snug line-clamp-2 font-medium">
                    {metric.description}
                  </p>
                </div>
                <div className="absolute bottom-0 left-0 h-0.5 w-0 bg-[var(--grad-primary)] group-hover:w-full transition-all duration-500" />
              </div>
            ))}
          </div>

          {/* CTA - Compact */}
          <div className="mt-5">
            <button 
              onClick={() => navigate('/admin')}
              className="group relative px-10 py-3 rounded-full bg-[var(--grad-primary)] text-white font-black text-xs hover:scale-105 transition-all shadow-xl shadow-[var(--accent)]/30 overflow-hidden uppercase tracking-widest"
            >
              <span className="relative z-10 flex items-center gap-2">
                Launch Command Centre <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
              </span>
              <div className="absolute inset-0 bg-white/10 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-500" />
            </button>
          </div>
        </div>
      </main>

      {/* Footer - Minimal */}
      <footer className="relative z-10 px-8 py-2 border-t border-white/5 text-center text-[var(--text-dim)] text-[8px] uppercase tracking-[0.3em] font-black bg-[var(--bg-main)]/80">
        Authorized Access Only • Live Data Pipeline
      </footer>
    </div>
  );
}
