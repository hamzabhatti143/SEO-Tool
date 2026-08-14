#!/usr/bin/env bash
# Boot Redis + DB migrations + ARQ worker + FastAPI in a single container
# (e.g. a Hugging Face Docker Space). Redis is in-memory/ephemeral, which is
# fine for a job queue — durable data lives in Postgres (Neon).
set -euo pipefail

export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-7860}"
# ARQ talks to Redis inside this container; not exposed publicly.
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379}"

echo "==> Starting Redis (ephemeral, no persistence)..."
redis-server --bind 127.0.0.1 --port 6379 --dir /home/user/redis \
  --save "" --appendonly no --daemonize yes

until redis-cli -h 127.0.0.1 -p 6379 ping >/dev/null 2>&1; do
  echo "    waiting for redis..."; sleep 0.3
done
echo "==> Redis is up."

echo "==> Applying database migrations (alembic upgrade head)..."
alembic upgrade head

echo "==> Starting ARQ worker (auto-restart on exit)..."
( while true; do
    arq app.worker.WorkerSettings || echo "    worker exited ($?); restarting in 2s"
    sleep 2
  done ) &

echo "==> Starting API on ${HOST}:${PORT}..."
exec python run.py
