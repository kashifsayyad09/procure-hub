import { useThemeStore } from '@/stores/themeStore'

/** Recharts writes colours as SVG attributes, which cannot read CSS variables, so resolve them per theme. */
export function useChartColors() {
  const dark = useThemeStore((s) => s.theme) === 'dark'
  return {
    accent: '#e3b210',
    accent2: '#dfba34',
    ink: dark ? '#f8f8f8' : '#1a1a19',
    muted: dark ? '#b0ada4' : '#6c6962',
    grid: dark ? '#3e3d38' : '#e6e3dc',
    surface: dark ? '#242422' : '#ffffff',
  }
}
