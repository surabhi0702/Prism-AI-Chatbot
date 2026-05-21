import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, Brain, Heart, Zap, Shield, Plus, MessageCircle, ChevronRight, TrendingUp } from 'lucide-react';
import { useAuthStore } from '../store/auth';

export default function PatientDashboard() {
  const { user } = useAuthStore();
  const navigate = useNavigate();

  const stats = [
    { label: 'Active Care Plans', value: '2', detail: '↑ Diabetes + Cardiovascular', color: 'text-[var(--accent)]' },
    { label: 'Specialist Agents', value: '10', detail: 'DM1–DM5 · CV1–CV5', color: 'text-[var(--accent)]' },
    { label: 'Conversations', value: '47', detail: 'This month', color: 'text-[var(--success)]' },
    { label: 'Days until billing', value: '5', detail: 'Trial ends May 1, 2026', color: 'text-[var(--error)]' },
  ];

  const subs = user?.subscribed_diseases || [];

  const DISEASE_METADATA = {
    'CA': { name: 'Cancer Care', icon: '🎗️', agents: ['CA1','CA2','CA3','CA4','CA5'], meta: ['Screening','Treatment','Support','Survivorship','Genetics'], price: 39 },
    'DM': { name: 'Diabetes Care', icon: '💧', agents: ['DM1','DM2','DM3','DM4','DM5'], meta: ['Monitoring','Medication','Nutrition','Complications','Lifestyle'], price: 29 },
    'CV': { name: 'Cardiovascular', icon: '❤️', agents: ['CV1','CV2','CV3','CV4','CV5'], meta: ['Clinical','Emergency','Medication','Rehab','Nutrition'], price: 29 },
    'MH': { name: 'Mental Health', icon: '🧠', agents: ['MH1','MH2','MH3','MH4','MH5'], meta: ['Depression','Anxiety','Sleep','Trauma','Crisis'], price: 24 },
    'RS': { name: 'Respiratory', icon: '🫁', agents: ['RS1','RS2','RS3','RS4','RS5'], meta: ['Asthma','COPD','Rehab','Medication','OSA'], price: 24 },
  };

  const activePlans = subs.map(code => {
    const meta = DISEASE_METADATA[code.toUpperCase()];
    if (!meta) return null;
    return {
      id: code.toLowerCase(),
      name: meta.name,
      icon: meta.icon,
      agents: meta.agents,
      agentsMeta: meta.meta,
      status: 'Active',
      renewDate: 'Next billing: Jun 21',
      price: meta.price
    };
  }).filter(Boolean);

  // If no subs, show Cancer Care as a lead-in for demo
  const displayPlans = activePlans.length > 0 ? activePlans : [
    { 
      id: 'ca', 
      name: 'Cancer Care (Demo)', 
      icon: '🎗️',
      agents: ['CA1','CA2','CA3','CA4','CA5'],
      agentsMeta: ['Screening','Treatment','Support','Survivorship','Genetics'],
      status: 'Trial — 7 days left',
      renewDate: 'Renewed May 21',
      price: 39
    }
  ];

  const healthSnapshot = [
    { label: 'Fasting glucose', value: '187', unit: 'mg/dL', status: 'high' },
    { label: 'HbA1c', value: '8.2', unit: '%', status: 'high' },
    { label: 'Blood pressure', value: '142/91', unit: '', status: 'warning' },
    { label: 'BMI', value: '28.4', unit: '', status: 'warning' },
    { label: 'Steps today', value: '4,820', unit: '', status: 'good' },
  ];

  return (
    <div className="min-h-screen bg-[var(--bg-main)] text-[var(--text-main)] p-8 font-sans">
      <div className="max-w-7xl mx-auto space-y-10">
        
        {/* Top Bar */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-black text-[var(--text-main)] mb-1 tracking-tight">Good morning, <span className="text-[var(--accent)]">{user?.name || 'María'}</span> 👋</h1>
            <p className="text-sm font-medium text-[var(--text-dim)]">Wednesday, May 6, 2026 · Your agents are active</p>
          </div>
          <button 
            onClick={() => navigate('/plans')}
            className="px-6 py-2.5 rounded-xl bg-[var(--accent)] text-white text-xs font-black uppercase tracking-widest hover:-translate-y-0.5 transition-all shadow-lg shadow-[var(--accent)]/20"
          >
            Manage subscriptions
          </button>
        </div>

        {/* Stats Strip */}
        <div className="grid md:grid-cols-4 gap-6">
          {stats.map((s, i) => (
            <div key={i} className="card-patient p-6 space-y-2 bg-[var(--bg-card)] border border-white/5 rounded-3xl">
              <div className="text-[10px] font-black text-gray-500 uppercase tracking-widest">{s.label}</div>
              <div className="text-4xl font-black text-white">{s.value}</div>
              <div className={`text-[10px] font-bold ${s.color} flex items-center gap-1`}>
                {s.detail}
              </div>
            </div>
          ))}
        </div>

        <div className="grid lg:grid-cols-[1fr,320px] gap-8">
          
          {/* Main Content: Active Plans */}
          <div className="space-y-6">
            <div className="flex items-center justify-between px-2">
            </div>

            {displayPlans.map((plan, idx) => (
              <div key={idx} className="card-patient p-8 space-y-8 bg-[var(--bg-card)] border border-white/5 rounded-[2rem]">
                <div className="flex justify-between items-start">
                  <div className="flex gap-6">
                    <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center text-3xl border border-white/10">
                      {plan.icon}
                    </div>
                    <div>
                      <h3 className="text-xl font-black text-white mb-1">{plan.name}</h3>
                      <div className="text-xs text-gray-500 font-medium">{plan.agents.length} agents · {plan.agents[0]} + {plan.agents[1]} · {plan.renewDate}</div>
                      <div className="mt-2 inline-flex px-2 py-0.5 rounded bg-[var(--accent)]/10 text-[var(--accent)] text-[10px] font-black uppercase tracking-widest">
                        {plan.status}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-black text-white">${plan.price}</div>
                    <div className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">/month</div>
                  </div>
                </div>

                <div className="grid grid-cols-5 gap-3">
                  {plan.agents.map((agent, i) => (
                    <div key={i} className="p-4 rounded-xl bg-white/5 border border-white/5 text-center space-y-1 hover:border-orange-500/30 hover:bg-white/10 transition-all cursor-pointer group">
                      <div className="w-8 h-8 rounded-lg bg-[#06080F] shadow-sm flex items-center justify-center text-gray-500 group-hover:text-[var(--accent)] transition-colors mx-auto">
                        {i === 0 ? <Activity size={16} /> : i === 1 ? <Zap size={16} /> : i === 2 ? <Plus size={16} /> : i === 3 ? <Activity size={16} /> : <TrendingUp size={16} />}
                      </div>
                      <div className="text-[9px] font-black text-gray-500 uppercase tracking-tighter">{agent}</div>
                      <div className="text-[10px] font-bold text-gray-300 truncate">{plan.agentsMeta[i]}</div>
                    </div>
                  ))}
                </div>

                <button 
                  onClick={() => navigate('/app')}
                  className="w-full py-4 rounded-2xl bg-[var(--accent)] text-white font-black text-sm flex items-center justify-center gap-3 hover:bg-orange-600 transition-all shadow-xl shadow-orange-500/10"
                >
                  <MessageCircle size={18} /> Open {plan.name} Chat
                </button>
              </div>
            ))}
          </div>

          {/* Right Content: Snapshot & Feed */}
          <div className="space-y-8">
            <div className="space-y-4">
              <div className="p-6 rounded-3xl bg-[var(--bg-card)] text-white space-y-6 border border-white/5 shadow-2xl shadow-black/20">
                <div className="text-[10px] font-black text-gray-500 uppercase tracking-widest border-b border-white/10 pb-4">Tracked Metrics</div>
                {healthSnapshot.map((item, i) => (
                  <div key={i} className="flex justify-between items-end">
                    <span className="text-xs font-medium text-gray-400">{item.label}</span>
                    <div className="text-right">
                      <span className={`text-lg font-black ${item.status === 'high' ? 'text-red-400' : item.status === 'warning' ? 'text-orange-400' : 'text-green-400'}`}>
                        {item.value}
                      </span>
                      {item.unit && <span className="text-[10px] font-bold text-gray-600 ml-1 uppercase">{item.unit}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <h2 className="text-lg font-black text-white uppercase tracking-widest px-2">Recent activity</h2>
              <div className="space-y-3">
                {[
                  { type: 'AI Insight', msg: 'New research on Metformin usage...', time: '2h ago' },
                  { type: 'Medication', msg: 'Dosage updated for CA-2 agent', time: '1d ago' },
                  { type: 'Report', msg: 'Lab results from Apr 24 processed', time: '3d ago' },
                ].map((act, i) => (
                  <div key={i} className="p-4 rounded-2xl bg-white/5 border border-white/5 flex items-center justify-between group cursor-pointer hover:border-orange-500/50 transition-all">
                    <div className="space-y-0.5">
                      <div className="text-[9px] font-black text-[var(--accent)] uppercase tracking-widest">{act.type}</div>
                      <div className="text-[11px] font-bold text-gray-300">{act.msg}</div>
                    </div>
                    <div className="text-[9px] font-bold text-gray-500">{act.time}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
