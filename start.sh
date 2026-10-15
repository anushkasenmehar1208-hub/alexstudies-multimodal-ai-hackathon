#!/bin/sh
set -e

APP_PORT="${PORT:-8080}"

if [ "${RUN_DATABASE_MIGRATIONS:-true}" = "true" ]; then
    echo "Applying idempotent database migrations"
    python3 -m alembic upgrade head
fi

echo "Starting production server on 0.0.0.0:$APP_PORT"
echo "APP_BASE_URL=${APP_BASE_URL:-not set}"
echo "DATABASE_URL=${DATABASE_URL:+set}"
echo "Frontend: /app/.web/build/client"

# Verify pre-compiled assets exist
ls -la /app/.web/ 2>/dev/null || echo "WARNING: /app/.web/ missing"
ls -la /app/.web/backend/ 2>/dev/null || echo "WARNING: backend dir missing"
ls -la /app/.web/build/client/ 2>/dev/null || echo "WARNING: frontend build missing"

# Set env vars BEFORE exec (must use __REFLEX_SKIP_COMPILE with double underscore)
export __REFLEX_SKIP_COMPILE=true
export REFLEX_WEB_WORKDIR=/app/.web

# Ensure pre-compiled frontend connects to this deployment's backend, not the old production domain
if [ -d "/app/.web/build/client/assets" ]; then
    TARGET_API="${REFLEX_API_URL:-https://alexstudies-track-d-api.onrender.com}"
    TARGET_HOST="${TARGET_API#https://}"
    TARGET_HOST="${TARGET_HOST#http://}"
    echo "Ensuring frontend connects to backend: $TARGET_API"
    sed -i "s|https://backend.alexstudies.com|${TARGET_API}|g" /app/.web/build/client/assets/*.js 2>/dev/null || true
    sed -i "s|wss://backend.alexstudies.com|wss://${TARGET_HOST}|g" /app/.web/build/client/assets/*.js 2>/dev/null || true
    sed -i "s|ws://backend.alexstudies.com|ws://${TARGET_HOST}|g" /app/.web/build/client/assets/*.js 2>/dev/null || true
fi

exec python3 production_server.py
