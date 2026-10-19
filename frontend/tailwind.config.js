/** Design tokens derived from Design.md (Plnty). Colours are CSS variables so light/dark share one config. */
const rgb = (v) => `rgb(var(--${v}) / <alpha-value>)`
const UNIT = 2.1 // Design.md base spacing unit (px)
const units = Object.fromEntries(
  Array.from({ length: 60 }, (_, i) => [`u${i + 1}`, `${+(UNIT * (i + 1)).toFixed(1)}px`]),
)

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: rgb('bg'), surface: rgb('surface'), panel: rgb('panel'), line: rgb('line'),
        ink: rgb('ink'), muted: rgb('muted'), pill: rgb('pill'),
        accent: rgb('accent'), accent2: rgb('accent2'),
        violet: rgb('violet'), 'violet-ink': rgb('violet-ink'),
        ok: rgb('ok'), bad: rgb('bad'),
        'on-accent': '#1a1a19',
      },
      spacing: units,
      borderRadius: { card: '24px', ctl: '16px', btn: '20px' },
      fontFamily: {
        display: ['"KMR Apparat"', '"Helvetica Neue"', 'Arial', 'system-ui', 'sans-serif'],
        body: ['"Suisse Intl"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'system-ui', 'sans-serif'],
      },
      boxShadow: { card: '0 1px 0 rgb(var(--ink) / .04), 0 16px 32px -20px rgb(var(--ink) / .18)' },
      letterSpacing: { display: '-0.04em' },
      transitionTimingFunction: { soft: 'cubic-bezier(.16,1,.3,1)' },
    },
  },
  plugins: [],
}
