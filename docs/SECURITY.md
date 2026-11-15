# Security notes (Phases 2 to 6)

## What is enforced
- **Authorization is server-side.** Every protected route checks the token, then loads the user so a role change or suspension takes effect immediately. Route guards in React only improve navigation.
- **Passwords:** argon2id, per-password salt, rehash on login when parameters change. Policy: 12 to 128 characters, a letter and a number, not containing the email name. Verifying an unknown email runs against a dummy hash to equalise timing.
- **Login abuse:** 5 failed attempts lock the account for 15 minutes. Wrong password and unknown email return the identical message.
- **Tokens:** access JWT pinned to HS256 with issuer, audience, expiry and type checks (`alg=none`, other algorithms, wrong secret, wrong audience and refresh-as-access are tested). Refresh tokens are opaque, hashed at rest, rotated on every use, and a late reuse revokes the whole family.
- **Browser storage:** no token in localStorage or sessionStorage. The access token is in memory; the refresh token is an HttpOnly, SameSite=Strict cookie limited to `/api/v1/auth`.
- **Secrets:** no defaults. The service refuses to start without `DATABASE_URL` and a `JWT_SECRET` of 32+ characters. The first admin is created with a CLI and a password you supply; there is no built-in account.
- **Least privilege:** the MySQL user `auth_svc` can reach only `auth_db` (tested: access to another database is denied). The init script rejects passwords containing quotes or backslashes so they cannot alter the SQL.
- **Database password handling:** passed as a separate variable and URL-encoded by the code, so characters such as `@`, `:`, `/`, `%` and `#` are safe.
- **Removed from Phase 1:** the unauthenticated role previews and `/app/*` access.
- Auth responses are `Cache-Control: no-store`. Logs are JSON and never contain passwords or tokens.

## Added in Phase 3
- **Ownership is enforced in the service, in the database query.** Employees can only load or change rows where `requester_id` is their own token subject. Someone else's request answers 404, so its existence is not revealed. Tested for read, edit, submit, cancel, delete and documents, and checked live across the two services.
- **Identity comes from the token only.** Fields such as `requester_id`, `status`, `number` or `total_amount` in a request body are ignored (tested).
- **Server-side state rules:** only drafts can be edited or deleted; submit re-validates; a stale `version` is refused, and write operations lock the row.
- **Input limits:** string lengths, numeric ranges and decimal places, 100 items, 10 documents, content-type allowlist (no SVG, HTML or executables), file names stripped of any path, control characters removed. Search treats `%` and `_` literally. Sorting accepts only listed columns.
- **Documents:** only metadata is stored; no file content is accepted or served, so there is no upload attack surface yet.
- **Least privilege:** `purchase_request_svc` can reach only `purchase_request_db`; verified live that it is denied `auth_db`.
- **Token staleness, observed:** after an administrator changed a user's role, that user's existing access token was still accepted by the Purchase Request service (HTTP 200) until it expired, at most 15 minutes. A new sign-in carried the new role and was refused (403). The auth service itself applies role changes immediately. Options for later: shorter tokens, or a revocation check.
- Frontend dependency upgrade: zod 3 to 4 to clear a new advisory (client-side validation only).

## Added in Phase 4
- **Separation of duties, enforced by the server:** nobody decides their own request; one person cannot approve two levels; a delegated approval can only be decided by the delegate; decided or cancelled approvals refuse further action. Each rule has a test that fails if the rule is removed (checked by deliberately breaking it).
- **Concurrency:** decisions lock the approval row, so two managers acting at once give one decision and one 409 (tested on real MySQL).
- **Service-to-service authentication:** separate secret (`INTERNAL_JWT_SECRET`), audience, token type and a named caller list. A user token cannot call an internal endpoint (even an administrator's) and a service token cannot be used on a public endpoint. Tested for wrong secret, wrong audience, wrong type, wrong caller, expired, unsigned and other algorithms.
- **Internal APIs are not exposed:** hidden from OpenAPI, not proxied (checked through the dev proxy: 404; direct without a token: 401).
- **Contracts are validated on both sides**, with non-empty identifiers, length limits and allowed values.
- **Least privilege:** `approval_svc` can reach only `approval_db` (verified: reading another service's table is denied).
- **Logs:** a bug where an extra log field called `level` replaced the severity was found and fixed; the shared formatter now prevents any extra field from overwriting a core field. Logs contain no tokens or passwords (checked in the live run).

## Added in Phase 5
- Vendors are isolated: a vendor user can read and change only the record whose `owner_id` is their token subject; anyone else gets 404. The owner comes from the token, never the body.
- The directory, summary and every review action need `vendor:read` or `vendor:verify`; employees, managers and finance get 403 on everything.
- Two-person verification and version-checked decisions (see `docs/API.md`). Every state change is written to the history with the actor, and to the outbox.
- Input is validated and cleaned (control characters removed, email, phone, web address, tax ID, category list). Web addresses must be http or https. Links open with `rel="noopener noreferrer nofollow"`.
- Unique indexes on tax ID and owner are the last guard against two requests racing; a clash returns 409, not 500 (tested).
- The internal vendor lookup returns no tax ID or owner, accepts only listed services with a service token, and is not routed by the dev proxy.
- A duplicate tax ID answers 409 with a message, which tells a vendor that the tax ID is registered. This is a deliberate usability choice.

## Added in Phase 6
- Procurement-only and vendor-only endpoints use different permissions; employees, managers, finance and administrators are refused everywhere on RFQs and quotations (tested for every endpoint).
- The vendor is identified from the signed token through the vendor service. A vendor id or header sent by the browser changes nothing. A vendor sees only RFQs they were invited to (404 otherwise, so another RFQ's existence is not revealed), only their own quotations, and never the budget, the internal estimates, other vendors or the award justification.
- Sealed bids: prices are hidden from procurement until the deadline or closing, drafts are never visible to procurement, and a vendor cannot change a submission after the deadline.
- Eligibility is re-checked at each step that matters (invite, issue, submit, select); an award needs the vendor service to be reachable, otherwise 503.
- Money is exact decimal in the database and in the API; quantities cannot be changed by vendors; unknown body fields (status, totals, vendor, owner) are ignored.
- Races end in 409, not 500 or a double award: unique indexes on one live RFQ per request, one active award per RFQ, one quotation and one invitation per vendor per RFQ, tested with the checks bypassed and with two real simultaneous requests on MySQL.
- Every state change is recorded in the history and the outbox; awards keep a snapshot of the scores, weights and evaluator notes used.
- The award contract is for listed services with a service token only; user tokens (even an administrator's) are refused.

## Known limitations (later phases)
- **Any manager can decide any request.** There is no department or reporting-line routing yet because there is no department directory. The history records who decided.
- Approval levels and the overdue time come from configuration, not an admin screen.
- A manager whose role is removed can still decide until their access token expires (up to 15 minutes), because services trust the signed role. Same window as the Purchase Request service.
- Overdue only flags and records; it does not notify or reassign (notifications arrive in Phase 10).
- Each service runs its own retry loop. With several replicas the loops overlap; this is safe because the calls are idempotent, only wasteful. Phase 11 replaces them with queues.
- Employees see only the final outcome, not which level their request is at.
- The outbox events are written but not yet published.
- Service tokens use a shared secret; per-service keys or mutual TLS would be stronger.
- No per-IP rate limiting yet (ingress, Phase 14). The 429 lockout response confirms an email exists, but only after repeated failures against it.
- No password reset by email (Phase 10), no forced change of an admin-set initial password, no MFA.
- Security events go to structured logs; they reach the Audit service in Phase 10.
- Access tokens use a shared secret. Services that verify them locally see a role change up to 15 minutes late; consider asymmetric keys before production.
- The Docker image and Compose stack were not run here (no Docker). The service and scripts were tested against a real MySQL 8.0 server instead.
- `npm audit` and `pip-audit` were clean when run. Re-run before each release.
- Vendor: documents (registration certificates, tax certificates) are not uploaded yet; only profile data is stored. A vendor registered by staff has no account link until an administrator-side linking feature exists. Suspending a vendor does not yet cancel anything in flight (no RFQs or orders exist). Notifications about verification arrive in Phase 10.
- RFQs and quotations: no attachments (specification documents, certificates) yet; vendors are not told about invitations or results until Phase 10 (the events are stored); one RFQ per request at a time and no partial awards or splitting an order between suppliers; no currency conversion; the evaluation criteria and weights are fixed in code; an award can be revoked even though no purchase order exists yet (Phase 7 will refuse it once one does).
