# Next phase: Phase 4, Approval Service

Objective: Approval microservice (FastAPI, `approval_db`, Alembic): multi-step approval workflow, approve and reject with reasons, approval history, delegation hooks, manager approval dashboard, notification integration points, end-to-end approval tests.

Open design question to settle first: how the Approval service learns about submitted requests and moves them to `approved` or `rejected`. Phase 3 keeps the Purchase Request service as the only writer of `purchase_request_db`. Recommended: the Purchase Request service exposes a small internal endpoint for status decisions that accepts only a service credential (not a user token), and the Approval service calls it after recording the decision. Phase 11 (SQS) later turns this into events with retries. Managers also need read access to the requests they must decide on; the Approval service should hold the approval records and a snapshot of what the manager needs, rather than reading another service's database.

Reuse from Phase 3:
- Service layout and test patterns in `backend/services/purchase-request-service` (app factory, `service.py` business layer, ownership checks, version locking, MySQL test option, migration tests).
- `backend/shared/procurehub_common` for roles, permissions (`approval:read`, `approval:decide`, `approval:delegate` already exist), token verification, logging and health routes.
- `infrastructure/docker/db-bootstrap/bootstrap.sh`: add one `ensure_user approval_svc approval_db APPROVAL_DB_PASSWORD` line, the variable to `.env.example` and to the `db-init` service.
- Compose pattern: `*-migrate` one-shot plus the service; Vite proxy rule for `/api/v1/approvals`.
- Frontend: `RequireAuth`, `DataTable`, `Modal`, `Drawer`, `ApprovalTimeline`, `features/purchase-requests/timeline.ts`; replace the manager sample dashboard.

Constraints: no shared models or cross-database joins; role and ownership rules enforced in the service; a manager must not approve their own request; keep one cumulative ZIP.
