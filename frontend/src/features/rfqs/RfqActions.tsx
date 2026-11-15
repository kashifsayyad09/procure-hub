import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { GitCompare, Pencil, Send, UserPlus } from 'lucide-react'
import { ApiError, rfqsApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Overlay'
import { Field } from '@/components/forms/Field'
import { TextAreaField } from '@/components/forms/Controls'
import { InviteDialog } from './InviteDialog'
import { fromLocalInput } from './labels'
import type { Rfq } from './types'

const messageFor = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Try again.')
type Dialog = 'close' | 'cancel' | 'extend' | 'invite' | null

/** Buttons for what the server says can happen next. The server refuses anything else, so this is convenience, not security. */
export function RfqActions({ rfq }: { rfq: Rfq }) {
  const qc = useQueryClient()
  const [dialog, setDialog] = useState<Dialog>(null)
  const [text, setText] = useState('')
  const [when, setWhen] = useState('')
  const [error, setError] = useState('')
  const has = (a: string) => (rfq.actions as string[]).includes(a)
  const done = () => {
    setDialog(null); setText(''); setWhen(''); setError('')
    void qc.invalidateQueries({ queryKey: ['rfq'] }); void qc.invalidateQueries({ queryKey: ['rfqs'] }); void qc.invalidateQueries({ queryKey: ['rfqs-summary'] })
  }
  const fail = (e: unknown) => { setError(messageFor(e)); if (e instanceof ApiError && e.status === 409) void qc.invalidateQueries({ queryKey: ['rfq'] }) }
  const publish = useMutation({ mutationFn: () => rfqsApi.publish(rfq.id), onSuccess: done, onError: fail })
  const act = useMutation({
    mutationFn: () => (dialog === 'close' ? rfqsApi.close(rfq.id) : dialog === 'cancel' ? rfqsApi.cancel(rfq.id, text.trim()) : rfqsApi.extend(rfq.id, rfq.version, fromLocalInput(when))),
    onSuccess: done, onError: fail,
  })
  const open = (d: Dialog) => { setError(''); setText(''); setWhen(''); setDialog(d) }
  const close = () => { setDialog(null); setError('') }
  const TITLES = { close: 'Close this RFQ?', cancel: 'Cancel this RFQ?', extend: 'Extend the deadline', invite: '' }
  const CONFIRM = { close: 'Close RFQ', cancel: 'Cancel RFQ', extend: 'Extend deadline', invite: '' }
  const blocked = (dialog === 'cancel' && text.trim().length < 3) || (dialog === 'extend' && !when)

  return (
    <div className="flex flex-col gap-u5">
      <div className="flex flex-wrap gap-u4">
        {has('edit') && <Link to={`/app/procurement/rfqs/${rfq.id}/edit`}><Button variant="soft"><Pencil className="h-4 w-4" aria-hidden /> Edit</Button></Link>}
        {has('invite') && <Button variant="soft" onClick={() => open('invite')}><UserPlus className="h-4 w-4" aria-hidden /> Invite vendors</Button>}
        {has('publish') && <Button loading={publish.isPending} onClick={() => { setError(''); publish.mutate() }}><Send className="h-4 w-4" aria-hidden /> Issue to vendors</Button>}
        {has('extend') && <Button variant="soft" onClick={() => open('extend')}>Extend deadline</Button>}
        {has('compare') && <Link to={`/app/procurement/rfqs/${rfq.id}/compare`}><Button><GitCompare className="h-4 w-4" aria-hidden /> Compare quotations</Button></Link>}
        {has('close') && <Button variant="outline" onClick={() => open('close')}>Close early</Button>}
        {has('cancel') && <Button variant="outline" onClick={() => open('cancel')}>Cancel RFQ</Button>}
      </div>
      {!dialog && error && <p role="alert" className="rounded-ctl bg-bad/15 p-u7 text-bad">{error}</p>}

      <InviteDialog rfq={rfq} open={dialog === 'invite'} onClose={close} />
      <Modal open={dialog !== null && dialog !== 'invite'} onClose={close} title={dialog && dialog !== 'invite' ? TITLES[dialog] : ''}
        footer={<><Button variant="soft" onClick={close}>Back</Button><Button loading={act.isPending} disabled={blocked} onClick={() => { setError(''); act.mutate() }}>{dialog && dialog !== 'invite' ? CONFIRM[dialog] : ''}</Button></>}>
        <div className="flex flex-col gap-u6">
          {dialog === 'close' && <p>Vendors will no longer be able to send or change quotations, and submitted prices will open for comparison.</p>}
          {dialog === 'cancel' && <><p>The purchase request will be free to go out for quotation again.</p><TextAreaField label="Reason" value={text} onChange={(e) => setText(e.target.value)} /></>}
          {dialog === 'extend' && <Field label="New deadline" type="datetime-local" hint="Must be later than the current deadline. In your local time." value={when} onChange={(e) => setWhen(e.target.value)} />}
          {error && <p role="alert" className="text-bad">{error}</p>}
        </div>
      </Modal>
    </div>
  )
}
