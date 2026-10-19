# Next phase: Phase 2, Authentication and Authorization

Objective: Authentication microservice (FastAPI, MySQL `auth_db`, Alembic), password hashing, JWT access and rotating refresh tokens, login/logout, role-based permissions enforced in the backend, protected React routes, real sessions, integration tests.

Reuse: `frontend/src/pages/auth/LoginPage.tsx` (form and Zod schema), `src/types/roles.ts`, `AppShell`, `docker-compose.yml` and `auth_db`.
Must remove: the Phase 1 role-preview links on the login page and in the profile menu, and unauthenticated `/app/*` access.
Constraints: no hardcoded secrets; services share no database models; keep the one-cumulative-ZIP convention.
