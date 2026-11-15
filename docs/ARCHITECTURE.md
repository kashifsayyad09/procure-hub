# Architecture (Phase 1 snapshot)

Target architecture is defined in the master build prompt: 11 FastAPI business services plus API gateway and MCP server on EKS, MySQL on RDS, SQS, NGINX ingress, Terraform, GitHub Actions and Argo CD. Phase 1 implements only the frontend foundation and the local database container.

## Frontend structure
- `src/components/ui` primitives; `layout` shell and dashboard template; `tables`, `charts`, `forms`
- `src/animations/gsap`: single GSAP entry (ScrollTrigger registered once), `useGsap` (scoped context, reverts on unmount, skipped under reduced motion), `useCountUp`, presets
- `src/three`: `SceneBackdrop` (lazy, WebGL and reduced-motion fallback) and `ParticleNetwork` (R3F, pauses when tab hidden)
- `src/stores`: Zustand for theme and sidebar; TanStack Query for server state
- `src/services/mockData.ts`: sample data and a simulated fetch, replaced by real APIs from Phase 2

## Performance
Three.js and Recharts are in lazy chunks and are not part of the entry bundle (entry about 120 kB gzip).

## Phase 2 additions
```
Browser --/api/v1--> (Vite proxy in dev, ingress later) --> auth-service --> auth_db
```
- `backend/services/auth-service`: FastAPI app factory (`app.main:create_app`), SQLAlchemy 2, Alembic, Pydantic settings, JSON logging with request IDs.
- Frontend: `services/api.ts` (memory token, one shared silent refresh, one retry), `stores/authStore.ts`, `components/auth/RequireAuth.tsx`, `pages/admin/UsersPage.tsx`.
- Other services will verify the same JWT (shared secret, issuer and audience) and check the permission they need.

## Phase 3 additions
```
Browser --/api/v1--> Vite proxy (dev) --+--> auth-service (8001)             --> auth_db
                     ingress (later)    +--> purchase-request-service (8002) --> purchase_request_db
```
- **Shared package** `backend/shared/procurehub_common`: roles, permission matrix, token verification, logging, request-ID middleware, health routes, DB URL builder. No database models, so services stay independent.
- **Token flow:** the auth service signs the access token (it now also carries the user's name and email). The Purchase Request service verifies the signature, issuer, audience and expiry itself and takes the role from the token. It never calls the auth service per request and has no foreign key to its users.
- **Purchase request service layers:** thin routers, `service.py` for business rules and ownership, SQLAlchemy models, Pydantic schemas. History and documents carry an explicit sequence number because MySQL timestamps only have one-second precision.
- **Frontend:** `features/purchase-requests` (types, exact money helpers, status badge, timeline), employee pages for the dashboard, list, multi-step form and detail. The employee dashboard now uses real data; the other roles still use sample data.
- **Database setup:** a one-shot `db-init` container runs `infrastructure/docker/db-bootstrap/bootstrap.sh` on every `docker compose up`. It is idempotent, so new services and changed passwords reach an existing data volume.

## Phase 4 additions: how the services work together
```
employee --submit--> purchase-request-service --register (service token)--> approval-service <--decide-- manager
                          ^                                                      |
                          +------- decision (service token), retried until delivered
```
**Design decision.** Each service is the only writer of its own database. The Purchase Request service owns the request; the Approval service owns the approval workflow and keeps a snapshot of what managers must see, so it never reads another service's tables. They talk through authenticated internal calls that are idempotent:

1. Submit saves the request as `submitted`, then registers it with the Approval service. If that call fails, the employee is not blocked; `approval_registered` stays false and a retry loop (every 20 s) registers it later. Registration is idempotent.
2. A final decision is saved first in the Approval service (`decision_sync = pending`), then pushed to the Purchase Request service. If that fails the manager is not blocked; a retry loop delivers it. A refusal (for example the requester cancelled in the meantime) is recorded as `conflict` and shown to the manager.
3. If the requester cancels, the Approval service is told and closes the workflow; if that message is lost, a later decision is refused with a conflict.
4. Every state change also writes a row to an **outbox table** (`approval_events`) in the same transaction. Phase 10 (notifications, audit) and Phase 11 (SQS) will publish these; Phase 11 replaces the two retry loops with queues and dead-letter handling.

**Service-to-service security.** Separate secret, audience and token type from user tokens; short lifetime; the receiver names which callers it accepts. Internal paths live under `/internal` and are hidden from OpenAPI. They must not be routed by the ingress (Phase 14 adds network policies too).

**Shared package additions:** service tokens, an HTTP client (short timeouts, one retry on network errors, request-ID propagation, `ServiceUnavailable` vs `ServiceRejected`), message contracts, and the user-token dependencies that were duplicated.
**Request ID** is propagated on every service call, so one transaction can be followed through all three logs.

## Phase 5 additions: vendors
- **vendor-service** (port 8004, `vendor_db`) follows the same layout as the other services: app factory, `service.py` for rules, thin routers, Alembic migration, outbox.
- **Ownership:** a vendor record stores the auth user id of its owner (no cross-database key). Vendor users see only that record. Procurement and administrators see all, and can register vendors that have no account yet.
- **Verification** is a two-person control: whoever submitted a profile (or changed a verified vendor's identity details) cannot be the one to verify it.
- **For later services:** an internal lookup (`VendorRef` contract in `procurehub_common`) lets the Quotation service check vendor status without touching `vendor_db`.
- **Frontend:** `features/vendors` (types, labels, status badge, shared profile view, form, action buttons), vendor pages under `/app/vendor`, staff pages under `/app/procurement/vendors` and `/app/admin/vendors` (same components, the base path comes from the role). The server returns the list of `actions` the caller may take, so screens never offer what will be refused.
- **Dev proxy:** `/api/v1/vendors` goes to port 8004.

## Phase 6 additions: RFQs and quotations
- **quotation-service** (port 8005, `quotation_db`) has the same layout as the other services, plus `scoring.py` (pure functions), `evaluation.py` (comparison, evaluation, selection) and `common.py` (calls to other services).
- **Calls out, never into other databases:** the purchase request service (approved requests, via a new internal API and `PurchaseRequestRef` contract) and the vendor service (lookup of vendor status, and by-owner lookup that turns a signed-in vendor user into a vendor).
- **Calls in:** the purchase order service (Phase 7) reads an award through `AwardRef`.
- **Sealed bids** are enforced by the service, not the screens: prices are `null` or 409 until the deadline passes or the RFQ is closed; vendors never receive budgets or other vendors' data.
- **Frontend:** `features/rfqs` (types, labels, badges, form, invite and compare dialogs, exact-decimal helper), procurement pages under `/app/procurement/rfqs`, vendor pages under `/app/vendor/rfqs`. The server returns the `actions` each caller may take. Dev proxy sends `/api/v1/rfqs` and `/api/v1/quotations` to port 8005.
- **Lifecycle:** RFQ draft, issued, closed, awarded (cancelled from draft, issued or closed; revoke returns awarded to closed). Quotation draft, submitted (back to draft by withdrawing), selected or not selected. An RFQ that is issued and past its deadline behaves as closed for comparison and selection (selecting closes it).
