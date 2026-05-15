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

CERTS_DIR="./traefik/certs"

if [[ ! -d "$CERTS_DIR" ]]; then
    echo "==> init-certs: no traefik/certs/ dir found — skipping"; exit 0
fi

CERT="${CERTS_DIR}/local.crt"
KEY="${CERTS_DIR}/local.key"

if [[ -f "$CERT" ]] && [[ "$ROTATE" != "true" ]]; then
    echo "==> init-certs: certs exist, skipping (--rotate to regenerate)"; exit 0
fi

echo "==> Generating self-signed TLS certificate"
openssl req -x509 -newkey rsa:2048 -keyout "$KEY" -out "$CERT" \
    -days 365 -nodes \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 "$KEY" && chmod 644 "$CERT"
echo "==> init-certs done — fingerprint: $(openssl x509 -in "$CERT" -noout -fingerprint -sha256 | cut -d= -f2)"
