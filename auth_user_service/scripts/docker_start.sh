#!/bin/sh
set -e

# Run migrations
# Check if alembic/versions is empty
if [ -z "$(ls -A ./shared_migrations/auth_user/versions)" ]; then
    echo "Generating Alembic migration..."
    if ! alembic -c ./auth_user_service/alembic.ini revision --autogenerate -m "Initial auth migration"; then
        echo "Failed to generate initial migration"
        exit 1
    else
        echo "Initial migration generated..."
    fi
fi

# Run any pre-start tasks
echo "Initialyse DB and data..."
echo "Checking if pre_start.sh exists at $(pwd)/auth_user_service/scripts/pre_start.sh"
ls -l $(pwd)/auth_user_service/scripts/pre_start.sh
if ! ./auth_user_service/scripts/pre_start.sh; then
    echo "Failed to initialise DB and data"
    exit 1  # Ensure the script exits if needed
fi

if [ "$VSCODE_DEBUG" = "true" ]; then
  echo "🔍 Starting auth_user_service under vscode debugpy…"
  # Wait for VS Code to attach before running Uvicorn
  if ! python -m debugpy \
    --listen 0.0.0.0:5678 \
    --wait-for-client \
    -m uvicorn auth_user_service.main:app \
      --host 0.0.0.0 --port 8000 --reload; then
        echo "Uvicorn failed to start auth_user_service. Dropping to a shell for debugging."
        exit 1  # Ensure the script exits if needed
    fi
else
    if ! uvicorn auth_user_service.main:app --host 0.0.0.0 --port 8000 --reload; then
        echo "Uvicorn failed to start. Dropping to a shell for debugging."
        exit 1  # Ensure the script exits if needed
    fi
fi