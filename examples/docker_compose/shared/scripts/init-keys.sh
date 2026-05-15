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
# Uses system python3 + stdlib only: no virtualenv, no cryptography lib dependency.
python3 - "$AUTH_ENV" "$PUB" <<'PY'
import sys, re, hashlib, subprocess

env_file, pub_path = sys.argv[1:]

result = subprocess.run(
    ['openssl', 'pkey', '-pubin', '-in', pub_path, '-pubout', '-outform', 'DER'],
    capture_output=True,
    text=False,
    check=True,
)
if not result.stdout:
    raise RuntimeError("openssl returned empty DER output — key generation may have failed")

kid = hashlib.sha256(result.stdout).hexdigest()[:16]

with open(env_file) as f:
    content = f.read()

if re.search(r'^ACCESS_KEY_ID=', content, re.M):
    content = re.sub(r'^ACCESS_KEY_ID=.*', f'ACCESS_KEY_ID={kid}', content, flags=re.M)
    with open(env_file, 'w') as f:
        f.write(content)
    print(f"    updated ACCESS_KEY_ID={kid} in {env_file}")
else:
    print(f"    WARNING: ACCESS_KEY_ID not found in {env_file}")
PY

echo "==> init-keys done: ${PRIV}, ${PUB}"
