# ProcureHub

AI-powered procurement platform: purchase requests, approvals, RFQs and quotations, purchase orders,
receiving, three-way invoice matching, notifications, audit and the SI-Talker assistant.

**Status:** Phase 6 of 17 (RFQs and quotations). See `PHASE_STATUS.md`.

Requires Node.js 22.12 or newer.

## Quick start

Requires Node.js 22.12+, Python 3.12+, and Docker for the database.

```bash
scripts/setup-local.sh                  # .env, frontend and auth-service dependencies
# edit .env: set the database passwords (including VENDOR_DB_PASSWORD and QUOTATION_DB_PASSWORD) and both secrets (JWT_SECRET and INTERNAL_JWT_SECRET, different values)
docker compose up -d --build            # MySQL, database setup, migrations, auth (:8001), purchase request (:8002), approval (:8003), vendor (:8004), quotation (:8005)
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

**Upgrading from Phase 3:** add `APPROVAL_DB_PASSWORD` and `INTERNAL_JWT_SECRET` to your `.env` (see `.env.example`; the internal secret must differ from `JWT_SECRET` and be at least 32 characters), then run `docker compose up -d --build`. The `db-init` step creates the new database user on your existing data, and requests already submitted are registered with the Approval service automatically. Changing a database password in `.env` is also applied by `db-init` on the next `up`.

Checks: `scripts/test-all.sh` (frontend typecheck, lint, tests, build; shared package and each service: lint and tests; the cross-service end-to-end tests).
Without Docker, see `backend/services/auth-service/README.md` to run the service against any MySQL.

## What exists
- Phase 6: quotation service (RFQs from approved requests, vendor invitations, sealed quotations, comparison, supplier scoring, selection and revocation, award contract for Phase 7), the procurement RFQ screens (list, new, detail with invitations, edit, comparison dashboard) and the vendor screens (invited RFQs, RFQ detail, quotation form).
- Phase 5: vendor service (registration, profiles, contacts, categories, verification by a second reviewer, directory, internal lookup for later services), the vendor portal (dashboard, profile, registration form), and the vendor directory and review screens for procurement and administrators.
- Phase 1: React/TypeScript frontend, design system, landing page, six role dashboards (sample data), GSAP and lazy Three.js.
- Phase 4: approval service (levels by amount, approve, reject, delegate, overdue flag), the services hand work to each other with retries, and the manager dashboard, approvals list and approval pages on real data.
- Phase 3: purchase request service (drafts, items, submit, cancel, documents, history), a shared backend package, and the employee dashboard, request list, three-step form and detail pages on real data.
- Phase 2: authentication service (argon2id, JWT, rotating refresh cookie, lockout, role permissions), real sign-in, protected routes, administrator user management.

Employee, manager, vendor and the vendor screens of procurement and administrators and the RFQ and quotation screens are real; the procurement, finance and administrator dashboards still show sample data. Later phases add the other seven business services, messaging, SI-Talker, Kubernetes, Terraform and CI/CD.

## Layout

```
frontend/         React app
backend/          services (auth-service so far)
infrastructure/   Docker init scripts (Terraform, Kubernetes, Helm added in later phases)
scripts/          setup, test, validate, package
docs/             architecture, database, security, design decisions, test report
```
