import { Card } from '@/components/ui/Card'
import { dateTime } from '@/features/purchase-requests/format'
import { VendorStatusBadge } from './VendorStatusBadge'
import { ACTION_LABEL, STATUS_HELP, countryName, paymentTerms } from './labels'
import type { VendorCategory, VendorDetail } from './types'

const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div><dt className="text-sm text-muted">{label}</dt><dd className="whitespace-pre-wrap break-words">{children || 'Not set'}</dd></div>
)

/** Read-only profile, the same for the vendor and for staff. What differs is which actions the server offers (see VendorActions). */
export function VendorProfileView({ vendor: v, categories, audience }: { vendor: VendorDetail; categories: VendorCategory[]; audience: 'vendor' | 'staff' }) {
  const label = (id: string) => categories.find((c) => c.id === id)?.label ?? id
  const address = [v.address_line1, v.address_line2, [v.city, v.state].filter(Boolean).join(', '), [v.postal_code, countryName(v.country)].filter(Boolean).join(' ')].filter(Boolean).join('\n')
  return (
    <div className="flex flex-col gap-u8">
      <Card aria-label="Verification status" className="flex flex-col gap-u4">
        <div className="flex flex-wrap items-center gap-u5"><h2 className="text-2xl">Verification</h2><VendorStatusBadge status={v.status} /></div>
        <p className="text-muted">{audience === 'vendor' ? STATUS_HELP[v.status] : v.status === 'pending' ? 'Waiting for a procurement reviewer.' : STATUS_HELP[v.status]}</p>
        {v.status_note && (v.status === 'rejected' || v.status === 'suspended') && (
          <p role="note" className="rounded-ctl bg-bad/15 p-u7 text-bad"><span className="font-medium">{v.status === 'rejected' ? 'Reason it was sent back: ' : 'Reason for suspension: '}</span>{v.status_note}</p>
        )}
        {v.verified_at && v.status === 'verified' && <p className="text-sm text-muted">Verified by {v.verified_by_name} on {dateTime(v.verified_at)}.</p>}
      </Card>

      <Card className="flex flex-col gap-u8">
        <h2 className="text-2xl">Company</h2>
        <dl className="grid gap-u6 sm:grid-cols-2">
          <Row label="Registered name">{v.legal_name}</Row><Row label="Trading name">{v.trade_name}</Row>
          <Row label="Tax ID">{v.tax_id}</Row><Row label="Registration number">{v.registration_number}</Row>
          <Row label="Website">{v.website ? <a href={v.website} target="_blank" rel="noopener noreferrer nofollow" className="underline underline-offset-4">{v.website}</a> : null}</Row>
          <Row label="Vendor number">{v.number}</Row>
          <div className="sm:col-span-2"><Row label="About the company">{v.description}</Row></div>
        </dl>
      </Card>

      <Card className="flex flex-col gap-u8">
        <h2 className="text-2xl">Address and terms</h2>
        <dl className="grid gap-u6 sm:grid-cols-2">
          <Row label="Address">{address}</Row>
          <div className="flex flex-col gap-u6"><Row label="Payment terms">{paymentTerms(v.payment_terms_days)}</Row><Row label="Invoice currency">{v.currency}</Row></div>
        </dl>
      </Card>

      <Card className="flex flex-col gap-u8">
        <h2 className="text-2xl">What you supply</h2>
        {v.categories.length === 0 ? <p className="text-muted">No categories chosen yet.</p> : (
          <ul className="flex flex-wrap gap-u3" aria-label="Categories">{v.categories.map((c) => <li key={c} className="rounded-full bg-pill px-u6 py-u2 text-sm">{label(c)}</li>)}</ul>
        )}
      </Card>

      <Card className="flex flex-col gap-u8">
        <h2 className="text-2xl">Contacts</h2>
        {v.contacts.length === 0 ? <p className="text-muted">No contacts added yet.</p> : (
          <ul className="grid gap-u6 sm:grid-cols-2">
            {v.contacts.map((c) => (
              <li key={c.id} className="rounded-ctl border border-line p-u7">
                <p className="font-medium">{c.name}{c.is_primary && <span className="ml-u3 rounded-full bg-accent/30 px-u4 py-u1 text-xs">Primary contact</span>}</p>
                {c.job_title && <p className="text-sm text-muted">{c.job_title}</p>}
                <p className="break-all">{c.email}</p>{c.phone && <p>{c.phone}</p>}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="flex flex-col gap-u8">
        <h2 className="text-2xl">History</h2>
        <ol className="flex flex-col gap-u6">
          {[...v.history].reverse().map((h) => (
            <li key={h.id} className="border-l-2 border-line pl-u7">
              <p className="font-medium">{ACTION_LABEL[h.action] ?? h.action}</p>
              <p className="text-sm text-muted">{h.actor_name}, {dateTime(h.created_at)}</p>
              {h.note && <p className="mt-u2">{h.note}</p>}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  )
}
