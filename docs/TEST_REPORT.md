# Test report: Phase 2

Environment: Node 22.22, Python 3.12, Linux container. No Docker, no browser.

## Results
| Check | Command | Result |
|---|---|---|
| Frontend typecheck (strict) | `cd frontend && npm run typecheck` | Pass |
| Frontend lint, zero warnings | `npm run lint` | Pass |
| Frontend tests | `npm test` | 52 of 52 passed (7 files) |
| Frontend production build | `npm run build` | Pass; Three.js and charts remain lazy chunks |
| Frontend dependency audit | `npm audit` | 0 vulnerabilities |
| Auth-service lint | `cd backend/services/auth-service && ruff check .` | Pass |
| Auth-service tests | `pytest -q` | 56 of 56 passed, 96% line coverage |
| Python dependency audit | `pip-audit -r requirements.txt` | No known vulnerabilities |
| Layout and secret scan | `scripts/validate-project.sh` | Pass |
| Live HTTP check | real uvicorn on SQLite behind the Vite dev proxy, driven with curl | Pass (below) |

## What the tests cover
**Backend:** password hashing and policy; JWT validity (expiry, wrong secret, audience, issuer, token type, `alg=none`, other algorithms); permission matrix and separation of duties; login success, identical errors for wrong password and unknown email, lockout and expiry of the lock, suspended accounts; refresh rotation with hashed storage, expiry, reuse detection, tolerance for near-simultaneous refresh; logout, logout-all, change password; every protected route rejecting anonymous callers; every non-admin role refused on user management; privilege escalation, forged admin tokens, demotion and suspension taking effect on existing tokens; self-lockout protection; user create, validation, duplicate email, search, filters and pagination; SQL-injection strings; migration upgrade, downgrade, no drift from the models, and valid MySQL DDL in offline mode; health and readiness; OpenAPI; first-admin CLI; settings refusing a missing or short secret.
**Frontend:** token kept in memory and absent from browser storage; login errors and lockout message; a single shared refresh for simultaneous callers; one silent retry and no refresh loop; forbidden responses not treated as an expired session; route guards for loading, anonymous, wrong role and right role; no role-preview shortcuts; administrator Users page (list, create, server error, self-protection, suspend, load error); all six dashboards, error and retry states.

**Mutation checks:** I deliberately broke three behaviours (no family revoke on token reuse, ignoring `is_active`, accepting HS512) and confirmed a test failed each time, then restored the code.

**Live check:** login through the proxy returned an `HttpOnly; SameSite=strict; Path=/api/v1/auth` cookie and `no-store`; refresh issued a new token; the admin created a user; that employee got 403 on `/users`; no token got 401; logout then refresh returned 401; `/health/ready` returned ok.

## Not executed
- The auth service against live MySQL 8.4, `docker compose up`, the Docker image build and the `02-create-service-users.sh` script (no Docker here). The compose file parses and the script passes `bash -n`.
- Real-browser checks: responsive layout, the Phase 2 screens (sign-in, Users page), the Three.js scene, keyboard and screen-reader behaviour, contrast measurement. Tailwind 4 output was checked for token presence only.
- Load, penetration and cross-browser testing.

## Notes
- Starlette prints a deprecation warning about `httpx` in its test client; it does not affect results.
- Recharts "width(0) and height(0)" messages in frontend tests come from jsdom having no layout.
