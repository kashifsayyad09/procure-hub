# Phase status

**Current phase:** 5 of 17, Vendor Service. Complete, awaiting approval.
**Completed:** Phases 1 to 4 (verified by user), Phase 5
**Pending:** Phases 6 to 17
**Next required action:** user approval to start Phase 6 (RFQ and Quotation Service).

## Implemented
- Phase 1: frontend foundation and design system. Phase 2: auth, sessions, user administration. Phase 3: purchase requests and employee screens. Phase 4: approval service, request-to-approval-to-decision hand-off, manager screens.
- Phase 5: vendor-service (4 of 11 business services built): registration, profiles, categories, contacts, verification with a second reviewer, directory, internal lookup; vendor portal and the vendor directory and review screens for procurement and administrators.

## Tests
See `docs/TEST_REPORT.md`.

## Known issues and limitations
- The Docker images and Compose stack have not been built or started (no Docker in the build environment). The services, migrations, bootstrap and cross-service tests ran on real MySQL 8.0, with real processes.
- No real-browser check of any screen has been done (none available), including the new vendor screens.
- Vendor documents (certificates) are not uploaded; only profile data is stored. A vendor registered by staff has no linked account until an account-linking feature is added.
- Verification of vendors, notifications and audit: no one is notified until Phase 10; events are stored in an outbox but not published until Phases 10 and 11.
- Procurement, finance and administrator dashboards still show sample data. Procurement has no RFQ screens until Phase 6.
- Any manager can decide any request (routing by department needs a department directory). A removed role stays effective up to 15 minutes (token lifetime). Other limitations in `docs/SECURITY.md`.
- Existing local setups: add `VENDOR_DB_PASSWORD` to `.env`, then `docker compose up -d --build`. In `frontend/`, run `npm install` once if `npm ci` complains (the lockfile was regenerated in this phase).
