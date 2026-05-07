import base64
import binascii
import concurrent.futures
import hashlib
import hmac
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / 'config.json'
load_dotenv(BASE_DIR / '.env')


def load_local_config() -> dict[str, str]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_local_config(config: dict[str, str]) -> None:
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


LOCAL_CONFIG = load_local_config()


def get_first_env(names: list[str]) -> str:
    for name in names:
        value = os.getenv(name, '').strip()
        if value:
            return value
    raise ValueError(f'缺少环境变量：{" / ".join(names)}')


MAX_IMAGE_UPLOADS = 3
ALLOWED_IMAGE_MIME_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
    'image/bmp',
}
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
IMAGE_SIGNATURES = {
    'image/jpeg': [b'\xff\xd8\xff'],
    'image/png': [b'\x89PNG\r\n\x1a\n'],
    'image/webp': [b'RIFF'],
    'image/gif': [b'GIF87a', b'GIF89a'],
    'image/bmp': [b'BM'],
}
GENERATED_SUITES_DIR = BASE_DIR / 'generated-suites'
SUPABASE_SESSION_COOKIE = 'aiimagenew_supabase_session'
SUPABASE_SESSION_SYNC_COOKIE = 'aiimagenew_supabase_session_sync'
ADMIN_SESSION_COOKIE = 'aiimagenew_admin_session'
PROTECTED_PAGE_PATHS = {'/suite', '/aplus', '/fashion', '/settings', '/generation-record'}
PUBLIC_API_PREFIXES = ('/api/auth/', '/api/admin/', '/api/app-mode', '/api/points/rules', '/api/points/quote', '/api/pay/notify', '/api/generate-mode2-image-edit-test', '/api/generate-mode2-image-edit-test/', '/api/fashion-models/upload', '/api/fashion-products/upload', '/api/reference-images/upload')
PUBLIC_PATH_PREFIXES = ('/static/', '/generated/')
PUBLIC_PATHS = {'/', '/logout'}
SUPABASE_URL = (os.getenv('SUPABASE_URL') or os.getenv('SUPABASE_PROJECT_URL') or '').strip()
SUPABASE_ANON_KEY = (os.getenv('SUPABASE_ANON_KEY') or os.getenv('SUPABASE_PUBLISHABLE_KEY') or '').strip()
SUPABASE_SERVICE_ROLE_KEY = (os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_SERVICE_KEY') or '').strip()
SUPABASE_USER_PROFILES_TABLE = 'user_profiles'
SUPABASE_POINTS_TABLE = 'user_points_balances'
SUPABASE_PAYMENTS_TABLE = 'zpay_transactions'
SUPABASE_GENERATION_TASKS_TABLE = 'generation_tasks'
GENERATION_TASK_TTL_SECONDS = max(int(os.getenv('GENERATION_TASK_TTL_SECONDS') or 7200), 300)
GENERATION_TASK_POLL_RETENTION_SECONDS = max(int(os.getenv('GENERATION_TASK_POLL_RETENTION_SECONDS') or 86400), 3600)
GENERATION_TASKS: dict[str, dict] = {}
GENERATION_TASKS_LOCK = threading.Lock()
GENERATION_TASK_CANCEL_EVENTS: dict[str, threading.Event] = {}
GENERATION_TASK_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=max(int(os.getenv('GENERATION_TASK_WORKERS') or 3), 1))
ZPAY_PID = (os.getenv('ZPAY_PID') or '').strip()
ZPAY_KEY = (os.getenv('ZPAY_KEY') or '').strip()
ZPAY_GATEWAY = (os.getenv('ZPAY_GATEWAY') or 'https://zpayz.cn/submit.php').strip()
ZPAY_NOTIFY_URL = (os.getenv('ZPAY_NOTIFY_URL') or '').strip()
ZPAY_RETURN_URL = (os.getenv('ZPAY_RETURN_URL') or '').strip()
ZPAY_DEFAULT_CHANNEL = (os.getenv('ZPAY_DEFAULT_CHANNEL') or 'alipay').strip()
ZPAY_SUCCESS_STATUSES = {'TRADE_SUCCESS', 'TRADE_FINISHED', 'SUCCESS'}
VIP_PLAN_CONFIG_TABLE = 'vip_plan_config'

REDIS_HOST = (os.getenv('REDIS_HOST') or 'localhost').strip()
REDIS_PORT = int(os.getenv('REDIS_PORT') or 6379)
REDIS_PASSWORD = (os.getenv('REDIS_PASSWORD') or '').strip() or None
REDIS_DB = int(os.getenv('REDIS_DB') or 0)
REDIS_MAX_CONNECTIONS = int(os.getenv('REDIS_MAX_CONNECTIONS') or 50)
REDIS_SOCKET_TIMEOUT = int(os.getenv('REDIS_SOCKET_TIMEOUT') or 5)
REDIS_SOCKET_CONNECT_TIMEOUT = int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT') or 5)

REDIS_CACHE_TTL = {
    'task_status': int(os.getenv('REDIS_CACHE_TTL_TASK') or 30),
    'user_points': int(os.getenv('REDIS_CACHE_TTL_POINTS') or 60),
    'user_profile': int(os.getenv('REDIS_CACHE_TTL_PROFILE') or 300),
    'vip_config': int(os.getenv('REDIS_CACHE_TTL_VIP') or 3600),
}


def get_env_csv(name: str) -> set[str]:
    raw_value = os.getenv(name, '').strip()
    return {
        value.strip().lower()
        for value in raw_value.split(',')
        if value.strip()
    }


def get_supabase_setting(name: str, default: str = '') -> str:
    if name in LOCAL_CONFIG:
        return str(LOCAL_CONFIG[name]).strip()
    return os.getenv(name, default).strip()


def get_supabase_setting_int(name: str, default: int) -> int:
    raw_value = get_supabase_setting(name, str(default))
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f'环境变量 {name} 必须为整数') from exc


def get_supabase_setting_float(name: str, default: float) -> float:
    raw_value = get_supabase_setting(name, str(default))
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(f'环境变量 {name} 必须为数字') from exc


def get_supabase_setting_bool(name: str, default: bool = False) -> bool:
    raw_value = get_supabase_setting(name, 'true' if default else 'false').lower()
    return raw_value in {'1', 'true', 'yes', 'on'}


def get_supabase_setting_csv(name: str) -> set[str]:
    raw_value = get_supabase_setting(name, '')
    return {
        value.strip().lower()
        for value in raw_value.split(',')
        if value.strip()
    }


def get_supabase_setting_json(name: str, default=None):
    raw_value = get_supabase_setting(name, '')
    if not raw_value:
        return default
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f'环境变量 {name} 必须为合法 JSON') from exc


def get_optional_env(name: str, default: str = '') -> str:
    return os.getenv(name, default).strip()


def get_optional_int_env(name: str, default: int) -> int:
    value = get_optional_env(name, str(default))
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f'环境变量 {name} 必须为整数') from exc


def get_optional_bool_env(name: str, default: bool = False) -> bool:
    raw_value = get_optional_env(name, 'true' if default else 'false').lower()
    return raw_value in {'1', 'true', 'yes', 'on'}


def build_supabase_request_url(path: str) -> str:
    return f'{SUPABASE_URL.rstrip("/")}{path}'


def _get_supabase_user_id(session_data: dict | None = None) -> str:
    session_payload = session_data or {}
    user = session_payload.get('user') or {}
    return str(user.get('id') or '').strip()


def _build_supabase_service_headers() -> dict:
    return {
        'apikey': SUPABASE_SERVICE_ROLE_KEY,
        'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
        'Content-Type': 'application/json',
    }


def _post_supabase_rpc(function_name: str, payload: dict) -> dict:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError('Supabase 服务配置缺失')

    response = requests.post(
        build_supabase_request_url(f'/rest/v1/rpc/{function_name}'),
        headers={
            **_build_supabase_service_headers(),
            'Prefer': 'return=representation',
        },
        json=payload,
        timeout=20,
    )
    response.raise_for_status()

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError('Supabase RPC 返回了无效响应') from exc


def get_mode2_allowed_image_hosts() -> set[str]:
    raw_value = get_supabase_setting('MODE2_ALLOWED_IMAGE_HOSTS', '')
    if not raw_value:
        raw_value = os.getenv('MODE2_ALLOWED_IMAGE_HOSTS', '').strip()
    allowed_hosts = {
        host.strip().lower()
        for host in raw_value.split(',')
        if host.strip()
    }
    cos_cdn_domain = os.getenv('COS_CDN_DOMAIN', '').strip()
    if cos_cdn_domain:
        parsed_domain = urlparse(cos_cdn_domain if '://' in cos_cdn_domain else f'https://{cos_cdn_domain}')
        if parsed_domain.hostname:
            allowed_hosts.add(parsed_domain.hostname.lower())
    cos_bucket = os.getenv('COS_BUCKET', '').strip()
    cos_region = os.getenv('COS_REGION', 'ap-guangzhou').strip() or 'ap-guangzhou'
    if cos_bucket:
        allowed_hosts.add(f'{cos_bucket}.cos.{cos_region}.myqcloud.com'.lower())
    return allowed_hosts


def get_settings_allowed_emails() -> set[str]:
    allowed_emails = get_env_csv('ADMIN_ALLOWED_EMAILS')
    single_email = os.getenv('ADMIN_ALLOWED_EMAIL', '').strip().lower()
    if single_email:
        allowed_emails.add(single_email)
    return allowed_emails


def get_settings_allowed_phones() -> set[str]:
    allowed_phones = get_env_csv('ADMIN_ALLOWED_PHONES')
    single_phone = os.getenv('ADMIN_ALLOWED_PHONE', '').strip().lower()
    if single_phone:
        allowed_phones.add(single_phone)
    return allowed_phones


def _normalize_supabase_setting_key(key: str) -> str:
    return str(key or '').strip().upper()


def _supabase_setting_is_sensitive(setting_key: str) -> bool:
    normalized_key = _normalize_supabase_setting_key(setting_key)
    return any(token in normalized_key for token in {'KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'PASS', 'PRIVATE'})


def _mask_supabase_setting_value(setting_value: str) -> str:
    return '••••••••' if setting_value else ''


def get_admin_password() -> str:
    return os.getenv('ADMIN_PASSWORD', '').strip()


def get_admin_session_secret() -> str:
    return os.getenv('ADMIN_SESSION_SECRET', '').strip() or SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY or 'aiimagenew-local-admin'


def _normalize_phone_identifier(value: str | None) -> str:
    normalized = str(value or '').strip().replace(' ', '').replace('-', '')
    if normalized.startswith('+86') and len(normalized) == 14:
        return normalized[3:]
    if normalized.startswith('86') and len(normalized) == 13:
        return normalized[2:]
    return normalized


def _is_truthy_flag(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def normalize_app_mode(value: str | None) -> str:
    normalized_mode = str(value or '').strip().lower()
    return normalized_mode if normalized_mode in {'mode1', 'mode2', 'mode3'} else 'mode1'


def get_app_mode() -> str:
    return normalize_app_mode(get_supabase_setting('APP_MODE', 'mode1'))


class DynamicSemaphore:

    def __init__(self, value: int = 0):
        self._cond = threading.Condition()
        self._value = value

    def acquire(self, timeout: float = None) -> bool:
        with self._cond:
            if timeout is not None and timeout > 0:
                deadline = time.time() + timeout
                while self._value <= 0:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        return False
                    self._cond.wait(remaining)
                self._value -= 1
                return True
            while self._value <= 0:
                self._cond.wait()
            self._value -= 1
            return True

    def release(self):
        with self._cond:
            self._value += 1
            self._cond.notify()

    def adjust(self, delta: int):
        with self._cond:
            self._value += delta
            if delta > 0:
                self._cond.notify_all()

    def get_value(self) -> int:
        with self._cond:
            return self._value


_round_robin_indices: dict[str, int] = {}
_round_robin_locks: dict[str, threading.Lock] = {}
_key_failure_counts: dict[str, int] = {}
_key_circuit_breaker_until: dict[str, float] = {}

_global_api_semaphore: DynamicSemaphore | None = None
_semaphore_init_lock = threading.Lock()
_semaphore_initialized = False


def _parse_api_keys(raw_keys: str) -> list[str]:
    if not raw_keys or not raw_keys.strip():
        return []
    return [k.strip() for k in raw_keys.split(',') if k.strip()]


def _get_api_concurrency_limit() -> int:
    return max(get_supabase_setting_int(
        'API_KEY_CONCURRENCY_LIMIT',
        get_optional_int_env('API_KEY_CONCURRENCY_LIMIT', 10),
    ), 1)


def _get_api_failure_threshold() -> int:
    return max(get_supabase_setting_int(
        'API_KEY_FAILURE_THRESHOLD',
        get_optional_int_env('API_KEY_FAILURE_THRESHOLD', 3),
    ), 1)


def _get_api_failure_cooldown() -> float:
    raw = get_supabase_setting(
        'API_KEY_FAILURE_COOLDOWN_SECONDS',
        get_optional_env('API_KEY_FAILURE_COOLDOWN_SECONDS', '60'),
    )
    try:
        return max(float(raw), 1.0)
    except ValueError:
        return 60.0


def _get_mode_keys(mode: str) -> list[str]:
    mode_num = mode[-1]
    key_name = f'MODE{mode_num}_IMAGE_API_KEY'
    raw = get_supabase_setting(key_name, get_optional_env(key_name, ''))
    if not raw:
        if mode_num == '1':
            raw = get_supabase_setting('ARK_API_KEY', get_optional_env('ARK_API_KEY', ''))
        elif mode_num == '3':
            raw = get_supabase_setting('OPENAI_API_KEY', get_optional_env('OPENAI_API_KEY', ''))
        if not raw:
            raw = get_supabase_setting('IMAGE_API_KEY', get_optional_env('IMAGE_API_KEY', ''))
    return _parse_api_keys(raw)


def _is_circuit_broken(key: str) -> bool:
    until = _key_circuit_breaker_until.get(key, 0)
    return until > time.time()


def _count_healthy_keys_for_mode(mode: str) -> int:
    keys = _get_mode_keys(mode)
    return sum(1 for k in keys if not _is_circuit_broken(k))


def _calculate_semaphore_capacity() -> int:
    limit = _get_api_concurrency_limit()
    total = 0
    for mode in ('mode1', 'mode2', 'mode3'):
        total += _count_healthy_keys_for_mode(mode) * limit
    return max(total, limit)


def _init_semaphore():
    global _global_api_semaphore, _semaphore_initialized
    with _semaphore_init_lock:
        if _semaphore_initialized:
            return
        capacity = _calculate_semaphore_capacity()
        _global_api_semaphore = DynamicSemaphore(capacity)
        _semaphore_initialized = True


def _adjust_semaphore_for_key_change():
    if _global_api_semaphore is None:
        return
    new_capacity = _calculate_semaphore_capacity()
    current = _global_api_semaphore.get_value()
    delta = new_capacity - current
    if delta != 0:
        _global_api_semaphore.adjust(delta)


def _sweep_recovered_keys():
    now = time.time()
    recovered = False
    for key, until in list(_key_circuit_breaker_until.items()):
        if until <= now:
            _key_circuit_breaker_until.pop(key, None)
            _key_failure_counts.pop(key, None)
            recovered = True
    if recovered:
        _adjust_semaphore_for_key_change()


def get_round_robin_api_key(mode: str) -> str:
    keys = _get_mode_keys(mode)
    if not keys:
        raise ValueError(
            f'{mode} 没有可用的 API Key，请配置 MODE{mode[-1]}_IMAGE_API_KEY'
        )
    _sweep_recovered_keys()
    lock = _round_robin_locks.get(mode)
    if lock is None:
        lock = threading.Lock()
        _round_robin_locks[mode] = lock
    now = time.time()
    with lock:
        idx = _round_robin_indices.get(mode, -1)
        for _ in range(len(keys)):
            idx = (idx + 1) % len(keys)
            key = keys[idx]
            if not _is_circuit_broken(key):
                _round_robin_indices[mode] = idx
                return key
        idx = (_round_robin_indices.get(mode, -1) + 1) % len(keys)
        key = keys[idx]
        _round_robin_indices[mode] = idx
        return key


def acquire_api_slot(timeout: float = 300) -> bool:
    _init_semaphore()
    return _global_api_semaphore.acquire(timeout)


def release_api_slot():
    if _global_api_semaphore is not None:
        _global_api_semaphore.release()


def report_key_success(key: str):
    cleared = _key_failure_counts.pop(key, None)
    if cleared is not None:
        pass
    until = _key_circuit_breaker_until.pop(key, None)
    if until is not None:
        _adjust_semaphore_for_key_change()


def report_key_failure(key: str):
    count = _key_failure_counts.get(key, 0) + 1
    _key_failure_counts[key] = count
    threshold = _get_api_failure_threshold()
    if count >= threshold and not _is_circuit_broken(key):
        cooldown = _get_api_failure_cooldown()
        _key_circuit_breaker_until[key] = time.time() + cooldown
        _adjust_semaphore_for_key_change()


def get_semaphore_stats() -> dict:
    if _global_api_semaphore is None:
        return {'initialized': False, 'value': 0}
    return {
        'initialized': True,
        'value': _global_api_semaphore.get_value(),
        'circuit_broken': dict(_key_circuit_breaker_until),
        'failure_counts': dict(_key_failure_counts),
    }
