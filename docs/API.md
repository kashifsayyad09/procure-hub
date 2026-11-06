# API (Phase 2: authentication service)

Base path `/api/v1`. Interactive OpenAPI docs: `/docs` on the service (disable with `DOCS_ENABLED=false`).
The browser always calls same-origin `/api/v1/...`; Vite proxies it in development and the ingress will in production.

## Sessions
- **Access token:** JWT (HS256, 15 minutes) returned in the response body. The frontend keeps it in memory only and sends `Authorization: Bearer ...`.
- **Refresh token:** random 384-bit value in an `HttpOnly; SameSite=Strict; Path=/api/v1/auth` cookie (`Secure` unless `COOKIE_SECURE=false`). Single use: every refresh issues a new one. Stored hashed (SHA-256).
- Claims: `iss`, `aud`, `sub` (user id), `role`, `typ=access`, `jti`, `iat`, `exp`.

## Endpoints
| Method and path | Who | Result |
|---|---|---|
| `POST /auth/login` `{email, password}` | anyone | 200 token + user + permissions, sets cookie. 401 wrong credentials, 403 suspended, 429 locked |
| `POST /auth/refresh` | cookie | 200 new token and cookie. 401 invalid, expired or reused (a late reuse revokes the whole session family) |
| `POST /auth/logout` | cookie | 204, revokes the session family, clears cookie |
| `POST /auth/logout-all` | signed in | 204, revokes every session of the user |
| `GET /auth/me` | signed in | current user and permissions |
| `POST /auth/change-password` | signed in | 204, ends all sessions. 400 wrong current password, 422 policy |
| `GET /users` | `user:read` | paged list. Query: `q`, `role`, `is_active`, `page`, `page_size` (max 100) |
| `POST /users` | `user:manage` | 201. 409 duplicate email, 422 policy |
| `GET /users/{id}` | `user:read` | 404 if unknown |
| `PATCH /users/{id}` | `user:manage` | change `full_name`, `role`, `is_active`. A role change or suspension ends the user's sessions. 409 if you target yourself |
| `GET /health/live`, `GET /health/ready` | open | liveness, and readiness (checks the database) |

## Roles and permissions
`employee`, `manager`, `procurement`, `vendor`, `finance`, `admin`. The full matrix is in `app/permissions.py`
(for example only `admin` holds `user:manage` and `role:assign`, only `manager` holds `approval:decide`). Later services reuse these names.

Errors are `{"detail": "message"}` (or a list of messages for validation). Every response carries `X-Request-ID`.

---

# API (Phase 3: purchase request service)

Base path `/api/v1/purchase-requests`. Same bearer token as the auth service. Money and quantities are JSON **strings** (for example `"49.98"`) so no precision is lost.

| Method and path | Who | Result |
|---|---|---|
| `GET /summary` | employee, procurement | counts per status, open value per currency, requests per month (last 6) |
| `GET /` | employee (own), procurement (approved only) | paged list. Query: `status`, `priority`, `q` (number, title, requester), `created_from`, `created_to`, `sort` (`created_at`, `total_amount`, `needed_by`, `number`, `status`, `updated_at`), `order`, `page`, `page_size` (max 100) |
| `POST /` | employee | 201 draft. Title is required; everything else may be filled in later |
| `GET /{id}` | owner, or procurement if approved | full request with items, documents and history. 404 if not visible |
| `PUT /{id}` | owner | replace a draft. Body includes the `version` you loaded. 409 if the version is stale or the request is not a draft |
| `POST /{id}/submit` | owner | draft to submitted. 422 lists everything still missing. 409 if not a draft |
| `POST /{id}/cancel` `{reason}` | owner | submitted to cancelled. 409 for drafts (delete them) and for approved or rejected requests |
| `DELETE /{id}` | owner | 204, drafts only |
| `POST /{id}/documents` `{file_name, content_type, size_bytes}` | owner, draft only | 201. Records the file's details only (`content_stored` is `false`) |
| `DELETE /{id}/documents/{doc_id}` | owner, draft only | 204 |

**Statuses:** `draft`, `submitted`, `approved`, `rejected`, `cancelled`. The Approval service (Phase 4) will move `submitted` to `approved` or `rejected`.
**Numbers:** `PR-<year>-<6 digits>`, allocated under a database lock so concurrent requests never share one. Deleting a draft leaves a gap.
**Limits:** 100 items per request, 10 documents, documents up to 10 MB of type PDF, PNG, JPEG, TXT, CSV, DOCX or XLSX. Currencies INR, USD, EUR, GBP.
**Errors:** `{"detail": "message"}`, or a list of messages for validation and submit problems.

---

# API (Phase 4: approval service)

Base path `/api/v1/approvals`. Managers only (`approval:read`, `approval:decide`, `approval:delegate`). Same bearer token as the other services.

| Method and path | Result |
|---|---|
| `GET /summary` | `waiting_for_me`, `overdue_for_me`, `delegated_to_me`, `decided_by_me_30d`, `approved_30d`, `rejected_30d`, `approved_value_30d` (per currency), `avg_decision_hours_30d`, `monthly` decisions (6 months) |
| `GET /` | paged list. `view`: `queue` (what I can decide now, longest waiting first by default), `mine` (I decided or was given), `all`. Also `status`, `priority`, `q`, `sort`, `order`, `page`, `page_size` (max 100) |
| `GET /{id}` | snapshot of the request, items, steps, history, and for the caller `can_decide` with a plain-language `blocked_reason` |
| `POST /{id}/approve` `{comment?}` | approves the current level. After the last level the request is approved |
| `POST /{id}/reject` `{reason}` | reason of at least 3 characters. Ends the workflow immediately |
| `POST /{id}/delegate` `{user_id, note?}` | hands the current level to another active manager. Only that manager can then decide |
| `GET /delegates` | managers a decision can be delegated to (never yourself) |

**Rules:** nobody decides their own request; one person cannot approve two levels of the same request; a delegated step can be decided only by the delegate; a decided or cancelled approval answers 409 to any further action (so two managers acting at once produce exactly one decision).
**Levels** depend on the total, per currency, from configuration (defaults: INR 1 level below 1,00,000, 2 levels from 1,00,000, 3 from 10,00,000; USD 1,500 and 15,000; EUR 1,400 and 14,000; GBP 1,200 and 12,000). A currency with no thresholds gets the strictest route. Amounts are never converted.
**Overdue:** a step waiting more than `ESCALATION_HOURS` (48) is flagged once and recorded in the history. Any eligible manager can still decide.

## Internal APIs (service to service, never through the ingress)
Called with a service token (`Authorization: Bearer ...`, separate secret `INTERNAL_JWT_SECRET`, audience `procurehub-internal`, type `service`, issuer equal to subject). User tokens are refused, even an administrator's.

| Call | Caller | Purpose |
|---|---|---|
| `POST /internal/v1/approvals` (approval service) | purchase-request-service | register a submitted request. Idempotent on `request_id` |
| `POST /internal/v1/approvals/{request_id}/cancel` (approval service) | purchase-request-service | the requester cancelled. Idempotent |
| `POST /internal/v1/purchase-requests/{id}/decision` (purchase request service) | approval-service | final approved or rejected. Idempotent; 409 if the request is no longer submitted |
| `GET /internal/v1/users?role=manager` (auth service) | approval-service | active managers, for delegation |

Message shapes live in `backend/shared/procurehub_common/contracts/approval.py` (versioned, validated on both sides).

# API (Phase 5: vendor service)

Base path `/api/v1/vendors`. Same bearer token as the other services. Vendor users (`vendor_profile:manage`) reach only the record they own; procurement and administrators (`vendor:read`, `vendor:manage`, `vendor:verify`) reach all of them. Someone else's record answers 404, never 403.

| Method and path | Who | Result |
|---|---|---|
| `GET /categories` | vendor, procurement, admin | the fixed category list `[{id, label}]` |
| `GET /summary` | procurement, admin | `counts` per status, `verified_by_category`, `monthly` registrations (6 months) |
| `GET /me` | vendor | the caller's own vendor record, or 404 until they register |
| `POST /` | vendor | registers the caller's company as a draft. One record per vendor user (409 after that) |
| `POST /onboard` | procurement, admin | registers a vendor with no linked account yet |
| `GET /` | procurement, admin | paged directory. `status`, `category`, `country`, `q` (name, number, tax ID, city; wildcards are literal), `sort`, `order`, `page`, `page_size` (max 100) |
| `GET /{id}` | owner, procurement, admin | full record: profile, contacts, history, `completeness`, and for the caller `actions` plus a plain-language `blocked_reason` |
| `PUT /{id}` | owner, procurement, admin | replaces the profile; body carries the `version` it was loaded at (409 if stale) |
| `POST /{id}/submit` | owner, procurement, admin | draft or sent-back to pending. 422 lists what is missing |
| `POST /{id}/verify` `{version, note?}` | procurement, admin | pending to verified |
| `POST /{id}/reject` `{version, reason}` | procurement, admin | pending to rejected (sent back); the vendor sees the reason |
| `POST /{id}/suspend` `{version, reason}` | procurement, admin | verified to suspended |
| `POST /{id}/reinstate` `{version, note?}` | procurement, admin | suspended to verified |

**Status flow:** draft, then pending, then verified or rejected (rejected goes back to pending after the vendor fixes it); verified can be suspended and reinstated.
**Rules:** a reviewer cannot verify or reject a profile they submitted themselves (403), so two people are always involved; verify, reject, suspend and reinstate carry the `version` the reviewer looked at, so a profile edited meanwhile must be looked at again (409); changing the company name, tax ID, registration number or country of a verified vendor puts it back to pending; a suspended vendor cannot edit its own profile; tax IDs are normalised (upper case, letters and digits only) and unique; the owner always comes from the token, never the body. Submitting needs: tax ID, street address, city, country, at least one category, and one contact with a name and an email.

## Internal API (service to service)
`GET /internal/v1/vendors/{id}` and `POST /internal/v1/vendors/lookup {ids}` (up to 100) return a `VendorRef` (`procurehub_common.contracts.vendor`): id, number, names, `status`, country, currency, payment terms, categories, primary contact. No tax ID, no owner. Unknown ids are left out of the lookup. Callers must be on the allowed list (quotation, purchase order, invoice, SI-Talker, MCP) and use a service token; user tokens, even an administrator's, are refused (401). Disabled (503) when `INTERNAL_JWT_SECRET` is not set. Phase 6 uses it to refuse RFQ invitations to vendors that are not `verified`.
