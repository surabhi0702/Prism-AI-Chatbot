import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useDeviceStore = create(
  persist(
    (set) => ({
      currentDevice: 'desktop', // 'desktop', 'tablet', 'mobile'
      setDevice: (device) => set({ currentDevice: device }),
    }),
    {
      name: 'prism-device-storage',
    }
  )
)
