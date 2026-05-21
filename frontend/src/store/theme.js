import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useThemeStore = create(
  persist(
    (set) => ({
      currentTheme: 'black-pink',
      setTheme: (theme) => set({ currentTheme: theme }),
    }),
    {
      name: 'prism-theme',
    }
  )
);
