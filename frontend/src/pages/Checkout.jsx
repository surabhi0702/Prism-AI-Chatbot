import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Lock, ShieldCheck, CheckCircle2, CreditCard } from 'lucide-react';
import api from '../services/api';
import { useAuthStore } from '../store/auth';

export default function Checkout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { updateUser } = useAuthStore();
  const [loading, setLoading] = React.useState(false);

  const params = new URLSearchParams(location.search);
  const planId = params.get('plan') || 'ca';

  const planNames = {
    'dm': 'Diabetes Care',
    'cv': 'Cardiovascular Care',
    'ca': 'Cancer Care',
    'mh': 'Mental Health',
    'rs': 'Respiratory Care'
  };

  const planPrices = {
    'dm': 29, 'cv': 29, 'ca': 39, 'mh': 24, 'rs': 24
  };

  const handleCheckout = async () => {
    setLoading(true);
    try {
      // Actually call the API to save subscription
      await api.post('/subscribe', {
        tier: 'premium',
        disease_codes: [planId.toUpperCase()]
      });
      
      // Update local store
      updateUser({ 
        subscription: 'premium', 
        subscribed_diseases: [planId.toUpperCase()] 
      });

      navigate('/app');
    } catch (e) {
      console.error("Checkout failed:", e);
      alert("Subscription failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FDFBF7] text-[#1E293B] py-20 px-6 font-sans">
      <div className="max-w-5xl mx-auto grid md:grid-cols-[1fr,380px] gap-12">
        
        {/* Left Column: Form */}
        <div className="space-y-12">
          <div>
            <h1 className="text-4xl font-black text-[#0F172A] mb-2 tracking-tight">Complete your subscription</h1>
            <p className="text-gray-500 font-medium">7-day free trial. Cancel anytime. No commitment.</p>
          </div>

          <div className="space-y-8">
            <section>
              <h3 className="text-sm font-black uppercase tracking-widest text-gray-400 mb-6">Account Information</h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="space-y-2">
                  <label className="text-xs font-black uppercase tracking-wider text-[#0F172A]">First Name</label>
                  <input type="text" defaultValue="María" className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-white focus:border-orange-500 outline-none transition-all font-medium" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-black uppercase tracking-wider text-[#0F172A]">Last Name</label>
                  <input type="text" defaultValue="González" className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-white focus:border-orange-500 outline-none transition-all font-medium" />
                </div>
              </div>
              <div className="space-y-2 mb-4">
                <label className="text-xs font-black uppercase tracking-wider text-[#0F172A]">Email Address</label>
                <input type="email" defaultValue="maria.gonzalez@email.com" className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-white focus:border-orange-500 outline-none transition-all font-medium" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-black uppercase tracking-wider text-[#0F172A]">Country</label>
                  <select className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-white focus:border-orange-500 outline-none transition-all font-medium appearance-none">
                    <option>Mexico</option>
                    <option>Brazil</option>
                    <option>Colombia</option>
                    <option>USA</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-black uppercase tracking-wider text-[#0F172A]">Language</label>
                  <select className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-white focus:border-orange-500 outline-none transition-all font-medium appearance-none">
                    <option>Spanish</option>
                    <option>Portuguese</option>
                    <option>English</option>
                  </select>
                </div>
              </div>
            </section>

            <section>
              <h3 className="text-sm font-black uppercase tracking-widest text-gray-400 mb-6">Payment details</h3>
              <div className="p-6 rounded-2xl border border-gray-200 bg-white space-y-4">
                <div className="flex items-center gap-4 p-4 rounded-xl bg-gray-50 border border-gray-100">
                  <CreditCard className="text-gray-400" />
                  <input type="text" defaultValue="4242 4242 4242 4242" className="bg-transparent outline-none font-mono text-sm flex-1" />
                  <div className="text-xs font-bold text-gray-400">MM/YY CVC</div>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-gray-400 font-bold uppercase tracking-widest px-2">
                  <Lock size={12} /> Encrypted & Secure Payment
                </div>
              </div>
            </section>
          </div>
        </div>

        {/* Right Column: Summary */}
        <div className="space-y-6">
          <div className="p-8 rounded-3xl bg-white border border-gray-100 shadow-xl shadow-gray-200/50 space-y-8">
            <h3 className="text-lg font-black text-[#0F172A]">Order summary</h3>
            
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-orange-50 flex items-center justify-center text-2xl">
                {planId === 'ca' ? '🎗️' : planId === 'dm' ? '💧' : planId === 'cv' ? '❤️' : planId === 'mh' ? '🧠' : '🫁'}
              </div>
              <div className="flex-1">
                <div className="font-bold text-sm">{planNames[planId]}</div>
                <div className="text-xs text-gray-400 font-medium tracking-tight">Active for 1 patient</div>
              </div>
              <div className="font-bold text-sm">${planPrices[planId]}/mo</div>
            </div>

            <div className="space-y-4 pt-6 border-t border-gray-50">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400 font-medium">Subtotal</span>
                <span className="font-bold">${planPrices[planId]}/mo</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400 font-medium">Trial period</span>
                <span className="text-green-600 font-bold">Free (7 days)</span>
              </div>
              <div className="flex justify-between items-end pt-4 border-t border-gray-100">
                <span className="text-lg font-black text-[#0F172A]">Total after trial</span>
                <span className="text-2xl font-black text-[#0F172A]">${planPrices[planId]}/mo</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-green-50 border border-green-100 flex gap-3">
              <CheckCircle2 className="text-green-600 shrink-0" size={20} />
              <div className="text-xs text-green-800 leading-relaxed">
                <b className="block mb-0.5">7-day free trial included</b>
                Your card will not be charged until your trial ends.
              </div>
            </div>

            <button 
              onClick={handleCheckout}
              disabled={loading}
              className="w-full py-5 rounded-2xl bg-[#0F172A] text-white font-black text-sm uppercase tracking-[0.2em] shadow-xl shadow-navy-900/20 hover:-translate-y-1 transition-all disabled:opacity-50"
            >
              {loading ? 'Processing...' : 'Start My Free Trial'}
            </button>

            <div className="text-center text-[10px] text-gray-400 font-bold uppercase tracking-widest">
              Secured by Stripe · AES-256 encrypted
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
