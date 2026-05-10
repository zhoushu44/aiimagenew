import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

from celery import Celery
from kombu import Exchange, Queue

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import get_optional_env, get_optional_int_env

logger = logging.getLogger(__name__)

def _normalize_redis_host(value: str) -> str:
    raw_value = str(value or '').strip()
    if '://' in raw_value:
        parsed = urlparse(raw_value)
        return (parsed.hostname or raw_value).strip()
    return raw_value.strip().strip('/')


REDIS_HOST = _normalize_redis_host(get_optional_env('REDIS_HOST', '127.0.0.1'))
REDIS_PORT = get_optional_int_env('REDIS_PORT', 6379)
REDIS_PASSWORD = get_optional_env('REDIS_PASSWORD', '')
REDIS_DB_CELERY = get_optional_int_env('REDIS_DB_CELERY', 3)


def _build_celery_redis_url() -> str:
    password_segment = f':{REDIS_PASSWORD}@' if REDIS_PASSWORD else ''
    return f'redis://{password_segment}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CELERY}'


CELERY_BROKER_URL = get_optional_env('CELERY_BROKER_URL', _build_celery_redis_url())
CELERY_RESULT_BACKEND = get_optional_env('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)
CELERY_WORKER_POOL = get_optional_env('CELERY_WORKER_POOL', 'gevent')

if CELERY_WORKER_POOL == 'gevent':
    _default_concurrency = 100
    try:
        import gevent
        logger.info('Celery worker pool: gevent (gevent available)')
    except ImportError:
        logger.warning('gevent not installed, falling back to prefork pool')
        CELERY_WORKER_POOL = 'prefork'
        _default_concurrency = 30
else:
    _default_concurrency = 30

CELERY_WORKER_CONCURRENCY = max(
    get_optional_int_env(
        'PARALLEL_WORKERS',
        get_optional_int_env('CELERY_WORKER_CONCURRENCY', _default_concurrency),
    ),
    1,
)
CELERY_WORKER_PREFETCH_MULTIPLIER = max(get_optional_int_env('CELERY_WORKER_PREFETCH_MULTIPLIER', 1), 1)
CELERY_TASK_TIME_LIMIT = max(get_optional_int_env('CELERY_TASK_TIME_LIMIT', 1200), 60)
CELERY_TASK_SOFT_TIME_LIMIT = max(get_optional_int_env('CELERY_TASK_SOFT_TIME_LIMIT', 900), 30)
CELERY_PRIORITY_QUEUE_NAME = get_optional_env('CELERY_PRIORITY_QUEUE_NAME', 'generation_priority')
CELERY_NORMAL_QUEUE_NAME = get_optional_env('CELERY_NORMAL_QUEUE_NAME', 'generation_normal')


generation_exchange = Exchange('generation', type='direct')


celery_app = Celery(
    'aiimagenew',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    imports=('celery_tasks',),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=False,
    worker_concurrency=CELERY_WORKER_CONCURRENCY,
    worker_pool=CELERY_WORKER_POOL,
    worker_prefetch_multiplier=CELERY_WORKER_PREFETCH_MULTIPLIER,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_disable_rate_limits=True,
    task_time_limit=CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=CELERY_TASK_SOFT_TIME_LIMIT,
    broker_transport_options={
        'priority_steps': [0],
        'sep': ':',
        'queue_order_strategy': 'priority',
        'visibility_timeout': 7200,
        'socket_timeout': 30,
        'socket_connect_timeout': 10,
        'retry_on_timeout': True,
    },
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    result_expires=3600,
    task_queue_max_priority=9,
    task_default_priority=3,
    task_default_queue=CELERY_NORMAL_QUEUE_NAME,
    task_queues=(
        Queue(CELERY_PRIORITY_QUEUE_NAME, generation_exchange, routing_key=CELERY_PRIORITY_QUEUE_NAME, max_priority=9),
        Queue(CELERY_NORMAL_QUEUE_NAME, generation_exchange, routing_key=CELERY_NORMAL_QUEUE_NAME, max_priority=9),
    ),
)

