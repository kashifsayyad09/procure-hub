# Next phase: Phase 6, RFQ and Quotation Service

Objective: Quotation microservice (FastAPI, `quotation_db`, Alembic): RFQ creation from approved purchase requests, vendor invitations, vendor quotation submission with line items, quotation comparison dashboard, supplier evaluation, supplier selection records, workflow integration tests.

Decisions to settle first:
- RFQ source: an RFQ copies a snapshot of an approved request's items (read through the Purchase Request service API, as procurement already can). Decide whether one request can have several RFQs, and what happens to an RFQ if the request is later cancelled.
- Invitations: only vendors whose status is `verified` may be invited. The Vendor service already exposes `POST /internal/v1/vendors/lookup` (service name `quotation-service` is on its allowed list). Decide how invitations reach vendors before notifications exist (Phase 10): the vendor portal lists RFQs they were invited to (`rfq:read_invited`).
- Evaluation: how quotations are scored (price, delivery time, vendor terms from the vendor profile) and who may select the winner (`rfq:manage`, `quotation:compare`).
- Vendor suspended or changed after an invitation: recommended that submitting a quotation re-checks status.

Reuse from Phase 5:
- Service layout and test patterns in `backend/services/vendor-service` (app factory, `service.py`, ownership scope, version-checked commands, unique-index race handling, migration tests, MySQL option, mutation-style rule tests, outbox).
- `backend/shared/procurehub_common`: `contracts/vendor.py` (`VendorRef`, `VendorLookup`), `service_client`, service tokens, permissions (`rfq:manage`, `rfq:read_invited`, `quotation:submit`, `quotation:compare` already declared).
- `infrastructure/docker/db-bootstrap/bootstrap.sh` (`ensure_user quotation_svc quotation_db QUOTATION_DB_PASSWORD`), `.env.example`, the `db-init` service, a compose migrate and service pair on port 8005, a Vite proxy rule for `/api/v1/rfqs` and `/api/v1/quotations`.
- `backend/tests`: add the service to the `Stack` and an RFQ scenario to the end-to-end tests (request approved, RFQ, invited verified vendor quotes, selection).
- Frontend: `features/vendors` (status badge, directory and detail patterns, multi-step form with a field array, review dialogs with reasons), `DataTable`, `Modal`, `Drawer`, `TrendChart`; replace the procurement sample dashboard and add RFQ nav items (`navConfig.ts`).

Constraints: no shared models or cross-database joins; ownership and role rules enforced in the service; vendors see only RFQs they were invited to and only their own quotations; no hardcoded secrets; keep one cumulative ZIP.
