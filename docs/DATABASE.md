# Database (Phase 1 foundation)

MySQL 8.4 runs locally via `docker-compose.yml`. `infrastructure/docker/mysql-init/01-create-databases.sql` creates one logical database per persistent service:
auth_db, purchase_request_db, approval_db, vendor_db, quotation_db, purchase_order_db, receiving_db, invoice_db, notification_db, audit_db, si_talker_db.

Rules for later phases: one dedicated MySQL user per service with grants only on its own database; Alembic migrations per service; no cross-database joins. The root password comes from `.env` (not committed). This setup has not been started in the build environment because Docker was unavailable.

## auth_db (Phase 2)
Migration `0001` (Alembic, `backend/services/auth-service/migrations`):
- `users`: id (uuid), email (unique, lowercase), full_name, password_hash, role, is_active, failed_login_attempts, locked_until, last_login_at, password_changed_at, created_at, updated_at. Indexed on email and role.
- `refresh_tokens`: id, user_id (FK, cascade delete), family_id, token_hash (unique), expires_at, created_at, revoked_at, replaced_by, user_agent. Indexed on user_id and family_id.
- Timestamps are naive UTC. Expired and revoked tokens are not purged yet; a cleanup job is a later task.

Verified: the migration runs on SQLite, matches the SQLAlchemy models (autogenerate diff is empty), downgrades cleanly, and renders valid MySQL DDL in offline mode. Not yet executed against live MySQL.
`02-create-service-users.sh` creates `auth_svc` with rights on `auth_db` only; each new service adds its own user.
