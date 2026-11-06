# Vendor service

Vendors register their company, keep a profile (company details, address, payment terms, categories, contacts) and are verified by procurement or an administrator. Procurement and administrators keep a directory. Later services ask this service whether a vendor is verified (see `docs/API.md`).

## Run locally
```bash
cd backend/services/vendor-service
python -m venv .venv && . .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt -e ../../shared
export DB_HOST=127.0.0.1 DB_PORT=3306 DB_NAME=vendor_db DB_USER=vendor_svc DB_PASSWORD="<VENDOR_DB_PASSWORD>"
export JWT_SECRET="<same as the auth service>" INTERNAL_JWT_SECRET="<same in every service, different from JWT_SECRET>"
alembic upgrade head
uvicorn app.main:create_app --factory --port 8004
```
OpenAPI docs: http://localhost:8004/docs. Tests: `pytest` (SQLite). On MySQL: `TEST_DATABASE_URL=mysql+pymysql://user:pass@127.0.0.1:3306/scratch_db pytest`.

## Configuration
| Variable | Default | Notes |
|---|---|---|
| `DB_HOST`, `DB_PORT` (3306), `DB_NAME`, `DB_USER`, `DB_PASSWORD` | required unless `DATABASE_URL` is set | the password may contain any character |
| `JWT_SECRET` | required | at least 32 characters; identical to the auth service's |
| `INTERNAL_JWT_SECRET` | unset | at least 32 characters. Without it the internal API answers 503 |
| `JWT_ISSUER`, `JWT_AUDIENCE` | `procurehub-auth`, `procurehub` | must match the auth service |
| `DOCS_ENABLED` | `true` | set `false` where the API is exposed |

## Rules the service enforces
- The owner of a record comes from the signed token. A vendor user sees and changes only their own record (someone else's answers 404). One record per vendor user.
- Procurement and administrators see every vendor, register vendors for companies without an account, and verify, send back, suspend and reinstate.
- A reviewer cannot decide on a profile they submitted. Decisions carry the version that was reviewed; a profile edited meanwhile must be reviewed again.
- Changing company name, tax ID, registration number or country on a verified vendor requires verification again. A suspended vendor cannot edit its own profile.
- Tax IDs are normalised and unique. Edits carry a `version` (409 when stale).
- Every change is recorded in the history and in an outbox table (`vendor_events`) for Phases 10 and 11.
