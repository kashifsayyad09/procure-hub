import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ApiError, rfqsApi } from '@/services/api'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Overlay'
import { SelectField, TextAreaField } from '@/components/forms/Controls'
import { money } from '@/features/purchase-requests/format'
import { unitPrice } from './labels'
import type { CompareQuotation } from './types'

const messageFor = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Try again.')
const SCORES = Array.from({ length: 11 }, (_, i) => i)

function useRefresh() {
  const qc = useQueryClient()
  return () => { void qc.invalidateQueries({ queryKey: ['comparison'] }); void qc.invalidateQueries({ queryKey: ['rfq'] }); void qc.invalidateQueries({ queryKey: ['rfqs'] }) }
}

/** The evaluator's two judgements. Price and delivery are calculated by the server and cannot be typed in here. */
export function EvaluateDialog({ rfqId, q, onClose }: { rfqId: string; q: CompareQuotation | null; onClose: () => void }) {
  const refresh = useRefresh()
  const ev = q?.evaluation ?? null
  const [comp, setComp] = useState<string>(ev?.compliance_score?.toString() ?? '')
  const [compNote, setCompNote] = useState(ev?.compliance_note ?? '')
  const [terms, setTerms] = useState<string>(ev?.terms_score?.toString() ?? '')
  const [termsNote, setTermsNote] = useState(ev?.terms_note ?? '')
  const [error, setError] = useState('')
  const save = useMutation({
    mutationFn: () => rfqsApi.evaluate(rfqId, q!.id, {
      compliance_score: comp === '' ? null : Number(comp), compliance_note: comp === '' ? null : compNote.trim(),
      terms_score: terms === '' ? null : Number(terms), terms_note: terms === '' ? null : termsNote.trim(), version: ev?.version,
    }),
    onSuccess: () => { refresh(); onClose() },
    onError: (e) => setError(messageFor(e)),
  })
  const problem = comp === '' && terms === '' ? 'Enter at least one score.' : comp !== '' && !compNote.trim() ? 'Say why you gave the compliance score.' : terms !== '' && !termsNote.trim() ? 'Say why you gave the commercial terms score.' : ''
  return (
    <Modal open={q !== null} onClose={onClose} title={q ? `Evaluate ${q.vendor_name}` : ''}
      footer={<><Button variant="soft" onClick={onClose}>Cancel</Button><Button loading={save.isPending} disabled={!!problem} onClick={() => { setError(''); save.mutate() }}>Save evaluation</Button></>}>
      <div className="flex flex-col gap-u6">
        <p className="text-muted">Your own judgement, from 0 (poor) to 10 (excellent). Each score needs a reason so the decision can be reviewed later. Price and delivery scores are calculated, not entered.</p>
        <SelectField label="Compliance with the requirements" value={comp} onChange={(e) => setComp(e.target.value)}><option value="">Not scored</option>{SCORES.map((s) => <option key={s} value={s}>{s}</option>)}</SelectField>
        {comp !== '' && <TextAreaField label="Why this compliance score" value={compNote} onChange={(e) => setCompNote(e.target.value)} />}
        <SelectField label="Commercial terms" value={terms} onChange={(e) => setTerms(e.target.value)}><option value="">Not scored</option>{SCORES.map((s) => <option key={s} value={s}>{s}</option>)}</SelectField>
        {terms !== '' && <TextAreaField label="Why this terms score" value={termsNote} onChange={(e) => setTermsNote(e.target.value)} />}
        {problem && <p role="status" className="text-muted">{problem}</p>}
        {error && <p role="alert" className="text-bad">{error}</p>}
      </div>
    </Modal>
  )
}

export function SelectDialog({ rfqId, q, onClose }: { rfqId: string; q: CompareQuotation | null; onClose: () => void }) {
  const refresh = useRefresh()
  const [text, setText] = useState('')
  const [ack, setAck] = useState(false)
  const [error, setError] = useState('')
  const choose = useMutation({
    mutationFn: () => rfqsApi.select(rfqId, { quotation_id: q!.id, justification: text.trim(), acknowledge_missing_items: ack }),
    onSuccess: () => { refresh(); onClose() },
    onError: (e) => setError(messageFor(e)),
  })
  const needsAck = q !== null && !q.complete
  return (
    <Modal open={q !== null} onClose={onClose} title={q ? `Select ${q.vendor_name}?` : ''}
      footer={<><Button variant="soft" onClick={onClose}>Cancel</Button><Button loading={choose.isPending} disabled={text.trim().length < 10 || (needsAck && !ack)} onClick={() => { setError(''); choose.mutate() }}>Select supplier</Button></>}>
      {q && (
        <div className="flex flex-col gap-u6">
          <p>You are awarding this RFQ to {q.vendor_name} for {money(unitPrice(q.total_amount), q.currency)}. The vendor is checked again at this moment, and the award is recorded with your name and reason.</p>
          <TextAreaField label="Why this supplier" hint="At least 10 characters. This becomes part of the permanent record." value={text} onChange={(e) => setText(e.target.value)} />
          {needsAck && (
            <label className="flex min-h-[44px] items-start gap-u5"><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-u2 h-5 w-5" />
              <span>I accept that item{q.missing_items.length === 1 ? '' : 's'} {q.missing_items.join(', ')} {q.missing_items.length === 1 ? 'is' : 'are'} not quoted.</span></label>
          )}
          {error && <p role="alert" className="text-bad">{error}</p>}
        </div>
      )}
    </Modal>
  )
}

export function RevokeDialog({ rfqId, open, vendorName, onClose }: { rfqId: string; open: boolean; vendorName: string; onClose: () => void }) {
  const refresh = useRefresh()
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const revoke = useMutation({ mutationFn: () => rfqsApi.revoke(rfqId, text.trim()), onSuccess: () => { refresh(); setText(''); onClose() }, onError: (e) => setError(messageFor(e)) })
  return (
    <Modal open={open} onClose={onClose} title="Revoke the award?"
      footer={<><Button variant="soft" onClick={onClose}>Keep the award</Button><Button loading={revoke.isPending} disabled={text.trim().length < 5} onClick={() => { setError(''); revoke.mutate() }}>Revoke award</Button></>}>
      <div className="flex flex-col gap-u6">
        <p>The award to {vendorName} is withdrawn and the RFQ goes back to closed so another supplier can be chosen. The earlier award stays in the history.</p>
        <TextAreaField label="Reason" value={text} onChange={(e) => setText(e.target.value)} />
        {error && <p role="alert" className="text-bad">{error}</p>}
      </div>
    </Modal>
  )
}
