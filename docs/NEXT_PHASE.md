# Next phase: Phase 7, Purchase Order Service

Objective: Purchase Order microservice (FastAPI, `purchase_order_db`, Alembic): create a purchase order from an awarded RFQ, PO numbering, line items, vendor confirmation, PO document generation, order lifecycle, order tracking dashboard, API and integration tests.

Decisions to settle first:
- Source: the order is built from `GET /internal/v1/rfqs/{rfq_id}/award` (`AwardRef`, service name `purchase-order-service` is already on the allowed list). Copy the lines, quantities, unit prices, currency, terms and payment terms into the order as a snapshot. Decide who may create the order (`purchase_order:create`, procurement) and whether it is automatic on award or a deliberate step (recommended: deliberate, one order per award).
- Locking the award: the quotation service lets procurement revoke an award. Once an order exists a revoke must be refused. Add an internal endpoint or event in Phase 7 (for example the order service tells the quotation service "this RFQ has an order", or the quotation service asks before revoking). Document it and test it.
- Vendor confirmation: vendors read their orders through the vendor-by-owner lookup (same pattern as quotations: `GET /internal/v1/vendors/by-owner/{user_id}`); confirm, or reject with a reason. A suspended vendor can read but not confirm (decide).
- PO document: generate a PDF (see the `pdf` skill) or HTML; store the file path/metadata, not binary blobs in MySQL (S3 arrives in Phase 15, so use a local directory behind an interface now).
- Statuses: draft, issued, confirmed, rejected, partially_received, received, closed, cancelled. Receiving (Phase 8) and invoices (Phase 9) will move the later ones; define the events they will send.

Reuse from Phase 6:
- Service layout and test patterns in `backend/services/quotation-service` (app factory, `service.py`, `common.py` for outside calls through `ServiceClient` with `httpx.MockTransport` fakes, version-checked commands, unique-index race handling with `commit(...)` translation, outbox, migration tests, MySQL option, mutation-style rule tests, clock fixture for deadlines).
- `backend/shared/procurehub_common`: `contracts/quotation.py` (`AwardRef`, `AwardItem`), `contracts/purchase_request.py`, `contracts/vendor.py`, `service_client`, service tokens, permissions (`purchase_order:*` and `order:confirm` already declared; check `permissions.py`).
- Money: `DECIMAL`, `line_total` rounding half up (`app/common.py`), exact-decimal frontend helper `features/rfqs/money.ts`.
- `infrastructure/docker/db-bootstrap/bootstrap.sh` (`ensure_user purchase_order_svc purchase_order_db PURCHASE_ORDER_DB_PASSWORD`), `.env.example`, the `db-init` service, a compose migrate and service pair on port 8006, a Vite proxy rule for `/api/v1/purchase-orders`.
- `backend/tests`: add the service to the `Stack` and a scenario that continues the Phase 6 flow (award, then purchase order, vendor confirms).
- Frontend: `features/rfqs` (status badges, dialogs, forms), `features/vendors`, `DataTable`, `Modal`, list and detail page patterns, `navConfig.ts` (the procurement and vendor "Orders" entries); replace the procurement sample dashboard with real figures if time allows.

Constraints: no shared models or cross-database joins; ownership and role rules enforced in the service; vendors see only their own orders; no hardcoded secrets; keep one cumulative ZIP; do not start Phase 8.
