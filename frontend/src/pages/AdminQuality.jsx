import React, { useState, useEffect } from "react";
import api from "../services/api";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, 
  Cell, LineChart, Line, AreaChart, Area
} from 'recharts';
import { 
  Activity, Brain, Shield, Zap, Layout, Clock, Search, 
  Filter, ChevronDown, Info, ArrowUpRight, TrendingUp,
  Target, AlertCircle, CheckCircle2, Download
} from 'lucide-react';

async function apiFetch(path) {
  const { data } = await api.get(path);
  return data;
}

const CQS_STRUCTURE = {
  engagement: {
    label: "Engagement",
    initial: "E",
    weight: 0.30,
    color: "#0C447C",
    bg: "#E6F1FB",
    desc: "How actively the patient participates and returns",
    params: [
      { key: "star_rating", label: "Star rating (avg)", tag: "Direct", weight: 35, source: "patient_feedback.rating", formula: "AVG(rating) per patient", tip: "Average user satisfaction rating collected after chats." },
      { key: "chip_click_rate", label: "Chip click rate", tag: "Derived", weight: 25, source: "messages.meta_json.chip_clicks", formula: "chip_click_count / chips_shown", tip: "Frequency of users clicking on suggested prompt chips." },
      { key: "return_session_rate", label: "Return session rate", tag: "Derived", weight: 20, source: "conversations.user_id COUNT", formula: "sessions > 1 / total patients", tip: "Percentage of users who come back for more than one session." },
      { key: "conv_depth", label: "Conversation depth (turns)", tag: "Derived", weight: 12, source: "COUNT(messages) per conversation", formula: "AVG(message_count) per conv", tip: "Average number of back-and-forth turns in a session." },
      { key: "elaboration_rate", label: "Follow-up elaboration rate", tag: "Derived", weight: 8, source: "LENGTH(messages.content)", formula: "user turns > 20 words / total", tip: "How often patients give detailed, long-form answers." }
    ]
  },
  response_quality: {
    label: "Response quality",
    initial: "R",
    weight: 0.25,
    color: "#3B6D11",
    bg: "#EAF3DE",
    desc: "Accuracy, relevance and depth of AI answers",
    params: [
      { key: "faithfulness", label: "Faithfulness (RAGAS)", tag: "RAGAS", weight: 30, source: "ragas_metrics.faithfulness", formula: "AVG(faithfulness_score)", tip: "Ensures the AI doesn't hallucinate; answers must be grounded in clinical docs." },
      { key: "answer_relevancy", label: "Answer relevancy (RAGAS)", tag: "RAGAS", weight: 25, source: "ragas_metrics.answer_relevancy", formula: "AVG(answer_relevancy)", tip: "Measures if the AI's response actually addresses the patient's core question." },
      { key: "context_precision", label: "Context precision (RAGAS)", tag: "RAGAS", weight: 20, source: "ragas_metrics.context_precision", formula: "AVG(context_precision)", tip: "How well the retrieved clinical documents matched the patient's query." },
      { key: "context_recall", label: "Context recall (RAGAS)", tag: "RAGAS", weight: 15, source: "ragas_metrics.context_recall", formula: "AVG(context_recall)", tip: "Whether all necessary information was found in the documentation to answer the query." },
      { key: "ai_confidence", label: "AI confidence score", tag: "Derived", weight: 10, source: "messages.confidence", formula: "AVG(confidence) where role=assistant", tip: "The AI's internal certainty level about the medical accuracy of its response." }
    ]
  },
  clinical_safety: {
    label: "Clinical safety",
    initial: "C",
    weight: 0.20,
    color: "#991B1B",
    bg: "#FEF2F2",
    desc: "Guardrails, escalation and safe messaging compliance",
    params: [
      { key: "guardrail_compliance", label: "Guardrail compliance rate", tag: "Safety", weight: 35, source: "system_alerts WHERE component=guardrail", formula: "1 - (guardrail_breaches / total)", tip: "Success rate of keeping the AI within strict clinical and safety boundaries." },
      { key: "escalation_accuracy", label: "Escalation accuracy", tag: "Safety", weight: 25, source: "conversations.escalated + system_alerts", formula: "appropriate_escalations / total_escalated", tip: "How correctly the AI identified when to bring in a human specialist." },
      { key: "emergency_response", label: "Emergency response time", tag: "Safety", weight: 20, source: "messages.processing_ms WHERE agent_id IN (CV2, MH5)", formula: "AVG(processing_ms) for CV2/MH5 agents", tip: "Latency of high-priority agents handling critical health topics." },
      { key: "disclaimer_rate", label: "Disclaimer present rate", tag: "Compliance", weight: 15, source: "messages.content LIKE %consult%", formula: "responses with disclaimer / total AI msgs", tip: "Percentage of AI messages that correctly include medical disclaimers." },
      { key: "citation_rate", label: "Citation provided rate", tag: "Compliance", weight: 5, source: "messages.citations IS NOT NULL", formula: "AI msgs with citations / total AI msgs", tip: "How often the AI backs up its claims with links to clinical sources." }
    ]
  },
  session_flow: {
    label: "Session flow",
    initial: "S",
    weight: 0.15,
    color: "#92400E",
    bg: "#FFFBEB",
    desc: "Conversation coherence, slot efficiency and frustration",
    params: [
      { key: "repeat_question_rate", label: "Repeat question rate", tag: "Coherence", weight: 30, source: "messages.meta_json.chip_echo_detected", formula: "chip_echo_count / total user msgs", tip: "How often the AI asks the same question multiple times (lower is better)." },
      { key: "slot_efficiency", label: "Slot fill efficiency", tag: "Coherence", weight: 25, source: "messages.meta_json.slots_filled COUNT", formula: "slots_filled / max_slots per intent", tip: "How quickly the AI gathers necessary medical data from the patient." },
      { key: "skip_rate", label: "Clarification skip rate", tag: "Coherence", weight: 20, source: "messages.meta_json.skip_used", formula: "skip_triggered / questions_asked", tip: "How often patients choose to skip clarifying questions." },
      { key: "intent_resolution", label: "Intent resolution rate", tag: "Coherence", weight: 15, source: "messages.meta_json.intent", formula: "intents_resolved / total intents detected", tip: "Success rate of resolving the patient's underlying medical need." },
      { key: "frustration_score", label: "Frustration score (avg)", tag: "Sentiment", weight: 10, source: "messages.frustration (inverted)", formula: "1 - AVG(frustration/100)", tip: "Measures patient sentiment throughout the conversation." }
    ]
  },
  format_variety: {
    label: "Format variety",
    initial: "F",
    weight: 0.07,
    color: "#1E3A8A",
    bg: "#EFF6FF",
    desc: "Response format rotation and length appropriateness",
    params: [
      { key: "format_rotation", label: "Format rotation index", tag: "Variety", weight: 40, source: "messages.meta_json.response_format", formula: "unique formats / total AI msgs (capped 1)", tip: "How well the AI mixes text, lists, and tables to present info." },
      { key: "length_appropriateness", label: "Appropriate length rate", tag: "Variety", weight: 35, source: "messages.meta_json.format_used + word_count", formula: "responses within intent word limit / total", tip: "Whether the AI answers were too long or too short for the context." },
      { key: "generic_response_rate", label: "Generic response rate", tag: "Variety", weight: 25, source: "messages.content regex check", formula: "1 - (numbered_1to6_format_count / total)", tip: "Measures how unique and personalized the AI's language is." }
    ]
  },
  velocity: {
    label: "Velocity",
    initial: "V",
    weight: 0.03,
    color: "#065F46",
    bg: "#ECFDF5",
    desc: "Latency and session completion speed",
    params: [
      { key: "p50_latency", label: "P50 response latency", tag: "Perf", weight: 50, source: "messages.processing_ms", formula: "PERCENTILE_CONT(0.5) of processing_ms", tip: "The median response time; the speed experienced by most users." },
      { key: "p95_latency", label: "P95 response latency", tag: "Perf", weight: 30, source: "messages.processing_ms", formula: "PERCENTILE_CONT(0.95) of processing_ms", tip: "The 'slowest' cases; ensures efficiency even for complex medical queries." },
      { key: "completion_rate", label: "Session completion rate", tag: "Perf", weight: 20, source: "conversations + COUNT(messages WHERE role=assistant)", formula: "convs with >=1 AI answer / total sessions", tip: "Percentage of started sessions that successfully reach a clinical response." }
    ]
  }
};

const Tooltip = ({ title, content, tag, source, formula, children }) => {
  const [active, setActive] = useState(false);
  if (!content) return children;
  return (
    <div 
      className="relative block w-full"
      onMouseEnter={() => setActive(true)} 
      onMouseLeave={() => setActive(false)}
    >
      {children}
      {active && (
        <div className="absolute z-[100] bottom-full left-1/2 -translate-x-1/2 mb-4 w-72 p-5 bg-[#0F172A] border border-white/20 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] pointer-events-none text-left animate-in fade-in zoom-in duration-200">
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-8 border-transparent border-t-[#0F172A]" />
          <div className="flex items-center justify-between mb-2 pb-2 border-b border-white/10">
            <span className="text-[11px] font-black text-white uppercase tracking-widest">{title}</span>
            {tag && <span className="px-2 py-0.5 rounded-md bg-white/5 text-[9px] font-black uppercase tracking-widest text-[var(--accent)] border border-white/10">{tag}</span>}
          </div>
          {source && <div className="text-[10px] font-mono text-white/40 mb-1 select-all">{source}</div>}
          {formula && <div className="text-[10px] text-white/50 mb-3 font-medium italic leading-relaxed">{formula}</div>}
          <div className="text-[12px] text-white/90 leading-relaxed font-medium">
            {content}
          </div>
        </div>
      )}
    </div>
  );
};

export default function AdminQuality() {
  const [activeDim, setActiveDim] = useState('engagement');
  const [disease, setDisease] = useState('all');
  const [agent, setAgent] = useState('all');
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [daysFilter, setDaysFilter] = useState(7);

  useEffect(() => {
    // Only show full loading spinner on first load
    if (!data) setLoading(true);
    
    api.get(`/admin/quality/summary?days=${daysFilter}`)
      .then(res => {
        const enhancedData = { ...res.data };
        if (!enhancedData.dimensions) enhancedData.dimensions = {};
        Object.keys(CQS_STRUCTURE).forEach(dk => {
          if (!enhancedData.dimensions[dk]) enhancedData.dimensions[dk] = 85; 
        });
        setData(enhancedData);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch quality summary", err);
        const mockData = { dimensions: {} };
        Object.keys(CQS_STRUCTURE).forEach(dk => mockData.dimensions[dk] = 85);
        setData(mockData);
        setLoading(false);
      });
  }, [daysFilter]); // Only re-fetch on timeframe change for now, or add disease/agent if needed

  const AGENTS_BY_DISEASE = {
    all: ["All Agents"],
    "Diabetes Care (DM)": ["Endocrinology Specialist", "Diabetes Primary Care", "Diabetes Nurse", "Diabetes Dietitian", "Diabetes Educator", "Human Coordinator"],
    "Cardiovascular (CV)": ["Cardiology Specialist", "CV Primary Care", "CV Nurse", "CV Technician", "Heart Health Coach", "Human Coordinator"],
    "Cancer Care (CA)": ["Oncology Specialist", "Cancer Primary Care", "Oncology Nurse", "Radiology Specialist", "Patient Navigator", "Human Coordinator"],
    "Mental Illness (MH)": ["Mental Health Specialist", "Psychiatric Nurse", "Therapist Agent", "MH Primary Care", "Support Group Coord", "Human Coordinator"],
    "Respiratory (RS)": ["Asthma Specialist", "COPD Specialist", "Pulmonary Rehab Specialist", "Respiratory Nurse", "Sleep Apnea Specialist", "Human Coordinator"]
  };

  const currentAgents = AGENTS_BY_DISEASE[disease] || AGENTS_BY_DISEASE.all;

  const downloadExcel = () => {
    if (!data || !data.matrix) return;
    const headers = ["Date", "Disease", "Agent", "Engagement (30%)", "Response Quality (25%)", "Clinical Safety (20%)", "Session Flow (15%)", "Format Variety (7%)", "Velocity (3%)", "CQS Overall", "Tier"];
    const rows = data.matrix.map(row => [
      row.date, row.disease, row.agent, row.E, row.R, row.C, row.S, row.F, row.V, row.cqs,
      row.cqs >= 85 ? "GREEN" : row.cqs >= 70 ? "AMBER" : "RED"
    ]);
    let csvContent = "data:text/csv;charset=utf-8," + headers.join(",") + "\n" + rows.map(e => e.join(",")).join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `CQS_Report_${daysFilter}_days.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const activeData = CQS_STRUCTURE[activeDim];

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      
      {/* Header & Filter */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/5 pb-6">
        <div>
          <h2 className="text-xl font-black text-[var(--text-main)] tracking-tight">Conversation Quality Score (CQS)</h2>
          <p className="text-xs text-[var(--text-dim)] font-medium mt-1">
            28 parameters · 6 dimensions · averaged per patient across all sessions. Click a dimension to explore.
          </p>
        </div>
        <div className="flex items-center gap-3 opacity-0 pointer-events-none">
          {/* Filters moved to Matrix section */}
        </div>
      </div>

      {/* Dimension Pills */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(CQS_STRUCTURE).map(([key, dim]) => {
          const isActive = activeDim === key;
          const score = data?.dimensions[key] || 0;
          return (
            <button
              key={key}
              onClick={() => setActiveDim(key)}
              style={{ 
                background: isActive ? dim.bg : 'var(--bg-card)',
                color: isActive ? dim.color : 'var(--text-dim)',
                borderColor: isActive ? dim.color : 'transparent'
              }}
              className={`px-4 py-2 rounded-full border text-[11px] font-black uppercase tracking-wider transition-all flex items-center gap-2 hover:scale-105 active:scale-95
                ${!isActive && 'hover:bg-white/5 border-white/5'}`}
            >
              <div className="w-1.5 h-1.5 rounded-full" style={{ background: dim.color }} />
              {dim.label}
              <span className="opacity-60 text-[9px] font-bold">{Math.round(dim.weight * 100)}%</span>
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-40 gap-4 min-h-[600px]">
          <div className="w-12 h-12 border-4 border-[var(--accent)]/10 border-t-[var(--accent)] rounded-full animate-spin" />
          <span className="text-sm font-black text-[var(--text-dim)] uppercase tracking-[0.2em] animate-pulse">Syncing Quality Engine...</span>
        </div>
      ) : (
        <>
          {/* Detail Card */}
          <div 
            className="card-premium p-1 transition-all duration-500 shadow-2xl relative"
            style={{ background: `linear-gradient(135deg, ${activeData.color}22, transparent)` }}
          >
            <div className="bg-[var(--bg-card)] rounded-[20px] p-8 border border-white/5">
              <div className="flex items-start justify-between mb-8">
                <div className="flex gap-5">
                  <div 
                    className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl font-black shadow-inner border"
                    style={{ background: activeData.bg, color: activeData.color, borderColor: `${activeData.color}33` }}
                  >
                    {activeData.initial}
                  </div>
                  <div>
                    <h3 className="text-xl font-black text-[var(--text-main)] flex items-center gap-2">
                      {activeData.label}
                      <span className="text-[10px] font-black text-[var(--text-dim)] uppercase tracking-[0.2em] bg-white/5 px-2 py-1 rounded-md">
                        {(activeData.weight * 100)}% of CQS · {activeData.params.length} parameters
                      </span>
                    </h3>
                    <p className="text-sm text-[var(--text-dim)] font-medium mt-1">{activeData.desc}</p>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-4xl font-black tracking-tighter" style={{ color: activeData.color }}>
                    {data?.dimensions[activeDim] || 0}
                  </div>
                  <div className="text-[10px] font-black text-[var(--text-dim)] uppercase tracking-widest">Dimension Achievement</div>
                </div>
              </div>

              <div className="space-y-6">
                {activeData.params.map(p => {
                  const weightVal = p.weight || 0;
                  return (
                    <Tooltip 
                      key={p.key} 
                      title={p.label} 
                      content={p.tip}
                      tag={p.tag}
                      source={p.source}
                      formula={p.formula}
                    >
                      <div className="group cursor-help">
                        <div className="flex justify-between items-end mb-2">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-black text-[var(--text-main)] group-hover:text-[var(--accent)] transition-colors">{p.label}</span>
                              <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-widest
                                ${p.tag === 'RAGAS' ? 'bg-indigo-500/10 text-indigo-400' : 
                                  p.tag === 'Safety' ? 'bg-red-500/10 text-red-400' :
                                  p.tag === 'Perf' ? 'bg-emerald-500/10 text-emerald-400' :
                                  'bg-white/10 text-[var(--text-dim)]'}`}
                              >
                                {p.tag}
                              </span>
                            </div>
                            <div className="font-mono text-[9px] text-[var(--text-dim)]/50 leading-tight">
                              {p.source}
                            </div>
                            <div className="text-[10px] text-[var(--text-dim)] font-medium">
                              {p.formula}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-sm font-black mb-1" style={{ color: activeData.color }}>{weightVal}%</div>
                          </div>
                        </div>
                        <div className="h-2 bg-white/5 rounded-full overflow-hidden border border-white/5">
                          <div 
                            className="h-full rounded-full transition-all duration-1000 shadow-sm"
                            style={{ width: `${weightVal}%`, background: `linear-gradient(to right, ${activeData.color}, ${activeData.color}88)` }}
                          />
                        </div>
                      </div>
                    </Tooltip>
                  );
                })}
              </div>
            </div>
          </div>


      {/* CQS Formula Footer */}
      <div className="p-6 rounded-2xl bg-white/5 border border-white/10 text-center space-y-4">
        <h4 className="text-[10px] font-black text-[var(--text-dim)] uppercase tracking-[0.3em]">CQS Composition Formula</h4>
        <div className="font-mono text-xs p-4 bg-black/20 rounded-xl inline-block border border-white/5 shadow-inner">
          <span className="text-[var(--text-dim)]">CQS = </span>
          {Object.entries(CQS_STRUCTURE).map(([k, v], i) => (
            <React.Fragment key={k}>
              <span style={{ color: v.color }} className="font-black">{v.initial}</span>
              <span className="text-white/30">×{v.weight.toFixed(2)}</span>
              {i < 5 && <span className="text-white/30 mx-2">+</span>}
            </React.Fragment>
          ))}
        </div>
        <p className="text-[10px] text-[var(--text-dim)] max-w-lg mx-auto leading-relaxed">
          The Conversation Quality Score is a weighted composite of clinical accuracy, safety adherence, user engagement, and system performance.
        </p>
      </div>

      <div className="mt-12 mb-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h3 className="text-xl font-black text-[var(--text-main)] flex items-center gap-2 mb-1">Real-time CQS Performance Matrix</h3>
          <p className="text-sm text-[var(--text-dim)] font-medium">Live 6-dimension conversation quality breakdown across all supported disease scopes and agent tiers.</p>
        </div>
        
        <div className="flex items-center gap-2 flex-nowrap overflow-x-auto no-scrollbar bg-[var(--bg-card)] border border-white/5 p-1.5 rounded-2xl shadow-2xl">
          {/* Disease Filter */}
          <div className="relative group min-w-[160px]">
            <Filter size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)]" />
            <select 
              value={disease} 
              onChange={e => {
                setDisease(e.target.value);
                setAgent('all');
              }}
              className="w-full pl-8 pr-7 py-1.5 bg-white/5 border border-white/5 rounded-xl text-[10px] font-bold appearance-none hover:border-[var(--accent)]/50 transition-all cursor-pointer"
            >
              <option value="all" className="bg-[#1a1a2e]">All Diseases</option>
              <option value="Diabetes Care (DM)" className="bg-[#1a1a2e]">Diabetes Care (DM)</option>
              <option value="Cardiovascular (CV)" className="bg-[#1a1a2e]">Cardiovascular (CV)</option>
              <option value="Cancer Care (CA)" className="bg-[#1a1a2e]">Cancer Care (CA)</option>
              <option value="Mental Illness (MH)" className="bg-[#1a1a2e]">Mental Illness (MH)</option>
              <option value="Respiratory (RS)" className="bg-[#1a1a2e]">Respiratory (RS)</option>
            </select>
            <ChevronDown size={12} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)] pointer-events-none" />
          </div>

          {/* Agent Filter - Cascading */}
          <div className={`relative group min-w-[180px] ${disease === 'all' ? 'opacity-50' : ''}`}>
            <Brain size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)]" />
            <select 
              value={agent} 
              disabled={disease === 'all'}
              onChange={e => setAgent(e.target.value)}
              className="w-full pl-8 pr-7 py-1.5 bg-white/5 border border-white/5 rounded-xl text-[10px] font-bold appearance-none hover:border-[var(--accent)]/50 transition-all cursor-pointer"
            >
              <option value="all" className="bg-[#1a1a2e]">All Agents</option>
              {currentAgents.map((a, i) => a !== "All Agents" && (
                <option key={i} value={a} className="bg-[#1a1a2e]">{a}</option>
              ))}
            </select>
            <ChevronDown size={12} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)] pointer-events-none" />
          </div>

          {/* Timeframe Filter */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white/5 rounded-xl border border-white/5 min-w-[140px]">
            <span className="text-[10px] font-black text-white/40 uppercase tracking-widest whitespace-nowrap">Timeframe:</span>
            <select 
              className="bg-transparent text-white text-[10px] font-bold outline-none cursor-pointer focus:ring-0 border-none p-0"
              value={daysFilter}
              onChange={(e) => setDaysFilter(parseInt(e.target.value))}
            >
              <option value="7" className="bg-[#1a1a2e]">Last 7 Days</option>
              <option value="14" className="bg-[#1a1a2e]">Last 14 Days</option>
              <option value="21" className="bg-[#1a1a2e]">Last 21 Days</option>
              <option value="30" className="bg-[#1a1a2e]">Last 1 Month</option>
            </select>
          </div>

          {/* Download Button */}
          <button 
            onClick={downloadExcel}
            className="flex items-center gap-2 px-4 py-1.5 rounded-xl bg-[var(--accent)] hover:brightness-110 text-white text-[10px] font-black transition-all shadow-lg whitespace-nowrap"
          >
            <Download size={12} />
            DOWNLOAD EXCEL
          </button>
        </div>
      </div>
        
        <div className="card overflow-hidden border border-white/5 bg-[var(--bg-card)]">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-[#0F172A]">
                <tr>
                  <th className="px-4 py-3 font-mono text-[10px] text-ink3 uppercase tracking-wider">Date</th>
                  <th className="px-4 py-3 font-mono text-[10px] text-ink3 uppercase tracking-wider">Disease</th>
                  <th className="px-4 py-3 font-mono text-[10px] text-ink3 uppercase tracking-wider">Agent</th>
                  <th className="px-4 py-3 font-mono text-[10px] text-white uppercase tracking-wider text-center">E<br/><span className="text-[8px] text-ink3">30%</span></th>
                  <th className="px-4 py-3 font-mono text-[10px] text-white uppercase tracking-wider text-center">R<br/><span className="text-[8px] text-ink3">25%</span></th>
                  <th className="px-4 py-3 font-mono text-[10px] text-white uppercase tracking-wider text-center">C<br/><span className="text-[8px] text-ink3">20%</span></th>
                  <th className="px-4 py-3 font-mono text-[10px] text-white uppercase tracking-wider text-center">S<br/><span className="text-[8px] text-ink3">15%</span></th>
                  <th className="px-4 py-3 font-mono text-[10px] text-white uppercase tracking-wider text-center">F<br/><span className="text-[8px] text-ink3">7%</span></th>
                  <th className="px-4 py-3 font-mono text-[10px] text-white uppercase tracking-wider text-center">V<br/><span className="text-[8px] text-ink3">3%</span></th>
                  <th className="px-4 py-3 font-mono text-[10px] text-[var(--accent)] uppercase tracking-wider font-black text-center border-l border-white/5">CQS Overall</th>
                  <th className="px-4 py-3 font-mono text-[10px] text-ink3 uppercase tracking-wider text-center">Tier</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {(() => {
                  const filtered = (data?.matrix || []).filter(row => {
                    const diseaseMatch = disease === 'all' || row.disease === disease;
                    const agentMatch = agent === 'all' || row.agent === agent;
                    return diseaseMatch && agentMatch;
                  });
                  if (filtered.length === 0) {
                    return <tr><td colSpan="11" className="px-4 py-8 text-center text-ink3">No matching matrix records found.</td></tr>;
                  }
                  return filtered.map((row, idx) => {
                    let tierColor = "#EF4444"; // Explicit Red
                    let tierLabel = "RED";
                    let bgTier = "rgba(239, 68, 68, 0.1)"; 
                    if (row.cqs >= 85) {
                      tierColor = "#10B981"; // Explicit Green
                      tierLabel = "GREEN";
                      bgTier = "rgba(16, 185, 129, 0.1)";
                    } else if (row.cqs >= 70) {
                      tierColor = "#F59E0B"; // Explicit Amber
                      tierLabel = "AMBER";
                      bgTier = "rgba(245, 158, 11, 0.1)";
                    }
                    return (
                      <tr key={idx} className="hover:bg-white/5 transition-colors">
                        <td className="px-4 py-3 font-mono text-[10px] text-white/50">{row.date}</td>
                        <td className="px-4 py-3 font-bold text-white/90">{row.disease}</td>
                        <td className="px-4 py-3 font-medium text-ink2">{row.agent}</td>
                        <td className="px-4 py-3 text-center text-white/80 font-mono">{row.E}</td>
                        <td className="px-4 py-3 text-center text-white/80 font-mono">{row.R}</td>
                        <td className="px-4 py-3 text-center text-white/80 font-mono">{row.C}</td>
                        <td className="px-4 py-3 text-center text-white/80 font-mono">{row.S}</td>
                        <td className="px-4 py-3 text-center text-white/80 font-mono">{row.F}</td>
                        <td className="px-4 py-3 text-center text-white/80 font-mono">{row.V}</td>
                        <td className="px-4 py-3 text-center font-black text-[14px] border-l border-white/5" style={{ color: tierColor }}>{row.cqs}</td>
                        <td className="px-4 py-3 text-center">
                          <span className="px-2 py-1 rounded-[4px] text-[9px] font-black tracking-widest border" style={{ color: tierColor, backgroundColor: bgTier, borderColor: `${tierColor}40` }}>
                            {tierLabel}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                })()}
              </tbody>
            </table>
          </div>
        </div>
      </>
      )}
    </div>
  );
}
