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
PUBLIC_API_PREFIXES = ('/api/auth/', '/api/admin/', '/api/app-mode', '/api/points/rules', '/api/points/quote', '/api/pay/notify')
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
    return {
        host.strip().lower()
        for host in raw_value.split(',')
        if host.strip()
    }


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
