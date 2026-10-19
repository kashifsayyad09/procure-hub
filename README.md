# ProcureHub

AI-powered procurement platform: purchase requests, approvals, RFQs and quotations, purchase orders,
receiving, three-way invoice matching, notifications, audit and the SI-Talker assistant.

**Status:** Phase 1 of 17 (foundation and UI design system). See `PHASE_STATUS.md`.

## Quick start

```bash
scripts/setup-local.sh          # installs frontend dependencies, creates .env
cd frontend && npm run dev      # http://localhost:5173
```

Database foundation (requires Docker): `docker compose up -d mysql`

Checks: `scripts/test-all.sh` runs typecheck, lint, unit tests and the production build.

## What exists in Phase 1

- React 18, TypeScript, Vite, Tailwind frontend in `frontend/`
- Design system built from `Design.md` / `Skill.md` (see `docs/DESIGN_DECISIONS.md`)
- Landing page, login UI, and six role dashboards (sample data)
- GSAP animations with reduced-motion handling, lazy-loaded Three.js backdrop with static fallback
- MySQL 8.4 Docker Compose with the 11 logical databases

Authentication, real data, and every backend service arrive in later phases.
Routes `/app/<role>` are open previews in Phase 1 and are protected in Phase 2.

## Layout

```
frontend/         React app
infrastructure/   Docker init scripts (Terraform, Kubernetes, Helm added in later phases)
scripts/          setup, test, validate, package
docs/             architecture, database, security, design decisions, test report
```
