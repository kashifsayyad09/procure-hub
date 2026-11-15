import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, rfqsApi, vendorsApi } from '@/services/api'
import { useDebounced } from '@/hooks/useDebounced'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Overlay'
import type { Rfq } from './types'

/** Picks vendors from the vendor directory. Only verified vendors are listed; the server checks again. */
export function InviteDialog({ rfq, open, onClose }: { rfq: Rfq; open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [picked, setPicked] = useState<string[]>([])
  const [error, setError] = useState('')
  const q = useDebounced(search.trim(), 300)
  const invitedNow = new Set(rfq.invitations.filter((i) => i.status === 'invited').map((i) => i.vendor_id))
  const vendors = useQuery({ queryKey: ['vendors', 'invite', q, category], enabled: open,
    queryFn: () => vendorsApi.list({ q: q || undefined, status: 'verified', category: category || undefined, page: 1, page_size: 50 }) })
  const cats = useQuery({ queryKey: ['vendor-categories'], queryFn: vendorsApi.categories, staleTime: Infinity, enabled: open })
  const send = useMutation({
    mutationFn: () => rfqsApi.invite(rfq.id, picked),
    onSuccess: () => { setPicked([]); setError(''); void qc.invalidateQueries({ queryKey: ['rfq'] }); void qc.invalidateQueries({ queryKey: ['rfqs'] }); onClose() },
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Something went wrong. Try again.'),
  })
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))
  const available = (vendors.data?.items ?? []).filter((v) => !invitedNow.has(v.id))
  const sendsNow = rfq.status === 'issued'

  return (
    <Modal open={open} onClose={onClose} title="Invite vendors"
      footer={<><Button variant="soft" onClick={onClose}>Cancel</Button><Button loading={send.isPending} disabled={picked.length === 0} onClick={() => { setError(''); send.mutate() }}>
        {sendsNow ? `Invite and send to ${picked.length}` : `Add ${picked.length} vendor${picked.length === 1 ? '' : 's'}`}</Button></>}>
      <div className="flex flex-col gap-u6">
        <p className="text-muted">{sendsNow ? 'Invitations are sent straight away because the RFQ is open.' : 'Vendors are told about the RFQ when you issue it.'} Only verified vendors can be invited.</p>
        <div className="flex flex-wrap gap-u4">
          <label className="min-w-[10rem] flex-1"><span className="sr-only">Search vendors</span>
            <input type="search" placeholder="Search vendors" value={search} onChange={(e) => setSearch(e.target.value)} className="h-11 w-full rounded-ctl border border-line bg-surface px-u6 placeholder:text-muted" /></label>
          <label><span className="sr-only">Category</span>
            <select value={category} onChange={(e) => setCategory(e.target.value)} className="h-11 rounded-ctl border border-line bg-surface px-u6"><option value="">Any category</option>{cats.data?.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}</select></label>
        </div>
        {vendors.isLoading ? <p role="status">Loading vendors</p> : vendors.isError ? <p role="alert" className="text-bad">Could not load vendors. Close this and try again.</p>
          : available.length === 0 ? <p className="text-muted">No verified vendors to add{q || category ? ' for this search' : ''}.</p> : (
            <ul className="flex max-h-72 flex-col gap-u3 overflow-y-auto" aria-label="Verified vendors">
              {available.map((v) => (
                <li key={v.id}><label className="flex min-h-[44px] items-center gap-u5 rounded-ctl border border-line px-u7">
                  <input type="checkbox" checked={picked.includes(v.id)} onChange={() => toggle(v.id)} className="h-5 w-5" />
                  <span><span className="block font-medium">{v.legal_name}</span><span className="block text-sm text-muted">{v.number}, {v.city || 'No city'}</span></span></label></li>
              ))}
            </ul>
          )}
        {error && <p role="alert" className="text-bad">{error}</p>}
      </div>
    </Modal>
  )
}
