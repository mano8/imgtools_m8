#!/usr/bin/env bash
# Runs inside the DB container via docker-entrypoint-initdb.d on first volume init only.
# Consumes env vars from the compose env_file snapshot — reads once, never re-reads.
# Requires Bash 4+ (associative arrays, ${var,,} case-folding).
set -Eeuo pipefail
IFS=$'\n\t'

# ── Policy constants ──────────────────────────────────────────────────────────
readonly IDENTIFIER_REGEX='^[A-Za-z][A-Za-z0-9_]{0,62}$'
readonly MIN_PASSWORD_LENGTH=12
readonly EXCLUDED_PREFIX_REGEX='^(MARIADB|MYSQL|POSTGRES|PG)$'
readonly -a WEAK_PASSWORDS=(
    changethis password secret admin 123456 postgres mariadb mysql
    root dev test qwerty welcome pass master default blank
)

# ── Engine detection ──────────────────────────────────────────────────────────
if   command -v mariadb &>/dev/null && command -v psql &>/dev/null; then
    echo "ERROR: ambiguous DB client — both mariadb and psql found" >&2; exit 1
elif command -v mariadb &>/dev/null; then ENGINE=mariadb
elif command -v psql    &>/dev/null; then ENGINE=postgres
else
    echo "ERROR: no supported DB client (mariadb or psql) found" >&2; exit 1
fi

# ── Helpers ───────────────────────────────────────────────────────────────────

is_nonempty() { [[ -n "${1//[[:space:]]/}" ]]; }

check_identifier() {
    local value="$1" label="$2"
    if ! [[ "$value" =~ $IDENTIFIER_REGEX ]]; then
        echo "ERROR: ${label}='${value}' — must match ^[A-Za-z][A-Za-z0-9_]{0,62}$" >&2
        return 1
    fi
}

# ── DB provisioning ───────────────────────────────────────────────────────────

create_user_and_db() {
    local user="$1" db_pass="$2" dbname="$3" prefix="$4"
    echo "==> provisioning [${prefix}] ${dbname} (${user})"
    case "$ENGINE" in
        mariadb)
            mariadb -u root -p"${MARIADB_ROOT_PASSWORD}" <<SQL
CREATE DATABASE IF NOT EXISTS \`${dbname}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${user}'@'%' IDENTIFIED BY '${db_pass}';
GRANT ALL PRIVILEGES ON \`${dbname}\`.* TO '${user}'@'%';
FLUSH PRIVILEGES;
SQL
            ;;
        postgres)
            psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${user}') THEN
        EXECUTE format('CREATE USER %I WITH PASSWORD %L', '${user}', '${db_pass}');
    END IF;
END
\$\$;
SELECT 'CREATE DATABASE "${dbname}" OWNER "${user}"'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${dbname}') \gexec
SQL
            ;;
    esac
}

# ── Discovery ─────────────────────────────────────────────────────────────────
# Collects and validates all DB triplets from the env snapshot.
# Emits sorted PREFIX|user|password|dbname lines to stdout.
# Prints all errors before exiting — never fails silently or partially.

discover_db_triplets() {
    local has_errors=false bare_any=false prefixed_any=false
    declare -a results=() prefixes=()

    # Bare DB_* (Scenario 1) — requires ALL THREE to distinguish from
    # DB_USER/DB_PASSWORD used purely for the Postgres engine superuser.
    if is_nonempty "${DB_USER:-}" && is_nonempty "${DB_PASSWORD:-}" && \
       is_nonempty "${DB_NAME:-}"; then
        bare_any=true
    fi

    # Prefixed *_DB_* (Scenarios 2-3), sorted for determinism
    while IFS= read -r varname; do
        if [[ "$varname" =~ ^([A-Z][A-Z0-9_]*)_DB_USER$ ]]; then
            local p="${BASH_REMATCH[1]}"
            if ! [[ "$p" =~ $EXCLUDED_PREFIX_REGEX ]]; then
                prefixes+=("$p")
                prefixed_any=true
            fi
        fi
    done < <(compgen -v | grep '_DB_USER$' | sort -u)

    # Ambiguity: both models active simultaneously
    if [[ $bare_any == true && $prefixed_any == true ]]; then
        echo "ERROR: ambiguous configuration — bare DB_* and prefixed *_DB_* vars both set; choose one model" >&2
        has_errors=true
    fi

    # Validate bare DB_* triplet (Scenario 1)
    if [[ $bare_any == true && $prefixed_any == false ]]; then
        local u="${DB_USER:-}" pw="${DB_PASSWORD:-}" n="${DB_NAME:-}" valid=true
        if ! is_nonempty "$u";  then echo "ERROR: DB_USER is missing or empty" >&2;    has_errors=true; valid=false; fi
        if ! is_nonempty "$pw"; then echo "ERROR: DB_PASSWORD is missing or empty" >&2; has_errors=true; valid=false; fi
        if ! is_nonempty "$n";  then echo "ERROR: DB_NAME is missing or empty" >&2;     has_errors=true; valid=false; fi
        if [[ $valid == true ]]; then
            check_identifier "$u" "DB_USER" || { has_errors=true; valid=false; }
            check_identifier "$n" "DB_NAME" || { has_errors=true; valid=false; }
        fi
        if [[ $valid == true ]]; then results+=("DEFAULT|${u}|${pw}|${n}"); fi
    fi

    # Validate prefixed triplets (Scenarios 2-3)
    for prefix in "${prefixes[@]}"; do
        local uv="${prefix}_DB_USER" pv="${prefix}_DB_PASSWORD" nv="${prefix}_DB_NAME"
        local u="${!uv:-}" pw="${!pv:-}" n="${!nv:-}" valid=true
        if ! is_nonempty "$u";  then echo "ERROR: ${uv} is missing or empty" >&2;    has_errors=true; valid=false; fi
        if ! is_nonempty "$pw"; then echo "ERROR: ${pv} is missing or empty" >&2; has_errors=true; valid=false; fi
        if ! is_nonempty "$n";  then echo "ERROR: ${nv} is missing or empty" >&2;    has_errors=true; valid=false; fi
        if [[ $valid == true ]]; then
            check_identifier "$u" "$uv" || { has_errors=true; valid=false; }
            check_identifier "$n" "$nv" || { has_errors=true; valid=false; }
        fi
        if [[ $valid == true ]]; then results+=("${prefix}|${u}|${pw}|${n}"); fi
    done

    # Nothing configured at all
    if [[ ${#results[@]} -eq 0 && $has_errors == false ]]; then
        echo "ERROR: no DB triplets found — set DB_USER/DB_PASSWORD/DB_NAME (single DB)" \
             "or PREFIX_DB_{USER,PASSWORD,NAME} vars in .env" >&2
        has_errors=true
    fi

    if [[ $has_errors == true ]]; then exit 1; fi

    printf '%s\n' "${results[@]}" | sort -u
}

# ── Cross-triplet validation ───────────────────────────────────────────────────
# Reads sorted PREFIX|user|password|dbname from stdin.
# Structural errors (isolation collapse) abort before any provisioning.
# Hygiene warnings print to stderr and do not block provisioning.

validate_cross_triplet() {
    declare -A name_to_prefix=()
    declare -A user_to_prefix=()
    declare -A pw_to_prefixes=()
    declare -a triplets=()
    declare -a warnings=()
    local has_errors=false

    while IFS='|' read -r prefix user pw dbname; do
        triplets+=("${prefix}|${user}|${pw}|${dbname}")

        # Duplicate DB_NAME → services would share one DB silently
        if [[ -n "${name_to_prefix[$dbname]:-}" ]]; then
            echo "ERROR: duplicate DB_NAME '${dbname}': ${name_to_prefix[$dbname]} and ${prefix}" >&2
            has_errors=true
        else
            name_to_prefix["$dbname"]="$prefix"
        fi

        # Duplicate DB_USER → grants of one user collapse across multiple DBs
        if [[ -n "${user_to_prefix[$user]:-}" ]]; then
            echo "ERROR: duplicate DB_USER '${user}': ${user_to_prefix[$user]} and ${prefix} — isolation collapses" >&2
            has_errors=true
        else
            user_to_prefix["$user"]="$prefix"
        fi

        # Accumulate prefixes per password (comma-separated; key is the raw password
        # but only prefix names appear in output — no raw password is ever printed)
        if [[ -n "${pw_to_prefixes[$pw]:-}" ]]; then
            pw_to_prefixes["$pw"]+=",${prefix}"
        else
            pw_to_prefixes["$pw"]="${prefix}"
        fi
    done

    if [[ $has_errors == true ]]; then exit 1; fi

    # Password hygiene warnings (grouped by shared password, sorted + deduplicated)
    for pw in "${!pw_to_prefixes[@]}"; do
        local prefix_str="${pw_to_prefixes[$pw]}"
        IFS=',' read -ra plist <<< "$prefix_str"

        if [[ ${#plist[@]} -gt 1 ]]; then
            warnings+=("WARNING: password reused across DB prefixes: ${prefix_str}")
        fi

        local normalized="${pw,,}"
        for weak in "${WEAK_PASSWORDS[@]}"; do
            if [[ "$normalized" == "$weak" ]]; then
                warnings+=("WARNING: weak placeholder password used by: ${prefix_str}")
                break
            fi
        done

        if [[ ${#pw} -lt $MIN_PASSWORD_LENGTH ]]; then
            warnings+=("WARNING: password shorter than ${MIN_PASSWORD_LENGTH} chars used by: ${prefix_str}")
        fi
    done

    if [[ ${#warnings[@]} -gt 0 ]]; then
        printf '%s\n' "${warnings[@]}" | sort -u >&2
    fi

    printf '%s\n' "${triplets[@]}"
}

# ── Main ──────────────────────────────────────────────────────────────────────

discovered="$(discover_db_triplets)"
validated="$(printf '%s\n' "$discovered" | validate_cross_triplet)"

mapfile -t TRIPLETS <<< "$validated"
[[ ${#TRIPLETS[@]} -gt 0 && -n "${TRIPLETS[0]}" ]] || {
    echo "ERROR: no valid DB triplets after validation" >&2; exit 1
}

while IFS='|' read -r prefix user pw dbname; do
    create_user_and_db "$user" "$pw" "$dbname" "$prefix"
done < <(printf '%s\n' "${TRIPLETS[@]}")

echo "==> init-db done [${ENGINE}]: provisioned ${#TRIPLETS[@]} database(s)"
