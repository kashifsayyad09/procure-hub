# Purchase request service

Employees create, edit, save as draft, submit and cancel purchase requests with line items and supporting-document details. Procurement can read approved requests.

## Run locally
```bash
cd backend/services/purchase-request-service
python -m venv .venv && . .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt -e ../../shared
export DB_HOST=127.0.0.1 DB_PORT=3306 DB_NAME=purchase_request_db DB_USER=purchase_request_svc DB_PASSWORD="<PURCHASE_REQUEST_DB_PASSWORD>"
export JWT_SECRET="<the same secret the auth service uses>"
alembic upgrade head
uvicorn app.main:create_app --factory --port 8002
```
OpenAPI docs: http://localhost:8002/docs. Tests: `pytest` (SQLite). On MySQL: `TEST_DATABASE_URL=mysql+pymysql://user:pass@127.0.0.1:3306/scratch_db pytest`.

## Configuration
| Variable | Default | Notes |
|---|---|---|
| `DB_HOST`, `DB_PORT` (3306), `DB_NAME`, `DB_USER`, `DB_PASSWORD` | required unless `DATABASE_URL` is set | the password may contain any character |
| `JWT_SECRET` | required | at least 32 characters; identical to the auth service's |
| `JWT_ISSUER`, `JWT_AUDIENCE` | `procurehub-auth`, `procurehub` | must match the auth service |
| `DOCS_ENABLED` | `true` | set `false` where the API is exposed |

## Rules the service enforces
- The requester identity comes from the signed token, never from the request body.
- Employees see and change only their own requests (someone else's request answers 404, not 403).
- Only drafts can be edited, deleted or have documents changed. Only submitted requests can be cancelled, with a reason.
- Edits carry a `version`; a stale version is refused (409) so two browser tabs cannot overwrite each other.
- A request can be submitted only when it has a department, a justification, at least one item and a total above zero.
- Money is exact: quantities have 3 decimals, prices 2, line totals round half up, and different currencies are never added together.
