import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BadgeCheck, Pencil, Send } from 'lucide-react'
import { ApiError, vendorsApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Overlay'
import { TextAreaField } from '@/components/forms/Controls'
import type { VendorDetail } from './types'

const messageFor = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Try again.')
type Dialog = 'verify' | 'reject' | 'suspend' | 'reinstate' | null

/** Buttons for what the server says this person can do next. The server refuses anything else, so this is convenience, not security. */
export function VendorActions({ vendor: v, editTo }: { vendor: VendorDetail; editTo: string }) {
  const qc = useQueryClient()
  const [dialog, setDialog] = useState<Dialog>(null)
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const has = (a: string) => (v.actions as string[]).includes(a)

  const done = () => {
    setDialog(null); setText(''); setError('')
    void qc.invalidateQueries({ queryKey: ['vendor'] }); void qc.invalidateQueries({ queryKey: ['vendors'] }); void qc.invalidateQueries({ queryKey: ['vendors-summary'] })
  }
  const fail = (e: unknown) => { setError(messageFor(e)); if (e instanceof ApiError && e.status === 409) void qc.invalidateQueries({ queryKey: ['vendor'] }) }
  const submit = useMutation({ mutationFn: () => vendorsApi.submit(v.id), onSuccess: done, onError: fail })
  const decide = useMutation({
    mutationFn: () => {
      const t = text.trim()
      if (dialog === 'verify') return vendorsApi.verify(v.id, v.version, t)
      if (dialog === 'reject') return vendorsApi.reject(v.id, v.version, t)
      if (dialog === 'suspend') return vendorsApi.suspend(v.id, v.version, t)
      return vendorsApi.reinstate(v.id, v.version, t)
    },
    onSuccess: done, onError: fail,
  })
  const open = (d: Dialog) => { setError(''); setText(''); setDialog(d) }
  const needsReason = dialog === 'reject' || dialog === 'suspend'
  const close = () => { setDialog(null); setError('') }
  const TITLES = { verify: 'Verify this vendor?', reject: 'Send this profile back?', suspend: 'Suspend this vendor?', reinstate: 'Reinstate this vendor?' }
  const CONFIRM = { verify: 'Verify vendor', reject: 'Send back', suspend: 'Suspend vendor', reinstate: 'Reinstate vendor' }

  return (
    <div className="flex flex-col gap-u5">
      <div className="flex flex-wrap gap-u4">
        {has('edit') && <Link to={editTo}><Button variant="soft"><Pencil className="h-4 w-4" aria-hidden /> Edit profile</Button></Link>}
        {has('submit') && <Button loading={submit.isPending} onClick={() => { setError(''); submit.mutate() }}><Send className="h-4 w-4" aria-hidden /> Submit for verification</Button>}
        {has('verify') && <Button onClick={() => open('verify')}><BadgeCheck className="h-4 w-4" aria-hidden /> Verify</Button>}
        {has('reject') && <Button variant="outline" onClick={() => open('reject')}>Send back</Button>}
        {has('suspend') && <Button variant="outline" onClick={() => open('suspend')}>Suspend</Button>}
        {has('reinstate') && <Button onClick={() => open('reinstate')}>Reinstate</Button>}
      </div>
      {v.blocked_reason && <p role="status" className="text-muted">{v.blocked_reason}</p>}
      {!dialog && error && <p role="alert" className="rounded-ctl bg-bad/15 p-u7 text-bad">{error}</p>}

      <Modal open={dialog !== null} onClose={close} title={dialog ? TITLES[dialog] : ''}
        footer={<><Button variant="soft" onClick={close}>Cancel</Button>
          <Button loading={decide.isPending} disabled={needsReason && text.trim().length < 3} onClick={() => { setError(''); decide.mutate() }}>{dialog ? CONFIRM[dialog] : ''}</Button></>}>
        <div className="flex flex-col gap-u6">
          {dialog === 'verify' && <p>{v.legal_name} will be able to take part in requests for quotation.</p>}
          {dialog === 'reject' && <p>{v.legal_name} will see your reason and can fix the profile and submit it again.</p>}
          {dialog === 'suspend' && <p>{v.legal_name} will no longer be offered new requests for quotation.</p>}
          {dialog === 'reinstate' && <p>{v.legal_name} will be verified again.</p>}
          <TextAreaField label={needsReason ? 'Reason' : 'Note (optional)'} hint={needsReason ? 'The vendor can read this.' : undefined} value={text} onChange={(e) => setText(e.target.value)} />
          {error && <p role="alert" className="text-bad">{error}</p>}
        </div>
      </Modal>
    </div>
  )
}
