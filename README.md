# ProcureHub

AI-powered procurement platform: purchase requests, approvals, RFQs and quotations, purchase orders,
receiving, three-way invoice matching, notifications, audit and the SI-Talker assistant.

**Status:** Phase 2 of 17 (authentication and authorization). See `PHASE_STATUS.md`.

Requires Node.js 22.12 or newer.

## Quick start

Requires Node.js 22.12+, Python 3.12+, and Docker for the database.

```bash
scripts/setup-local.sh                  # .env, frontend and auth-service dependencies
# edit .env: set the passwords and JWT_SECRET
docker compose up -d --build            # MySQL, migrations, auth service on :8001
```
Create the first administrator (there is no default account). The password is prompted for if you leave out `ADMIN_PASSWORD`; it needs 12+ characters with a letter and a number, and must not contain the name part of your email.

macOS / Linux:
```bash
docker compose run --rm -e ADMIN_PASSWORD='<strong password>' auth-service \
  python -m app.cli create-admin --email you@company.com --name "Your Name"
```
Windows PowerShell:
```powershell
docker compose run --rm -e ADMIN_PASSWORD='<strong password>' auth-service `
  python -m app.cli create-admin --email you@company.com --name "Your Name"
```
Then start the frontend:
```bash
cd frontend && npm run dev              # http://localhost:5173, /api is proxied to :8001
```

**Changing a database password later:** MySQL creates its users only the first time the data volume is created. After editing `AUTH_DB_PASSWORD` in `.env`, run `docker compose down -v` (this deletes local data) and start again.

Checks: `scripts/test-all.sh` (frontend typecheck, lint, tests, build; auth-service lint and tests).
Without Docker, see `backend/services/auth-service/README.md` to run the service against any MySQL.

## What exists
- Phase 1: React/TypeScript frontend, design system, landing page, six role dashboards (sample data), GSAP and lazy Three.js.
- Phase 2: authentication service (argon2id, JWT, rotating refresh cookie, lockout, role permissions), real sign-in, protected routes, administrator user management.

Later phases add the other ten business services, messaging, SI-Talker, Kubernetes, Terraform and CI/CD.

## Layout

```
frontend/         React app
backend/          services (auth-service so far)
infrastructure/   Docker init scripts (Terraform, Kubernetes, Helm added in later phases)
scripts/          setup, test, validate, package
docs/             architecture, database, security, design decisions, test report
```
