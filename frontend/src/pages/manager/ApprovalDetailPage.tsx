import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, approvalsApi } from '@/services/api'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { ApprovalTimeline } from '@/components/ui/ApprovalTimeline'
import { Modal } from '@/components/ui/Overlay'
import { SelectField, TextAreaField } from '@/components/forms/Controls'
import { ApprovalStatusBadge } from '@/features/approvals/ApprovalStatusBadge'
import { chainFor } from '@/features/approvals/chain'
import { dateOnly, dateTime, money } from '@/features/purchase-requests/format'

const messageFor = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Try again.')
const ACTION_LABEL: Record<string, string> = { requested: 'Requested', approved: 'Approved', rejected: 'Rejected', delegated: 'Delegated', escalated: 'Flagged overdue', cancelled: 'Cancelled', sync_conflict: 'Could not update the request' }

export default function ApprovalDetailPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const { data: a, isLoading, isError, error, refetch } = useQuery({ queryKey: ['approval', id], queryFn: () => approvalsApi.get(id) })
  const [dialog, setDialog] = useState<'approve' | 'reject' | 'delegate' | null>(null)
  const [comment, setComment] = useState('')
  const [reason, setReason] = useState('')
  const [delegateId, setDelegateId] = useState('')
  const [note, setNote] = useState('')
  const [problem, setProblem] = useState('')
  const delegates = useQuery({ queryKey: ['delegates'], queryFn: approvalsApi.delegates, enabled: dialog === 'delegate' })

  const done = () => {
    setDialog(null); setProblem(''); setComment(''); setReason(''); setDelegateId(''); setNote('')
    void qc.invalidateQueries({ queryKey: ['approval', id] }); void qc.invalidateQueries({ queryKey: ['approvals'] }); void qc.invalidateQueries({ queryKey: ['approvals-summary'] })
  }
  const failed = (e: unknown) => { setDialog(null); setProblem(messageFor(e)); void qc.invalidateQueries({ queryKey: ['approval', id] }) }
  const approve = useMutation({ mutationFn: () => approvalsApi.approve(id, comment.trim()), onSuccess: done, onError: failed })
  const reject = useMutation({ mutationFn: () => approvalsApi.reject(id, reason.trim()), onSuccess: done, onError: failed })
  const delegate = useMutation({ mutationFn: () => approvalsApi.delegate(id, delegateId, note.trim()), onSuccess: done, onError: failed })

  if (isLoading) return <div role="status" aria-busy="true"><span className="sr-only">Loading approval</span><Skeleton className="h-96 rounded-card" /></div>
  if (isError || !a) return <ErrorState title="Could not open this approval" description={messageFor(error)} onRetry={() => void refetch()} />

  return (
    <div className="flex flex-col gap-u12">
      <header className="flex flex-wrap items-start justify-between gap-u8">
        <div>
          <Link to="/app/manager/approvals" className="text-sm text-muted underline-offset-4 hover:underline">Back to approvals</Link>
          <p className="mt-u3 text-muted">{a.request_number}</p>
          <h1 className="display-lg">{a.title}</h1>
          <div className="mt-u4 flex flex-wrap items-center gap-u3"><ApprovalStatusBadge status={a.status} />{a.overdue && <Badge tone="bad">Overdue</Badge>}
            {a.status === 'pending' && <span className="text-sm text-muted">Level {a.current_level} of {a.total_levels}</span>}</div>
        </div>
        {a.can_decide && (
          <div className="flex flex-wrap gap-u4">
            <Button onClick={() => setDialog('approve')}>Approve</Button>
            <Button variant="outline" onClick={() => setDialog('reject')}>Reject</Button>
            <Button variant="soft" onClick={() => setDialog('delegate')}>Delegate</Button>
          </div>
        )}
      </header>

      {problem && <p role="alert" className="rounded-ctl bg-bad/15 p-u7 text-bad">{problem}</p>}
      {a.status === 'pending' && !a.can_decide && a.blocked_reason && <p role="status" className="rounded-ctl bg-accent/20 p-u7">{a.blocked_reason}</p>}
      {a.decision_sync === 'pending' && <p role="status" className="rounded-ctl bg-accent/20 p-u7">Your decision is saved. The request is being updated and will show the result shortly.</p>}
      {a.decision_sync === 'conflict' && <p role="alert" className="rounded-ctl bg-bad/15 p-u7 text-bad">The decision is saved, but the request could not be updated: {a.last_sync_error}. It may have been cancelled by the requester.</p>}

      <div className="grid gap-u8 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="mb-u6 text-2xl">Request</h2>
          <dl className="grid gap-u6 sm:grid-cols-2">
            <div><dt className="text-sm text-muted">Requested by</dt><dd>{a.requester_name}</dd></div>
            <div><dt className="text-sm text-muted">Department</dt><dd>{a.department || 'Not set'}</dd></div>
            <div><dt className="text-sm text-muted">Priority</dt><dd className="capitalize">{a.priority}</dd></div>
            <div><dt className="text-sm text-muted">Needed by</dt><dd>{dateOnly(a.needed_by)}</dd></div>
            <div><dt className="text-sm text-muted">Submitted</dt><dd>{dateTime(a.created_at)}</dd></div>
            <div><dt className="text-sm text-muted">Total</dt><dd className="font-medium">{money(a.total_amount, a.currency)}</dd></div>
            <div className="sm:col-span-2"><dt className="text-sm text-muted">Why it is needed</dt><dd className="whitespace-pre-wrap">{a.justification || 'Not set'}</dd></div>
          </dl>
        </Card>
        <Card>
          <h2 className="mb-u8 text-2xl">Approval route</h2>
          <ApprovalTimeline steps={chainFor(a)} />
        </Card>
      </div>

      <Card>
        <h2 className="mb-u6 text-2xl">Items</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] border-collapse text-left">
            <caption className="sr-only">Items in {a.request_number}</caption>
            <thead><tr className="border-b border-line text-sm text-muted">
              <th scope="col" className="px-u4 py-u4 font-medium">#</th><th scope="col" className="px-u4 py-u4 font-medium">Description</th>
              <th scope="col" className="px-u4 py-u4 text-right font-medium">Quantity</th><th scope="col" className="px-u4 py-u4 text-right font-medium">Unit price</th><th scope="col" className="px-u4 py-u4 text-right font-medium">Total</th>
            </tr></thead>
            <tbody>
              {a.items.map((i) => (
                <tr key={i.line_no} className="border-b border-line">
                  <td className="px-u4 py-u4">{i.line_no}</td><td className="px-u4 py-u4">{i.description}</td>
                  <td className="px-u4 py-u4 text-right tabular-nums">{Number(i.quantity)} {i.unit}</td>
                  <td className="px-u4 py-u4 text-right tabular-nums">{money(i.unit_price, a.currency)}</td><td className="px-u4 py-u4 text-right tabular-nums">{money(i.line_total, a.currency)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot><tr><th scope="row" colSpan={4} className="px-u4 py-u4 text-right">Total</th><td className="px-u4 py-u4 text-right font-medium tabular-nums">{money(a.total_amount, a.currency)}</td></tr></tfoot>
          </table>
        </div>
      </Card>

      <Card>
        <h2 className="mb-u6 text-2xl">History</h2>
        <ol className="flex flex-col gap-u6">
          {a.history.map((h) => (
            <li key={h.id}>
              <p className="font-medium">{ACTION_LABEL[h.action] ?? h.action}{h.level ? `, level ${h.level}` : ''}</p>
              <p className="text-sm text-muted">{h.actor_name}, {dateTime(h.created_at)}</p>
              {h.note && <p className="text-sm">{h.note}</p>}
            </li>
          ))}
        </ol>
      </Card>

      <Modal open={dialog === 'approve'} onClose={() => setDialog(null)} title="Approve this request?"
        footer={<><Button variant="soft" onClick={() => setDialog(null)}>Not yet</Button><Button loading={approve.isPending} onClick={() => approve.mutate()}>Approve</Button></>}>
        <p className="mb-u6">{a.total_levels > a.current_level ? `This is level ${a.current_level} of ${a.total_levels}. Another manager must approve the next level.` : `${money(a.total_amount, a.currency)} will be approved for ${a.requester_name}.`}</p>
        <TextAreaField label="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} />
      </Modal>
      <Modal open={dialog === 'reject'} onClose={() => setDialog(null)} title="Reject this request?"
        footer={<><Button variant="soft" onClick={() => setDialog(null)}>Keep waiting</Button><Button loading={reject.isPending} disabled={reason.trim().length < 3} onClick={() => reject.mutate()}>Reject</Button></>}>
        <TextAreaField label="Reason" hint={`${a.requester_name} will see this.`} value={reason} onChange={(e) => setReason(e.target.value)} />
      </Modal>
      <Modal open={dialog === 'delegate'} onClose={() => setDialog(null)} title="Delegate this approval"
        footer={<><Button variant="soft" onClick={() => setDialog(null)}>Cancel</Button><Button loading={delegate.isPending} disabled={!delegateId} onClick={() => delegate.mutate()}>Delegate</Button></>}>
        {delegates.isError ? <p role="alert" className="text-bad">{messageFor(delegates.error)}</p> : delegates.isLoading ? <p>Loading managers</p> : (
          <div className="flex flex-col gap-u6">
            <SelectField label="Manager" value={delegateId} onChange={(e) => setDelegateId(e.target.value)} hint="Only this manager will be able to decide.">
              <option value="">Choose a manager</option>{delegates.data?.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
            </SelectField>
            <TextAreaField label="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
        )}
      </Modal>
    </div>
  )
}
