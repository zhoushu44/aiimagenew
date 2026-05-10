#!/bin/sh
set -e

celery -A celery_app.celery_app worker \
  --loglevel=info \
  --pool=${CELERY_WORKER_POOL:-prefork} \
  --concurrency=${CELERY_WORKER_CONCURRENCY:-30} \
  --prefetch-multiplier=${CELERY_WORKER_PREFETCH_MULTIPLIER:-1} \
  -Q ${CELERY_PRIORITY_QUEUE_NAME:-generation_priority},${CELERY_NORMAL_QUEUE_NAME:-generation_normal} \
  -O fair \
  > /proc/1/fd/1 2>/proc/1/fd/2 &

exec gunicorn -w ${GUNICORN_WORKERS:-8} -b 0.0.0.0:${PORT:-5078} --timeout ${GUNICORN_TIMEOUT:-300} --max-requests ${GUNICORN_MAX_REQUESTS:-500} --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-50} --access-logfile - app:app
