import React from 'react';
import { Monitor, Tablet, Smartphone } from 'lucide-react';
import { useDeviceStore } from '../store/device';

export default function DeviceSwitcher() {
  const { currentDevice, setDevice } = useDeviceStore();

  const devices = [
    { id: 'desktop', icon: Monitor, label: 'Desktop', width: '100%' },
    { id: 'tablet', icon: Tablet, label: 'iPad / Tablet', width: '768px' },
    { id: 'mobile', icon: Smartphone, label: 'Mobile Phone', width: '390px' },
  ];

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 backdrop-blur-xl shadow-2xl">
      {devices.map((device) => {
        const Icon = device.icon;
        const isActive = currentDevice === device.id;
        return (
          <button
            key={device.id}
            onClick={() => setDevice(device.id)}
            className={`group relative p-2 rounded-full transition-all duration-300 flex items-center justify-center
              ${isActive ? 'bg-[var(--accent)] text-white shadow-lg shadow-[var(--accent)]/30' : 'text-[var(--text-dim)] hover:text-[var(--text-main)] hover:bg-white/5'}`}
            title={device.label}
          >
            <Icon size={18} />
            <div className="absolute -top-10 left-1/2 -translate-x-1/2 px-3 py-1 rounded-md bg-black text-white text-[9px] font-black opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none uppercase tracking-tighter z-50">
              {device.label}
            </div>
            {isActive && (
               <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-white" />
            )}
          </button>
        );
      })}
    </div>
  );
}
