import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Layout, Settings, Activity, Shield, Users, LogOut, ChevronRight } from 'lucide-react';
import { useAuthStore } from '../store/auth';

export default function UnifiedNav() {
  const { user, logout } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();
  
  const isAdmin = location.pathname.startsWith('/admin');
  const isPatient = location.pathname.startsWith('/app') || location.pathname.startsWith('/plans') || location.pathname.startsWith('/checkout') || location.pathname.startsWith('/patient') || location.pathname.startsWith('/dashboard');
  const isHome = location.pathname === '/';

  const navBg = 'bg-[var(--bg-card)]';
  const accentColor = 'text-[var(--accent)]';

  if (isHome && !user) return null; // Don't show nav on landing if not logged in

  return (
    <nav className={`fixed top-0 left-0 right-0 z-[100] h-16 border-b ${isAdmin ? 'border-gray-800' : 'border-white/10'} ${navBg} backdrop-blur-lg px-6 flex items-center justify-between`}>
      <div className="flex items-center gap-8">
        <Link to="/" className="flex items-center gap-2 group">
          <div className="w-8 h-8 rounded-lg bg-[var(--grad-primary)] flex items-center justify-center font-bold text-white shadow-lg transition-transform group-hover:scale-110">
            P
          </div>
          <span className="font-bold text-xl tracking-tight text-white">PRISM</span>
        </Link>

        {/* Dynamic Links */}
        <div className="hidden md:flex items-center gap-6">
          {isAdmin ? (
            <>
              <Link to="/admin" className="text-sm font-medium text-gray-300 hover:text-white transition-colors">System Overview</Link>
              <Link to="/admin/agents" className="text-sm font-medium text-gray-300 hover:text-white transition-colors">Agent Registry</Link>
              <Link to="/admin/analytics" className="text-sm font-medium text-gray-300 hover:text-white transition-colors">Analytics</Link>
            </>
          ) : (
            <>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Portal Switcher */}
        {user?.role === 'admin' && (
          <button 
            onClick={() => navigate(isAdmin ? '/app' : '/admin')}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-full border border-[var(--accent)]/30 bg-[var(--accent)]/10 text-[var(--accent)] hover:bg-[var(--accent)]/20 text-xs font-semibold transition-all`}
          >
            {isAdmin ? '🏥 Patient Portal' : '⚙ Admin Console'}
          </button>
        )}

        <div className="h-6 w-px bg-white/10 mx-2" />

        <div className="flex items-center gap-3">
          <div className="flex flex-col items-end">
            <span className="text-xs font-bold text-white">{user?.name || 'Guest User'}</span>
            <span className={`text-[10px] font-mono ${isAdmin ? 'text-blue-400' : 'text-orange-400'} uppercase tracking-wider`}>
              {isAdmin ? 'Administrator' : 'Patient'}
            </span>
          </div>
          <button 
            onClick={logout}
            className="p-2 rounded-lg bg-white/5 text-gray-400 hover:text-white hover:bg-white/10 transition-all"
          >
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </nav>
  );
}
