# Next phase: Phase 5, Vendor Service

Objective: Vendor microservice (FastAPI, `vendor_db`, Alembic): vendor onboarding and registration, vendor profiles and contacts, categories, a vendor directory, verification status, the vendor portal screens, authorization tests.

Decisions to settle first:
- How a vendor user relates to a vendor record. Vendor users already exist in the auth service (role `vendor`). Recommended: the vendor record stores the auth user id of its owner (no foreign key), and a vendor can manage only the record whose owner id equals their token subject, the same ownership pattern as purchase requests. Administrators or procurement create or verify vendors (`vendor:read` exists for procurement; add a `vendor:verify` permission).
- Who can verify a vendor, and what verification means for Phase 6 (only verified vendors can be invited to an RFQ).

Reuse from Phase 4:
- Service layout and test patterns in `backend/services/approval-service` and `purchase-request-service` (app factory, `service.py` business layer, ownership checks, MySQL test option, migration tests, mutation-style rule tests).
- `backend/shared/procurehub_common`: roles and permissions, `make_user_auth`, logging, health, service tokens and contracts for any call to another service (an RFQ invitation will need the vendor list from this service).
- `infrastructure/docker/db-bootstrap/bootstrap.sh`: add `ensure_user vendor_svc vendor_db VENDOR_DB_PASSWORD`, the variable to `.env.example` and the `db-init` service; compose migrate and service pair; Vite proxy rule for `/api/v1/vendors`.
- `backend/tests`: add vendor scenarios to the cross-service end-to-end test.
- Frontend: `RequireAuth`, `DataTable`, `Modal`, `Drawer`, the multi-step form pattern from `RequestFormPage`, status badges, `ApprovalTimeline`; replace the vendor sample dashboard.

Constraints: no shared models or cross-database joins; ownership enforced in the service; vendors see only their own record; no hardcoded secrets; keep one cumulative ZIP.
