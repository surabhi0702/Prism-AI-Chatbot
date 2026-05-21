import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Activity, Brain, Globe, Zap, ArrowRight, Settings, Layers, FileDown, History, HeartPulse, Video, MessageSquare, Download, ThumbsUp, FileText } from 'lucide-react';

export default function PatientLanding() {
  const navigate = useNavigate();

  const features = [
    { icon: <Activity />, title: '5 Disease Domains', desc: 'Specialized care for chronic conditions.' },
    { icon: <Brain />, title: '30 Specialist AI Agents', desc: 'Expert companions for every health journey.' },
    { icon: <Shield />, title: 'Evidence-Based Care', desc: 'Answers backed by PubMed, CDC, and WHO.' },
    { icon: <Globe />, title: 'Multilingual Support', desc: 'English, Spanish, Hindi, Telugu, and more.' },
    { icon: <Layers />, title: 'Multimodal Support', desc: 'Interact via text, images, and voice.' },
    { icon: <FileDown />, title: 'Prescription Download', desc: 'Securely download AI medical prescriptions.' },
    { icon: <History />, title: 'Long Term Memory', desc: 'Personalized longitudinal care history.' },
    { icon: <MessageSquare />, title: 'Patient Engagement by more conversation', desc: 'Interactive tools to keep you active.' },
    { icon: <Video />, title: 'Tele Medicine', desc: 'Seamlessly connect with human specialists.' },
    { icon: <Download />, title: 'Chat Message Download option', desc: 'Securely download your chat history.' },
    { icon: <ThumbsUp />, title: 'Patient Feedback Mechanism', desc: 'Rate and review your AI care experience.' },
    { icon: <FileText />, title: 'Upload Medical Documents & Subsequent Analysis', desc: 'AI-driven analysis of your medical records.' },
  ];

  return (
    <div className="h-full min-h-screen bg-[var(--bg-main)] text-[var(--text-main)] transition-colors selection:bg-[var(--accent)]/30 flex flex-col overflow-hidden relative">
      
      {/* Subtle background glow */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] right-[-10%] w-[50%] h-[50%] bg-[var(--accent)]/10 blur-[120px] rounded-full" />
      </div>

      <nav className="relative z-10 px-8 py-1 flex justify-between items-center max-w-7xl mx-auto w-full">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)] flex items-center justify-center font-bold shadow-lg shadow-[var(--accent)]/20 text-white">P</div>
          <span className="text-xl font-bold tracking-tight">PRISM Patient</span>
        </div>
        <button 
          onClick={() => navigate('/login?role=admin')}
          className="flex items-center gap-2 text-gray-400 hover:text-white text-xs font-bold border border-white/10 px-4 py-2 rounded-full hover:bg-white/5 transition-all"
        >
          <Settings size={14} /> Admin Console
        </button>
      </nav>

      {/* Hero */}
      <section className="relative z-10 px-6 py-1 max-w-7xl mx-auto flex flex-col items-center text-center">
        <div className="inline-flex items-center gap-2 px-4 py-1 rounded-full bg-[var(--accent)]/10 text-[var(--accent)] text-[9px] font-black uppercase tracking-widest mb-1 border border-[var(--accent)]/20">
          <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
          Trusted by 10k+ Patients Across LATAM
        </div>
        <h1 className="text-2xl md:text-4xl font-black mb-0.5 tracking-tight leading-[0.95] text-[var(--text-main)]">
          Personalised AI care <br />
          <span className="bg-[var(--grad-primary)] bg-clip-text text-transparent">
            at your fingertips.
          </span>
        </h1>
        <p className="text-xs md:text-sm max-w-lg mb-1 leading-relaxed font-medium text-gray-400">
          Evidence-based guidance for Cancer, Diabetes, Cardiovascular, Mental Health & Respiratory care. 
          Your health companion, available 24/7.
        </p>
        <div className="flex gap-4 items-center">
          <button 
            onClick={() => navigate('/login?role=patient')}
            className="px-8 py-3.5 rounded-xl bg-[var(--accent)] text-white font-black text-xs uppercase tracking-widest shadow-2xl shadow-[var(--accent)]/20 hover:-translate-y-1 transition-all flex items-center gap-3"
          >
            Get Started <ArrowRight size={18} />
          </button>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="relative z-10 px-6 py-1 bg-white/5 border-y border-white/5 flex-1 flex items-center overflow-hidden">
        <div className="max-w-7xl mx-auto grid grid-cols-2 lg:grid-cols-3 gap-2 w-full">
          {features.map((f, i) => (
            <div key={i} className="p-2.5 rounded-xl border border-white/5 bg-[var(--bg-card)] hover:border-[var(--accent)]/30 transition-all group flex items-center gap-3">
              <div className="w-9 h-9 shrink-0 rounded-lg bg-[var(--accent)]/10 text-[var(--accent)] flex items-center justify-center group-hover:scale-110 transition-transform">
                {React.cloneElement(f.icon, { size: 18 })}
              </div>
              <div className="text-left">
                <h3 className="text-[13px] font-bold text-white leading-tight">{f.title}</h3>
                <p className="text-[10px] text-gray-400 leading-tight mt-0.5">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Trust Strip */}
      <section className="relative z-10 px-6 py-1 max-w-7xl mx-auto text-center">
        <h2 className="text-[8px] font-black text-gray-600 uppercase tracking-[0.4em] mb-1">Built with Medical Evidence from</h2>
        <div className="flex flex-wrap justify-center items-center gap-6 md:gap-12 opacity-30 grayscale invert">
          <span className="text-xs font-black">PubMed</span>
          <span className="text-xs font-black">CDC</span>
          <span className="text-xs font-black">WHO</span>
          <span className="text-xs font-black">PAHO</span>
          <span className="text-xs font-black">ASCO</span>
        </div>
      </section>
    </div>
  );
}
