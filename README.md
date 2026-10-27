# ProcureHub

AI-powered procurement platform: purchase requests, approvals, RFQs and quotations, purchase orders,
receiving, three-way invoice matching, notifications, audit and the SI-Talker assistant.

**Status:** Phase 3 of 17 (purchase requests). See `PHASE_STATUS.md`.

Requires Node.js 22.12 or newer.

## Quick start

Requires Node.js 22.12+, Python 3.12+, and Docker for the database.

```bash
scripts/setup-local.sh                  # .env, frontend and auth-service dependencies
# edit .env: set the passwords (including PURCHASE_REQUEST_DB_PASSWORD) and JWT_SECRET
docker compose up -d --build            # MySQL, database setup, migrations, auth (:8001) and purchase request (:8002) services
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
cd frontend && npm run dev              # http://localhost:5173, /api is proxied to the services
```

**Upgrading from Phase 2:** add `PURCHASE_REQUEST_DB_PASSWORD` to your `.env` (see `.env.example`), then run `docker compose up -d --build`. The `db-init` step creates the new database user on your existing data. Changing a database password in `.env` is also applied by `db-init` on the next `up`.

Checks: `scripts/test-all.sh` (frontend typecheck, lint, tests, build; auth-service lint and tests).
Without Docker, see `backend/services/auth-service/README.md` to run the service against any MySQL.

## What exists
- Phase 1: React/TypeScript frontend, design system, landing page, six role dashboards (sample data), GSAP and lazy Three.js.
- Phase 3: purchase request service (drafts, items, submit, cancel, documents, history), a shared backend package, and the employee dashboard, request list, three-step form and detail pages on real data.
- Phase 2: authentication service (argon2id, JWT, rotating refresh cookie, lockout, role permissions), real sign-in, protected routes, administrator user management.

Employee, administrator and procurement-read flows are real; the other dashboards still show sample data. Later phases add the other nine business services, messaging, SI-Talker, Kubernetes, Terraform and CI/CD.

## Layout

```
frontend/         React app
backend/          services (auth-service so far)
infrastructure/   Docker init scripts (Terraform, Kubernetes, Helm added in later phases)
scripts/          setup, test, validate, package
docs/             architecture, database, security, design decisions, test report
```
