# Database (Phase 1 foundation)

MySQL 8.4 runs locally via `docker-compose.yml`. `infrastructure/docker/mysql-init/01-create-databases.sql` creates one logical database per persistent service:
auth_db, purchase_request_db, approval_db, vendor_db, quotation_db, purchase_order_db, receiving_db, invoice_db, notification_db, audit_db, si_talker_db.

Rules for later phases: one dedicated MySQL user per service with grants only on its own database; Alembic migrations per service; no cross-database joins. The root password comes from `.env` (not committed). This setup has not been started in the build environment because Docker was unavailable.
