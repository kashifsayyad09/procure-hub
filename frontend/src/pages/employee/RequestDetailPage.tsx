import { useState, type ChangeEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, Trash2 } from 'lucide-react'
import { ApiError, purchaseRequestsApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { Modal } from '@/components/ui/Overlay'
import { TextAreaField } from '@/components/forms/Controls'
import { RequestStatusBadge } from '@/features/purchase-requests/RequestStatusBadge'
import { dateOnly, dateTime, fileSize, money } from '@/features/purchase-requests/format'
import { ALLOWED_DOCUMENT_TYPES, MAX_DOCUMENT_BYTES } from '@/features/purchase-requests/types'

const messageFor = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Try again.')

export default function RequestDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: r, isLoading, isError, error, refetch } = useQuery({ queryKey: ['request', id], queryFn: () => purchaseRequestsApi.get(id) })
  const [dialog, setDialog] = useState<'delete' | 'cancel' | null>(null)
  const [reason, setReason] = useState('')
  const [problem, setProblem] = useState('')
  const [docError, setDocError] = useState('')

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['request', id] }); void qc.invalidateQueries({ queryKey: ['requests'] }); void qc.invalidateQueries({ queryKey: ['requests-summary'] })
  }
  const onError = (e: unknown) => { setDialog(null); setProblem(messageFor(e)) }
  const submit = useMutation({ mutationFn: () => purchaseRequestsApi.submit(id), onSuccess: () => { setProblem(''); refresh() }, onError })
  const cancel = useMutation({ mutationFn: () => purchaseRequestsApi.cancel(id, reason), onSuccess: () => { setDialog(null); setReason(''); setProblem(''); refresh() }, onError })
  const remove = useMutation({ mutationFn: () => purchaseRequestsApi.remove(id), onSuccess: () => { void qc.invalidateQueries({ queryKey: ['requests'] }); void qc.invalidateQueries({ queryKey: ['requests-summary'] }); navigate('/app/employee/requests', { replace: true }) }, onError })
  const addDoc = useMutation({ mutationFn: (f: { file_name: string; content_type: string; size_bytes: number }) => purchaseRequestsApi.addDocument(id, f), onSuccess: () => { setDocError(''); refresh() }, onError: (e) => setDocError(messageFor(e)) })
  const removeDoc = useMutation({ mutationFn: (docId: string) => purchaseRequestsApi.removeDocument(id, docId), onSuccess: refresh, onError: (e) => setDocError(messageFor(e)) })

  const onFile = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    if (!ALLOWED_DOCUMENT_TYPES[f.type]) return setDocError('This file type is not allowed. Use PDF, PNG, JPEG, TXT, CSV, DOCX or XLSX.')
    if (f.size === 0 || f.size > MAX_DOCUMENT_BYTES) return setDocError('Files must be between 1 byte and 10 MB.')
    setDocError('')
    addDoc.mutate({ file_name: f.name, content_type: f.type, size_bytes: f.size })
  }

  if (isLoading) return <div role="status" aria-busy="true"><span className="sr-only">Loading request</span><Skeleton className="h-96 rounded-card" /></div>
  if (isError || !r) return <ErrorState title="Could not open this request" description={messageFor(error)} onRetry={() => void refetch()} />

  const isDraft = r.status === 'draft'
  return (
    <div className="flex flex-col gap-u12">
      <header className="flex flex-wrap items-start justify-between gap-u8">
        <div>
          <Link to="/app/employee/requests" className="text-sm text-muted underline-offset-4 hover:underline">Back to my requests</Link>
          <p className="mt-u3 text-muted">{r.number}</p>
          <h1 className="display-lg">{r.title}</h1>
          <div className="mt-u4"><RequestStatusBadge status={r.status} /></div>
        </div>
        <div className="flex flex-wrap gap-u4">
          {isDraft && <Link to={`/app/employee/requests/${r.id}/edit`}><Button variant="soft">Edit</Button></Link>}
          {isDraft && <Button loading={submit.isPending} onClick={() => submit.mutate()}>Submit for approval</Button>}
          {isDraft && <Button variant="outline" onClick={() => setDialog('delete')}>Delete draft</Button>}
          {r.status === 'submitted' && <Button variant="outline" onClick={() => setDialog('cancel')}>Cancel request</Button>}
        </div>
      </header>

      {problem && <p role="alert" className="rounded-ctl bg-bad/15 p-u7 text-bad">{problem}</p>}

      <div className="grid gap-u8 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="mb-u6 text-2xl">Overview</h2>
          <dl className="grid gap-u6 sm:grid-cols-2">
            <div><dt className="text-sm text-muted">Requested by</dt><dd>{r.requester_name}</dd></div>
            <div><dt className="text-sm text-muted">Department</dt><dd>{r.department || 'Not set'}</dd></div>
            <div><dt className="text-sm text-muted">Priority</dt><dd className="capitalize">{r.priority}</dd></div>
            <div><dt className="text-sm text-muted">Needed by</dt><dd>{dateOnly(r.needed_by)}</dd></div>
            <div><dt className="text-sm text-muted">Created</dt><dd>{dateTime(r.created_at)}</dd></div>
            <div><dt className="text-sm text-muted">Total</dt><dd className="font-medium">{money(r.total_amount, r.currency)}</dd></div>
            <div className="sm:col-span-2"><dt className="text-sm text-muted">Why it is needed</dt><dd className="whitespace-pre-wrap">{r.justification || 'Not set'}</dd></div>
            {r.decided_at && (
              <div className="sm:col-span-2">
                <dt className="text-sm text-muted">Decision</dt>
                <dd>{r.status === 'approved' ? 'Approved' : 'Rejected'} by {r.decided_by_name ?? 'a manager'}, {dateTime(r.decided_at)}{r.decision_note && <span className="block whitespace-pre-wrap">{r.decision_note}</span>}</dd>
              </div>
            )}
            {r.cancel_reason && <div className="sm:col-span-2"><dt className="text-sm text-muted">Cancellation reason</dt><dd>{r.cancel_reason}</dd></div>}
          </dl>
        </Card>
        <Card>
          <h2 className="mb-u6 text-2xl">History</h2>
          <ol className="flex flex-col gap-u6">
            {r.history.map((h) => (
              <li key={h.id}>
                <p className="font-medium">{h.from_status ? `${h.from_status} to ${h.to_status}` : `Created as ${h.to_status}`}</p>
                <p className="text-sm text-muted">{h.actor_name}, {dateTime(h.created_at)}</p>
                {h.note && <p className="text-sm">{h.note}</p>}
              </li>
            ))}
          </ol>
        </Card>
      </div>

      <Card>
        <h2 className="mb-u6 text-2xl">Items</h2>
        {r.items.length === 0 ? <p className="text-muted">No items yet.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[34rem] border-collapse text-left">
              <caption className="sr-only">Items in {r.number}</caption>
              <thead><tr className="border-b border-line text-sm text-muted">
                <th scope="col" className="px-u4 py-u4 font-medium">#</th><th scope="col" className="px-u4 py-u4 font-medium">Description</th>
                <th scope="col" className="px-u4 py-u4 text-right font-medium">Quantity</th><th scope="col" className="px-u4 py-u4 text-right font-medium">Unit price</th><th scope="col" className="px-u4 py-u4 text-right font-medium">Total</th>
              </tr></thead>
              <tbody>
                {r.items.map((i) => (
                  <tr key={i.id} className="border-b border-line">
                    <td className="px-u4 py-u4">{i.line_no}</td>
                    <td className="px-u4 py-u4">{i.description}{i.notes && <span className="block text-sm text-muted">{i.notes}</span>}</td>
                    <td className="px-u4 py-u4 text-right tabular-nums">{Number(i.quantity)} {i.unit}</td>
                    <td className="px-u4 py-u4 text-right tabular-nums">{money(i.unit_price, r.currency)}</td>
                    <td className="px-u4 py-u4 text-right tabular-nums">{money(i.line_total, r.currency)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot><tr><th scope="row" colSpan={4} className="px-u4 py-u4 text-right">Total</th><td className="px-u4 py-u4 text-right font-medium tabular-nums">{money(r.total_amount, r.currency)}</td></tr></tfoot>
            </table>
          </div>
        )}
      </Card>

      <Card>
        <h2 className="mb-u2 text-2xl">Supporting documents</h2>
        <p className="mb-u6 text-sm text-muted">For now only the file details are recorded. Uploading the file itself arrives with object storage in a later phase.</p>
        {r.documents.length === 0 ? <p className="text-muted">No documents added.</p> : (
          <ul className="flex flex-col gap-u4">
            {r.documents.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-u4 rounded-ctl border border-line p-u6">
                <span className="flex min-w-0 items-center gap-u4"><FileText className="h-5 w-5 shrink-0" aria-hidden /><span className="truncate">{d.file_name}</span><span className="shrink-0 text-sm text-muted">{fileSize(d.size_bytes)}</span></span>
                {isDraft && <Button variant="ghost" size="sm" aria-label={`Remove ${d.file_name}`} onClick={() => removeDoc.mutate(d.id)}><Trash2 className="h-4 w-4" aria-hidden /></Button>}
              </li>
            ))}
          </ul>
        )}
        {isDraft && (
          <div className="mt-u8">
            <label className="flex flex-col gap-u3"><span className="text-sm font-medium">Add a document</span>
              <input type="file" accept={Object.keys(ALLOWED_DOCUMENT_TYPES).join(',')} onChange={onFile} className="text-sm" />
            </label>
            <p className="mt-u3 text-sm text-muted">PDF, PNG, JPEG, TXT, CSV, DOCX or XLSX, up to 10 MB, at most 10 per request.</p>
          </div>
        )}
        {docError && <p role="alert" className="mt-u6 rounded-ctl bg-bad/15 p-u7 text-bad">{docError}</p>}
      </Card>

      <Modal open={dialog === 'delete'} onClose={() => setDialog(null)} title="Delete this draft?"
        footer={<><Button variant="soft" onClick={() => setDialog(null)}>Keep draft</Button><Button loading={remove.isPending} onClick={() => remove.mutate()}>Delete draft</Button></>}>
        <p>{r.number} will be removed permanently. This cannot be undone.</p>
      </Modal>
      <Modal open={dialog === 'cancel'} onClose={() => setDialog(null)} title="Cancel this request?"
        footer={<><Button variant="soft" onClick={() => setDialog(null)}>Keep request</Button><Button loading={cancel.isPending} disabled={reason.trim().length < 3} onClick={() => cancel.mutate()}>Cancel request</Button></>}>
        <TextAreaField label="Reason" hint="Your manager will see this." value={reason} onChange={(e) => setReason(e.target.value)} />
      </Modal>
    </div>
  )
}
