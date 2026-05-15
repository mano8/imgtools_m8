#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
bash "${SCRIPT_DIR}/../shared/scripts/init-common.sh" "$@"
exit $?
