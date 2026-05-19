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

if command -v mkcert &>/dev/null; then
    echo "==> Generating mkcert TLS certificate (trusted by OS/browsers)"
    echo "    Tip: run 'mkcert -install' once to register the local CA system-wide."
    mkcert -cert-file "$CERT" -key-file "$KEY" localhost 127.0.0.1 ::1
    chmod 600 "$KEY" && chmod 644 "$CERT"
    echo "==> init-certs done (mkcert — trusted cert)"
    echo "    Chrome, Edge, Safari: trusted automatically."
    echo "    Firefox: see traefik/certs/README_DEV.md for manual CA import steps."
else
    echo ""
    echo "==> WARNING: mkcert not found — falling back to an untrusted self-signed certificate."
    echo "    All browsers will show a cert warning on https://localhost:4430."
    echo "    Chrome extensions may silently fail on fetch() calls."
    echo ""
    echo "    Note: 'docker compose up' generates certs automatically via cert-init if none"
    echo "    exist yet — you only need this script for the browser-trusted mkcert path."
    echo ""
    echo "    To get trusted certs: install mkcert, then re-run:  bash init.sh --rotate-certs"
    echo ""
    echo "    Install mkcert:"
    echo "      Windows : winget install FiloSottile.mkcert   (or: choco install mkcert)"
    echo "      macOS   : brew install mkcert && brew install nss   # nss needed for Firefox"
    echo "      Linux   : https://github.com/FiloSottile/mkcert#linux"
    echo ""
    echo "    After installing, run once: mkcert -install"
    echo ""
    # Use a self-contained temp config so openssl never needs to locate system
    # openssl.cnf (missing in many Windows / Git Bash environments).
    # CN is in the config file — no -subj flag means no MSYS_NO_PATHCONV needed.
    TMPCONF=$(mktemp)
    cat > "$TMPCONF" <<-CONF
[req]
distinguished_name = req_distinguished_name
x509_extensions    = v3_req
prompt             = no

[req_distinguished_name]
CN = localhost

[v3_req]
subjectAltName = DNS:localhost,IP:127.0.0.1
CONF

    openssl req -x509 -newkey rsa:2048 \
        -keyout "$KEY" -out "$CERT" \
        -days 365 -nodes \
        -config "$TMPCONF" \
        -extensions v3_req
    rm -f "$TMPCONF"
    chmod 600 "$KEY" && chmod 644 "$CERT"
    echo "==> init-certs done (openssl fallback) — fingerprint: $(openssl x509 -in "$CERT" -noout -fingerprint -sha256 | cut -d= -f2)"
fi
