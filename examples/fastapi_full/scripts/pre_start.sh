#!/bin/sh
set -e
set -x

# Ensure PYTHONPATH is set correctly
export PYTHONPATH=/opt/fastapi_full

echo "Current working directory: $(pwd)"

echo "Waiting for DB..."
fastapi-m8-prestart || { echo "Failed to reach DB"; exit 1; }

# Run migrations
echo "Run Migrations"
alembic -c /opt/fastapi_full/alembic.ini upgrade head || { echo "Migration failed"; exit 1; }

# Create initial data in DB
# echo "Create initial data in DB"
# python -m fastapi_full.initial_data || { echo "Failed to create initial data"; exit 1; }
