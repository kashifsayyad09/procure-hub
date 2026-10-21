# Authentication service

FastAPI service: users, login/logout, argon2id password hashing, short-lived JWT access tokens, rotating refresh tokens, role permissions.

## Run locally
```bash
cd backend/services/auth-service
python -m venv .venv && . .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
export DB_HOST=127.0.0.1 DB_PORT=3306 DB_NAME=auth_db DB_USER=auth_svc DB_PASSWORD="<AUTH_DB_PASSWORD>"
export JWT_SECRET="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
export COOKIE_SECURE=false                              # plain-http local development only
alembic upgrade head
ADMIN_PASSWORD='<a strong password>' python -m app.cli create-admin --email you@company.com --name "Your Name"
uvicorn app.main:create_app --factory --port 8001
```
OpenAPI docs: http://localhost:8001/docs. Tests: `pytest` (in-memory SQLite). To run the whole suite on MySQL, create a scratch database and set `TEST_DATABASE_URL=mysql+pymysql://user:pass@127.0.0.1:3306/scratch_db` (its tables are dropped).

## Configuration (environment variables)
| Variable | Default | Notes |
|---|---|---|
| `DB_HOST`, `DB_PORT` (3306), `DB_NAME`, `DB_USER`, `DB_PASSWORD` | required unless `DATABASE_URL` is set | Preferred: the password may contain any character |
| `DATABASE_URL` | optional | A full SQLAlchemy URL instead of the `DB_*` variables (special characters in the password must be percent-encoded) |
| `JWT_SECRET` | required | at least 32 characters; from AWS Secrets Manager in production |
| `COOKIE_SECURE` | `true` | set `false` only for local http |
| `ACCESS_TOKEN_TTL_MINUTES` | 15 | |
| `REFRESH_TOKEN_TTL_DAYS` | 7 | |
| `MAX_FAILED_LOGINS` / `LOCKOUT_MINUTES` | 5 / 15 | |
| `DOCS_ENABLED` | `true` | set `false` where the API is exposed |
