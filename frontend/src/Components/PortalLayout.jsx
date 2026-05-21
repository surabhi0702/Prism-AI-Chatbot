import React from 'react';
import { useLocation } from 'react-router-dom';
import UnifiedNav from './UnifiedNav';
import { useDeviceStore } from '../store/device';

export default function PortalLayout({ children }) {
  const location = useLocation();
  const { currentDevice } = useDeviceStore();
  
  const isPatientRoute = location.pathname.startsWith('/app') || 
                         location.pathname.startsWith('/plans') || 
                         location.pathname.startsWith('/checkout') || 
                         location.pathname.startsWith('/patient') || 
                         location.pathname.startsWith('/dashboard');
                         
  const isHome = location.pathname === '/';
  const isApp = location.pathname.startsWith('/app');
  const isSimulationEnabled = isHome;
  const isLanding = isHome || location.pathname === '/patient';
  const isAdmin = location.pathname.startsWith('/admin');

  // Device dimensions
  const deviceWidths = {
    desktop: '100%',
    tablet: '768px',
    mobile: '390px'
  };

  const currentWidth = isSimulationEnabled ? deviceWidths[currentDevice] : '100%';
  const isSimulated = isSimulationEnabled && currentDevice !== 'desktop';

  return (
    <div className={`min-h-screen transition-all duration-500 bg-[var(--bg-main)] text-[var(--text-main)] ${isPatientRoute ? 'pw' : ''} flex flex-col items-center justify-center`}>

      {/* Device Simulation Wrapper */}
      <div 
        className={`transition-all duration-500 relative flex flex-col bg-[var(--bg-main)]
          ${isSimulated ? 'shadow-[0_0_100px_rgba(0,0,0,0.5)] border-[8px] border-[#1a1c24] my-8 rounded-[3rem] overflow-hidden' : 'w-full'}`}
        style={{ 
          width: currentWidth,
          height: (isSimulated || isApp) ? (isSimulated ? 'calc(100vh - 64px)' : '100vh') : 'auto',
          minHeight: (isSimulated || isApp) ? '0' : '100vh',
          transform: isSimulated ? 'translate3d(0,0,0)' : 'none' // Containing block for fixed elements
        }}
      >
        {!isLanding && <UnifiedNav />}
        
        <main className={`flex-1 transition-all duration-500 ${isApp ? 'overflow-hidden' : 'overflow-y-auto overflow-x-hidden'} ${!isLanding ? 'pt-16' : ''}`}>
          {children}
        </main>

        {/* Mobile Home Indicator */}
        {isSimulated && currentDevice === 'mobile' && (
          <div className="absolute bottom-2 left-1/2 -translate-x-1/2 w-32 h-1.5 bg-white/20 rounded-full z-[110]" />
        )}
      </div>

      {/* Background decoration (visible only when simulated) */}
      {isSimulated && (
        <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-[var(--accent)]/5 blur-[120px] rounded-full" />
          <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-blue-600/5 blur-[120px] rounded-full" />
        </div>
      )}
    </div>
  );
}
