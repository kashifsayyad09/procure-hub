# Test report: Phase 6

Environment: Node 22.23, Python 3.12, MySQL 8.0.46 installed in the build sandbox. No Docker, no browser.

## Results
| Check | Command | Result |
|---|---|---|
| Frontend typecheck, lint | `npm run typecheck`, `npm run lint` | Pass, zero warnings |
| Frontend tests | `npm test` | 189 of 189 passed (12 files; 60 are new RFQ and quotation tests) |
| Frontend production build | `npm run build` | Pass; each RFQ screen is its own lazy chunk |
| Shared package | `cd backend/shared && pytest` | 18 of 18 passed |
| Auth service, SQLite | `pytest` | 62 passed, 1 skipped |
| Approval service, SQLite | `pytest` | 73 passed, 3 skipped |
| Purchase request service, SQLite / real MySQL | `pytest` | 103 passed, 2 skipped / 105 of 105 (6 new tests for the internal read API) |
| Vendor service, SQLite / real MySQL | `pytest` | 111 passed, 1 skipped / 112 of 112 (1 new test for the by-owner lookup) |
| Quotation service, SQLite / real MySQL | `pytest` | 235 passed, 2 skipped / 237 of 237 (includes a real two-simultaneous-requests selection race and the real-MySQL migration); 98% coverage |
| Cross-service end-to-end, SQLite / real MySQL | `cd backend/tests && pytest` | 17 of 17 / 17 of 17 (14 existing, 3 new) |
| Lint (shared, 5 services, e2e) | `ruff check .` | Pass |
| Dependency audits | `npm audit`, `pip-audit` (quotation service) | No known vulnerabilities |
| Layout and secret scan | `scripts/validate-project.sh` | Pass |

Not re-run on MySQL this phase: the auth and approval suites (neither changed; they passed on MySQL in Phase 4). The cross-service suite on MySQL connected as the MySQL root user; the restricted-user checks were done separately (below).

## What the new tests cover
**RFQ lifecycle:** creation from an approved request with exact copied items and budget; clarifications allowed but quantities fixed; non-approved, unknown and empty requests refused; one live RFQ per request, cancel frees it, and a race past the check stopped by the unique index (409, not 500); deadline rules (too close, past, too far, time-zone conversion); every field validation; edit a draft with the version, stale version, issued RFQs not editable; publish needs a vendor, a valid deadline and still-verified vendors; close, cancel (reason required), extend (later only, not after it passed); every illegal transition on a cancelled RFQ; history order; outbox events; failed creation leaves nothing behind; eligible-request list with live-RFQ marking; list filters, search with literal wildcards, sorting, paging, bad parameters; summary; other services down (503) or not configured, while reading own data still works.
**Invitations and vendor view:** verified vendors only (all or nothing); unknown vendors; duplicates (409); withdraw and re-invite without duplicating; inviting after issue sends at once but not after the deadline; vendors see only issued RFQs they were invited to (404 for others); no budget, estimate or other vendor in any vendor response; the vendor comes from the token, not from query strings or headers; withdrawn invitation removes access; decline; no profile (403), unverified or suspended vendors can read but not quote; vendor service down (503).
**Quotations:** every RFQ line created, totals computed by the server; exact decimal arithmetic (0.1 and 0.2 cases, half-up rounding to the cent, 4-decimal prices); quantities cannot be changed; vendors cannot set status, totals, vendor, number or version; every field validation (negative, NaN, huge, over-precise prices, bad currency, lead time, validity, duplicate and foreign lines); validity must reach the deadline; edit with version; submit needs lead time, validity and a price; one submission only; a racing second create stopped by the unique index; deadline, close and cancel stop quoting; withdraw and resubmit; vendors cannot touch each other's quotations (404); sealed prices (rows, detail and comparison refuse until open; drafts never visible to procurement).
**Comparison, evaluation, selection:** exact totals, missing items, lowest price and fastest, budget check, vendor status now; scores by hand-computed numbers (95.57, 100, 87.23, 84.33); mixed currencies kept apart with an explicit note; the comparison survives a vendor-service outage and says so, while selection refuses (503); evaluation validation, reasons required, versions, clearing a score, locked after award; selection refused before the deadline unless closed, auto-closes when past the deadline, justification required, foreign or non-submitted quotations refused, a vendor no longer verified cannot win, incomplete quotations need acknowledgement; repeating the same selection is harmless, a different one conflicts, the database refuses a second award even with the checks bypassed, a race past the checks is a 409, two real simultaneous selections on MySQL give exactly one award; vendors learn only the outcome of their own quotation; revoke needs a reason, reopens the choice, keeps history; awarded RFQs cannot be cancelled; the award contract has what a purchase order needs and nothing internal, is 404 before the award and after a revoke, and only listed services with the secret can read it.
**Scoring (pure unit tests):** weights add up to 100; price and delivery relative to the best in the same currency; overall only when all four parts exist; partial quotations not scored and not the benchmark; currencies never mixed; zero totals; ties; determinism and rounding.
**Authorization:** every endpoint refuses anonymous callers; employee, manager, finance, administrator and unknown roles refused on all of them; vendors refused on procurement endpoints and procurement on vendor endpoints; invalid, expired, wrongly signed, wrong audience, refresh-type and unsigned tokens; role from the token only; the request's approval status read from the purchase request service, not the body; mass assignment ignored; injection-style inputs harmless.
**Operations:** health, OpenAPI, docs switch, configuration validation, request ids, migration matches models and downgrades, valid MySQL DDL with the guarding unique indexes, DECIMAL money, no foreign keys into other services, and the same on real MySQL.
**Real-process end-to-end (five services, tokens from the real auth service):** employee request approved by a manager; procurement sees it as eligible and cannot start an RFQ from a draft request; RFQ, invitations, issue; vendors invited only see it, a never-invited vendor gets 404 and an unregistered vendor 403; no budget leaks; quotations submitted; competitor cannot read; prices sealed; deadline passes (real wait); late withdrawal refused; comparison, evaluation, ranking (87.23 and 84.33), selection; a second selection by another officer refused; outcomes visible to vendors; award contract readable by a service token only. A vendor suspended after the invitation cannot quote.
**Frontend:** exact-decimal helper and time helpers; submission-problem rules; RFQ list (figures, server-side filters, search, paging, empty and error states); new-RFQ flow (approved requests, existing-RFQ link instead of a second RFQ, validation, correct request body with a UTC deadline, server refusal); RFQ detail (sealed notice, draft vs issued actions, issue refused message, cancel needs a reason, extend sends the version, invitation picker uses verified vendors only and excludes already-invited, withdraw hidden after submission, award panel, error state); edit page; comparison (side-by-side table, currencies kept apart, sorting and filtering, sealed state, empty state, vendor-status warning, evaluation dialog with reasons and version, selection needs justification and acknowledgement for missing items, server refusal shown, revoke with reason and history); vendor list (register-first, badges, empty and error states); vendor RFQ detail (no budget, start or decline, why blocked, missing items for a draft, withdraw, outcome, refusals, 404); quotation form (exact total preview, correct body, submit gated, validation, save and submit, edit with version, read-only when submitted); access for every role.

## Mutation checks (tests that must fail when a rule is broken)
Quotation service (12): prices never sealed, duplicate invitations allowed, invitation scope removed, deadline not enforced on quoting, unverified vendors invitable, selection skipping the vendor check, quotation ownership not checked, approved-only check removed, price score inverted, missing items not acknowledged, drafts visible to staff, currencies mixed in scoring; plus the unique index on live RFQs removed. Frontend (7): cancel without a reason, missing items without acknowledgement, justification length, money rounding half down, withdraw shown after submission, submit not gated, evaluation version not sent. Every change made a test fail; the code was restored afterwards.

## Real full-stack runs (no browser)
Real MySQL 8.0.46. The bootstrap script with a password containing `@ : / % #` created `quotation_svc` (and refuses to run without `QUOTATION_DB_PASSWORD`). Migrations ran as each service's restricted user; the quotation migration also downgraded and upgraded as `quotation_svc`. `quotation_svc` is denied reading `vendor_db` and `purchase_request_db`. All money columns are `DECIMAL`. A real quotation-service process ran as `quotation_svc`: health ready, a procurement token got the summary, an employee got 403, an anonymous call 401, an unconfigured dependency 503, and the log held no password or token.

## Defects found and fixed in this phase
1. Editing a quotation draft failed with a 409 "clashes with an existing record": new line rows were inserted before the old ones were deleted and hit the unique index (the same class of bug as Phase 5). Fixed, with regression tests.
2. Two awards for the same RFQ within one second had no stable order on MySQL (timestamps have 1-second precision). Added an explicit per-RFQ sequence to selections.
3. The autogenerated migration downgrade dropped indexes before the tables that need them for foreign keys, which MySQL refuses. The downgrade now drops tables, children first.
4. A manual score of 0 was shown as `0` while all others had two decimals; manual scores now always have two decimals.
5. Dead code removed (a vendor-unavailable branch that could never run).

## Docker configuration checks (no Docker available)
Compose: the new `quotation-migrate` and `quotation-service` entries follow the existing pattern (one database user, secrets from `.env`, ports on 127.0.0.1, service URLs by Compose DNS name); `QUOTATION_DB_PASSWORD` is in `.env.example` and the `db-init` service. The Dockerfile is the approved pattern with the name and port changed. Not built or started.

## Not executed
- `docker compose up`, building the images, in-container healthchecks; MySQL 8.4 specifically (tested on 8.0).
- Any real-browser check: the new screens, the comparison table at narrow widths, keyboard and screen-reader use, contrast. The frontend tests use a mocked API; the real API was exercised by the backend and end-to-end tests.
- Auth and approval suites on MySQL in this phase.
- Load, failure-injection, penetration and cross-browser testing.


---

# Earlier phase report (kept for history)

## Phase 5 report

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
