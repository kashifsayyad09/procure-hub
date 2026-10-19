import { useEffect, useState } from 'react'
import { gsap } from './index'
import { prefersReducedMotion } from '@/hooks/useReducedMotion'

/** Animates a number from 0 to `target`. Returns the final value immediately under reduced motion. */
export function useCountUp(target: number, duration = 1.1): number {
  const [value, setValue] = useState(() => (prefersReducedMotion() ? target : 0))
  useEffect(() => {
    if (prefersReducedMotion()) {
      setValue(target)
      return
    }
    const state = { v: 0 }
    const tween = gsap.to(state, {
      v: target,
      duration,
      ease: 'power2.out',
      onUpdate: () => setValue(Math.round(state.v)),
    })
    return () => {
      tween.kill()
    }
  }, [target, duration])
  return value
}
