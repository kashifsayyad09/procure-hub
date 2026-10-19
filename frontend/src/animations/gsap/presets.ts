import { gsap } from './index'

/** Staggered entrance for every matching child. Call inside useGsap. */
export function staggerIn(targets: gsap.TweenTarget, opts: { y?: number; stagger?: number; delay?: number } = {}) {
  return gsap.from(targets, {
    opacity: 0,
    y: opts.y ?? 18,
    duration: 0.6,
    ease: 'power3.out',
    stagger: opts.stagger ?? 0.07,
    delay: opts.delay ?? 0,
    clearProps: 'transform,opacity',
  })
}

/** Reveal each target as it scrolls into view. Call inside useGsap. */
export function revealOnScroll(targets: Element[]) {
  targets.forEach((el) =>
    gsap.from(el, {
      opacity: 0,
      y: 28,
      duration: 0.7,
      ease: 'power3.out',
      clearProps: 'transform,opacity',
      scrollTrigger: { trigger: el, start: 'top 85%', once: true },
    }),
  )
}
