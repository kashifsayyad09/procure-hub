import type { Currency } from './types'

export const money = (amount: string | number, currency: Currency | string): string =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number(amount))

export const dateOnly = (iso: string | null): string =>
  iso ? new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Not set'

/** The API returns naive UTC timestamps, so mark them as UTC before formatting in the viewer's time zone. */
export const dateTime = (iso: string): string =>
  new Date(iso.endsWith('Z') ? iso : `${iso}Z`).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' })

export const monthLabel = (ym: string): string => {
  const [y, m] = ym.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString('en-IN', { month: 'short' })
}

export const fileSize = (bytes: number): string => (bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`)

// ---- exact preview arithmetic (the server is authoritative; this only previews) ---------------------
const scaled = (s: string, decimals: number): bigint | null => {
  const m = /^(\d+)(?:\.(\d+))?$/.exec(s.trim())
  if (!m) return null
  const frac = m[2] ?? ''
  if (frac.length > decimals) return null
  return BigInt(m[1] + frac.padEnd(decimals, '0'))
}

/** Line total in cents, rounded half up like the server, or null if either value is not a valid number. */
export function lineTotalCents(quantity: string, unitPrice: string): bigint | null {
  const q = scaled(quantity, 3)
  const p = scaled(unitPrice, 2)
  if (q === null || p === null) return null
  return (q * p + 500n) / 1000n
}

export const centsToString = (cents: bigint): string => `${cents / 100n}.${(cents % 100n).toString().padStart(2, '0')}`
