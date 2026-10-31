# Test report: Phase 4

Environment: Node 22.22, Python 3.12, MySQL 8.0.46 installed in the build sandbox. No Docker, no browser.

## Results
| Check | Command | Result |
|---|---|---|
| Frontend typecheck, lint | `npm run typecheck`, `npm run lint` | Pass, zero warnings |
| Frontend tests | `npm test` | 99 of 99 passed (10 files) |
| Frontend production build | `npm run build` | Pass; Three.js and charts remain lazy chunks |
| Shared package | `cd backend/shared && pytest` | 18 of 18 passed |
| Auth service, SQLite / real MySQL | `pytest` | 62 passed, 1 skipped / 63 of 63 |
| Purchase request service, SQLite / real MySQL | `pytest` | 97 passed, 2 skipped / 99 of 99; 96% coverage |
| Approval service, SQLite / real MySQL | `pytest` | 73 passed, 3 skipped / 76 of 76; 95% coverage |
| Cross-service end-to-end, SQLite / real MySQL | `cd backend/tests && pytest` | 10 of 10 / 10 of 10 |
| Lint (shared, 3 services, e2e) | `ruff check .` | Pass |
| Dependency audits | `npm audit`, `pip-audit` (3 services) | No known vulnerabilities (a late `minimatch` advisory in lint tooling was fixed with an `overrides` pin) |
| Layout and secret scan | `scripts/validate-project.sh` | Pass |

(The skipped tests are the MySQL-only ones; they run, and pass, when `TEST_DATABASE_URL` points at MySQL.)

## What the new tests cover
**Approval rules:** approval levels at every threshold boundary and per currency; threshold and secret configuration validation; internal registration (idempotent, validated, route per amount); single, two and three level workflows; rejection with a reason ending the workflow; double decisions; nobody decides their own request; one person cannot approve two levels; every non-manager role, anonymous callers and invalid, expired, wrongly signed and service tokens refused on every endpoint; history order with identical timestamps; an outbox event for every change.
**Delegation:** only the delegate can decide; the delegate can pass it on; invalid targets (self, requester, unknown, someone who already approved); list of delegates and failure when the auth service is down.
**Keeping services in step:** decisions kept and delivered after an outage (down and 5xx), a refused decision recorded as a conflict and not retried, cancellation closing the workflow (idempotent, unknown request, after a decision), registration retried after an outage, failed registration never breaking submit, upgrade from a Phase 3 database.
**Internal security:** the decision endpoint and the registration endpoint accept only the right service; user tokens, even an admin's, are refused; disabled when no secret is configured.
**Queues and dashboards:** queue, my-decisions and all views; filters, literal wildcards, sorting, paging; summary figures; overdue flagging (once, not for fresh or decided items, next level starts its own clock).
**Real-process end-to-end (three services, real HTTP):** small request approved end to end; two-level request needing two different managers; rejection reason reaching the employee; delegation using the real manager list from the auth service; cancellation closing the approval; submitting while the approval service is down and catching up; a decision made while the request service is down delivered later; access enforced across services; queue content per manager; dashboard numbers from real data.
**Frontend:** manager dashboard on real data (counts, chart, approval route, empty and error states), approvals list (views, server-side search, filters, paging), approval detail (approve with comment, reject needs a reason, delegate, blocked reasons, pending and conflicting sync notices, errors), employee request page showing who decided and why, sidebar, access checks.

## Mutation checks (tests that must fail when a rule is broken)
Approval service: self-approval allowed, same manager on every level, delegation ignored, decided approvals decidable again, last level never completing, threshold off by one. Frontend: reject without a reason, buttons shown to managers who cannot act, list opening on the wrong view, delegate sending no user. Every change made a test fail; the code was restored afterwards.

## Real full-stack run (no browser)
Real MySQL, the bootstrap script with passwords containing `@ : / % #`, all three migrations, the admin CLI, the three services, and the Vite proxy; every call through the proxy.
- A 160,000 INR request needed two levels: the first manager's second approval was refused (403); the second manager completed it; the employee then saw it approved by that manager with his comment.
- The delegates list came from the real auth service and excluded the caller and non-managers.
- The employee token was refused on the approvals API (403). The internal API returned 404 through the proxy, and 401 directly without a service token or with an admin's user token.
- MySQL held the expected approval, steps (decided by the two managers) and outbox events; `approval_svc` was denied reading the other service's table; logs contained no tokens or passwords.

## Defects found and fixed in this phase
1. The shared contract accepted empty identifiers (an empty `request_id` created a workflow). Fixed with minimum lengths and a regression test.
2. A log field named `level` overwrote the log severity in the JSON output. Fixed in the shared formatter (extra fields can no longer overwrite core fields) and in the approval service, with tests.

## Docker configuration checks (no Docker available)
Compose file: references, build contexts, mounts, variables defined in `.env.example`, ports on 127.0.0.1, one database user per service, internal secret on every service, no start-up dependency between the Purchase Request and Approval services (each tolerates the other being down). Dockerfile COPY paths and ports. Image-equivalent run for the Approval service: clean install of the pinned requirements and the shared package, migration, server command, Dockerfile healthcheck command, refusal to start without the internal secret. The `db-init` script on real MySQL creates all three users and isolates them. All pass.

## Not executed
- `docker compose up`, building the images, in-container healthchecks and start-up ordering; MySQL 8.4 specifically (tested on 8.0).
- Any real-browser check: the manager screens (dashboard, queue, detail, dialogs), the employee screens, responsive layout, keyboard and screen-reader use, contrast, the Three.js scene.
- Load, failure-injection beyond stop/start of a service, penetration and cross-browser testing.
