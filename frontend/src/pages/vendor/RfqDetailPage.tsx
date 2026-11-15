import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, quotationsApi, rfqsApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { Modal } from '@/components/ui/Overlay'
import { dateOnly, dateTime, money } from '@/features/purchase-requests/format'
import { QuotationStatusBadge, RfqStatusBadge } from '@/features/rfqs/RfqStatusBadge'
import { INVITATION_LABEL, timeLeft, unitPrice } from '@/features/rfqs/labels'

const OUTCOME: Record<string, string> = { selected: 'Congratulations: your quotation was selected. The buyer will be in touch about the order.', not_selected: 'The buyer chose another supplier for this request. Thank you for quoting.' }

export default function VendorRfqDetailPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const [confirmDecline, setConfirmDecline] = useState(false)
  const [error, setError] = useState('')
  const { data: rfq, isLoading, isError, error: loadError, refetch } = useQuery({ queryKey: ['rfq', 'invited', 'one', id], queryFn: () => rfqsApi.invitedRfq(id), retry: false })
  const quote = useQuery({ queryKey: ['quotation', rfq?.quotation?.id], queryFn: () => quotationsApi.get(rfq!.quotation!.id), enabled: !!rfq?.quotation })
  const refresh = () => { void qc.invalidateQueries({ queryKey: ['rfq'] }); void qc.invalidateQueries({ queryKey: ['quotation'] }) }
  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : 'Something went wrong. Try again.')
  const decline = useMutation({ mutationFn: () => rfqsApi.decline(id), onSuccess: () => { setConfirmDecline(false); setError(''); refresh() }, onError: (e) => { setConfirmDecline(false); fail(e) } })
  const withdraw = useMutation({ mutationFn: () => quotationsApi.withdraw(rfq!.quotation!.id), onSuccess: () => { setError(''); refresh() }, onError: fail })

  if (isLoading) return <div role="status" aria-busy="true"><span className="sr-only">Loading RFQ</span><Skeleton className="h-64 w-full rounded-card" /></div>
  if (isError || !rfq) return <ErrorState title="Could not open this request" description={loadError instanceof ApiError ? loadError.message : 'Try again in a moment.'} onRetry={() => void refetch()} />
  const q = quote.data
  const outcome = rfq.quotation && OUTCOME[rfq.quotation.status]

  return (
    <div className="flex flex-col gap-u12">
      <header>
        <Link to="/app/vendor/rfqs" className="text-sm text-muted underline-offset-4 hover:underline">Back to requests</Link>
        <div className="mt-u3 flex flex-wrap items-center gap-u5"><h1 className="display-lg">{rfq.title}</h1><RfqStatusBadge status={rfq.status} /></div>
        <p className="mt-u4 text-muted">{rfq.number}, deadline {dateTime(rfq.deadline)}{rfq.status === 'issued' && !rfq.deadline_passed ? `, ${timeLeft(rfq.deadline)}` : ''}. Your invitation: {INVITATION_LABEL[rfq.invitation_status].toLowerCase()}.</p>
      </header>

      {outcome && <p role="note" className="rounded-ctl bg-accent/20 p-u7">{outcome}</p>}
      {rfq.blocked_reason && !outcome && <p role="status" className="rounded-ctl bg-bad/15 p-u7 text-bad">{rfq.blocked_reason}</p>}

      <Card className="flex flex-col gap-u6" aria-label="Your quotation">
        <h2 className="text-2xl">Your quotation</h2>
        {!rfq.quotation ? (
          <><p className="text-muted">{rfq.can_quote ? 'You have not started a quotation. You can save a draft and come back before the deadline.' : 'You did not send a quotation.'}</p>
            {rfq.can_quote && <div className="flex flex-wrap gap-u4"><Link to={`/app/vendor/rfqs/${rfq.id}/quote`}><Button>Start a quotation</Button></Link>
              {rfq.invitation_status === 'invited' && <Button variant="outline" onClick={() => setConfirmDecline(true)}>Decline to quote</Button>}</div>}</>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-u5"><QuotationStatusBadge status={rfq.quotation.status} /><span>{rfq.quotation.number}</span><span className="font-medium">{money(unitPrice(rfq.quotation.total_amount), rfq.quotation.currency)}</span></div>
            {q && q.status === 'draft' && q.problems.length > 0 && <ul className="list-disc pl-u10 text-muted" aria-label="Still needed before you can submit">{q.problems.map((p) => <li key={p}>{p}</li>)}</ul>}
            {q?.status === 'submitted' && q.submitted_at && <p className="text-muted">Submitted {dateTime(q.submitted_at)}. Buyers cannot see your prices until the deadline passes.</p>}
            <div className="flex flex-wrap gap-u4">
              {q?.can_edit && <Link to={`/app/vendor/rfqs/${rfq.id}/quote`}><Button>Edit and submit</Button></Link>}
              {q?.can_withdraw && <Button variant="outline" loading={withdraw.isPending} onClick={() => { setError(''); withdraw.mutate() }}>Withdraw to make changes</Button>}
              {rfq.quotation.status !== 'draft' && <Link to={`/app/vendor/rfqs/${rfq.id}/quote`}><Button variant="soft">View quotation</Button></Link>}
            </div>
          </>
        )}
        {error && <p role="alert" className="rounded-ctl bg-bad/15 p-u7 text-bad">{error}</p>}
      </Card>

      <Card className="flex flex-col gap-u8">
        <h2 className="text-2xl">What the buyer needs</h2>
        <dl className="grid gap-u6 sm:grid-cols-2">
          <div><dt className="text-sm text-muted">Needed by</dt><dd>{rfq.needed_by ? dateOnly(rfq.needed_by) : 'Not stated'}</dd></div>
          <div><dt className="text-sm text-muted">Buyer's currency</dt><dd>{rfq.currency} (you may quote in another currency)</dd></div>
          <div className="sm:col-span-2"><dt className="text-sm text-muted">Description</dt><dd className="whitespace-pre-wrap">{rfq.description || 'None'}</dd></div>
          <div className="sm:col-span-2"><dt className="text-sm text-muted">Requirements</dt><dd className="whitespace-pre-wrap">{rfq.requirements || 'None'}</dd></div>
        </dl>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[28rem] border-collapse text-left">
            <caption className="sr-only">Items to quote</caption>
            <thead><tr className="border-b border-line text-sm text-muted"><th scope="col" className="px-u4 py-u3 font-medium">#</th><th scope="col" className="px-u4 py-u3 font-medium">Item</th><th scope="col" className="px-u4 py-u3 font-medium">Quantity</th></tr></thead>
            <tbody>{rfq.items.map((i) => (
              <tr key={i.id} className="border-b border-line last:border-0"><td className="px-u4 py-u3">{i.line_no}</td><td className="px-u4 py-u3">{i.description}{i.specification && <span className="block text-sm text-muted">{i.specification}</span>}</td>
                <td className="px-u4 py-u3">{i.quantity.replace(/\.?0+$/, '')} {i.unit}</td></tr>))}</tbody>
          </table>
        </div>
      </Card>

      <Modal open={confirmDecline} onClose={() => setConfirmDecline(false)} title="Decline to quote?"
        footer={<><Button variant="soft" onClick={() => setConfirmDecline(false)}>Back</Button><Button loading={decline.isPending} onClick={() => decline.mutate()}>Decline</Button></>}>
        <p>The buyer will see that you declined. You will not be able to send a quotation for this request.</p>
      </Modal>
    </div>
  )
}
