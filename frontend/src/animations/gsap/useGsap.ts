import { useLayoutEffect, type DependencyList, type RefObject } from 'react'
import { gsap } from './index'
import { prefersReducedMotion } from '@/hooks/useReducedMotion'

/**
 * Runs `setup` inside a gsap.context scoped to `scope`, and reverts every tween and
 * ScrollTrigger it created on unmount. `setup` is skipped when the user prefers reduced motion.
 */
export function useGsap(
  scope: RefObject<HTMLElement | null>,
  setup: (ctx: gsap.Context) => void,
  deps: DependencyList = [],
) {
  useLayoutEffect(() => {
    if (!scope.current || prefersReducedMotion()) return
    const ctx = gsap.context((self) => setup(self), scope)
    return () => ctx.revert()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}
