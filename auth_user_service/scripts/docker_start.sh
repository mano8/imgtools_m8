#!/bin/sh
set -e

# Install local SDK override when mounted at /opt/auth_sdk_m8_src (dev only)
if [ -d /opt/auth_sdk_m8_src ]; then
    echo "Installing local auth_sdk_m8 from /opt/auth_sdk_m8_src..."
    pip install --quiet --user /opt/auth_sdk_m8_src[all]
fi

# Run migrations
# Check if alembic/versions has no .py files (ignores .gitkeep)
if [ -z "$(find /opt/shared_migrations/auth_user/versions -maxdepth 1 -name '*.py' -print -quit)" ]; then
    echo "Generating Alembic migration..."
    if ! alembic -c /opt/auth_user_service/alembic.ini revision --autogenerate -m "Initial auth migration"; then
        echo "Failed to generate initial migration"
        exit 1
    else
        echo "Initial migration generated..."
    fi
else
    echo "Migrations already exist, skipping generation."
fi

# Run any pre-start tasks
echo "Initialyse DB and data..."
echo "Checking if pre_start.sh exists at $(pwd)/auth_user_service/scripts/pre_start.sh"
ls -l $(pwd)/auth_user_service/scripts/pre_start.sh
if ! ./auth_user_service/scripts/pre_start.sh; then
    echo "Failed to initialise DB and data"
    exit 1  # Ensure the script exits if needed
fi

# CIDRs that uvicorn will trust as a reverse proxy for X-Forwarded-For.
# Override via env to match your deployment network.
TRUSTED_PROXY_IPS="${TRUSTED_PROXY_IPS:-172.16.0.0/12}"

if [ "$VSCODE_DEBUG" = "true" ]; then
  echo "Starting auth_user_service under VS Code debugpy..."
  exec python -m debugpy \
    --listen 0.0.0.0:5678 \
    --wait-for-client \
    -m uvicorn auth_user_service.main:app \
      --host 0.0.0.0 --port 8000 --reload \
      --proxy-headers \
      --forwarded-allow-ips="${TRUSTED_PROXY_IPS}"
else
  exec uvicorn auth_user_service.main:app \
      --host 0.0.0.0 --port 8000 \
      --proxy-headers \
      --forwarded-allow-ips="${TRUSTED_PROXY_IPS}"
fi