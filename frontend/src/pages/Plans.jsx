import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, Info, Heart, Brain, Zap, Shield, Activity } from 'lucide-react';

const PLANS = [
  { 
    id: 'dm', 
    name: 'Diabetes Care', 
    icon: <div className="w-12 h-12 rounded-2xl bg-pink-100 text-pink-600 flex items-center justify-center text-2xl">💧</div>,
    price: 29, 
    desc: 'Comprehensive management for Type 1 & 2 diabetes — monitoring, nutrition, and prevention.',
    features: ['Blood Glucose & Lab Interpretation','Medication & Insulin Management','LATAM Nutrition & Glycaemic Index','Complication Prevention','Lifestyle & Metabolic Wellness']
  },
  { 
    id: 'cv', 
    name: 'Cardiovascular Care', 
    icon: <div className="w-12 h-12 rounded-2xl bg-red-100 text-red-600 flex items-center justify-center text-2xl">❤️</div>,
    price: 29, 
    desc: 'From risk screening to cardiac rehabilitation — including Chagas disease awareness.',
    features: ['Risk Screening & Awareness','Emergency & Critical Alert','Medication & Treatment Navigation','Cardiac Rehabilitation','Heart-Healthy DASH Nutrition']
  },
  { 
    id: 'ca', 
    name: 'Cancer Care', 
    icon: <div className="w-12 h-12 rounded-2xl bg-orange-100 text-orange-600 flex items-center justify-center text-2xl">🎗️</div>,
    price: 39, 
    desc: 'Screening navigation, treatment guidance, pain management, and survivorship support.',
    features: ['Screening & Early Detection','Treatment Navigation','Pain & Palliative Care','Emotional & Mental Support','Survivorship & Post-Treatment']
  },
  { 
    id: 'mh', 
    name: 'Mental Health', 
    icon: <div className="w-12 h-12 rounded-2xl bg-purple-100 text-purple-600 flex items-center justify-center text-2xl">🧠</div>,
    price: 24, 
    desc: 'Specialised companions for depression, anxiety, trauma, and crisis management.',
    features: ['Depression & Mood Tracking','Anxiety Management','Sleep Hygiene & Trauma','Crisis Response Protocol','Cognitive Behavioral Support']
  },
  { 
    id: 'rs', 
    name: 'Respiratory Care', 
    icon: <div className="w-12 h-12 rounded-2xl bg-blue-100 text-blue-600 flex items-center justify-center text-2xl">🫁</div>,
    price: 24, 
    desc: 'Advanced support for asthma, COPD, and sleep apnea therapy management.',
    features: ['Lung Function Monitoring','Inhaler Technique Guidance','COPD Flare-up Prevention','Sleep Apnea Therapy','Oxygen Management']
  },
];

export default function Plans() {
  const [billing, setBilling] = useState('monthly');
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[var(--bg-main)] text-[var(--text-main)] py-20 px-6 transition-colors">
      <div className="max-w-7xl mx-auto text-center">
        <h1 className="text-4xl md:text-6xl font-black mb-6 tracking-tight">Choose your care plan</h1>
        <p className="text-[var(--text-dim)] text-lg mb-12 font-medium">Subscribe to one condition or bundle multiple for comprehensive care.</p>

        {/* Toggle with Radio Buttons */}
        <div className="flex items-center justify-center gap-8 mb-16">
          <label className={`flex items-center gap-3 cursor-pointer p-4 rounded-2xl border transition-all ${billing === 'monthly' ? 'bg-orange-500/10 border-orange-500/50 text-white' : 'bg-white/5 border-white/10 text-gray-400'}`}>
            <input 
              type="radio" 
              name="billing" 
              value="monthly" 
              checked={billing === 'monthly'} 
              onChange={() => setBilling('monthly')}
              className="w-4 h-4 accent-orange-500"
            />
            <span className="font-bold">Monthly Billing</span>
          </label>

          <label className={`flex items-center gap-3 cursor-pointer p-4 rounded-2xl border transition-all ${billing === 'annual' ? 'bg-orange-500/10 border-orange-500/50 text-white' : 'bg-white/5 border-white/10 text-gray-400'}`}>
            <input 
              type="radio" 
              name="billing" 
              value="annual" 
              checked={billing === 'annual'} 
              onChange={() => setBilling('annual')}
              className="w-4 h-4 accent-orange-500"
            />
            <div className="text-left">
              <span className="font-bold block">Annual Billing</span>
              <span className="text-[10px] bg-green-500 text-white px-2 py-0.5 rounded-full font-black uppercase">Save 20%</span>
            </div>
          </label>
        </div>

        {/* Plans Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
          {PLANS.map((p) => (
            <div key={p.id} className="card-patient p-8 text-left flex flex-col hover:border-orange-500 transition-all group relative overflow-hidden">
              {p.id === 'ca' && (
                <div className="absolute top-0 right-0 bg-navy-900 text-white text-[10px] font-black px-4 py-1 rounded-bl-xl uppercase">Most Subscribed</div>
              )}
              
              <div className="mb-6 group-hover:scale-110 transition-transform">{p.icon}</div>
              <h3 className="text-xl font-bold mb-3 text-white">{p.name}</h3>
              <p className="text-xs text-gray-400 leading-relaxed mb-6 flex-1">{p.desc}</p>
              
              <div className="mb-8">
                <div className="flex items-end gap-1">
                  <span className="text-3xl font-black text-white">${billing === 'monthly' ? p.price : Math.floor(p.price * 0.8)}</span>
                  <span className="text-sm text-gray-400 font-bold mb-1">/month</span>
                </div>
                {billing === 'annual' && (
                  <div className="text-[10px] text-green-400 font-bold mt-1">or ${Math.floor(p.price * 0.8 * 12)}/year (save ${p.price * 12 - Math.floor(p.price * 0.8 * 12)})</div>
                )}
              </div>

              <div className="space-y-3 mb-8">
                {p.features.map(f => (
                  <div key={f} className="flex items-start gap-2 text-[10px] font-bold text-gray-300">
                    <Check size={14} className="text-green-500 mt-0.5 shrink-0" />
                    <span>{f}</span>
                  </div>
                ))}
              </div>

              <button 
                onClick={() => navigate(`/checkout?plan=${p.id}`)}
                className="w-full py-3 rounded-xl bg-white/5 border border-white/10 text-white font-black text-xs hover:bg-orange-500 hover:border-orange-500 transition-all uppercase tracking-widest"
              >
                Select Plan
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
