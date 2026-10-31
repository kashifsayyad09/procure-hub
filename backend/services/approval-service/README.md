# Approval service

Managers approve, reject or delegate purchase requests. The number of approval levels depends on the amount. The Purchase Request service registers each submitted request here and receives the final decision back (see `docs/ARCHITECTURE.md`).

## Run locally
```bash
cd backend/services/approval-service
python -m venv .venv && . .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt -e ../../shared
export DB_HOST=127.0.0.1 DB_PORT=3306 DB_NAME=approval_db DB_USER=approval_svc DB_PASSWORD="<APPROVAL_DB_PASSWORD>"
export JWT_SECRET="<same as the auth service>" INTERNAL_JWT_SECRET="<same in all three services, different from JWT_SECRET>"
export PURCHASE_REQUEST_SERVICE_URL=http://localhost:8002 AUTH_SERVICE_URL=http://localhost:8001
alembic upgrade head
uvicorn app.main:create_app --factory --port 8003
```
OpenAPI docs: http://localhost:8003/docs. Tests: `pytest` (SQLite) or `TEST_DATABASE_URL=mysql+pymysql://user:pass@127.0.0.1:3306/scratch_db pytest`.

## Configuration
| Variable | Default | Notes |
|---|---|---|
| `DB_*` or `DATABASE_URL` | required | the password may contain any character |
| `JWT_SECRET`, `INTERNAL_JWT_SECRET` | required | at least 32 characters each |
| `PURCHASE_REQUEST_SERVICE_URL`, `AUTH_SERVICE_URL` | unset | without the first, decisions wait; without the second, delegation is unavailable |
| `APPROVAL_THRESHOLDS` | see `app/config.py` | JSON, per currency: `{"INR": [100000, 1000000]}` means 2 levels from the first amount, 3 from the second |
| `ESCALATION_HOURS` | 48 | pending longer than this is flagged overdue |
| `BACKGROUND_JOBS`, `RECONCILE_INTERVAL_SECONDS` | true, 20 | retry loop for decisions and the overdue check |
