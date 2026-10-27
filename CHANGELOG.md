# Changelog

## Phase 3 (0.3.0): Purchase Request Service
### Added
- Purchase Request microservice (FastAPI, `purchase_request_db`, Alembic): create, edit, save as draft, submit, cancel and delete drafts; line items with exact decimal totals; request numbers `PR-<year>-<6 digits>`; list with filters, search, sorting and paging; summary for dashboards; document metadata; status history; optimistic locking.
- Shared package `backend/shared/procurehub_common`: roles, permission matrix, token verification, JSON logging, request-ID middleware, health routes, database URL builder.
- Employee screens: real dashboard, request list, three-step create/edit form, request detail with documents and history.
- `db-init` Compose service and `db-bootstrap/bootstrap.sh`: idempotent database and per-service user setup that also works on an existing data volume.
- Compose services `purchase-request-migrate` and `purchase-request-service`; Vite proxy rule for `/api/v1/purchase-requests`.
- 79 backend tests (81 on MySQL) and 31 new frontend tests.
### Changed
- Auth service now uses the shared package; access tokens also carry the user's name and email.
- Docker builds for services use `backend/` as the build context.
- `.env` needs a new variable, `PURCHASE_REQUEST_DB_PASSWORD`.
- Employee dashboard no longer uses sample data; the sidebar links to My requests.
- zod 3 to 4 and `@hookform/resolvers` 3 to 5 (security advisory).
### Removed
- `infrastructure/docker/mysql-init` (replaced by `db-bootstrap`).

## Phase 2 revision: Docker configuration testing
## Phase 2 revision: Docker configuration testing
### Fixed
- A database password containing `@` or `%` corrupted `DATABASE_URL` and the service could not connect. Compose and the service now use separate `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` variables (`DATABASE_URL` still works).
- `.dockerignore` now excludes `.venv`, `*.db` and caches from the build context.
### Added
- Backend tests can run on a real MySQL server (`TEST_DATABASE_URL`), including a migration test. PowerShell command in the README. Notes on `$` in `.env` and on changing a database password.

## Phase 2 (0.2.0): Authentication and Authorization
### Added
- Authentication microservice (FastAPI): login, logout, logout-all, refresh with rotation and reuse detection, change password, `/me`, user administration, health endpoints, OpenAPI.
- Argon2id hashing, JWT access tokens, lockout, password policy, role-permission matrix.
- Alembic migration `0001` (users, refresh_tokens), first-admin CLI, Dockerfile, pinned requirements.
- Compose services `auth-migrate` and `auth-service`; per-service MySQL user script.
- Frontend: real sign-in, in-memory session with silent refresh, protected and role-restricted routes, administrator Users page (create, search, filter, change role, suspend), Vite `/api` proxy.
- 56 backend tests and 32 new frontend tests.
### Changed
- Login page, profile menu, sidebar and landing page use real sessions.
### Removed
- Phase 1 role-preview shortcuts and unauthenticated `/app/*` access.

## Phase 1 fix: dependency security and deprecations
- `npm audit`: 26 vulnerabilities (2 critical) reduced to 0. Upgrades: Vite 5 to 7, Vitest 2 to 5, Tailwind 3 to 4 (via `@config`, tokens unchanged), React Router 6 to 7, ESLint 9 to 10, Recharts 2 to 3, jsdom 25 to 29, TypeScript 5.9, plus patch/minor bumps.
- Removed `autoprefixer` (built into Tailwind 4). PostCSS uses `@tailwindcss/postcss`.
- `overrides` pins `three-mesh-bvh` to 0.8 (removes the deprecation warning from Drei 9).
- ESLint uses the two classic react-hooks rules; the React Compiler rules in plugin v7 do not apply to this project.
- Test suite: async timeout raised to absorb cold-start of lazy routes.
- `engines.node` set to >=22.12.0 (required by Vite 7 and Vitest 5).

## Phase 1 (0.1.0)
### Added
- Frontend foundation: React 18.3, TypeScript 5.6, Vite 5.4, Tailwind 3.4, React Router 6, TanStack Query 5, Zustand 5, React Hook Form + Zod, Recharts, Lucide, GSAP 3.12, Three.js 0.169 with React Three Fiber 8 and Drei 9.
- Design tokens from Design.md; light theme default with dark theme.
- UI components, app shell, landing page, login UI, six role dashboards (sample data).
- Vitest suite (20 tests), ESLint, strict TypeScript.
- docker-compose.yml with MySQL 8.4 and init script for 11 logical databases.
- Helper scripts and documentation.
