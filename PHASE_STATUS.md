# Phase status

**Current phase:** 6 of 17, RFQ and Quotation Service. Complete, awaiting approval.
**Completed:** Phases 1 to 5 (verified by user), Phase 6
**Pending:** Phases 7 to 17
**Next required action:** user approval to start Phase 7 (Purchase Order Service).

## Implemented
- Phase 1: frontend foundation and design system. Phase 2: auth, sessions, user administration. Phase 3: purchase requests and employee screens. Phase 4: approval service and manager screens. Phase 5: vendor service, vendor portal, vendor directory and review.
- Phase 6: quotation-service (5 of 11 business services built): RFQs from approved requests, invitations to verified vendors, quotations, sealed bids, comparison, scoring, supplier selection and revocation, award contract; procurement and vendor screens for all of it. Small additions to the purchase request and vendor services (internal read APIs).

## Tests
See `docs/TEST_REPORT.md`.

## Known issues and limitations
- The Docker images and Compose stack have not been built or started (no Docker in the build environment). The services, migrations, bootstrap and cross-service tests ran on real MySQL 8.0, with real processes.
- No real-browser check of any screen has been done (none available), including the new RFQ, comparison and quotation screens. Frontend tests use a mocked API.
- RFQs and quotations: no file attachments; no notifications (events are stored in an outbox until Phases 10 and 11); one RFQ per request at a time, no split awards; no currency conversion; scoring criteria and weights are fixed in code; an award can be revoked even though purchase orders do not exist yet (Phase 7 must refuse it once one does).
- The procurement, finance and administrator dashboards still show sample data (the procurement dashboard does not yet show RFQ figures; the RFQ list page does).
- Vendor: no certificate uploads; a vendor registered by staff has no linked account until a linking feature exists.
- Any manager can decide any request (routing by department needs a department directory). A removed role stays effective up to 15 minutes (token lifetime). Other limitations in `docs/SECURITY.md`.
- Existing local setups: add `QUOTATION_DB_PASSWORD` to `.env`, then `docker compose up -d --build`.
