import React, { useState } from 'react'
import {
  BarChart, Bar, ComposedChart, ResponsiveContainer, XAxis, YAxis, CartesianGrid,
  Tooltip as ChartTooltip, Legend, PieChart, Pie, Cell, LineChart, Line
} from 'recharts'
import {
  Search, Users, Heart, AlertCircle, Activity, ChevronRight,
  TrendingUp, Shield, MessageSquare, Smile, Compass, LifeBuoy, Info
} from 'lucide-react'

// --- Local Shared Components ---
const MetricCard = ({ label, value, sub, color = 'var(--accent)', icon, tip }) => (
  <div className="bg-[var(--bg-card)] border border-white/5 rounded-2xl p-5 hover:border-white/10 transition-all group relative w-full shadow-lg">
    {/* Overflow wrapper specifically for the background decorative glow to prevent tooltip clipping */}
    <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none z-0">
      <div className="absolute top-0 right-0 w-24 h-24 bg-white/5 blur-3xl group-hover:bg-white/10 transition-all" />
    </div>
    <div className="relative z-10">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-[var(--text-dim)] font-bold uppercase tracking-[0.1em]">{label}</span>
          {tip && (
            <div className="relative cursor-pointer text-[var(--text-dim)] hover:text-white transition-colors group/tip select-none flex items-center">
              <Info size={11} />
              {/* Tooltip bubble with absolute positioning */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2.5 bg-black/90 backdrop-blur-md border border-white/10 text-[9px] font-medium text-white rounded-xl opacity-0 scale-95 pointer-events-none group-hover/tip:opacity-100 group-hover/tip:scale-100 transition-all duration-200 z-50 shadow-xl leading-normal text-center normal-case tracking-normal">
                {tip}
                <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-black/90" />
              </div>
            </div>
          )}
        </div>
        <div className="w-9 h-9 rounded-xl flex items-center justify-center shadow-lg" style={{ background: color + '20', color }}>{icon}</div>
      </div>
      <div className="text-2xl font-black tracking-tight mb-1" style={{ color }}>{value}</div>
      {sub && <div className="text-[10px] font-bold text-[var(--text-dim)]">{sub}</div>}
    </div>
  </div>
)

const Badge = ({ children, color = 'var(--accent)' }) => (
  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold"
    style={{ color, background: color + '12', border: `1px solid ${color}25` }}>
    {children}
  </span>
)

export default function AdminSentiment({ data }) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedDisease, setSelectedDisease] = useState('ALL')
  const [selectedCategory, setSelectedCategory] = useState('ALL')
  const [selectedPatient, setSelectedPatient] = useState(null)

  // Fallbacks if data is not loaded yet
  const overallStats = data?.overall_stats || {
    total_patients: 0,
    avg_sentiment_score: 0,
    distress_count: 0,
    equanimity_count: 0,
    reassured_count: 0,
    intervention_count: 0
  }
  
  const diseaseWise = data?.disease_wise || []
  const userSpecific = data?.user_specific || []

  // Filtering patients
  const filteredPatients = userSpecific.filter(p => {
    const matchesSearch = p.name?.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          p.email?.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesDisease = selectedDisease === 'ALL' || p.disease_code === selectedDisease
    const matchesCategory = selectedCategory === 'ALL' || p.sentiment_category === selectedCategory
    return matchesSearch && matchesDisease && matchesCategory
  })

  // Theme constants
  const CATEGORY_COLORS = {
    'Clinically Reassured': '#2DD4BF',   // Neon Teal
    'Clinical Equanimity': '#818CF8',   // Indigo
    'Clinical Distress': '#F472B6'      // Neon Pink/Red
  }

  // Distribution chart data
  const distributionData = [
    { name: 'Clinically Reassured', value: overallStats.reassured_count, color: CATEGORY_COLORS['Clinically Reassured'] },
    { name: 'Clinical Equanimity', value: overallStats.equanimity_count, color: CATEGORY_COLORS['Clinical Equanimity'] },
    { name: 'Clinical Distress', value: overallStats.distress_count, color: CATEGORY_COLORS['Clinical Distress'] }
  ].filter(d => d.value > 0)

  // Handler to close drawers
  const closeDrawer = () => setSelectedPatient(null)

  // Generate mock frustration details for modal rendering
  const getMockTelemetry = (patient) => {
    // Deterministic simulation based on user id/email
    const seed = (patient.name || '').length + (patient.email || '').length
    const points = []
    let base = patient.avg_frustration || 30
    for (let i = 1; i <= 6; i++) {
      const offset = Math.sin(seed + i) * 15
      points.push({
        turn: `Turn ${i}`,
        Frustration: Math.round(Math.max(5, Math.min(99, base + offset)))
      })
    }
    
    // Custom recommendation based on clinical category
    let clinicalPlan = []
    let warnings = []
    
    if (patient.sentiment_category === 'Clinical Distress') {
      clinicalPlan = [
        "Immediate Care Integration: Relaunch primary therapeutic agent with simplified phrasing filters.",
        "Clinical Handover: Flag this record for immediate human cardiologist/endocrinologist contact.",
        "System Override: Lower response temperature to 0.05 to prevent clinical ambiguity or confusion."
      ]
      warnings = [
        "Acute Distress: Patient exhibits repetitive queries with rising frustration signals.",
        "Alignment Failure: Low feedback stars indicate discrepancy in medical advice expectations."
      ]
    } else if (patient.sentiment_category === 'Clinical Equanimity') {
      clinicalPlan = [
        "Routine Ingestion Review: Monitor PubMed citation density in upcoming turns.",
        "Engagement Enhancement: Deploy interactive health coaching prompts in patient dashboard.",
        "Continuous Audit: Keep standard 15-day HIPAA retention logs active."
      ]
      warnings = [
        "Compensated State: Stable trajectory, but patient lacks high-reassurance signals."
      ]
    } else {
      clinicalPlan = [
        "Optimal Alignment Maintained: Document ingestion pipeline is serving GOLD standard content.",
        "Peer Recommendations: Patient is fully aligned with clinical guidelines. Continue routine monitoring.",
        "Knowledge Reinforcement: Keep background vector databases synced with CDC Guidelines."
      ]
      warnings = [
        "Clinically Stable: No therapeutic issues or cognitive frustration detected."
      ]
    }

    return { points, clinicalPlan, warnings }
  }

  const patientTelemetry = selectedPatient ? getMockTelemetry(selectedPatient) : null

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-700 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-xl font-disp font-black tracking-tight text-[var(--text-main)]">
            Patient Sentiment & Telemetry Scorecard
          </h2>
          <p className="text-sm text-[var(--text-dim)] mt-0.5">
            Disease-specific emotional metrics, structured patient feedback evaluation, and automated clinical intervention triggers.
          </p>
        </div>
        <div className="text-[10px] font-mono text-[var(--text-dim)] flex items-center gap-2 bg-black/20 px-3 py-2 rounded-xl border border-white/5 shadow-inner">
          <div className="w-1.5 h-1.5 rounded-full bg-teal animate-pulse" />
          <span>Active Patient Sentiment Monitor (v3.4)</span>
        </div>
      </div>

      {/* Global Clinical Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Overall Sentiment Index"
          value={`${overallStats.avg_sentiment_score}%`}
          color="var(--accent)"
          icon={<Heart size={14} />}
          sub="Global patient compliance"
          tip="The average emotional and clinical alignment score calculated across all active patient profiles."
        />
        <MetricCard
          label="Interventions Indicated"
          value={overallStats.intervention_count}
          color="#F472B6"
          icon={<AlertCircle size={14} />}
          sub="Requires active clinician follow-up"
          tip="Total patients currently flagged for urgent human coordination due to high frustration levels or low rating trends."
        />
        <MetricCard
          label="Clinically Reassured"
          value={overallStats.reassured_count}
          color="#2DD4BF"
          icon={<Smile size={14} />}
          sub="Optimal therapeutic state"
          tip="Patients who exhibit high confidence, positive feedback, and low conversational frustration."
        />
        <MetricCard
          label="Clinical Distress"
          value={overallStats.distress_count}
          color="#F472B6"
          icon={<Activity size={14} />}
          sub="Decompensated emotional states"
          tip="Patients who exhibit rising frustration telemetry, negative feedback, or human-escalation events."
        />
      </div>

      {/* Analytics Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Disease-Wise Bar Chart */}
        <div className="card-premium lg:col-span-2 p-5 bg-[var(--bg-card)] border border-white/5 rounded-3xl flex flex-col justify-between shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-[var(--accent)]/5 blur-3xl rounded-full pointer-events-none" />
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-disp font-bold text-xs uppercase tracking-wider text-[var(--text-dim)]">Disease-Wise Clinical Sentiment</h3>
              <p className="text-[10px] text-[var(--text-dim)]">Average alignment score segmentations by therapeutic area</p>
            </div>
            <Badge color="var(--accent)">Therapeutic Areas</Badge>
          </div>
          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={diseaseWise} margin={{ top: 15, right: 15, left: 10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis 
                  dataKey="disease_name" 
                  tick={{ fill: 'var(--text-dim)', fontSize: 9 }} 
                  axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  label={{ value: 'Therapeutic Areas', position: 'insideBottom', offset: -10, fill: 'var(--text-dim)', fontSize: 10, fontWeight: 'bold' }}
                />
                <YAxis 
                  domain={[0, 100]}
                  tick={{ fill: 'var(--text-dim)', fontSize: 9 }} 
                  axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
                  label={{ value: 'Avg Sentiment Score (%)', angle: -90, position: 'insideLeft', offset: 0, fill: 'var(--text-dim)', fontSize: 10, fontWeight: 'bold' }}
                />
                <ChartTooltip 
                  contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12, fontSize: 10 }}
                  cursor={{ fill: 'rgba(255,255,255,0.02)' }}
                />
                <Bar dataKey="avg_sentiment_score" fill="var(--accent)" radius={[8, 8, 0, 0]} name="Avg Sentiment Score">
                  {diseaseWise.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={index % 2 === 0 ? 'var(--accent)' : '#A78BFA'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Sentiment Distribution Pie Chart */}
        <div className="card-premium p-5 bg-[var(--bg-card)] border border-white/5 rounded-3xl flex flex-col justify-between shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-24 h-24 bg-white/5 blur-2xl rounded-full pointer-events-none" />
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-disp font-bold text-xs uppercase tracking-wider text-[var(--text-dim)]">Taxonomy Distribution</h3>
              <p className="text-[10px] text-[var(--text-dim)]">Emotional state categorization ratio</p>
            </div>
            <Badge color="#818CF8">Proportions</Badge>
          </div>
          <div className="h-44 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={distributionData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={70}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {distributionData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-col gap-2 mt-2">
            {distributionData.map((item, idx) => (
              <div key={idx} className="flex justify-between items-center text-[10px] font-mono">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ background: item.color }} />
                  <span className="text-[var(--text-dim)]">{item.name}</span>
                </div>
                <span className="font-bold text-[var(--text-main)]">{item.value} patients</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Control Filter Panel */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 bg-[var(--bg-card)] border border-white/5 p-4 rounded-2xl shadow-xl">
        <div className="flex items-center gap-3 bg-white/5 border border-white/5 px-4 py-2.5 rounded-xl w-full max-w-sm">
          <Search size={14} className="text-[var(--text-dim)]" />
          <input 
            type="text" 
            placeholder="Filter clinical database by patient name/email..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-transparent text-xs text-[var(--text-main)] outline-none border-none w-full"
          />
          {searchQuery && <button onClick={() => setSearchQuery('')} className="text-[10px] text-[var(--text-dim)] hover:text-white font-bold">Clear</button>}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {/* Disease filter select */}
          <div className="bg-white/5 border border-white/5 px-3 py-1.5 rounded-xl flex items-center gap-2">
            <span className="text-[9px] text-[var(--text-dim)] font-black uppercase">Therapeutic Group:</span>
            <select
              className="bg-transparent text-[10px] font-bold text-white outline-none border-none p-0 cursor-pointer"
              value={selectedDisease}
              onChange={(e) => setSelectedDisease(e.target.value)}
            >
              <option value="ALL" className="bg-[#1a1a2e]">All Groups</option>
              <option value="DM" className="bg-[#1a1a2e]">Diabetes (DM)</option>
              <option value="CV" className="bg-[#1a1a2e]">Cardiovascular (CV)</option>
              <option value="CA" className="bg-[#1a1a2e]">Cancer Care (CA)</option>
              <option value="MH" className="bg-[#1a1a2e]">Mental Illness (MH)</option>
              <option value="RS" className="bg-[#1a1a2e]">Respiratory (RS)</option>
            </select>
          </div>

          {/* Category filter select */}
          <div className="bg-white/5 border border-white/5 px-3 py-1.5 rounded-xl flex items-center gap-2">
            <span className="text-[9px] text-[var(--text-dim)] font-black uppercase">Clinical State:</span>
            <select
              className="bg-transparent text-[10px] font-bold text-white outline-none border-none p-0 cursor-pointer"
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
            >
              <option value="ALL" className="bg-[#1a1a2e]">All States</option>
              <option value="Clinically Reassured" className="bg-[#1a1a2e]">Clinically Reassured</option>
              <option value="Clinical Equanimity" className="bg-[#1a1a2e]">Clinical Equanimity</option>
              <option value="Clinical Distress" className="bg-[#1a1a2e]">Clinical Distress</option>
            </select>
          </div>
        </div>
      </div>

      {/* Patient Specific Telemetry Table */}
      <div className="card overflow-hidden bg-[var(--bg-card)] border border-white/5 rounded-3xl shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-bg3 border-b border-white/10">
              <tr>
                <th className="px-4 py-3.5 font-mono text-[10px] text-ink3 uppercase">Patient Profile</th>
                <th className="px-4 py-3.5 font-mono text-[10px] text-ink3 uppercase">Therapeutic Area</th>
                <th className="px-4 py-3.5 font-mono text-[10px] text-ink3 uppercase">Sentiment Score</th>
                <th className="px-4 py-3.5 font-mono text-[10px] text-ink3 uppercase">Clinical State</th>
                <th className="px-4 py-3.5 font-mono text-[10px] text-ink3 uppercase">Avg Feedback</th>
                <th className="px-4 py-3.5 font-mono text-[10px] text-ink3 uppercase">Int. Required?</th>
                <th className="px-4 py-3.5 font-mono text-[10px] text-ink3 uppercase">Timestamp</th>
                <th className="px-4 py-3.5 font-mono text-[10px] text-ink3 uppercase text-right">Clinical Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filteredPatients.map((p, idx) => {
                const badgeColor = CATEGORY_COLORS[p.sentiment_category] || 'var(--accent)'
                return (
                  <tr 
                    key={idx}
                    onClick={() => setSelectedPatient(p)}
                    className="hover:bg-white/5 transition-colors cursor-pointer"
                  >
                    {/* Patient Profile */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-[var(--accent)]/10 text-[var(--accent)] flex items-center justify-center font-black text-xs font-disp">
                          {p.name?.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <div className="font-bold text-[var(--text-main)]">{p.name}</div>
                          <div className="text-[10px] text-[var(--text-dim)] font-mono">{p.email}</div>
                        </div>
                      </div>
                    </td>

                    {/* Disease */}
                    <td className="px-4 py-3 text-[var(--text-main)] font-semibold">
                      {p.primary_disease}
                    </td>

                    {/* Sentiment score bar */}
                    <td className="px-4 py-3">
                      <div className="w-28">
                        <div className="flex justify-between items-center text-[9px] font-mono font-bold mb-1 text-[var(--text-dim)]">
                          <span>Patient Score</span>
                          <span>{p.sentiment_score}%</span>
                        </div>
                        <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                          <div 
                            className="h-full rounded-full" 
                            style={{ 
                              width: `${p.sentiment_score}%`,
                              background: `linear-gradient(to right, ${badgeColor}, var(--accent))`
                            }}
                          />
                        </div>
                      </div>
                    </td>

                    {/* Category */}
                    <td className="px-4 py-3">
                      <Badge color={badgeColor}>{p.sentiment_category.toUpperCase()}</Badge>
                    </td>

                    {/* Avg Feedback rating */}
                    <td className="px-4 py-3 font-mono font-bold text-[var(--text-main)] text-sm">
                      {p.avg_feedback_rating ? `${p.avg_feedback_rating} / 5 ★` : '—'}
                    </td>

                    {/* Intervention indicator */}
                    <td className="px-4 py-3">
                      {p.intervention_required ? (
                        <span className="inline-flex items-center gap-1.5 bg-red-600/10 border border-red-500/20 px-2 py-0.5 rounded-full text-[9px] font-bold text-red-500">
                          <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                          INTERVENTION INDICATED
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full text-[9px] font-bold text-emerald-500">
                          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                          ROUTINE MONITORING
                        </span>
                      )}
                    </td>

                    {/* Timestamp */}
                    <td className="px-4 py-3 font-mono text-[10px] text-[var(--text-dim)]">
                      {p.timestamp || '—'}
                    </td>

                    {/* Details action */}
                    <td className="px-4 py-3 text-right">
                      <button 
                        className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-[var(--text-dim)] hover:text-white flex items-center justify-center transition-all ml-auto"
                        title="Open diagnostic sheet"
                      >
                        <ChevronRight size={14} />
                      </button>
                    </td>
                  </tr>
                )
              })}

              {filteredPatients.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-16 text-center text-[var(--text-dim)] font-medium">
                    No clinical matches found in the patient database.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Patient Diagnostic Modal Drawer */}
      {selectedPatient && patientTelemetry && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md flex items-center justify-center z-50 animate-in fade-in duration-300">
          <div className="bg-[var(--bg-card)] border border-white/10 rounded-3xl w-full max-w-xl p-6 relative overflow-hidden shadow-2xl animate-in zoom-in duration-300 space-y-6 max-h-[90vh] overflow-y-auto">
            {/* Decorative blur */}
            <div className="absolute top-0 right-0 w-32 h-32 bg-[var(--accent)]/10 blur-3xl rounded-full pointer-events-none" />
            
            {/* Drawer Header */}
            <div className="flex items-center justify-between pb-4 border-b border-white/5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[var(--accent)]/10 text-[var(--accent)] flex items-center justify-center font-bold text-sm font-disp">
                  {selectedPatient.name?.charAt(0).toUpperCase()}
                </div>
                <div>
                  <h3 className="font-disp font-bold text-base text-[var(--text-main)] flex items-center gap-2">
                    {selectedPatient.name}
                    {selectedPatient.intervention_required && (
                      <span className="text-[8px] bg-red-600 text-white font-black px-1.5 py-0.5 rounded uppercase tracking-wider animate-pulse">Critical</span>
                    )}
                  </h3>
                  <p className="text-[10px] text-[var(--text-dim)] font-mono">{selectedPatient.email}</p>
                </div>
              </div>
              <button 
                onClick={closeDrawer}
                className="w-8 h-8 rounded-xl bg-white/5 hover:bg-white/10 text-[var(--text-dim)] hover:text-white flex items-center justify-center transition-all font-black text-sm"
              >
                ×
              </button>
            </div>

            {/* Diagnostic Clinical Scoreboard */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-black/20 p-4 rounded-2xl border border-white/5 text-center">
                <div className="text-[8px] text-[var(--text-dim)] font-black uppercase tracking-wider mb-1">Sentiment Score</div>
                <div className="text-xl font-black text-[var(--accent)] font-mono">{selectedPatient.sentiment_score}%</div>
                <div className="text-[8px] text-[var(--text-dim)] font-mono mt-0.5">{selectedPatient.sentiment_category}</div>
              </div>
              <div className="bg-black/20 p-4 rounded-2xl border border-white/5 text-center">
                <div className="text-[8px] text-[var(--text-dim)] font-black uppercase tracking-wider mb-1">Avg Frustration</div>
                <div className="text-xl font-black text-pink-400 font-mono">{selectedPatient.avg_frustration}/100</div>
                <div className="text-[8px] text-[var(--text-dim)] font-mono mt-0.5">Conversational stress</div>
              </div>
              <div className="bg-black/20 p-4 rounded-2xl border border-white/5 text-center">
                <div className="text-[8px] text-[var(--text-dim)] font-black uppercase tracking-wider mb-1">Feedback Rating</div>
                <div className="text-xl font-black text-teal font-mono">
                  {selectedPatient.avg_feedback_rating ? `${selectedPatient.avg_feedback_rating}/5` : '—'}
                </div>
                <div className="text-[8px] text-[var(--text-dim)] font-mono mt-0.5">Patient star review</div>
              </div>
            </div>

            {/* Frustration Telemetry Line Chart */}
            <div className="bg-black/20 p-4 rounded-2xl border border-white/5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-dim)] block mb-3">
                Real-Time Frustration Telemetry (Recent Turns)
              </span>
              <div className="h-36 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={patientTelemetry.points}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="turn" tick={{ fill: 'var(--text-dim)', fontSize: 8 }} />
                    <YAxis tick={{ fill: 'var(--text-dim)', fontSize: 8 }} domain={[0, 100]} />
                    <ChartTooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', fontSize: 9 }} />
                    <Line type="monotone" dataKey="Frustration" stroke="#F472B6" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Clinical Notes & Recommendations */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Warnings */}
              <div className="bg-red-500/5 p-4 rounded-2xl border border-red-500/10">
                <span className="text-[9px] font-black uppercase tracking-wider text-red-400 flex items-center gap-1.5 mb-2">
                  <Shield size={12} /> Clinical Risk Assessment
                </span>
                <ul className="space-y-2 text-[10px] text-white/80 font-medium">
                  {patientTelemetry.warnings.map((w, idx) => (
                    <li key={idx} className="flex gap-2 items-start">
                      <div className="w-1.5 h-1.5 rounded-full bg-red-400 mt-1 flex-shrink-0" />
                      <span>{w}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Action Plan */}
              <div className="bg-teal/5 p-4 rounded-2xl border border-teal/10">
                <span className="text-[9px] font-black uppercase tracking-wider text-teal flex items-center gap-1.5 mb-2">
                  <Compass size={12} /> Recommended Care Strategy
                </span>
                <ul className="space-y-2 text-[10px] text-white/80 font-medium">
                  {patientTelemetry.clinicalPlan.map((p, idx) => (
                    <li key={idx} className="flex gap-2 items-start">
                      <div className="w-1.5 h-1.5 rounded-full bg-teal mt-1 flex-shrink-0" />
                      <span>{p}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            
            <button
              onClick={closeDrawer}
              className="w-full bg-[var(--accent)] text-white hover:opacity-90 font-bold py-2.5 rounded-xl text-xs transition-all shadow-lg shadow-[var(--accent)]/20"
            >
              Close Patient Diagnostic Sheet
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
