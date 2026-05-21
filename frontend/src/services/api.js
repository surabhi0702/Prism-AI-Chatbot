import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('prism-auth')
      localStorage.removeItem('prism-auth-admin')
      const adminRoute = window.location.pathname.startsWith('/admin')
      window.location.href = adminRoute ? '/login?role=admin' : '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// Disease colors
export const DISEASE_COLORS = {
  CA: { color: '#A78BFA', bg: 'rgba(167,139,250,0.12)', icon: '🎗', name: 'Cancer Care' },
  DM: { color: '#60A5FA', bg: 'rgba(96,165,250,0.12)',  icon: '🩺', name: 'Diabetes' },
  CV: { color: '#F472B6', bg: 'rgba(244,114,182,0.12)', icon: '❤️', name: 'Cardiovascular' },
  MH: { color: '#34D399', bg: 'rgba(52,211,153,0.12)',  icon: '🧠', name: 'Mental Illness' },
  RS: { color: '#F5C842', bg: 'rgba(245,200,66,0.12)',  icon: '🫁', name: 'Respiratory' },
}

export const LANG_OPTIONS = [
  { code: 'en', name: 'English',  flag: '🇺🇸' },
  { code: 'hi', name: 'हिंदी',    flag: '🇮🇳' },
  { code: 'te', name: 'తెలుగు',  flag: '🇮🇳' },
  { code: 'es', name: 'Español',  flag: '🇲🇽' },
  { code: 'pa', name: 'ਪੰਜਾਬੀ',  flag: '🇮🇳' },
]
