# Next phase: Phase 3, Purchase Request Service

Objective: Purchase Request microservice (FastAPI, `purchase_request_db`, Alembic): create, edit, save as draft, submit; line items; listing and filtering; detail pages; lifecycle statuses; supporting-document metadata; API tests; employee frontend pages replacing sample data.

Reuse from Phase 2:
- Service layout and app-factory pattern in `backend/services/auth-service` (config, JSON logging, request IDs, health endpoints, Dockerfile, ruff and pytest setup, migration test pattern).
- JWT verification: same `JWT_SECRET`, issuer `procurehub-auth`, audience `procurehub`, `typ=access`. Put the verification code in `backend/shared` so services do not copy it. Check permissions such as `purchase_request:create`, `purchase_request:read_own`, `purchase_request:submit` from `app/permissions.py`.
- `frontend/src/services/api.ts` (add a `purchaseRequestsApi`), `RequireAuth`, `DataTable`, `Modal`, `Drawer`, `ApprovalTimeline`.
- Add a `purchase_request_svc` MySQL user in `infrastructure/docker/mysql-init/02-create-service-users.sh`, compose services, and a Vite proxy rule (or the API gateway) for `/api/v1/purchase-requests`.

Constraints: no shared models or cross-database joins between services; ownership is enforced in the service (an employee reads only their own requests); no hardcoded secrets; keep one cumulative ZIP.
