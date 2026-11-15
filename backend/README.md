# Backend

One folder per business service under `services/`. Each service has its own FastAPI app, database, migrations, tests and Dockerfile, and shares no tables or models with any other.

| Service | Folder | Port (local) | Database | Status |
|---|---|---|---|---|
| Authentication | `services/auth-service` | 8001 | `auth_db` | Phase 2 |
| Purchase request | `services/purchase-request-service` | 8002 | `purchase_request_db` | Phase 3 |
| Approval | `services/approval-service` | 8003 | `approval_db` | Phase 4 |

## Shared package
`shared/procurehub_common` holds only what every service must agree on: roles, the permission matrix, access-token verification, service-to-service tokens and HTTP client, message contracts, JSON logging and request IDs, health routes, and the database URL builder. It contains no database models. Install it with `pip install -e backend/shared` (the setup script does this).

## Docker
Build from this folder so the shared package is in the build context:
`docker build -f services/<service>/Dockerfile .`  (Compose does this for you.)

## Tests
`cd services/<service> && pytest`. Set `TEST_DATABASE_URL` to a scratch MySQL database to run the suite on MySQL instead of SQLite.

## Cross-service tests
`tests/` starts the auth, purchase request, approval, vendor and quotation services as real processes (SQLite files, or MySQL with `E2E_AUTH_DB_URL`, `E2E_PR_DB_URL`, `E2E_APPROVAL_DB_URL`, `E2E_VENDOR_DB_URL`, `E2E_QUOTATION_DB_URL`) and drives the request-to-decision flow, vendor onboarding and the whole RFQ-to-selection flow over HTTP, including stopping and restarting a service. Run `cd tests && pytest`.
