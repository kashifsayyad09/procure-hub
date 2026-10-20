#!/bin/bash
# Creates one MySQL user per service with access to that service's database only.
# Passwords come from environment variables passed to the mysql container.
set -euo pipefail
: "${AUTH_DB_PASSWORD:?AUTH_DB_PASSWORD is required}"
case "$AUTH_DB_PASSWORD" in *\'*|*\\*|*\"*) echo "AUTH_DB_PASSWORD must not contain quotes or backslashes" >&2; exit 1;; esac
mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" <<SQL
CREATE USER IF NOT EXISTS 'auth_svc'@'%' IDENTIFIED BY '${AUTH_DB_PASSWORD}';
GRANT ALL PRIVILEGES ON auth_db.* TO 'auth_svc'@'%';
FLUSH PRIVILEGES;
SQL
