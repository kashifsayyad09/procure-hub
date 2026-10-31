# Phase status

**Current phase:** 4 of 17, Approval Service. Complete, awaiting approval.
**Completed:** Phases 1 to 3 (verified by user), Phase 4
**Pending:** Phases 5 to 17
**Next required action:** user approval to start Phase 5 (Vendor Service).

## Implemented
- Phase 1: frontend foundation and design system. Phase 2: auth, sessions, user administration. Phase 3: purchase requests and employee screens.
- Phase 4: approval-service (3 of 11 business services built), the request-to-approval-to-decision hand-off between services, manager screens on real data, cross-service end-to-end tests.

## Tests
See `docs/TEST_REPORT.md`.

## Known issues and limitations
- The Docker images and Compose stack have not been built or started (no Docker in the build environment). Services, migrations, bootstrap and the three-service hand-off were tested on a real MySQL 8.0 server, with real processes, and with image-equivalent steps.
- No real-browser check of any screen has been done (none available), including the new manager pages.
- Any manager can decide any request; routing by department needs a department directory (planned). Approval thresholds come from configuration.
- A removed manager role stays effective for up to 15 minutes (token lifetime).
- Overdue approvals are flagged but nobody is notified until Phase 10. Events are stored in an outbox but not published until Phases 10 and 11.
- The Approval and Purchase Request services each run a retry loop; Phase 11 replaces them with queues.
- Procurement can read approved requests but has no screens yet (Phase 6). Documents: only file details are recorded.
- Other limitations in `docs/SECURITY.md`. Dashboards for procurement, vendor, finance and admin still show sample data.
- Existing local setups: add `APPROVAL_DB_PASSWORD` and `INTERNAL_JWT_SECRET` to `.env`, then `docker compose up -d --build`. Requests submitted in Phase 3 are registered with the Approval service automatically.
