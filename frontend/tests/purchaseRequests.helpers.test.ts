import { centsToString, dateOnly, fileSize, lineTotalCents, money } from '@/features/purchase-requests/format'
import { timelineFor } from '@/features/purchase-requests/timeline'
import { submitProblems, totalCents, formSchema, type FormValues } from '@/pages/employee/RequestFormPage'
import { ApiError, purchaseRequestsApi } from '@/services/api'
import { mockApi } from './helpers'

describe('exact money arithmetic in the preview', () => {
  it('matches the server: half-up rounding, no floating point drift', () => {
    expect(centsToString(lineTotalCents('2.5', '19.99')!)).toBe('49.98') // 49.975 rounds up, 49.97 would be a float error
    expect(centsToString(lineTotalCents('3', '0.10')!)).toBe('0.30')
    expect(centsToString(lineTotalCents('0.333', '10.00')!)).toBe('3.33')
    expect(centsToString(lineTotalCents('1000000', '100000000')!)).toBe('100000000000000.00') // beyond Number's safe range, still exact
  })
  it('refuses values the server would refuse', () => {
    for (const [q, p] of [['', '1'], ['1', ''], ['abc', '1'], ['1', '1.234'], ['1.0001', '1'], ['-1', '1'], ['1e3', '1']]) expect(lineTotalCents(q, p)).toBeNull()
  })
  it('formats currency and dates for readers', () => {
    expect(money('99002.00', 'INR')).toMatch(/99,002/)
    expect(dateOnly('2026-03-05')).toMatch(/5 Mar 2026/)
    expect(dateOnly(null)).toBe('Not set')
    expect(fileSize(500)).toBe('1 KB')
    expect(fileSize(3 * 1024 * 1024)).toBe('3.0 MB')
  })
})

const values = (over: Partial<FormValues> = {}): FormValues => ({
  title: 'Laptops', department: 'Design', priority: 'normal', needed_by: '', currency: 'INR', justification: 'Needed for work',
  items: [{ description: 'Laptop', quantity: '2', unit: 'each', unit_price: '50000', notes: '' }], ...over,
})

describe('submit checks', () => {
  it('a complete request has no problems', () => expect(submitProblems(values())).toEqual([]))
  it('reports each missing piece in plain language', () => {
    expect(submitProblems(values({ department: ' ', justification: '', items: [] }))).toEqual(['Enter the department.', 'Explain why this purchase is needed.', 'Add at least one item.'])
    expect(submitProblems(values({ items: [{ description: 'Free', quantity: '1', unit: 'each', unit_price: '0', notes: '' }] }))).toEqual(['The total must be greater than zero.'])
  })
  it('totals only valid lines', () => {
    expect(totalCents(values().items)).toBe(10000000n)
    expect(totalCents([{ description: 'x', quantity: 'bad', unit: 'each', unit_price: '5', notes: '' }])).toBe(0n)
  })
})

describe('form rules mirror the server', () => {
  const bad = (v: Partial<FormValues>) => !formSchema.safeParse(values(v)).success
  it('rejects short titles, bad numbers and past dates', () => {
    expect(bad({ title: 'ab' })).toBe(true)
    expect(bad({ needed_by: '2000-01-01' })).toBe(true)
    expect(bad({ items: [{ description: 'x', quantity: '0', unit: 'each', unit_price: '1', notes: '' }] })).toBe(true)
    expect(bad({ items: [{ description: 'x', quantity: '1', unit: 'each', unit_price: '1.999', notes: '' }] })).toBe(true)
    expect(bad({ items: Array.from({ length: 101 }, () => ({ description: 'x', quantity: '1', unit: 'each', unit_price: '1', notes: '' })) })).toBe(true)
    expect(bad({})).toBe(false)
  })
})

describe('timeline', () => {
  it('shows where a request is on its way to delivery', () => {
    const states = (status: Parameters<typeof timelineFor>[0]['status']) => timelineFor({ status, submitted_at: '2026-03-01T10:00:00' }).map((s) => s.state)
    expect(states('draft')).toEqual(['current', 'pending', 'pending', 'pending'])
    expect(states('submitted')).toEqual(['done', 'current', 'pending', 'pending'])
    expect(states('approved')).toEqual(['done', 'done', 'current', 'pending'])
    expect(states('rejected')).toEqual(['done', 'done'])
    expect(states('cancelled')).toEqual(['done', 'done'])
  })
})

describe('API client for purchase requests', () => {
  it('builds the query string and omits empty filters', async () => {
    const { calls } = mockApi(() => ({ body: { items: [], total: 0, page: 1, page_size: 10 } }))
    await purchaseRequestsApi.list({ page: 2, page_size: 10, q: 'desk', status: 'submitted', priority: '', sort: 'total_amount', order: 'desc' })
    expect(calls[0].path).toBe('/purchase-requests?page=2&page_size=10&q=desk&status=submitted&sort=total_amount&order=desc')
  })
  it('names the field in validation errors', async () => {
    mockApi(() => ({ status: 422, body: { detail: [{ loc: ['body', 'items', 0, 'quantity'], msg: 'Input should be greater than 0' }, { loc: ['body', 'title'], msg: 'Too short' }] } }))
    await expect(purchaseRequestsApi.create({ title: 'x', justification: '', department: '', priority: 'normal', needed_by: null, currency: 'INR', items: [] }))
      .rejects.toMatchObject({ status: 422, message: 'quantity: Input should be greater than 0 title: Too short' })
    expect(ApiError).toBeDefined()
  })
})
