#!/bin/sh
set -e
set -x

# Ensure PYTHONPATH is set correctly
export PYTHONPATH=/opt/auth_user_service

echo "Current working directory: $(pwd)"

echo "Initialysing DB..."
python -m auth_user_service.scripts.fastapi_pre_start || { echo "Failed to initialise DB"; exit 1; }

# Run migrations
echo "Run Migrations"
alembic -c ./auth_user_service/alembic.ini upgrade head || { echo "Migration failed"; exit 1; }

# Create initial data in DB
echo "Create initial data in DB"
python -m auth_user_service.scripts.initial_data || { echo "Failed to create initial data"; exit 1; }
