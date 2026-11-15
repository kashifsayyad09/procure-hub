/** Exact decimal arithmetic for showing a quotation total while the vendor types. Display only: the server computes the real totals. */
const parts = (v: string): { n: bigint; scale: number } | null => {
  const m = /^(\d{1,10})(?:\.(\d{1,4}))?$/.exec(v.trim())
  if (!m) return null
  const frac = m[2] ?? ''
  return { n: BigInt(m[1] + frac), scale: frac.length }
}
const qtyParts = (v: string): { n: bigint; scale: number } => {
  const [i, f = ''] = v.split('.')
  return { n: BigInt(i + f), scale: f.length }
}

/** quantity x unit price in cents, rounded half up, or null if the price is not a valid number. */
export function lineCents(quantity: string, price: string): bigint | null {
  const p = parts(price)
  if (!p) return null
  const q = qtyParts(quantity)
  const scale = BigInt(10) ** BigInt(q.scale + p.scale)
  const cents = (q.n * p.n * 100n * 2n + scale) / (scale * 2n) // half up
  return cents
}
export const centsText = (c: bigint): string => `${c / 100n}.${(c % 100n).toString().padStart(2, '0')}`
export const isPrice = (v: string): boolean => parts(v) !== null
