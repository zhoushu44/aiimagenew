import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

import redis
from dotenv import load_dotenv
from redis.connection import ConnectionPool
from urllib.parse import urlparse

load_dotenv(Path(__file__).resolve().parent / '.env')

logger = logging.getLogger(__name__)

def _normalize_redis_host(value: str) -> str:
    raw_value = str(value or '').strip()
    if '://' in raw_value:
        parsed = urlparse(raw_value)
        return (parsed.hostname or raw_value).strip()
    return raw_value.strip().strip('/')


REDIS_HOST = _normalize_redis_host(os.getenv('REDIS_HOST', 'localhost'))
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '').strip() or None
REDIS_MAX_CONNECTIONS = int(os.getenv('REDIS_MAX_CONNECTIONS', 50))
REDIS_SOCKET_TIMEOUT = float(os.getenv('REDIS_SOCKET_TIMEOUT', 30))
REDIS_SOCKET_CONNECT_TIMEOUT = float(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', 10))

REDIS_DB_DEFAULT = int(os.getenv('REDIS_DB', 0))
REDIS_DB_TASKS = int(os.getenv('REDIS_DB_TASKS', 1))
REDIS_DB_API = int(os.getenv('REDIS_DB_API', 2))
REDIS_DB_CELERY = int(os.getenv('REDIS_DB_CELERY', 3))
REDIS_DB_MONITOR = int(os.getenv('REDIS_DB_MONITOR', 4))

REDIS_CACHE_TTL = {
    'task_status_active': int(os.getenv('REDIS_CACHE_TTL_TASK_ACTIVE', 10)),
    'task_status_done': int(os.getenv('REDIS_CACHE_TTL_TASK_DONE', 300)),
    'user_points': int(os.getenv('REDIS_CACHE_TTL_POINTS', 60)),
    'user_profile': int(os.getenv('REDIS_CACHE_TTL_PROFILE', 300)),
    'vip_config': int(os.getenv('REDIS_CACHE_TTL_VIP', 3600)),
}

_RECONNECT_COOLDOWN_SECONDS = 5

_pools: dict[int, ConnectionPool] = {}
_clients: dict[int, Optional[redis.Redis]] = {}
_client_locks: dict[int, threading.Lock] = {}
_last_connect_fail_time: dict[int, float] = {}


def _get_pool(db: int) -> ConnectionPool:
    if db not in _pools:
        _pools[db] = ConnectionPool(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            db=db,
            max_connections=REDIS_MAX_CONNECTIONS,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
            retry_on_timeout=True,
            health_check_interval=30,
            decode_responses=True,
        )
    return _pools[db]


def _get_client_lock(db: int) -> threading.Lock:
    if db not in _client_locks:
        _client_locks[db] = threading.Lock()
    return _client_locks[db]


def _get_client(db: int) -> Optional[redis.Redis]:
    if db in _clients and _clients[db] is not None:
        try:
            _clients[db].ping()
            return _clients[db]
        except redis.RedisError:
            with _get_client_lock(db):
                if _clients.get(db) is not None:
                    logger.warning('Redis DB%d connection lost, reconnecting...', db)
                    _clients[db] = None
    with _get_client_lock(db):
        if _clients.get(db) is not None:
            try:
                _clients[db].ping()
                return _clients[db]
            except redis.RedisError:
                _clients[db] = None
        last_fail = _last_connect_fail_time.get(db, 0)
        if time.time() - last_fail < _RECONNECT_COOLDOWN_SECONDS:
            return None
        try:
            client = redis.Redis(connection_pool=_get_pool(db))
            client.ping()
            _clients[db] = client
            _last_connect_fail_time.pop(db, None)
            logger.info('Redis DB%d connection established: %s:%d', db, REDIS_HOST, REDIS_PORT)
            return client
        except redis.RedisError as exc:
            _clients[db] = None
            _last_connect_fail_time[db] = time.time()
            logger.warning('Redis DB%d connection failed: %s', db, exc)
            return None


def get_redis_client() -> redis.Redis:
    return _get_client(REDIS_DB_DEFAULT)


def get_tasks_redis_client() -> redis.Redis:
    return _get_client(REDIS_DB_TASKS)


def get_api_redis_client() -> redis.Redis:
    return _get_client(REDIS_DB_API)


def get_celery_redis_client() -> redis.Redis:
    return _get_client(REDIS_DB_CELERY)


def get_monitor_redis_client() -> redis.Redis:
    return _get_client(REDIS_DB_MONITOR)


def is_redis_available() -> bool:
    client = get_redis_client()
    if not client:
        return False
    try:
        client.ping()
        return True
    except redis.RedisError:
        return False


def cache_get(key: str) -> Optional[Any]:
    client = get_redis_client()
    if not client:
        return None
    try:
        value = client.get(key)
        if value:
            return json.loads(value)
        return None
    except (redis.RedisError, json.JSONDecodeError) as exc:
        logger.warning('Redis cache get failed for key %s: %s', key, exc)
        return None


def cache_set(key: str, value: Any, ttl: int = 30) -> bool:
    client = get_redis_client()
    if not client:
        return False
    try:
        serialized = json.dumps(value, ensure_ascii=False)
        client.setex(key, ttl, serialized)
        return True
    except (redis.RedisError, json.JSONEncodeError) as exc:
        logger.warning('Redis cache set failed for key %s: %s', key, exc)
        return False


def cache_delete(key: str) -> bool:
    client = get_redis_client()
    if not client:
        return False
    try:
        client.delete(key)
        return True
    except redis.RedisError as exc:
        logger.warning('Redis cache delete failed for key %s: %s', key, exc)
        return False


def cache_delete_pattern(pattern: str) -> int:
    client = get_redis_client()
    if not client:
        return 0
    try:
        deleted = 0
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                deleted += client.delete(*keys)
            if cursor == 0:
                break
        return deleted
    except redis.RedisError as exc:
        logger.warning('Redis cache delete pattern failed for %s: %s', pattern, exc)
        return 0


def tasks_cache_get(key: str) -> Optional[Any]:
    client = get_tasks_redis_client()
    if not client:
        return None
    try:
        value = client.get(key)
        if value:
            return json.loads(value)
        return None
    except (redis.RedisError, json.JSONDecodeError) as exc:
        logger.warning('Redis tasks cache get failed for key %s: %s', key, exc)
        return None


def tasks_cache_set(key: str, value: Any, ttl: int = 30) -> bool:
    client = get_tasks_redis_client()
    if not client:
        return False
    try:
        serialized = json.dumps(value, ensure_ascii=False)
        client.setex(key, ttl, serialized)
        return True
    except (redis.RedisError, json.JSONEncodeError) as exc:
        logger.warning('Redis tasks cache set failed for key %s: %s', key, exc)
        return False


def tasks_cache_delete(key: str) -> bool:
    client = get_tasks_redis_client()
    if not client:
        return False
    try:
        client.delete(key)
        return True
    except redis.RedisError as exc:
        logger.warning('Redis tasks cache delete failed for key %s: %s', key, exc)
        return False


def build_task_cache_key(task_id: str) -> str:
    return f"task:{task_id}"


def build_user_points_cache_key(user_id: str) -> str:
    return f"points:{user_id}"


def build_user_profile_cache_key(user_id: str) -> str:
    return f"profile:{user_id}"


def invalidate_task_cache(task_id: str) -> bool:
    return tasks_cache_delete(build_task_cache_key(task_id))


def invalidate_user_points_cache(user_id: str) -> bool:
    return cache_delete(build_user_points_cache_key(user_id))


def invalidate_user_profile_cache(user_id: str) -> bool:
    return cache_delete(build_user_profile_cache_key(user_id))


def get_task_cache_ttl(status: str = '') -> int:
    normalized = str(status or '').strip().lower()
    if normalized in {'pending', 'running'}:
        return REDIS_CACHE_TTL.get('task_status_active', 10)
    return REDIS_CACHE_TTL.get('task_status_done', 300)


def build_celery_redis_url() -> str:
    password_segment = f':{REDIS_PASSWORD}@' if REDIS_PASSWORD else ''
    return f'redis://{password_segment}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_CELERY}'
