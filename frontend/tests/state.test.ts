import { act, renderHook } from '@testing-library/react'
import { useThemeStore } from '@/stores/themeStore'
import { useReducedMotion } from '@/hooks/useReducedMotion'
import { useCountUp } from '@/animations/gsap/useCountUp'
import { loginSchema } from '@/pages/auth/LoginPage'
import { mockMatchMedia } from './setup'

describe('theme store', () => {
  it('toggles the dark class on <html> and persists the choice', () => {
    act(() => useThemeStore.getState().setTheme('light'))
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    act(() => useThemeStore.getState().toggle())
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('procurehub-theme')).toBe('dark')
    act(() => useThemeStore.getState().setTheme('light'))
  })
})

describe('reduced motion', () => {
  it('reports the user preference', () => {
    mockMatchMedia(true)
    expect(renderHook(() => useReducedMotion()).result.current).toBe(true)
    mockMatchMedia(false)
    expect(renderHook(() => useReducedMotion()).result.current).toBe(false)
  })
  it('count-up returns the final value immediately when motion is reduced', () => {
    mockMatchMedia(true)
    expect(renderHook(() => useCountUp(42)).result.current).toBe(42)
    mockMatchMedia(false)
  })
})

describe('login schema', () => {
  it('rejects bad email and short password, accepts valid input', () => {
    expect(loginSchema.safeParse({ email: 'nope', password: 'short' }).success).toBe(false)
    expect(loginSchema.safeParse({ email: 'a@b.co', password: 'longenough' }).success).toBe(true)
  })
})
