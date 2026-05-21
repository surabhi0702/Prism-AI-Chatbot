// src/store/auth.js
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import api from '../services/api'

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user:  null,
      token: null,
      login: async (email, password) => {
        const { data } = await api.post('/auth/token', { email, password })
        api.defaults.headers.common['Authorization'] = `Bearer ${data.token}`
        set({ user: data.user, token: data.token })
        return { user: data.user, warning: data.warning }
      },
      register: async (email, name, password, country = 'USA') => {
        const { data } = await api.post('/auth/register', { email, name, password, country })
        api.defaults.headers.common['Authorization'] = `Bearer ${data.token}`
        set({ user: data.user, token: data.token })
        return data.user
      },
      logout: () => {
        delete api.defaults.headers.common['Authorization']
        set({ user: null, token: null })
      },
      updateUser: (updates) => set((s) => ({ user: { ...s.user, ...updates } })),
      hydrate: () => {
        const { token } = get()
        if (token) api.defaults.headers.common['Authorization'] = `Bearer ${token}`
      },
    }),
    { 
      name: import.meta.env.MODE === 'admin' ? 'prism-auth-admin' : 'prism-auth', 
      partialize: (s) => ({ token: s.token, user: s.user }) 
    }
  )
)
