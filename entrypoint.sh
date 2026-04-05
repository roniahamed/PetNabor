#!/bin/bash
# bash entrypoint.sh
set -e

# Ensure Django FILE_UPLOAD_TEMP_DIR exists before any management command runs.
mkdir -p /app/tmp_uploads

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Applying database migrations..."
python manage.py migrate

exec "$@"
