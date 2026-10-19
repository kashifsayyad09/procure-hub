import { lazy, Suspense, useState } from 'react'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { useThemeStore } from '@/stores/themeStore'

// three.js and react-three-fiber load only when a page with a backdrop is opened.
const ParticleNetwork = lazy(() => import('./ParticleNetwork'))

function canUseWebGL(): boolean {
  try {
    const c = document.createElement('canvas')
    return !!(c.getContext('webgl2') || c.getContext('webgl'))
  } catch {
    return false
  }
}

/** Static stand-in: used for reduced motion, missing WebGL, and while the 3D chunk loads. */
export function StaticBackdrop() {
  const nodes: [number, number][] = [[12, 20], [28, 62], [40, 30], [55, 70], [66, 24], [78, 56], [90, 34], [48, 48]]
  const edges: [number, number][] = [[0, 2], [2, 4], [4, 6], [1, 2], [2, 7], [7, 3], [7, 5], [5, 6], [3, 5]]
  return (
    <svg viewBox="0 0 100 80" preserveAspectRatio="xMidYMid slice" className="h-full w-full text-ink" aria-hidden focusable="false">
      {edges.map(([a, b]) => (
        <line key={`${a}-${b}`} x1={nodes[a][0]} y1={nodes[a][1]} x2={nodes[b][0]} y2={nodes[b][1]} stroke="currentColor" strokeOpacity="0.2" strokeWidth="0.25" />
      ))}
      {nodes.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="0.9" fill="#e3b210" />)}
    </svg>
  )
}

/** Decorative only (aria-hidden). Never place behind forms or tables. */
export function SceneBackdrop({ className = '' }: { className?: string }) {
  const reduced = useReducedMotion()
  const dark = useThemeStore((s) => s.theme) === 'dark'
  const [webgl] = useState(canUseWebGL)
  return (
    <div aria-hidden className={`pointer-events-none ${className}`}>
      {reduced || !webgl ? (
        <StaticBackdrop />
      ) : (
        <Suspense fallback={<StaticBackdrop />}>
          <ParticleNetwork nodeColor="#e3b210" lineColor={dark ? '#f8f8f8' : '#1a1a19'} />
        </Suspense>
      )}
    </div>
  )
}
