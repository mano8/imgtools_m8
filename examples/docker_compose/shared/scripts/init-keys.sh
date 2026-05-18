#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROTATE=false
while [[ "${1:-}" == --* ]]; do
    case "$1" in
        --rotate) ROTATE=true; shift ;;
        *) echo "Usage: $0 [--rotate]"; exit 1 ;;
    esac
done

AUTH_ENV="./auth.env"
KEYS_DIR="./keys"

[[ -f "$AUTH_ENV" ]] || { echo "ERROR: ${AUTH_ENV} not found — run from example directory"; exit 1; }

# awk: single process, returns 0 on no-match — safe under pipefail unlike grep|cut|tr
ACCESS_ALGO="$(awk -F= '/^ACCESS_TOKEN_ALGORITHM=/{gsub(/["'"'"'[:space:]]/, "", $2); print $2}' "$AUTH_ENV")"
[[ -n "$ACCESS_ALGO" ]] || { echo "ERROR: ACCESS_TOKEN_ALGORITHM not found in ${AUTH_ENV}"; exit 1; }

if [[ "$ACCESS_ALGO" != RS* ]] && [[ "$ACCESS_ALGO" != ES* ]]; then
    echo "==> init-keys: ${ACCESS_ALGO} — no key files needed"; exit 0
fi

mkdir -p "$KEYS_DIR"
PRIV="${KEYS_DIR}/private.pem"
PUB="${KEYS_DIR}/public.pem"

# SC2091: string comparison, not command execution
if [[ -f "$PRIV" ]] && [[ "$ROTATE" != "true" ]]; then
    echo "==> init-keys: keys exist, skipping (--rotate to regenerate)"; exit 0
fi

echo "==> Generating keys for ${ACCESS_ALGO}"
# No 2>/dev/null — real failures (missing openssl, unsupported algo) must surface
case "$ACCESS_ALGO" in
    RS256|RS384)
        openssl genrsa -out "$PRIV" 2048
        openssl rsa -in "$PRIV" -pubout -out "$PUB" ;;
    RS512)
        openssl genrsa -out "$PRIV" 4096
        openssl rsa -in "$PRIV" -pubout -out "$PUB" ;;
    ES256)
        openssl ecparam -name prime256v1 -genkey -noout -out "$PRIV"
        openssl ec -in "$PRIV" -pubout -out "$PUB" ;;
    ES384)
        openssl ecparam -name secp384r1 -genkey -noout -out "$PRIV"
        openssl ec -in "$PRIV" -pubout -out "$PUB" ;;
    ES512)
        openssl ecparam -name secp521r1 -genkey -noout -out "$PRIV"
        openssl ec -in "$PRIV" -pubout -out "$PUB" ;;
    *) echo "ERROR: unsupported algorithm ${ACCESS_ALGO}"; exit 1 ;;
esac

chmod 600 "$PRIV" && chmod 644 "$PUB"

# Behavior-based capability guard: test DER export on the actual generated key.
# Catches broken openssl builds without relying on --help flag heuristics.
openssl pkey -pubin -in "$PUB" -pubout -outform DER >/dev/null 2>&1 || {
    echo "ERROR: OpenSSL cannot export DER from ${PUB} — pkey subcommand unsupported or broken build"
    exit 1
}

# KID: SHA256 of canonical DER bytes — stable across PEM formatting differences.
# Pure openssl pipeline — no Python dependency (avoids Windows Store stub issue).
# awk '{print $NF}' extracts the hex digest regardless of OpenSSL version prefix format.
kid=$(openssl pkey -pubin -in "$PUB" -pubout -outform DER 2>/dev/null \
      | openssl dgst -sha256 2>/dev/null \
      | awk '{print $NF}' \
      | cut -c1-16)

[[ -n "$kid" ]] || { echo "ERROR: failed to compute KID from ${PUB}" >&2; exit 1; }

# Update ACCESS_KEY_ID in auth.env.
# Uses a temp file instead of sed -i to avoid macOS/GNU sed portability differences.
if grep -q "^ACCESS_KEY_ID=" "$AUTH_ENV"; then
    tmp=$(mktemp)
    sed "s/^ACCESS_KEY_ID=.*/ACCESS_KEY_ID=${kid}/" "$AUTH_ENV" > "$tmp" && mv "$tmp" "$AUTH_ENV"
    echo "    updated ACCESS_KEY_ID=${kid} in ${AUTH_ENV}"
else
    echo "    WARNING: ACCESS_KEY_ID not found in ${AUTH_ENV}"
fi

echo "==> init-keys done: ${PRIV}, ${PUB}"
