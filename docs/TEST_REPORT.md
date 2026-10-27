# Test report: Phase 3

Environment: Node 22.22, Python 3.12, MySQL 8.0.46 installed in the build sandbox. No Docker, no browser.

## Results
| Check | Command | Result |
|---|---|---|
| Frontend typecheck (strict) | `cd frontend && npm run typecheck` | Pass |
| Frontend lint, zero warnings | `npm run lint` | Pass |
| Frontend tests | `npm test` | 83 of 83 passed (9 files) |
| Frontend production build | `npm run build` | Pass. Entry bundle 123 kB gzipped; Three.js and charts are lazy chunks, nothing preloaded |
| Frontend dependency audit | `npm audit` | 0 vulnerabilities (after upgrading zod 3 to 4 for a new advisory) |
| Auth service lint | `ruff check .` | Pass |
| Auth service tests, SQLite | `pytest -q` | 59 passed, 1 skipped (the MySQL-only migration test) |
| Auth service tests, real MySQL | `TEST_DATABASE_URL=... pytest -q` | 60 of 60 passed |
| Purchase request service lint | `ruff check .` | Pass |
| Purchase request tests, SQLite | `pytest -q` | 79 passed, 2 skipped (MySQL-only), 99% line coverage |
| Purchase request tests, real MySQL | `TEST_DATABASE_URL=... pytest -q` | 81 of 81 passed, including the migration and 36 concurrent creates |
| Python dependency audit | `pip-audit -r requirements.txt` | No known vulnerabilities (both services) |
| Layout and secret scan | `scripts/validate-project.sh` | Pass |

## What the new tests cover
**Purchase request service (backend):** create, validation of every field and limit, text cleaning, exact decimal totals (half-up rounding, no float drift), sequential unique numbers; edit with a version lock (stale edits refused); delete drafts; submit rules (every missing item reported at once, double submit, locked after submit); cancel with a reason; approved and rejected requests locked; documents (allowlist, size, path stripping, limit of 10, draft only); list filters, search with literal wildcards, sorting limited to listed columns, paging, date range; summary counts, per-currency totals, month buckets; every endpoint rejecting anonymous callers; invalid, expired, wrongly signed, wrong audience, wrong issuer, wrong type, other-algorithm and unsigned tokens; vendor, finance, admin, manager and unknown roles refused; employees unable to see or change each other's requests; identity taken from the token, not the body; procurement limited to approved requests and read-only; SQL-injection strings; health and OpenAPI; refusal to start without a strong secret; history and documents ordering when timestamps are identical; migration up, no drift, down, valid MySQL DDL; concurrent numbering on MySQL.
**Auth service:** the 59 existing tests still pass after moving shared code into `procurehub_common`; one new test checks the token's name and email claims.
**Frontend:** exact money preview (matches the server's rounding, beyond Number's safe range), form rules mirroring the server, submit problems in plain language, timeline states, API query building and field-named errors, the dashboard on real data (counts, chart data, recent table, empty state, error state), request list (server-side search, filter, sort, paging, two kinds of empty state), the three-step form (valid and invalid paths, version sent on edit, server errors, submit flow), the detail page (actions per status, delete confirmation, cancel needs a reason, document checks before any server call, draft-only controls hidden), and access checks.

## Mutation checks (tests that must fail when a rule is broken)
Backend: employee ownership scope ignored; no version check; edits allowed after submit; writes not limited to the owner. Frontend: rounding down instead of half-up; edit not sending the loaded version; Submit enabled despite problems. Each change made a test fail, and the code was restored afterwards.

## Real-service end-to-end check (no browser)
Real MySQL, the bootstrap script, both migrations, the admin CLI, both services and the Vite proxy; all calls through the proxy.
- A token issued by the auth service was accepted by the Purchase Request service. A request was created, submitted (a second submit gave 409) and listed; a submitted request refused a document change (409).
- Another employee got 404 for it and saw an empty list; admin and vendor got 403; no token and a tampered token got 401.
- Procurement saw 0 requests until the request was approved in the database, then 1, and could not create requests (403).
- Totals were exact: 2.5 x 19.99 + 3 x 0.10 = 50.28.
- MySQL held the expected rows; history was stored in order; logs contained no tokens or passwords.
- Observed token staleness: after an admin changed a user's role, the user's old token still returned 200 at the Purchase Request service until expiry (at most 15 minutes); signing in again gave a token with the new role, refused with 403.

## Docker configuration checks (no Docker available)
- Compose file: references, build contexts and Dockerfile paths, bind mounts, variables defined in `.env.example`, ports on 127.0.0.1 only, each service has its own database user. Pass (scripted).
- Dockerfile COPY targets exist in the `backend/` build context and are not excluded by `.dockerignore`; ports consistent; non-root user; healthcheck present. Pass.
- Image-equivalent run for the Purchase Request service: clean install of the pinned requirements plus the shared package as a normal package, then the migrate command, the server command, the Dockerfile healthcheck command, and refusal to start without a secret or a database setting. Pass.
- `db-init` bootstrap script on real MySQL: works on an already-initialised server, creates the new service user, applies a changed password, rejects quotes and missing values before running SQL, is safe to re-run, and each service user is denied the other's database. Pass.

## Not executed
- `docker compose up`, building the images, the in-container healthchecks and start-up ordering; MySQL 8.4 specifically (tested on 8.0).
- Any real-browser check: the new employee screens (dashboard, list, three-step form, detail), responsive layout, keyboard and screen-reader use, colour contrast, the Three.js scene.
- Load, penetration and cross-browser testing.

## Notes
- Starlette prints a deprecation warning about its test client; Recharts and jsdom print size messages in frontend tests. Neither affects results.
