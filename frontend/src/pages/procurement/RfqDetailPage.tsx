import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, rfqsApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { dateOnly, dateTime, money } from '@/features/purchase-requests/format'
import { RfqActions } from '@/features/rfqs/RfqActions'
import { QuotationStatusBadge, RfqStatusBadge } from '@/features/rfqs/RfqStatusBadge'
import { INVITATION_LABEL, RFQ_ACTION_LABEL, timeLeft, unitPrice } from '@/features/rfqs/labels'
import { useState } from 'react'

export default function RfqDetailPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const { data: rfq, isLoading, isError, error: loadError, refetch } = useQuery({ queryKey: ['rfq', id], queryFn: () => rfqsApi.get(id) })
  const quotes = useQuery({ queryKey: ['rfq', id, 'quotations'], queryFn: () => rfqsApi.quotations(id), enabled: !!rfq && rfq.status !== 'draft' })
  const withdraw = useMutation({
    mutationFn: (invId: string) => rfqsApi.withdrawInvitation(id, invId),
    onSuccess: () => { setError(''); void qc.invalidateQueries({ queryKey: ['rfq'] }) },
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Something went wrong. Try again.'),
  })
  if (isLoading) return <div role="status" aria-busy="true"><span className="sr-only">Loading RFQ</span><Skeleton className="h-64 w-full rounded-card" /></div>
  if (isError || !rfq) return <ErrorState title="Could not open this RFQ" description={loadError instanceof ApiError ? loadError.message : 'Try again in a moment.'} onRetry={() => void refetch()} />
  const live = rfq.invitations.filter((i) => i.status !== 'withdrawn')
  const canWithdraw = ['draft', 'issued', 'closed'].includes(rfq.status)

  return (
    <div className="flex flex-col gap-u12">
      <header>
        <Link to="/app/procurement/rfqs" className="text-sm text-muted underline-offset-4 hover:underline">Back to RFQs</Link>
        <div className="mt-u3 flex flex-wrap items-center gap-u5"><h1 className="display-lg">{rfq.title}</h1><RfqStatusBadge status={rfq.status} /></div>
        <p className="mt-u4 text-muted">{rfq.number}, from {rfq.purchase_request_number}{rfq.department ? `, ${rfq.department}` : ''}</p>
      </header>
      <RfqActions rfq={rfq} />
      {rfq.status === 'cancelled' && rfq.cancel_reason && <p role="note" className="rounded-ctl bg-bad/15 p-u7 text-bad">Cancelled: {rfq.cancel_reason}</p>}

      {rfq.selection && (
        <Card aria-label="Award" className="flex flex-col gap-u4">
          <h2 className="text-2xl">Awarded to {rfq.selection.vendor_name}</h2>
          <p>{money(rfq.selection.total_amount, rfq.selection.currency)}. Selected by {rfq.selection.selected_by_name} on {dateTime(rfq.selection.selected_at)}.</p>
          <p className="text-muted">{rfq.selection.justification}</p>
          {rfq.selection.acknowledged_missing_items && <p className="text-sm text-muted">This quotation did not price every item, and that was accepted.</p>}
        </Card>
      )}

      <Card className="flex flex-col gap-u8">
        <h2 className="text-2xl">Overview</h2>
        <dl className="grid gap-u6 sm:grid-cols-2">
          <div><dt className="text-sm text-muted">Quotation deadline</dt><dd>{dateTime(rfq.deadline)}{rfq.status === 'issued' && <span className="block text-sm text-muted">{timeLeft(rfq.deadline)}</span>}</dd></div>
          <div><dt className="text-sm text-muted">Budget (internal)</dt><dd>{money(rfq.budget_amount, rfq.currency)}</dd></div>
          <div><dt className="text-sm text-muted">Needed by</dt><dd>{rfq.needed_by ? dateOnly(rfq.needed_by) : 'Not set'}</dd></div>
          <div><dt className="text-sm text-muted">Created by</dt><dd>{rfq.created_by_name}</dd></div>
          <div className="sm:col-span-2"><dt className="text-sm text-muted">Description</dt><dd className="whitespace-pre-wrap">{rfq.description || 'None'}</dd></div>
          <div className="sm:col-span-2"><dt className="text-sm text-muted">Requirements</dt><dd className="whitespace-pre-wrap">{rfq.requirements || 'None'}</dd></div>
        </dl>
      </Card>

      <Card className="flex flex-col gap-u6">
        <h2 className="text-2xl">Items</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] border-collapse text-left">
            <caption className="sr-only">RFQ items</caption>
            <thead><tr className="border-b border-line text-sm text-muted"><th scope="col" className="px-u4 py-u3 font-medium">#</th><th scope="col" className="px-u4 py-u3 font-medium">Item</th>
              <th scope="col" className="px-u4 py-u3 font-medium">Quantity</th><th scope="col" className="px-u4 py-u3 font-medium">Estimate per unit</th></tr></thead>
            <tbody>{rfq.items.map((i) => (
              <tr key={i.id} className="border-b border-line last:border-0"><td className="px-u4 py-u3">{i.line_no}</td>
                <td className="px-u4 py-u3">{i.description}{i.specification && <span className="block text-sm text-muted">{i.specification}</span>}</td>
                <td className="px-u4 py-u3">{i.quantity.replace(/\.?0+$/, '')} {i.unit}</td><td className="px-u4 py-u3">{money(i.estimated_unit_price ?? '0', rfq.currency)}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </Card>

      <Card className="flex flex-col gap-u6" aria-label="Invited vendors">
        <h2 className="text-2xl">Invited vendors</h2>
        {live.length === 0 ? <p className="text-muted">No vendors invited yet. Use Invite vendors, then issue the RFQ.</p> : (
          <ul className="flex flex-col gap-u4">
            {live.map((i) => (
              <li key={i.id} className="flex flex-wrap items-center justify-between gap-u5 rounded-ctl border border-line p-u7">
                <div><p className="font-medium">{i.vendor_name}</p><p className="text-sm text-muted">{i.vendor_number}, {INVITATION_LABEL[i.status]}{i.sent_at ? `, sent ${dateTime(i.sent_at)}` : ', not sent yet'}</p></div>
                <div className="flex items-center gap-u4">
                  {i.quotation_status && <QuotationStatusBadge status={i.quotation_status} />}
                  {canWithdraw && i.status === 'invited' && i.quotation_status !== 'submitted' && i.quotation_status !== 'selected' && i.quotation_status !== 'not_selected' && (
                    <Button variant="ghost" size="sm" aria-label={`Withdraw invitation to ${i.vendor_name}`} loading={withdraw.isPending && withdraw.variables === i.id} onClick={() => withdraw.mutate(i.id)}>Withdraw</Button>)}
                </div>
              </li>
            ))}
          </ul>
        )}
        {error && <p role="alert" className="text-bad">{error}</p>}
      </Card>

      {rfq.status !== 'draft' && (
        <Card className="flex flex-col gap-u6" aria-label="Quotations">
          <h2 className="text-2xl">Quotations</h2>
          {!rfq.quotations_open && <p role="note" className="rounded-ctl bg-accent/20 p-u7">Prices are sealed until the deadline passes or you close the RFQ, so every vendor is judged on the same footing. You can see who has responded.</p>}
          {quotes.isLoading ? <p role="status">Loading quotations</p> : quotes.isError ? <p role="alert" className="text-bad">Could not load quotations.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[34rem] border-collapse text-left">
                <caption className="sr-only">Quotations by vendor</caption>
                <thead><tr className="border-b border-line text-sm text-muted"><th scope="col" className="px-u4 py-u3 font-medium">Vendor</th><th scope="col" className="px-u4 py-u3 font-medium">Invitation</th>
                  <th scope="col" className="px-u4 py-u3 font-medium">Quotation</th><th scope="col" className="px-u4 py-u3 font-medium">Total</th><th scope="col" className="px-u4 py-u3 font-medium">Lead time</th></tr></thead>
                <tbody>{quotes.data?.rows.map((r) => (
                  <tr key={r.vendor_id} className="border-b border-line last:border-0"><td className="px-u4 py-u3">{r.vendor_name}</td><td className="px-u4 py-u3">{INVITATION_LABEL[r.invitation_status]}</td>
                    <td className="px-u4 py-u3">{r.status ? <QuotationStatusBadge status={r.status} /> : <span className="text-muted">None yet</span>}</td>
                    <td className="px-u4 py-u3">{r.total_amount ? money(unitPrice(r.total_amount), r.currency ?? rfq.currency) : <span className="text-muted">{r.status && r.status !== 'draft' ? 'Sealed' : 'Not available'}</span>}</td>
                    <td className="px-u4 py-u3">{r.lead_time_days ? `${r.lead_time_days} days` : <span className="text-muted">{r.status && r.status !== 'draft' ? 'Sealed' : 'Not available'}</span>}</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      <Card className="flex flex-col gap-u6">
        <h2 className="text-2xl">History</h2>
        <ol className="flex flex-col gap-u6">{[...rfq.history].reverse().map((h) => (
          <li key={h.id} className="border-l-2 border-line pl-u7"><p className="font-medium">{RFQ_ACTION_LABEL[h.action] ?? h.action}</p><p className="text-sm text-muted">{h.actor_name}, {dateTime(h.created_at)}</p>{h.note && <p className="mt-u2">{h.note}</p>}</li>
        ))}</ol>
      </Card>
    </div>
  )
}
