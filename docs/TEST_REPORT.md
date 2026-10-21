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
| Auth-service tests | `pytest -q` | 58 passed and 1 skipped on SQLite (the skipped one is the MySQL-only migration test); 59 of 59 passed on MySQL; about 96% line coverage |
| Python dependency audit | `pip-audit -r requirements.txt` | No known vulnerabilities |
| Layout and secret scan | `scripts/validate-project.sh` | Pass |
| Live HTTP check | real uvicorn on SQLite behind the Vite dev proxy, driven with curl | Pass (below) |

## What the tests cover
**Backend:** password hashing and policy; JWT validity (expiry, wrong secret, audience, issuer, token type, `alg=none`, other algorithms); permission matrix and separation of duties; login success, identical errors for wrong password and unknown email, lockout and expiry of the lock, suspended accounts; refresh rotation with hashed storage, expiry, reuse detection, tolerance for near-simultaneous refresh; logout, logout-all, change password; every protected route rejecting anonymous callers; every non-admin role refused on user management; privilege escalation, forged admin tokens, demotion and suspension taking effect on existing tokens; self-lockout protection; user create, validation, duplicate email, search, filters and pagination; SQL-injection strings; migration upgrade, downgrade, no drift from the models, and valid MySQL DDL in offline mode; health and readiness; OpenAPI; first-admin CLI; settings refusing a missing or short secret.
**Frontend:** token kept in memory and absent from browser storage; login errors and lockout message; a single shared refresh for simultaneous callers; one silent retry and no refresh loop; forbidden responses not treated as an expired session; route guards for loading, anonymous, wrong role and right role; no role-preview shortcuts; administrator Users page (list, create, server error, self-protection, suspend, load error); all six dashboards, error and retry states.

**Mutation checks:** I deliberately broke three behaviours (no family revoke on token reuse, ignoring `is_active`, accepting HS512) and confirmed a test failed each time, then restored the code.

**Live check:** login through the proxy returned an `HttpOnly; SameSite=strict; Path=/api/v1/auth` cookie and `no-store`; refresh issued a new token; the admin created a user; that employee got 403 on `/users`; no token got 401; logout then refresh returned 401; `/health/ready` returned ok.

## Docker configuration testing (added after delivery)
Docker is not available in the build environment, so images were not built and Compose was not started. Instead:
| Check | Result |
|---|---|
| Compose file: service references, build contexts, bind mounts, volumes, variables all defined in `.env.example`, ports bound to 127.0.0.1, `$$` escaping in the healthcheck | Pass (scripted) |
| Dockerfile equivalent: copy only the files the Dockerfile copies, clean `pip install -r requirements.txt` (production pins only), then run the `auth-migrate` command, the first-admin command, the container `CMD`, and the Dockerfile `HEALTHCHECK` command | Pass |
| Service refuses to start without `JWT_SECRET` | Pass |
| MySQL init scripts run on a real MySQL 8.0.46: 11 databases created, `auth_svc` user created, re-run is safe, access to another database denied | Pass |
| Init script safety: missing password fails, a quote is rejected before any SQL is sent, `$` and backticks are not expanded | Pass |
| Full backend suite on real MySQL | 59 of 59 passed (includes the migration upgrade, drift check, downgrade) |
| Live service on real MySQL: migration, admin CLI, readiness, login, create user, case-insensitive duplicate (409), search; database holds argon2id hashes and 64-character refresh-token hashes; logs contain no passwords | Pass |
| **Defect found and fixed:** DB passwords containing `@` or `%` broke `DATABASE_URL` | Fixed, with tests |

Still not exercised: building the image, Compose networking and `depends_on` ordering, the in-container healthchecks, the `mysql:8.4` image (tested on 8.0), and how the MySQL image runs init scripts.

## Not executed
- `docker compose up`, the Docker image build, and MySQL 8.4 specifically (see above for what was tested instead).
- Real-browser checks: responsive layout, the Phase 2 screens (sign-in, Users page), the Three.js scene, keyboard and screen-reader behaviour, contrast measurement. Tailwind 4 output was checked for token presence only.
- Load, penetration and cross-browser testing.

## Notes
- Starlette prints a deprecation warning about `httpx` in its test client; it does not affect results.
- Recharts "width(0) and height(0)" messages in frontend tests come from jsdom having no layout.
