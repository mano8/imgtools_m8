#!/usr/bin/env bash
# generate_keys.sh — generate a fresh RSA-2048 key pair for asymmetric_m8
#
# Usage:
#   cd examples/docker_compose/asymmetric_m8/keys
#   bash generate_keys.sh
#
# After running, copy the printed lines into the shared .env and auth.env.
# Never commit the private key to source control.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRIVATE_PEM="${SCRIPT_DIR}/private.pem"
PUBLIC_PEM="${SCRIPT_DIR}/public.pem"

echo "Generating RSA-2048 key pair..."
openssl genrsa -out "${PRIVATE_PEM}" 2048 2>/dev/null
openssl rsa -in "${PRIVATE_PEM}" -pubout -out "${PUBLIC_PEM}" 2>/dev/null
chmod 600 "${PRIVATE_PEM}"

PRIVATE_ONELINE=$(awk '{printf "%s\\n", $0}' "${PRIVATE_PEM}")
PUBLIC_ONELINE=$(awk '{printf "%s\\n", $0}' "${PUBLIC_PEM}")

echo ""
echo "=== Paste these into .env and auth.env ==="
echo ""
echo "ACCESS_PRIVATE_KEY=\"${PRIVATE_ONELINE}\""
echo ""
echo "ACCESS_PUBLIC_KEY=\"${PUBLIC_ONELINE}\""
echo ""
echo "# Compute ACCESS_KEY_ID (first 16 hex chars of SHA-256 of public key):"
if command -v python3 &>/dev/null; then
    KID=$(python3 -c "import hashlib; d=open('${PUBLIC_PEM}').read().strip().encode(); print(hashlib.sha256(d).hexdigest()[:16])")
    echo "ACCESS_KEY_ID=\"${KID}\""
else
    echo "# Run: python3 -c \"import hashlib; d=open('public.pem').read().strip().encode(); print(hashlib.sha256(d).hexdigest()[:16])\""
fi
echo ""
echo "Keys written to:"
echo "  ${PRIVATE_PEM}  (keep secret)"
echo "  ${PUBLIC_PEM}"
