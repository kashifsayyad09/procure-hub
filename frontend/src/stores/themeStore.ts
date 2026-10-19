import { create } from 'zustand'

export type Theme = 'light' | 'dark'
const KEY = 'procurehub-theme'

function readStored(): Theme {
  try {
    return localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

function apply(theme: Theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

interface ThemeState {
  theme: Theme
  setTheme: (t: Theme) => void
  toggle: () => void
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: readStored(),
  setTheme: (theme) => {
    try { localStorage.setItem(KEY, theme) } catch { /* storage unavailable */ }
    apply(theme)
    set({ theme })
  },
  toggle: () => get().setTheme(get().theme === 'dark' ? 'light' : 'dark'),
}))

export const initTheme = () => apply(useThemeStore.getState().theme)
