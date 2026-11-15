# Database (Phase 1 foundation)

MySQL 8.4 runs locally via `docker-compose.yml`. The bootstrap script creates one logical database per persistent service:
auth_db, purchase_request_db, approval_db, vendor_db, quotation_db, purchase_order_db, receiving_db, invoice_db, notification_db, audit_db, si_talker_db.

Rules for later phases: one dedicated MySQL user per service with grants only on its own database; Alembic migrations per service; no cross-database joins. The root password comes from `.env` (not committed). This setup has not been started in the build environment because Docker was unavailable.

## auth_db (Phase 2)
Migration `0001` (Alembic, `backend/services/auth-service/migrations`):
- `users`: id (uuid), email (unique, lowercase), full_name, password_hash, role, is_active, failed_login_attempts, locked_until, last_login_at, password_changed_at, created_at, updated_at. Indexed on email and role.
- `refresh_tokens`: id, user_id (FK, cascade delete), family_id, token_hash (unique), expires_at, created_at, revoked_at, replaced_by, user_agent. Indexed on user_id and family_id.
- Timestamps are naive UTC. Expired and revoked tokens are not purged yet; a cleanup job is a later task.

Verified on SQLite and on a real MySQL 8.0.46 server: the migration upgrades, matches the SQLAlchemy models (autogenerate diff is empty), downgrades and upgrades again. MySQL 8.4 itself (the image Compose uses) was not available to test.
`infrastructure/docker/db-bootstrap/bootstrap.sh` creates the 11 databases and one user per service with rights on that service's database only. It is idempotent and runs on every `docker compose up` (the `db-init` service), so it also applies to an existing data volume and applies password changes. Each new service adds one `ensure_user` line. Passwords must not contain quotes or backslashes.

## purchase_request_db (Phase 3)
Migration `0001`:
- `purchase_requests`: id, `number` (unique), requester_id / name / email (copied from the token; not a foreign key to another service's table), department, title, justification, priority, needed_by, currency, status, `total_amount` NUMERIC(14,2), cancel_reason, `version` (optimistic lock), submitted_at, created_at, updated_at. Indexes on requester_id, created_at, (requester_id, status), (status, created_at).
- `purchase_request_items`: request_id (FK, cascade), line_no, description, quantity NUMERIC(12,3), unit, unit_price NUMERIC(14,2), notes.
- `purchase_request_documents`: request_id (FK, cascade), position, file_name, content_type, size_bytes, storage_key, `content_stored`. Details only; no file content is stored yet.
- `purchase_request_history`: request_id (FK, cascade), `seq`, from_status, to_status, actor, note.
- `number_sequences`: one counter row per year, locked while a number is allocated.

Verified on SQLite and on a real MySQL 8.0.46 server (upgrade, no drift from the models, downgrade, and 36 concurrent creates producing 36 unique, gap-free numbers). MySQL 8.4 itself was not available.

## purchase_request_db: migration 0002 (Phase 4)
Adds `approval_registered` (default false), `decided_at`, `decided_by_name`, `decision_note` to `purchase_requests`. Requests submitted before this phase get `approval_registered = false`, so the retry loop registers them with the Approval service automatically (tested by upgrading a Phase 3 database).

## approval_db (Phase 4)
Migration `0001`:
- `approvals`: one per request: `request_id` (unique, from the Purchase Request service; not a foreign key), a snapshot (number, title, justification, department, priority, currency, `total_amount` NUMERIC(14,2), needed_by, requester, items as JSON text), `status` (pending, approved, rejected, cancelled), `current_level`, `total_levels`, `decision_sync` (not_needed, pending, synced, conflict), `sync_attempts`, `last_sync_error`, timestamps.
- `approval_steps`: one per level: status (waiting, pending, approved, rejected, skipped), `assigned_to_*` (delegation), `decided_by_*`, `comment`, `activated_at`, `escalated_at`.
- `approval_history`: ordered by an explicit `seq` (MySQL timestamps have one-second precision).
- `approval_events`: the outbox, with `published_at` empty until Phases 10/11.

Verified on SQLite and real MySQL 8.0.46: upgrade, no drift from the models, downgrade, and two concurrent decisions on one step producing exactly one decision. The bootstrap script now also creates `approval_svc` with rights on `approval_db` only.

## vendor_db (Phase 5)
Migration `0001` (user `vendor_svc`, rights on `vendor_db` only):
- `vendors`: `number` (`VND-<year>-<6 digits>`, unique), `owner_id` (the auth user; unique, nullable, not a foreign key), legal and trading names, `tax_id` (normalised, unique, nullable), registration number, website, address, `country`, `payment_terms_days`, `currency`, `status` (draft, pending, verified, rejected, suspended), `status_note`, `submitted_by_id` (the reviewer must be someone else), submission and verification details, optimistic-locking `version`.
- `vendor_categories` (unique per vendor and category), `vendor_contacts` (one primary), `vendor_history` (explicit `seq`), `vendor_events` (outbox, `published_at` empty until Phases 10/11), `number_sequences`.

Verified on SQLite and real MySQL 8.0.46: upgrade, no drift from the models, downgrade, the whole suite, and a real service process running as `vendor_svc`, which is refused access to `approval_db`.

## quotation_db (Phase 6)
Migration `0001` (user `quotation_svc`, rights on `quotation_db` only; verified: reading `vendor_db` or `purchase_request_db` is denied):
- `rfqs`: `number` (`RFQ-<year>-<6 digits>`), the purchase request's id and number (a copy, not a foreign key), `active_request_id` (unique, set while the RFQ is live and cleared on cancel: one live RFQ per request), `budget_amount`, `currency`, title, description, requirements, `deadline`, `status`, `version`, timestamps and users.
- `rfq_items` (quantity `DECIMAL(12,3)`, `estimated_unit_price` `DECIMAL(14,2)`, specification), `rfq_invitations` (unique per RFQ and vendor), `quotations` (unique per RFQ and vendor, `total_amount` `DECIMAL(14,2)`), `quotation_items` (`unit_price` `DECIMAL(14,4)`, `line_total` `DECIMAL(14,2)`, unique per quotation and RFQ item), `evaluations` (one per quotation: the two manual scores and notes), `selections` (`seq`, `active_rfq_id` unique while the award stands, justification, score snapshot as JSON), `rfq_history` (explicit `seq`), `quotation_events` (outbox), `number_sequences` (per kind and year).
- Foreign keys only inside this database. Vendor and request ids are plain columns.

Verified on SQLite and real MySQL 8.0.46: upgrade, no drift from the models, downgrade (tables only, children first: an earlier autogenerated version failed on MySQL), the whole suite, a real concurrent selection race, and a real service process running as `quotation_svc`.
