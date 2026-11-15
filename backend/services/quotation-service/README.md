# Quotation service

Turns an approved purchase request into a request for quotation (RFQ), invites verified vendors, takes their quotations, and supports comparison, evaluation and selection of a supplier.

```
approved request -> RFQ (draft) -> invite vendors -> issue -> vendors quote -> deadline / close -> compare, evaluate -> select -> awarded
```

## Run locally
```bash
cd backend/services/quotation-service
python -m venv .venv && . .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt -e ../../shared
export DB_HOST=127.0.0.1 DB_PORT=3306 DB_NAME=quotation_db DB_USER=quotation_svc DB_PASSWORD="<QUOTATION_DB_PASSWORD>"
export JWT_SECRET="<same as the auth service>" INTERNAL_JWT_SECRET="<same in every service, different from JWT_SECRET>"
export VENDOR_SERVICE_URL=http://localhost:8004 PURCHASE_REQUEST_SERVICE_URL=http://localhost:8002
alembic upgrade head
uvicorn app.main:create_app --factory --port 8005
```
OpenAPI docs: http://localhost:8005/docs. Tests: `pytest` (SQLite, other services replaced by contract-faithful fakes). On MySQL: `TEST_DATABASE_URL=mysql+pymysql://user:pass@127.0.0.1:3306/scratch_db pytest` (also runs a real two-people-at-once selection race).

## Configuration
| Variable | Default | Notes |
|---|---|---|
| `DB_HOST`, `DB_PORT` (3306), `DB_NAME`, `DB_USER`, `DB_PASSWORD` | required unless `DATABASE_URL` is set | the password may contain any character |
| `JWT_SECRET` | required | at least 32 characters; identical to the auth service's |
| `INTERNAL_JWT_SECRET` | unset | at least 32 characters. Required when either service URL is set; also verifies calls from the purchase order service |
| `VENDOR_SERVICE_URL`, `PURCHASE_REQUEST_SERVICE_URL` | unset | without them, steps that need those services answer 503 "not configured" |
| `MIN_DEADLINE_HOURS` | `1` | an RFQ deadline must be at least this far ahead when set or issued |
| `MAX_DEADLINE_DAYS` | `365` | |
| `DOCS_ENABLED` | `true` | set `false` where the API is exposed |

## Rules the service enforces
- **Eligibility:** an RFQ is created only from a purchase request that the purchase request service reports as `approved`. One live RFQ per request (a unique index); cancelling frees the request.
- **Vendors:** only `verified` vendors can be invited (checked when invited, when the RFQ is issued, when a quotation is submitted, and when a supplier is selected). A vendor user is identified by asking the vendor service who owns the token's user id; nothing about the vendor comes from the browser.
- **Sealed bids:** procurement sees who has responded but not prices until the deadline has passed or the RFQ is closed. A vendor's draft is never visible to procurement. Vendors never see the budget, the estimates, other vendors or other quotations.
- **Money:** exact decimals (`DECIMAL`), never floats. Unit prices have up to 4 decimals, line totals and totals are rounded half up to 2 and computed by the server. Quantities always come from the RFQ.
- **Currencies:** a vendor may quote in any supported currency. Quotations are compared, scored and ranked only within the same currency; nothing is converted.
- **Scoring:** price 40 and delivery 20 (calculated), compliance 25 and commercial terms 15 (entered by the evaluator, 0 to 10, each with a reason). Details in `app/scoring.py` and `docs/API.md`.
- **Selection:** the RFQ row is locked and a unique index on `selections.active_rfq_id` means two awards cannot both succeed. Repeating the same selection is harmless; a different one conflicts. An award can be revoked (with a reason) and a new one made; the history keeps every award.
- **Outbox:** every state change writes a row in `quotation_events` in the same transaction, for the Notification and Audit services (Phases 10, 11).
