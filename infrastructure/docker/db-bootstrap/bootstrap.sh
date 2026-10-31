#!/bin/bash
# Idempotent: creates the 11 logical databases and one MySQL user per service, limited to that service's database.
# Runs on every `docker compose up` (the db-init service), so new services and changed passwords apply to an existing
# data volume too. Passwords come from environment variables.
set -euo pipefail
: "${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD is required}"
export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"   # keeps the password out of the process list
HOST="${MYSQL_HOST:-localhost}"
run_sql() { mysql -h"$HOST" -uroot; }

check() {  # name value: required, and no quotes or backslashes that could alter the SQL
  case "$2" in
    '') echo "$1 is required" >&2; exit 1;;
    *\'*|*\\*|*\"*) echo "$1 must not contain quotes or backslashes" >&2; exit 1;;
  esac
}

DATABASES="auth_db purchase_request_db approval_db vendor_db quotation_db purchase_order_db receiving_db invoice_db notification_db audit_db si_talker_db"
for db in $DATABASES; do
  echo "CREATE DATABASE IF NOT EXISTS \`$db\` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;" | run_sql
done

ensure_user() {  # user database password_variable_name
  local user="$1" db="$2" var="$3" pw="${!3:-}"
  check "$var" "$pw"
  run_sql <<SQL
CREATE USER IF NOT EXISTS '${user}'@'%' IDENTIFIED BY '${pw}';
ALTER USER '${user}'@'%' IDENTIFIED BY '${pw}';
GRANT ALL PRIVILEGES ON \`${db}\`.* TO '${user}'@'%';
SQL
  echo "ready: ${user} -> ${db}"
}

ensure_user auth_svc auth_db AUTH_DB_PASSWORD
ensure_user purchase_request_svc purchase_request_db PURCHASE_REQUEST_DB_PASSWORD
ensure_user approval_svc approval_db APPROVAL_DB_PASSWORD
echo "database bootstrap complete"
