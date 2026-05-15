#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARED="$(cd "${SCRIPT_DIR}/../shared/scripts" && pwd)"

ROTATE_KEYS=false
ROTATE_CERTS=false

for arg in "$@"; do
    case "$arg" in
        --rotate-keys)  ROTATE_KEYS=true ;;
        --rotate-certs) ROTATE_CERTS=true ;;
        --rotate-all)   ROTATE_KEYS=true; ROTATE_CERTS=true ;;
        *) echo "Usage: $0 [--rotate-keys] [--rotate-certs] [--rotate-all]"; exit 1 ;;
    esac
done

cd "$SCRIPT_DIR"
echo "==> M8 init: $(basename "$SCRIPT_DIR")"

for old_vol in mysql_db postgres_data; do
    if [[ -d "./${old_vol}" ]]; then
        echo "WARNING: legacy volume './${old_vol}/' found — delete it before 'docker compose up'"
    fi
done
if [[ -d "./db_data" ]]; then
    echo "NOTE: db_data/ exists — init-db.sh will NOT re-run (delete to reinitialize)"
fi

run_init() {
    local script="$1" rotate="$2"
    # SC2091: compare string, do not execute it as a command
    if [[ "$rotate" == "true" ]]; then
        bash "${SHARED}/${script}" --rotate
    else
        bash "${SHARED}/${script}"
    fi
}

run_init "init-keys.sh"  "$ROTATE_KEYS"
run_init "init-certs.sh" "$ROTATE_CERTS"

echo "==> Done — DB init runs automatically on first: docker compose up -d"
