#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# Runs inside the DB container via docker-entrypoint-initdb.d on first volume init only.
# Receives AUTH_DB_* and API_DB_* from the container environment (set in docker-compose.yml).

if command -v mariadb &>/dev/null && command -v psql &>/dev/null; then
    echo "ERROR: ambiguous DB client environment — both mariadb and psql found"; exit 1
elif command -v mariadb &>/dev/null; then
    ENGINE=mariadb
elif command -v psql &>/dev/null; then
    ENGINE=postgres
else
    echo "ERROR: no supported DB client (mariadb or psql) found"; exit 1
fi

create_user_and_db() {
    local user="$1" password="$2" dbname="$3"
    case "$ENGINE" in
        mariadb)
            mariadb -u root -p"${MARIADB_ROOT_PASSWORD}" <<SQL
CREATE DATABASE IF NOT EXISTS \`${dbname}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${user}'@'%' IDENTIFIED BY '${password}';
-- Dev-grade: GRANT ALL includes DROP/ALTER/CREATE — restrict to DML-only for production
GRANT ALL PRIVILEGES ON \`${dbname}\`.* TO '${user}'@'%';
FLUSH PRIVILEGES;
SQL
            ;;
        postgres)
            psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${user}') THEN
        EXECUTE format('CREATE USER %I WITH PASSWORD %L', '${user}', '${password}');
    END IF;
END
\$\$;
SELECT 'CREATE DATABASE "${dbname}" OWNER "${user}"'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${dbname}') \gexec
SQL
            ;;
    esac
}

create_user_and_db "${AUTH_DB_USER}" "${AUTH_DB_PASSWORD}" "${AUTH_DB_NAME}"
create_user_and_db "${API_DB_USER}"  "${API_DB_PASSWORD}"  "${API_DB_NAME}"

echo "==> init-db done [${ENGINE}]: ${AUTH_DB_NAME} (${AUTH_DB_USER}), ${API_DB_NAME} (${API_DB_USER})"
