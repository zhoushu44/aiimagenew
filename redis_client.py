import json
import logging
import os
from typing import Any, Optional

import redis
from redis.connection import ConnectionPool

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost').strip()
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '').strip() or None
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_MAX_CONNECTIONS = int(os.getenv('REDIS_MAX_CONNECTIONS', 50))
REDIS_SOCKET_TIMEOUT = int(os.getenv('REDIS_SOCKET_TIMEOUT', 5))
REDIS_SOCKET_CONNECT_TIMEOUT = int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', 5))

REDIS_CACHE_TTL = {
    'task_status': int(os.getenv('REDIS_CACHE_TTL_TASK', 30)),
    'user_points': int(os.getenv('REDIS_CACHE_TTL_POINTS', 60)),
    'user_profile': int(os.getenv('REDIS_CACHE_TTL_PROFILE', 300)),
    'vip_config': int(os.getenv('REDIS_CACHE_TTL_VIP', 3600)),
}

_redis_pool: Optional[ConnectionPool] = None
_redis_client: Optional[redis.Redis] = None


def get_redis_pool() -> ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = ConnectionPool(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            db=REDIS_DB,
            max_connections=REDIS_MAX_CONNECTIONS,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
            decode_responses=True,
        )
    return _redis_pool


def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(connection_pool=get_redis_pool())
            _redis_client.ping()
            logger.info('Redis connection established: %s:%d', REDIS_HOST, REDIS_PORT)
        except redis.RedisError as exc:
            logger.warning('Redis connection failed: %s', exc)
            _redis_client = None
    return _redis_client


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
        keys = client.keys(pattern)
        if not keys:
            return 0
        return client.delete(*keys)
    except redis.RedisError as exc:
        logger.warning('Redis cache delete pattern failed for %s: %s', pattern, exc)
        return 0


def build_task_cache_key(task_id: str) -> str:
    return f"task:{task_id}"


def build_user_points_cache_key(user_id: str) -> str:
    return f"points:{user_id}"


def build_user_profile_cache_key(user_id: str) -> str:
    return f"profile:{user_id}"


def invalidate_task_cache(task_id: str) -> bool:
    return cache_delete(build_task_cache_key(task_id))


def invalidate_user_points_cache(user_id: str) -> bool:
    return cache_delete(build_user_points_cache_key(user_id))


def invalidate_user_profile_cache(user_id: str) -> bool:
    return cache_delete(build_user_profile_cache_key(user_id))
