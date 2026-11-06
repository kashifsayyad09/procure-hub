# Test report: Phase 5

Environment: Node 22.23, Python 3.12, MySQL 8.0.46 installed in the build sandbox. No Docker, no browser.

## Results
| Check | Command | Result |
|---|---|---|
| Frontend typecheck, lint | `npm run typecheck`, `npm run lint` | Pass, zero warnings |
| Frontend tests | `npm test` | 129 of 129 passed (11 files; 31 are new vendor tests) |
| Frontend production build | `npm run build` | Pass; Three.js and charts remain lazy chunks, the vendor form is its own chunk |
| Shared package | `cd backend/shared && pytest` | 18 of 18 passed |
| Auth service, SQLite | `pytest` | 62 passed, 1 skipped |
| Purchase request service, SQLite | `pytest` | 97 passed, 2 skipped |
| Approval service, SQLite | `pytest` | 73 passed, 3 skipped |
| Vendor service, SQLite / real MySQL | `pytest` | 110 passed, 1 skipped / 111 of 111; 98% coverage |
| Cross-service end-to-end, SQLite / real MySQL | `cd backend/tests && pytest` | 14 of 14 / 14 of 14 (10 existing, 4 new) |
| Lint (shared, 4 services, e2e) | `ruff check .` | Pass |
| Dependency audits | `npm audit`, `pip-audit` (vendor service) | No known vulnerabilities |
| Layout and secret scan | `scripts/validate-project.sh` | Pass |

The Auth, Purchase Request and Approval suites were run on SQLite only in this phase (they passed on MySQL in Phase 4; Phase 5 changed only the shared permission matrix, which they exercise on SQLite).

## What the new tests cover
**Registration and profile:** vendor registers as a draft; owner and status come from the token, not the body; sequential numbers; one record per vendor user; staff onboarding of a vendor without an account; the same tax ID refused however it is typed; drafts with only a name; every field validation (name, tax ID, website scheme, country, payment terms, currency, categories, descriptions, contact email and phone, duplicate contact emails, two primaries, contact limit); first contact becomes primary; text cleaning and category de-duplication; update, stale version, tax ID clashes; vendors cannot read or change each other's records; unknown fields ignored; responses carry no owner id; outbox events written with the change and absent when the request fails; two requests racing past the checks stopped by the unique indexes (409, not 500).
**Verification:** submit lists what is missing; pending, verified, sent back (reason required, visible to the vendor), fixed and resubmitted; suspend and reinstate; only the right states allow each step; a suspended vendor cannot edit but staff can; identity changes on a verified vendor need verification again, other changes do not; a reviewer cannot decide on their own submission or on a change they made; a profile edited after a reviewer opened it must be reviewed again; the actions offered match caller and state; the full history order; outbox events for every decision; vendors cannot use review endpoints.
**Authorization:** every endpoint refuses anonymous callers; invalid, expired, wrongly signed, wrong audience, refresh-type and unsigned tokens; employee, manager and finance refused everywhere; vendors refused on the directory, summary, onboarding and review endpoints; procurement and administrators have no profile of their own; a forged role header changes nothing.
**Queries and internal API:** directory filters (status, category, country), search on name, number, tax ID and city with `%` and `_` treated literally, sorting, paging and bad parameters; list items hold no private detail; summary figures; internal lookup returns status and no private fields, leaves out unknown ids, refuses user tokens (even an administrator's), unlisted services, wrong secrets; disabled without a secret and hidden from the docs. Migration matches the models, downgrades, produces valid MySQL DDL, and runs on a real MySQL server.
**Real-process end-to-end (four services, tokens from the real auth service):** a vendor registers, submits, procurement verifies; a vendor cannot verify themselves; vendors cannot see each other; the directory is refused to vendors, employees and managers; staff onboard a vendor and a second reviewer verifies it; a service token can look up vendor status and a user token cannot.
**Frontend:** vendor dashboard (not registered, progress and missing items, error with retry); profile page (reason it was sent back, only the actions the server offers, submit refused with the server's message); the four-step form (right request body, one primary contact, validation blocks a step and says what to fix); suspended vendors do not get the form; directory (figures, server-side filter, search and paging, empty and error states, opening a vendor under the right area for each role); review dialogs (verify sends the reviewed version and note, reasons required, suspend and reinstate, reviewer-blocked message, stale-version message); staff onboarding; other roles kept out; form rule helpers.

## Mutation checks (tests that must fail when a rule is broken)
Vendor service: self-verification allowed, stale version ignored, no re-verification after an identity change, vendors seeing every vendor, suspended vendors able to edit, submission skipping the completeness check, tax IDs not normalised. Frontend: reason not required in the dialog, wrong version sent on verify, primary contact ignored. Every change made a test fail; the code was restored afterwards.

## Real full-stack run (no browser)
Real MySQL 8.0.46, the bootstrap script with a password containing `@ : / % #` (it refuses to run without `VENDOR_DB_PASSWORD`), the migration run as `vendor_svc`, and a real service process. A vendor was registered, submitted and verified over HTTP; MySQL held the vendor and its three outbox events; `vendor_svc` was denied reading `approval_db`; the service log contained no password or token.

## Defects found and fixed in this phase
1. Saving a profile with unchanged categories failed with a 500: the database inserted the new category rows before deleting the old ones and hit the unique index. Fixed (old rows are removed first), with a regression test.
2. A registration race (two requests with the same tax ID or owner) would have returned a 500 because the clash surfaced while flushing, before the guarded commit. Fixed (clashes are translated to 409 at both points), with a test that forces the race.
3. The Phase 4 `package-lock.json` did not match `package.json` (`npm ci` failed on an `ajv` and `json-schema-traverse` mismatch). Regenerated with `npm install`: 3 packages added, 2 re-hoisted, no direct dependency changed; `npm audit` reports none.

## Docker configuration checks (no Docker available)
Compose file: the new `vendor-migrate` and `vendor-service` entries follow the existing pattern (build context, one database user, ports on 127.0.0.1, secrets from `.env`); `VENDOR_DB_PASSWORD` is in `.env.example` and the `db-init` service. The Dockerfile is the approved pattern with the service name and port changed. The bootstrap script ran on real MySQL. Not built or started.

## Not executed
- `docker compose up`, building the images, in-container healthchecks; MySQL 8.4 specifically (tested on 8.0).
- Any real-browser check: the vendor portal, the directory, the review dialogs, the form, responsive layout, keyboard and screen-reader use, contrast.
- Auth, Purchase Request and Approval suites on MySQL in this phase.
- Load, failure-injection, penetration and cross-browser testing.
