# Phase status

**Current phase:** 3 of 17, Purchase Request Service. Complete, awaiting approval.
**Completed:** Phases 1 and 2 (verified by user), Phase 3
**Pending:** Phases 4 to 17
**Next required action:** user approval to start Phase 4 (Approval Service).

## Implemented
- Phase 1: frontend foundation, design system, landing page, role dashboards (sample data).
- Phase 2: auth-service, real sessions, protected routes, admin user management.
- Phase 3: purchase-request-service (2 of 11 business services built), shared backend package, employee request screens on real data, idempotent database bootstrap.

## Tests
See `docs/TEST_REPORT.md`.

## Known issues and limitations
- The Docker images and Compose stack have not been built or started (no Docker in the build environment). Services, migrations and bootstrap were tested against a real MySQL 8.0 server and with image-equivalent steps.
- No real-browser check of any screen has been done (none available), including the new employee pages and the pages after the Tailwind 4 and zod 4 upgrades.
- Managers cannot read requests yet, and nothing can approve a request until Phase 4. Procurement can read approved requests, but none will exist until then.
- Documents: only file details are recorded; file upload to object storage comes later.
- Role changes reach the Purchase Request service only when the user's token is renewed (up to 15 minutes); see `docs/SECURITY.md`.
- Request numbers leave gaps when drafts are deleted. Department is free text; there is no department directory yet.
- Other limitations in `docs/SECURITY.md` (no password reset email, no MFA, no per-IP rate limit).
- Dashboards for manager, procurement, vendor, finance and admin still show sample data.
- Existing local setups: add `PURCHASE_REQUEST_DB_PASSWORD` to `.env`, then `docker compose up -d --build`.
