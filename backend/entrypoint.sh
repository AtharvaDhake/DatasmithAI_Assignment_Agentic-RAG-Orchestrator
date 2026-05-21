#!/bin/sh
set -e

python /app/embed_server.py &

until curl -sf -X POST http://localhost:8001 \
    -H "Content-Type: application/json" \
    -d '{"text":"ping"}' > /dev/null 2>&1; do
  sleep 1
done

exec /app/server
