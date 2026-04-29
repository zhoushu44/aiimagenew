import base64
import binascii
import concurrent.futures
import hashlib
import hmac
import io
import ipaddress
import json
import mimetypes
import os
import re
import shutil
import socket
import threading
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

import requests
from dotenv import load_dotenv
from flask import Flask, g, jsonify, make_response, redirect, request, send_file, send_from_directory
from openai import APIError, APIStatusError, OpenAI
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from werkzeug.exceptions import RequestEntityTooLarge

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

app = Flask(__name__, static_folder=str(BASE_DIR / 'static'), static_url_path='/static')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.after_request
def disable_static_file_cache(response):
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


@app.errorhandler(RequestEntityTooLarge)
def handle_request_entity_too_large(exc):
    limit_bytes = (app.config.get('MAX_CONTENT_LENGTH') or 0) if 'UPLOAD_MAX_BYTES' not in globals() else (app.config.get('MAX_CONTENT_LENGTH') or UPLOAD_MAX_BYTES)
    if limit_bytes:
        limit_text = f'{max(int(limit_bytes) / 1024 / 1024, 0):.1f}MB'
        message = f'上传内容过大，请压缩图片后重试，当前最大允许 {limit_text}'
    else:
        message = '上传内容过大，请压缩图片后重试'
    return jsonify({'success': False, 'error': message}), 413


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
PROTECTED_PAGE_PATHS = {'/suite', '/aplus', '/fashion', '/settings'}
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
GENERATION_TASK_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=max(int(os.getenv('GENERATION_TASK_WORKERS') or 2), 1))
ZPAY_PID = (os.getenv('ZPAY_PID') or '').strip()
ZPAY_KEY = (os.getenv('ZPAY_KEY') or '').strip()
ZPAY_GATEWAY = (os.getenv('ZPAY_GATEWAY') or 'https://zpayz.cn/submit.php').strip()
ZPAY_NOTIFY_URL = (os.getenv('ZPAY_NOTIFY_URL') or '').strip()
ZPAY_RETURN_URL = (os.getenv('ZPAY_RETURN_URL') or '').strip()
ZPAY_DEFAULT_CHANNEL = (os.getenv('ZPAY_DEFAULT_CHANNEL') or 'alipay').strip()
ZPAY_SUBSCRIPTION_PRODUCT_DAYS = (os.getenv('SUBSCRIPTION_PRODUCT_DAYS_JSON') or '{}').strip()
ZPAY_SUCCESS_STATUSES = {'TRADE_SUCCESS', 'TRADE_FINISHED', 'SUCCESS'}
PAYMENT_POINTS_PACKAGE_MAP = {
    'plan_1': 100,
    'plan_2': 300,
    'plan_3': 1000,
    'month': 100,
    'quarter': 300,
    'year': 1000,
}


def build_supabase_request_url(path: str) -> str:
    return f'{SUPABASE_URL.rstrip("/")}{path}'


def _get_supabase_user_id(session_data: dict | None = None) -> str:
    session_payload = session_data or g.get('supabase_session') or {}
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


def _fetch_user_points_row(user_id: str) -> dict | None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return None
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id:
        return None

    response = requests.get(
        build_supabase_request_url(f'/rest/v1/{SUPABASE_POINTS_TABLE}'),
        headers=_build_supabase_service_headers(),
        params={
            'select': '*',
            'user_id': f'eq.{normalized_user_id}',
            'limit': '1',
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or not payload:
        return None
    row = payload[0]
    return row if isinstance(row, dict) else None


def _normalize_points_row(points_row: dict | None, user_id: str = '') -> dict:
    payload = points_row if isinstance(points_row, dict) else {}
    normalized_user_id = str(payload.get('user_id') or user_id or '').strip()
    balance = payload.get('balance')
    if balance is None:
        balance = payload.get('points_balance')
    total_earned = payload.get('total_earned')
    total_spent = payload.get('total_spent')
    return {
        'user_id': normalized_user_id,
        'balance': int(balance or 0),
        'total_earned': int(total_earned or 0),
        'total_spent': int(total_spent or 0),
        'signup_bonus_awarded_at': payload.get('signup_bonus_awarded_at'),
        'last_daily_claim_at': payload.get('last_daily_claim_at'),
        'created_at': payload.get('created_at'),
        'updated_at': payload.get('updated_at'),
    }


def _build_legacy_points_balance_row(user_id: str) -> dict:
    normalized_user_id = str(user_id or '').strip()
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        'user_id': normalized_user_id,
        'balance': 0,
        'total_earned': 0,
        'total_spent': 0,
        'signup_bonus_awarded_at': None,
        'last_daily_claim_at': None,
        'created_at': timestamp,
        'updated_at': timestamp,
    }


def _create_legacy_points_balance_row(user_id: str) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id or not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return None
    seed_row = _build_legacy_points_balance_row(normalized_user_id)
    response = requests.post(
        build_supabase_request_url(f'/rest/v1/{SUPABASE_POINTS_TABLE}'),
        headers={
            **_build_supabase_service_headers(),
            'Prefer': 'resolution=merge-duplicates,return=representation',
        },
        json=seed_row,
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, list) and payload:
        return _normalize_points_row(payload[0], normalized_user_id)
    if isinstance(payload, dict):
        return _normalize_points_row(payload, normalized_user_id)
    return _normalize_points_row(seed_row, normalized_user_id)


def _ensure_points_balance_row_direct(user_id: str) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id:
        return None
    points_row = get_user_points_balance(normalized_user_id)
    if points_row:
        return _normalize_points_row(points_row, normalized_user_id)
    try:
        return _create_legacy_points_balance_row(normalized_user_id)
    except requests.RequestException as exc:
        app.logger.warning('Failed to create legacy points balance row for %s: %s', normalized_user_id, exc)
        return _normalize_points_row(_build_legacy_points_balance_row(normalized_user_id), normalized_user_id)


def _claim_daily_free_points_direct(user_id: str, amount: int) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    normalized_amount = max(int(amount or 0), 0)
    if not normalized_user_id:
        return None
    points_row = _ensure_points_balance_row_direct(normalized_user_id)
    if not points_row:
        return None

    last_claim_at = parse_iso_datetime(points_row.get('last_daily_claim_at'))
    now = datetime.now(timezone.utc)
    if last_claim_at and last_claim_at.astimezone(timezone.utc).date() >= now.date():
        return {
            'success': True,
            'claimed': False,
            'reason': 'already_claimed_today',
            'balance_row': points_row,
        }

    updated_row = {
        'balance': int(points_row.get('balance') or 0) + normalized_amount,
        'total_earned': int(points_row.get('total_earned') or 0) + normalized_amount,
        'last_daily_claim_at': now.isoformat(),
        'updated_at': now.isoformat(),
    }
    response = requests.patch(
        build_supabase_request_url(f'/rest/v1/{SUPABASE_POINTS_TABLE}'),
        headers={
            **_build_supabase_service_headers(),
            'Prefer': 'return=representation',
        },
        params={
            'user_id': f'eq.{normalized_user_id}',
        },
        json=updated_row,
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, list) and payload:
        updated_points_row = _normalize_points_row(payload[0], normalized_user_id)
    elif isinstance(payload, dict):
        updated_points_row = _normalize_points_row(payload, normalized_user_id)
    else:
        updated_points_row = _normalize_points_row({**points_row, **updated_row}, normalized_user_id)
    return {
        'success': True,
        'claimed': True,
        'balance_row': updated_points_row,
    }


def ensure_user_points_balance(user_id: str) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id:
        return None
    try:
        payload = _post_supabase_rpc('ensure_user_points_balance', {'p_user_id': normalized_user_id})
        if isinstance(payload, dict):
            balance_row = payload.get('balance_row') if isinstance(payload.get('balance_row'), dict) else payload
            return _normalize_points_row(balance_row, normalized_user_id)
    except requests.RequestException as exc:
        app.logger.warning('Failed to ensure user points balance for %s: %s', normalized_user_id, exc)
    except RuntimeError as exc:
        app.logger.warning('Failed to ensure user points balance for %s: %s', normalized_user_id, exc)
    return _ensure_points_balance_row_direct(normalized_user_id)


def award_signup_bonus_points(user_id: str, amount: int) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id:
        return None
    try:
        payload = _post_supabase_rpc('award_signup_bonus_points', {'p_user_id': normalized_user_id, 'p_amount': int(amount)})
    except requests.RequestException as exc:
        app.logger.warning('Failed to award signup bonus for %s: %s', normalized_user_id, exc)
        return None
    except RuntimeError as exc:
        app.logger.warning('Failed to award signup bonus for %s: %s', normalized_user_id, exc)
        return None
    return payload if isinstance(payload, dict) else None


def claim_daily_free_points(user_id: str, amount: int) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id:
        return None
    try:
        payload = _post_supabase_rpc('claim_daily_free_points', {'p_user_id': normalized_user_id, 'p_amount': int(amount)})
        if isinstance(payload, dict):
            balance_row = payload.get('balance_row') if isinstance(payload.get('balance_row'), dict) else payload
            payload['balance_row'] = _normalize_points_row(balance_row, normalized_user_id)
        return payload if isinstance(payload, dict) else None
    except requests.HTTPError as exc:
        response = getattr(exc, 'response', None)
        error_text = ''
        if response is not None:
            try:
                error_payload = response.json()
                if isinstance(error_payload, dict):
                    error_text = str(
                        error_payload.get('message')
                        or error_payload.get('error')
                        or error_payload.get('error_description')
                        or ''
                    )
            except ValueError:
                error_text = response.text or ''
        app.logger.warning('Failed to claim daily points for %s: %s', normalized_user_id, exc)
        try:
            fallback_payload = _claim_daily_free_points_direct(normalized_user_id, amount)
            if fallback_payload:
                app.logger.warning('Claim daily points fallback applied for %s after RPC HTTP failure', normalized_user_id)
                return fallback_payload
        except requests.RequestException as fallback_exc:
            app.logger.warning('Daily points fallback failed for %s: %s', normalized_user_id, fallback_exc)
        return {
            'success': False,
            'claimed': False,
            'error': error_text or '领取失败，请稍后重试',
            'balance_row': get_user_points_balance(normalized_user_id) or ensure_user_points_balance(normalized_user_id) or {},
        }
    except requests.RequestException as exc:
        app.logger.warning('Failed to claim daily points for %s: %s', normalized_user_id, exc)
        try:
            fallback_payload = _claim_daily_free_points_direct(normalized_user_id, amount)
            if fallback_payload:
                app.logger.warning('Claim daily points fallback applied for %s after RPC request failure', normalized_user_id)
                return fallback_payload
        except requests.RequestException as fallback_exc:
            app.logger.warning('Daily points fallback failed for %s: %s', normalized_user_id, fallback_exc)
        return {
            'success': False,
            'claimed': False,
            'error': '领取失败，请稍后重试',
            'balance_row': get_user_points_balance(normalized_user_id) or ensure_user_points_balance(normalized_user_id) or {},
        }
    except RuntimeError as exc:
        app.logger.warning('Failed to claim daily points for %s: %s', normalized_user_id, exc)
        try:
            fallback_payload = _claim_daily_free_points_direct(normalized_user_id, amount)
            if fallback_payload:
                app.logger.warning('Claim daily points fallback applied for %s after RPC runtime failure', normalized_user_id)
                return fallback_payload
        except requests.RequestException as fallback_exc:
            app.logger.warning('Daily points fallback failed for %s: %s', normalized_user_id, fallback_exc)
        return {
            'success': False,
            'claimed': False,
            'error': str(exc) or '领取失败，请稍后重试',
            'balance_row': get_user_points_balance(normalized_user_id) or ensure_user_points_balance(normalized_user_id) or {},
        }


def _spend_user_points_direct(user_id: str, amount: int, transaction_type: str = 'consume', reason: str = '', metadata: dict | None = None) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    normalized_amount = int(amount)
    if not normalized_user_id or normalized_amount <= 0:
        return None
    points_row = _ensure_points_balance_row_direct(normalized_user_id)
    if not points_row:
        return None
    previous_balance = int(points_row.get('balance') or 0)
    if previous_balance < normalized_amount:
        return {
            'success': False,
            'spent': False,
            'error': 'INSUFFICIENT_POINTS',
            'balance_row': points_row,
        }
    updated_row = {
        'balance': previous_balance - normalized_amount,
        'total_spent': int(points_row.get('total_spent') or 0) + normalized_amount,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    response = requests.patch(
        build_supabase_request_url(f'/rest/v1/{SUPABASE_POINTS_TABLE}'),
        headers={
            **_build_supabase_service_headers(),
            'Prefer': 'return=representation',
        },
        params={
            'user_id': f'eq.{normalized_user_id}',
            'balance': f'gte.{normalized_amount}',
        },
        json=updated_row,
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or not payload:
        balance_row = get_user_points_balance(normalized_user_id) or points_row
        return {
            'success': False,
            'spent': False,
            'error': 'INSUFFICIENT_POINTS',
            'balance_row': balance_row,
        }
    balance_row = _normalize_points_row(payload[0], normalized_user_id)
    transaction_row = None
    try:
        transaction_response = requests.post(
            build_supabase_request_url('/rest/v1/user_points_transactions'),
            headers={
                **_build_supabase_service_headers(),
                'Prefer': 'return=representation',
            },
            json={
                'user_id': normalized_user_id,
                'amount': -normalized_amount,
                'balance_before': previous_balance,
                'balance_after': int(balance_row.get('balance') or 0),
                'transaction_type': str(transaction_type or 'consume').strip() or 'consume',
                'reason': str(reason or '').strip(),
                'metadata': metadata if isinstance(metadata, dict) else {},
            },
            timeout=20,
        )
        transaction_response.raise_for_status()
        transaction_payload = transaction_response.json()
        if isinstance(transaction_payload, list) and transaction_payload:
            transaction_row = transaction_payload[0]
        elif isinstance(transaction_payload, dict):
            transaction_row = transaction_payload
    except requests.RequestException as exc:
        app.logger.warning('Failed to insert direct spend transaction for %s: %s', normalized_user_id, exc)
    return {
        'success': True,
        'spent': True,
        'balance_row': balance_row,
        'transaction_row': transaction_row,
    }


def spend_user_points(user_id: str, amount: int, transaction_type: str = 'consume', reason: str = '', metadata: dict | None = None) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id:
        return None
    normalized_amount = int(amount)
    normalized_transaction_type = str(transaction_type or 'consume').strip() or 'consume'
    normalized_reason = str(reason or '').strip()
    normalized_metadata = metadata if isinstance(metadata, dict) else {}

    def build_spend_failure(error_message: str = '') -> dict:
        balance_row = get_user_points_balance(normalized_user_id) or ensure_user_points_balance(normalized_user_id) or {}
        return {
            'success': False,
            'spent': False,
            'error': str(error_message or '扣减积分失败').strip() or '扣减积分失败',
            'balance_row': balance_row,
        }

    rpc_payloads = [
        {
            'p_user_id': normalized_user_id,
            'p_amount': normalized_amount,
            'p_transaction_type': normalized_transaction_type,
            'p_reason': normalized_reason,
            'p_metadata': normalized_metadata,
        },
        {
            'target_user_id': normalized_user_id,
            'spend_points': normalized_amount,
            'target_type': normalized_transaction_type,
            'target_reason': normalized_reason,
            'target_metadata': normalized_metadata,
        },
        {
            'p_user_id': normalized_user_id,
            'p_amount': normalized_amount,
        },
    ]
    last_error_text = ''
    last_exception = None
    for rpc_payload in rpc_payloads:
        try:
            payload = _post_supabase_rpc('spend_user_points', rpc_payload)
            if isinstance(payload, dict):
                if payload.get('spent') is True:
                    return payload
                if payload.get('success') is True and payload.get('spent') is False:
                    return payload
                if 'balance' in payload and 'user_id' in payload:
                    return {
                        'success': True,
                        'spent': True,
                        'balance_row': _normalize_points_row(payload, normalized_user_id),
                    }
            return payload if isinstance(payload, dict) else None
        except requests.HTTPError as exc:
            last_exception = exc
            response = getattr(exc, 'response', None)
            error_text = ''
            if response is not None:
                try:
                    error_payload = response.json()
                    if isinstance(error_payload, dict):
                        error_text = str(
                            error_payload.get('message')
                            or error_payload.get('error')
                            or error_payload.get('error_description')
                            or ''
                        )
                except ValueError:
                    error_text = response.text or ''
            last_error_text = error_text
            if response is not None and response.status_code >= 400 and (
                '积分余额不足' in error_text or 'INSUFFICIENT_POINTS' in error_text
            ):
                try:
                    fallback_result = _spend_user_points_direct(normalized_user_id, normalized_amount, normalized_transaction_type, normalized_reason, normalized_metadata)
                    if isinstance(fallback_result, dict) and fallback_result.get('spent'):
                        return fallback_result
                except requests.RequestException as fallback_exc:
                    app.logger.warning('Direct spend user points fallback failed for %s: %s', normalized_user_id, fallback_exc)
                    return build_spend_failure(str(fallback_exc))
                balance_row = get_user_points_balance(normalized_user_id) or ensure_user_points_balance(normalized_user_id) or {}
                return {
                    'success': False,
                    'spent': False,
                    'error': 'INSUFFICIENT_POINTS',
                    'balance_row': balance_row,
                }
            if response is not None and response.status_code == 404 and 'Could not find the function' in error_text:
                continue
            if response is not None and response.status_code == 400 and 'INSUFFICIENT_POINTS' in error_text:
                try:
                    return _spend_user_points_direct(normalized_user_id, normalized_amount, normalized_transaction_type, normalized_reason, normalized_metadata)
                except requests.RequestException as fallback_exc:
                    app.logger.warning('Direct spend user points fallback failed for %s: %s', normalized_user_id, fallback_exc)
                    return build_spend_failure(str(fallback_exc))
            app.logger.warning('Failed to spend user points for %s: %s', normalized_user_id, exc)
            return build_spend_failure(error_text or str(exc))
        except requests.RequestException as exc:
            app.logger.warning('Failed to spend user points for %s: %s', normalized_user_id, exc)
            return build_spend_failure(str(exc))
        except RuntimeError as exc:
            last_exception = exc
            last_error_text = str(exc)
            if '返回了无效响应' in last_error_text:
                continue
            app.logger.warning('Failed to spend user points for %s: %s', normalized_user_id, exc)
            return build_spend_failure(last_error_text)
    app.logger.warning('Failed to spend user points for %s after trying compatible RPC payloads: %s', normalized_user_id, last_exception or last_error_text)
    return build_spend_failure(last_error_text or str(last_exception or '扣减积分失败'))


def add_user_points_direct(user_id: str, amount: int, transaction_type: str = 'refund', reason: str = '', metadata: dict | None = None, related_transaction_id=None) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    normalized_amount = max(int(amount), 0)
    if not normalized_user_id or normalized_amount <= 0:
        return None
    points_row = _ensure_points_balance_row_direct(normalized_user_id)
    if not points_row:
        return None
    previous_balance = int(points_row.get('balance') or 0)
    updated_row = {
        'balance': previous_balance + normalized_amount,
        'total_earned': int(points_row.get('total_earned') or 0) + normalized_amount,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    response = requests.patch(
        build_supabase_request_url(f'/rest/v1/{SUPABASE_POINTS_TABLE}'),
        headers={
            **_build_supabase_service_headers(),
            'Prefer': 'return=representation',
        },
        params={
            'user_id': f'eq.{normalized_user_id}',
        },
        json=updated_row,
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or not payload:
        return get_user_points_balance(normalized_user_id) or points_row
    balance_row = _normalize_points_row(payload[0], normalized_user_id)
    transaction_row = None
    try:
        transaction_response = requests.post(
            build_supabase_request_url('/rest/v1/user_points_transactions'),
            headers={
                **_build_supabase_service_headers(),
                'Prefer': 'return=representation',
            },
            json={
                'user_id': normalized_user_id,
                'amount': normalized_amount,
                'balance_before': previous_balance,
                'balance_after': int(balance_row.get('balance') or 0),
                'transaction_type': str(transaction_type or 'refund').strip() or 'refund',
                'reason': str(reason or '').strip(),
                'metadata': metadata if isinstance(metadata, dict) else {},
                'related_transaction_id': related_transaction_id,
            },
            timeout=20,
        )
        transaction_response.raise_for_status()
        transaction_payload = transaction_response.json()
        if isinstance(transaction_payload, list) and transaction_payload:
            transaction_row = transaction_payload[0]
        elif isinstance(transaction_payload, dict):
            transaction_row = transaction_payload
    except requests.RequestException as exc:
        app.logger.warning('Failed to insert direct add transaction for %s: %s', normalized_user_id, exc)
    return {
        'success': True,
        'added': True,
        'balance_row': balance_row,
        'transaction_row': transaction_row,
    }


def add_user_points(user_id: str, amount: int, transaction_type: str = 'refund', reason: str = '', metadata: dict | None = None, related_transaction_id=None) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id:
        return None
    normalized_amount = max(int(amount), 0)
    if normalized_amount <= 0:
        return ensure_user_points_balance(normalized_user_id) or get_user_points_balance(normalized_user_id)
    normalized_metadata = metadata if isinstance(metadata, dict) else {}
    rpc_payloads = [
        {
            'p_user_id': normalized_user_id,
            'p_amount': normalized_amount,
            'p_transaction_type': str(transaction_type or 'refund').strip() or 'refund',
            'p_reason': str(reason or '').strip(),
            'p_metadata': normalized_metadata,
            'p_related_transaction_id': related_transaction_id,
        },
        {
            'p_user_id': normalized_user_id,
            'p_amount': normalized_amount,
            'p_transaction_type': str(transaction_type or 'refund').strip() or 'refund',
            'p_reason': str(reason or '').strip(),
            'p_metadata': normalized_metadata,
        },
    ]
    last_exception = None
    for rpc_payload in rpc_payloads:
        try:
            payload = _post_supabase_rpc('add_user_points', rpc_payload)
            return payload if isinstance(payload, dict) else None
        except requests.HTTPError as exc:
            last_exception = exc
            response = getattr(exc, 'response', None)
            error_text = ''
            if response is not None:
                try:
                    error_payload = response.json()
                    if isinstance(error_payload, dict):
                        error_text = str(error_payload.get('message') or error_payload.get('error') or '')
                except ValueError:
                    error_text = response.text or ''
            if response is not None and response.status_code == 404 and 'Could not find the function' in error_text:
                continue
            app.logger.warning('Failed to add user points for %s: %s', normalized_user_id, exc)
            break
        except (requests.RequestException, RuntimeError) as exc:
            last_exception = exc
            app.logger.warning('Failed to add user points for %s: %s', normalized_user_id, exc)
            break
    try:
        return add_user_points_direct(normalized_user_id, normalized_amount, transaction_type, reason, normalized_metadata, related_transaction_id)
    except requests.RequestException as fallback_exc:
        app.logger.warning('Direct add user points fallback failed for %s after %s: %s', normalized_user_id, last_exception, fallback_exc)
        return None


def serialize_points_payload(points_row: dict | None, user_profile_row: dict | None = None) -> dict:
    payload = _normalize_points_row(points_row)
    profile_payload = user_profile_row if isinstance(user_profile_row, dict) else {}
    subscribe_expire = profile_payload.get('subscribe_expire')
    subscribe_expire_at = parse_iso_datetime(subscribe_expire)
    membership_active = bool(subscribe_expire_at and subscribe_expire_at > datetime.now(timezone.utc))
    return {
        'balance': int(payload.get('balance') or 0),
        'total_earned': int(payload.get('total_earned') or 0),
        'total_spent': int(payload.get('total_spent') or 0),
        'signup_bonus_awarded_at': payload.get('signup_bonus_awarded_at'),
        'last_daily_claim_at': payload.get('last_daily_claim_at'),
        'signup_bonus': POINTS_SIGNUP_BONUS,
        'daily_free': POINTS_DAILY_FREE,
        'subscribe_expire': subscribe_expire,
        'membership_active': membership_active,
    }


def get_user_points_balance(user_id: str) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id:
        return None
    try:
        return _fetch_user_points_row(normalized_user_id)
    except requests.RequestException as exc:
        app.logger.warning('Failed to fetch user points balance for %s: %s', normalized_user_id, exc)
        return None


def parse_money_amount(value) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('金额格式不正确') from exc
    if amount <= Decimal('0.00'):
        raise ValueError('金额必须大于 0')
    return amount


def get_payment_points_amount(package_id: str) -> int:
    normalized_package_id = str(package_id or '').strip()
    if not normalized_package_id:
        return 0
    return max(int(PAYMENT_POINTS_PACKAGE_MAP.get(normalized_package_id, 0) or 0), 0)


def grant_payment_points_once(order_row: dict) -> dict | None:
    user_id = str((order_row or {}).get('user_id') or '').strip()
    order_no = get_payment_order_no(order_row)
    package_id = get_payment_package_id(order_row)
    points_amount = get_payment_points_amount(package_id)
    if not user_id or not order_no or points_amount <= 0:
        return None
    existing_response = requests.get(
        build_supabase_request_url('/rest/v1/user_points_transactions'),
        headers=_build_supabase_service_headers(),
        params={
            'select': 'id',
            'user_id': f'eq.{user_id}',
            'transaction_type': 'eq.purchase',
            'metadata->>order_no': f'eq.{order_no}',
            'limit': '1',
        },
        timeout=20,
    )
    existing_response.raise_for_status()
    existing_payload = existing_response.json()
    if isinstance(existing_payload, list) and existing_payload:
        return get_user_points_balance(user_id)
    return add_user_points(
        user_id,
        points_amount,
        'purchase',
        '购买积分套餐入账',
        {
            'order_no': order_no,
            'package_id': package_id,
            'amount': str((order_row or {}).get('amount') or ''),
            'zpay_trade_no': get_payment_trade_no(order_row),
        },
    )


def load_subscription_days_config() -> dict[str, int]:
    try:
        payload = json.loads(ZPAY_SUBSCRIPTION_PRODUCT_DAYS or '{}')
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, int] = {}
    for key, value in payload.items():
        key_str = str(key or '').strip()
        if not key_str:
            continue
        try:
            normalized[key_str] = max(int(value), 0)
        except (TypeError, ValueError):
            continue
    return normalized


def get_subscription_days(product_id: str) -> int:
    normalized_product_id = str(product_id or '').strip()
    days = load_subscription_days_config().get(normalized_product_id, 0)
    if days <= 0:
        raise ValueError(f'订阅商品 {normalized_product_id} 未配置有效时长')
    return days


def generate_payment_order_no() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:12]}"[:32]


def _extract_single_supabase_row(payload, *, allow_empty: bool = False) -> dict | None:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        if not payload:
            return {} if allow_empty else None
        row = payload[0]
        return row if isinstance(row, dict) else None
    return None


def _safe_json_payload(payload):
    try:
        return json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        return None


def is_generation_task_persistence_enabled() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def build_generation_task_db_payload(task: dict) -> dict:
    payload = task if isinstance(task, dict) else {}
    return {
        'id': payload.get('task_id'),
        'user_id': payload.get('user_id'),
        'mode': payload.get('mode') or 'suite',
        'request_id': payload.get('request_id') or None,
        'status': payload.get('status') or 'pending',
        'result': _safe_json_payload(payload.get('result')),
        'error': payload.get('error') or None,
        'details': payload.get('details') or None,
        'spend_record': _safe_json_payload(payload.get('spend_record')),
        'refunded': bool(payload.get('refunded')),
        'refund_error': payload.get('refund_error') or None,
        'created_at': payload.get('created_at') or datetime.now(timezone.utc).isoformat(),
        'updated_at': payload.get('updated_at') or datetime.now(timezone.utc).isoformat(),
    }


def normalize_generation_task_row(row: dict | None) -> dict | None:
    if not isinstance(row, dict):
        return None
    task_id = str(row.get('id') or row.get('task_id') or '').strip()
    if not task_id:
        return None
    return {
        'task_id': task_id,
        'user_id': str(row.get('user_id') or '').strip(),
        'mode': row.get('mode') or 'suite',
        'request_id': row.get('request_id') or '',
        'spend_record': row.get('spend_record') if isinstance(row.get('spend_record'), dict) else None,
        'status': row.get('status') or 'pending',
        'result': row.get('result') if isinstance(row.get('result'), dict) else None,
        'error': row.get('error') or '',
        'details': row.get('details') or '',
        'refunded': bool(row.get('refunded')),
        'refund_error': row.get('refund_error') or '',
        'created_at': row.get('created_at'),
        'updated_at': row.get('updated_at'),
        'created_at_ts': time.time(),
        'updated_at_ts': time.time(),
    }


def persist_generation_task(task: dict) -> None:
    if not is_generation_task_persistence_enabled():
        return
    db_payload = build_generation_task_db_payload(task)
    if not db_payload.get('id') or not db_payload.get('user_id'):
        return
    try:
        response = requests.post(
            build_supabase_request_url(f'/rest/v1/{SUPABASE_GENERATION_TASKS_TABLE}'),
            headers={
                **_build_supabase_service_headers(),
                'Prefer': 'resolution=merge-duplicates,return=minimal',
            },
            params={'on_conflict': 'id'},
            json=db_payload,
            timeout=20,
        )
        if response.status_code >= 400:
            app.logger.warning('Failed to persist generation task %s: status=%s body=%s', db_payload.get('id'), response.status_code, response.text)
            response.raise_for_status()
    except Exception as exc:
        app.logger.warning('Failed to persist generation task %s: %s', db_payload.get('id'), exc)


def fetch_generation_task_row(task_id: str) -> dict | None:
    if not is_generation_task_persistence_enabled():
        return None
    normalized_task_id = str(task_id or '').strip()
    if not normalized_task_id:
        return None
    try:
        response = requests.get(
            build_supabase_request_url(f'/rest/v1/{SUPABASE_GENERATION_TASKS_TABLE}'),
            headers=_build_supabase_service_headers(),
            params={
                'select': '*',
                'id': f'eq.{normalized_task_id}',
                'limit': '1',
            },
            timeout=20,
        )
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            app.logger.warning('Failed to fetch generation task %s: status=%s body=%s', normalized_task_id, response.status_code, response.text)
            return None
        return _extract_single_supabase_row(response.json())
    except Exception as exc:
        app.logger.warning('Failed to fetch generation task %s: %s', normalized_task_id, exc)
        return None


def cache_generation_task(task: dict | None) -> None:
    if not isinstance(task, dict) or not task.get('task_id'):
        return
    with GENERATION_TASKS_LOCK:
        GENERATION_TASKS[str(task.get('task_id'))] = dict(task)


def cleanup_generation_tasks():
    now = time.time()
    with GENERATION_TASKS_LOCK:
        stale_ids = [
            task_id
            for task_id, task in GENERATION_TASKS.items()
            if now - float(task.get('updated_at_ts') or task.get('created_at_ts') or now) > GENERATION_TASK_POLL_RETENTION_SECONDS
        ]
        for task_id in stale_ids:
            GENERATION_TASKS.pop(task_id, None)


def create_generation_task(user_id: str, mode: str, request_id: str = '', spend_record: dict | None = None) -> dict:
    cleanup_generation_tasks()
    now = time.time()
    task_id = uuid.uuid4().hex
    task = {
        'task_id': task_id,
        'user_id': str(user_id or '').strip(),
        'mode': str(mode or 'suite').strip() or 'suite',
        'request_id': str(request_id or '').strip(),
        'spend_record': spend_record if isinstance(spend_record, dict) else None,
        'status': 'pending',
        'result': None,
        'error': '',
        'details': '',
        'refunded': False,
        'refund_error': '',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'created_at_ts': now,
        'updated_at_ts': now,
    }
    cache_generation_task(task)
    persist_generation_task(task)
    return serialize_generation_task(task)


def update_generation_task(task_id: str, **patch) -> dict | None:
    normalized_task_id = str(task_id or '').strip()
    if not normalized_task_id:
        return None
    with GENERATION_TASKS_LOCK:
        task = GENERATION_TASKS.get(normalized_task_id)
        if not task:
            db_task = normalize_generation_task_row(fetch_generation_task_row(normalized_task_id))
            if not db_task:
                return None
            task = db_task
            GENERATION_TASKS[normalized_task_id] = task
        task.update(patch)
        task['updated_at'] = datetime.now(timezone.utc).isoformat()
        task['updated_at_ts'] = time.time()
        snapshot = dict(task)
    persist_generation_task(snapshot)
    return snapshot


def get_generation_task(task_id: str) -> dict | None:
    normalized_task_id = str(task_id or '').strip()
    if not normalized_task_id:
        return None
    cleanup_generation_tasks()
    db_task = normalize_generation_task_row(fetch_generation_task_row(normalized_task_id))
    if db_task:
        cache_generation_task(db_task)
        return db_task
    with GENERATION_TASKS_LOCK:
        task = GENERATION_TASKS.get(normalized_task_id)
        return dict(task) if task else None


def serialize_generation_task(task: dict | None) -> dict:
    payload = task if isinstance(task, dict) else {}
    return {
        'task_id': payload.get('task_id'),
        'mode': payload.get('mode'),
        'request_id': payload.get('request_id') or '',
        'status': payload.get('status') or 'missing',
        'result': payload.get('result') if isinstance(payload.get('result'), dict) else None,
        'error': payload.get('error') or '',
        'details': payload.get('details') or '',
        'refunded': bool(payload.get('refunded')),
        'refund_error': payload.get('refund_error') or '',
        'created_at': payload.get('created_at'),
        'updated_at': payload.get('updated_at'),
    }


def fail_generation_task_with_refund(task_id: str, error: str, details: str = ''):
    task = update_generation_task(task_id, status='failed', error=str(error or '生成失败'), details=str(details or ''))
    if not task:
        return
    spend_record = task.get('spend_record') if isinstance(task.get('spend_record'), dict) else None
    if not spend_record or bool(spend_record.get('skipped')) or int(spend_record.get('amount') or 0) <= 0:
        return
    refund_amount = int(spend_record.get('amount') or 0)
    try:
        request_id = str(task.get('request_id') or spend_record.get('requestId') or (spend_record.get('metadata') or {}).get('request_id') or '').strip()
        if not request_id:
            update_generation_task(task_id, refund_error='缺少 request_id，无法自动返还积分')
            return
        metadata = spend_record.get('metadata') if isinstance(spend_record.get('metadata'), dict) else {}
        existing_refund = find_refund_transaction_for_request(task.get('user_id'), request_id)
        if existing_refund:
            update_generation_task(task_id, refunded=True)
            return
        spend_row = find_refundable_spend_transaction(task.get('user_id'), request_id, refund_amount, str(spend_record.get('type') or '').strip())
        if not spend_row:
            spend_row = find_refundable_spend_transaction(task.get('user_id'), request_id, refund_amount)
        if not spend_row:
            update_generation_task(task_id, refund_error='未找到匹配的原始扣费记录，无法自动返还积分')
            return
        refund_metadata = {
            **metadata,
            'request_id': request_id,
            'refunded': True,
            'refund_reason': 'generation_task_failed',
            'generation_task_id': task_id,
            'refunded_spend_transaction_id': spend_row.get('id'),
        }
        add_user_points(
            task.get('user_id'),
            refund_amount,
            'refund',
            f'{spend_record.get("reason") or "生成消耗"}失败返还',
            refund_metadata,
            spend_row.get('id'),
        )
        update_generation_task(task_id, refunded=True, refund_error='')
    except Exception as exc:
        app.logger.warning('Failed to refund generation task %s: %s', task_id, exc)
        update_generation_task(task_id, refund_error=str(exc))


def run_generation_task(task_id: str, form_payload: dict, file_payloads: dict):
    update_generation_task(task_id, status='running')
    try:
        result = build_generation_result_from_payload(form_payload, file_payloads)
        update_generation_task(task_id, status='succeeded', result=result, error='', details='')
    except RequestEntityTooLarge as exc:
        fail_generation_task_with_refund(task_id, '上传内容过大，请压缩图片后重试', str(exc))
    except ValueError as exc:
        fail_generation_task_with_refund(task_id, str(exc))
    except RuntimeError as exc:
        payload, _status_code = parse_runtime_error(exc)
        fail_generation_task_with_refund(task_id, payload.get('error') or str(exc), payload.get('details') or '')
    except (APIError, APIStatusError) as exc:
        payload, _status_code = parse_ark_exception(exc)
        fail_generation_task_with_refund(task_id, payload.get('error') or '图像生成接口调用失败', payload.get('details') or '')
    except requests.Timeout as exc:
        fail_generation_task_with_refund(task_id, '请求超时，请稍后重试', str(exc))
    except requests.RequestException as exc:
        fail_generation_task_with_refund(task_id, f'请求失败：{exc}', str(exc))
    except Exception as exc:
        app.logger.exception('Generation task failed: %s', task_id)
        fail_generation_task_with_refund(task_id, f'服务端异常：{exc}', str(exc))


def get_payment_order_no(order_row: dict | None) -> str:
    return str((order_row or {}).get('order_no') or (order_row or {}).get('out_trade_no') or '').strip()


def get_payment_pay_type(order_row: dict | None) -> str:
    return str((order_row or {}).get('pay_type') or (order_row or {}).get('type') or '').strip()


def get_payment_package_id(order_row: dict | None) -> str:
    return str((order_row or {}).get('package_id') or (order_row or {}).get('product_id') or '').strip()


def get_payment_trade_no(order_row: dict | None) -> str:
    return str((order_row or {}).get('zpay_trade_no') or (order_row or {}).get('trade_no') or '').strip()


def get_payment_subscribe_start(order_row: dict | None) -> str:
    return str((order_row or {}).get('subscribe_start_at') or (order_row or {}).get('subscribe_start') or '').strip()


def get_payment_subscribe_expire(order_row: dict | None) -> str:
    return str((order_row or {}).get('subscribe_expire_at') or (order_row or {}).get('subscribe_expire') or '').strip()



def build_legacy_payment_order_payload(order_payload: dict) -> dict:
    return {
        'out_trade_no': order_payload.get('order_no'),
        'user_id': order_payload.get('user_id'),
        'amount': order_payload.get('amount'),
        'status': order_payload.get('status'),
        'type': order_payload.get('pay_type'),
        'product_id': order_payload.get('package_id'),
        'trade_no': order_payload.get('zpay_trade_no'),
        'subscribe_start': order_payload.get('subscribe_start_at'),
        'subscribe_expire': order_payload.get('subscribe_expire_at'),
    }


def build_legacy_payment_patch_payload(patch_payload: dict) -> dict:
    legacy_payload = {}
    if 'status' in patch_payload:
        legacy_payload['status'] = patch_payload.get('status')
    if 'zpay_trade_no' in patch_payload:
        legacy_payload['trade_no'] = patch_payload.get('zpay_trade_no')
    if 'subscribe_start_at' in patch_payload:
        legacy_payload['subscribe_start'] = patch_payload.get('subscribe_start_at')
    if 'subscribe_expire_at' in patch_payload:
        legacy_payload['subscribe_expire'] = patch_payload.get('subscribe_expire_at')
    return legacy_payload



def fetch_latest_active_subscription(user_id: str, product_id: str) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    normalized_product_id = str(product_id or '').strip()
    if not normalized_user_id or not normalized_product_id:
        return None
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError('Supabase 服务配置缺失')
    response = requests.get(
        build_supabase_request_url(f'/rest/v1/{SUPABASE_PAYMENTS_TABLE}'),
        headers=_build_supabase_service_headers(),
        params={
            'select': 'subscribe_expire',
            'user_id': f'eq.{normalized_user_id}',
            'product_id': f'eq.{normalized_product_id}',
            'type': 'eq.subscription',
            'status': 'eq.paid',
            'order': 'subscribe_expire.desc',
            'limit': '1',
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return _extract_single_supabase_row(payload)


def parse_iso_datetime(value: str | None) -> datetime | None:
    raw_value = str(value or '').strip()
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value.replace('Z', '+00:00'))
    except ValueError:
        return None


def compute_subscription_period(user_id: str, product_id: str) -> tuple[datetime, datetime, int]:
    subscription_days = get_subscription_days(product_id)
    now = datetime.now(timezone.utc)
    latest_row = fetch_latest_active_subscription(user_id, product_id)
    latest_expire = parse_iso_datetime(get_payment_subscribe_expire(latest_row))
    subscribe_start = latest_expire if latest_expire and latest_expire > now else now
    subscribe_expire = subscribe_start + timedelta(days=subscription_days)
    return subscribe_start, subscribe_expire, subscription_days


def build_zpay_sign(params: dict) -> str:
    if not ZPAY_KEY:
        raise RuntimeError('ZPAY_KEY 未配置')
    sign_segments: list[str] = []
    for key in sorted(params.keys()):
        if key in {'sign', 'sign_type'}:
            continue
        value = params.get(key)
        if value is None:
            continue
        value_str = str(value).strip()
        if not value_str:
            continue
        sign_segments.append(f'{key}={value_str}')
    sign_source = '&'.join(sign_segments) + ZPAY_KEY
    return hashlib.md5(sign_source.encode('utf-8')).hexdigest()


def build_zpay_payment_url(*, out_trade_no: str, product_id: str, amount: Decimal, pay_type: str, user_id: str) -> str:
    if not ZPAY_PID:
        raise RuntimeError('ZPAY_PID 未配置')
    if not ZPAY_NOTIFY_URL:
        raise RuntimeError('ZPAY_NOTIFY_URL 未配置')
    if not ZPAY_RETURN_URL:
        raise RuntimeError('ZPAY_RETURN_URL 未配置')
    payment_params = {
        'pid': ZPAY_PID,
        'type': ZPAY_DEFAULT_CHANNEL or 'alipay',
        'out_trade_no': out_trade_no,
        'notify_url': ZPAY_NOTIFY_URL,
        'return_url': ZPAY_RETURN_URL,
        'name': f'{product_id}支付订单',
        'money': f'{amount:.2f}',
        'param': json.dumps({
            'user_id': user_id,
            'product_id': product_id,
            'pay_type': pay_type,
            'out_trade_no': out_trade_no,
        }, ensure_ascii=False, separators=(',', ':')),
        'sign_type': 'MD5',
    }
    payment_params['sign'] = build_zpay_sign(payment_params)
    return f"{ZPAY_GATEWAY}?{urlencode(payment_params)}"


def create_payment_order_record(order_payload: dict) -> dict:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError('Supabase 服务配置缺失')
    db_payload = build_legacy_payment_order_payload(order_payload)
    response = requests.post(
        build_supabase_request_url(f'/rest/v1/{SUPABASE_PAYMENTS_TABLE}'),
        headers={
            **_build_supabase_service_headers(),
            'Prefer': 'return=representation',
        },
        json=db_payload,
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    row = _extract_single_supabase_row(payload)
    if not row:
        raise RuntimeError('订单写入失败')
    return row


def fetch_payment_order_by_out_trade_no(out_trade_no: str) -> dict | None:
    normalized_order_no = str(out_trade_no or '').strip()
    if not normalized_order_no:
        return None
    response = requests.get(
        build_supabase_request_url(f'/rest/v1/{SUPABASE_PAYMENTS_TABLE}'),
        headers=_build_supabase_service_headers(),
        params={
            'select': '*',
            'out_trade_no': f'eq.{normalized_order_no}',
            'limit': '1',
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return _extract_single_supabase_row(payload)


def fetch_user_profile_by_user_id(user_id: str) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id:
        return None
    response = requests.get(
        build_supabase_request_url(f'/rest/v1/{SUPABASE_USER_PROFILES_TABLE}'),
        headers=_build_supabase_service_headers(),
        params={
            'select': '*',
            'user_id': f'eq.{normalized_user_id}',
            'limit': '1',
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return _extract_single_supabase_row(payload, allow_empty=True)


def update_payment_order(out_trade_no: str, patch_payload: dict) -> dict:
    normalized_order_no = str(out_trade_no or '').strip()
    if not normalized_order_no:
        raise ValueError('缺少 out_trade_no')
    db_payload = build_legacy_payment_patch_payload(patch_payload)
    response = requests.patch(
        build_supabase_request_url(f'/rest/v1/{SUPABASE_PAYMENTS_TABLE}'),
        headers={
            **_build_supabase_service_headers(),
            'Prefer': 'return=minimal',
        },
        params={
            'out_trade_no': f'eq.{normalized_order_no}',
        },
        json=db_payload,
        timeout=20,
    )
    if response.status_code >= 400:
        app.logger.warning('Failed to patch payment order %s: status=%s body=%s', normalized_order_no, response.status_code, response.text)
        response.raise_for_status()
    row = fetch_payment_order_by_out_trade_no(normalized_order_no)
    if not row:
        raise RuntimeError('更新支付订单失败')
    return row


def upsert_user_subscription_profile(user_id: str, subscribe_expire: str | None) -> dict:
    normalized_user_id = str(user_id or '').strip()
    normalized_expire = str(subscribe_expire or '').strip()
    if not normalized_user_id:
        raise ValueError('缺少 user_id')
    existing_row = fetch_user_profile_by_user_id(normalized_user_id)
    if existing_row:
        response = requests.patch(
            build_supabase_request_url(f'/rest/v1/{SUPABASE_USER_PROFILES_TABLE}'),
            headers={
                **_build_supabase_service_headers(),
                'Prefer': 'return=minimal',
            },
            params={'user_id': f'eq.{normalized_user_id}'},
            json={
                'subscribe_expire': normalized_expire or None,
            },
            timeout=20,
        )
        if response.status_code >= 400:
            app.logger.warning('Failed to patch user subscription profile for %s: %s', normalized_user_id, response.text)
            response.raise_for_status()
        refreshed_row = fetch_user_profile_by_user_id(normalized_user_id)
        return refreshed_row or {}
    response = requests.post(
        build_supabase_request_url(f'/rest/v1/{SUPABASE_USER_PROFILES_TABLE}'),
        headers={
            **_build_supabase_service_headers(),
            'Prefer': 'return=representation',
        },
        json={
            'user_id': normalized_user_id,
            'subscribe_expire': normalized_expire or None,
        },
        timeout=20,
    )
    if response.status_code >= 400:
        app.logger.warning('Failed to create user subscription profile for %s: %s', normalized_user_id, response.text)
        response.raise_for_status()
    payload = response.json()
    row = _extract_single_supabase_row(payload, allow_empty=True)
    return row or {}


def verify_zpay_callback_signature(params: dict) -> bool:
    provided_sign = str((params or {}).get('sign') or '').strip().lower()
    if not provided_sign:
        return False
    return provided_sign == build_zpay_sign(params)


def normalize_callback_payload() -> dict:
    payload = request.values.to_dict(flat=True) if request.values else {}
    normalized_payload = {str(key): value for key, value in payload.items()}
    if 'trade_status' not in normalized_payload:
        status_value = normalized_payload.get('status') or normalized_payload.get('trade_state') or normalized_payload.get('state')
        if status_value is not None:
            normalized_payload['trade_status'] = status_value
    if 'money' not in normalized_payload:
        money_value = normalized_payload.get('total_amount') or normalized_payload.get('amount') or normalized_payload.get('realmoney')
        if money_value is not None:
            normalized_payload['money'] = money_value
    if 'out_trade_no' not in normalized_payload:
        order_no = normalized_payload.get('out_order_no') or normalized_payload.get('merchant_order_no')
        if order_no is not None:
            normalized_payload['out_trade_no'] = order_no
    if 'trade_no' not in normalized_payload:
        trade_no = normalized_payload.get('oid') or normalized_payload.get('pay_no') or normalized_payload.get('transaction_id')
        if trade_no is not None:
            normalized_payload['trade_no'] = trade_no
    return normalized_payload


def is_order_success(order_row: dict | None) -> bool:
    return str((order_row or {}).get('status') or '').strip().lower() == 'paid'


def validate_callback_amount(order_row: dict, callback_money: str) -> None:
    order_amount = parse_money_amount((order_row or {}).get('amount'))
    paid_amount = parse_money_amount(callback_money)
    if order_amount != paid_amount:
        raise ValueError('订单金额不匹配')


def process_success_payment(order_row: dict, callback_trade_no: str) -> dict:
    out_trade_no = get_payment_order_no(order_row)
    if not out_trade_no:
        raise ValueError('订单号缺失')
    patch_payload = {
        'status': 'paid',
        'zpay_trade_no': str(callback_trade_no or '').strip() or None,
        'paid_at': datetime.now(timezone.utc).isoformat(),
        'payment_method': str(((order_row or {}).get('callback_payload') or {}).get('type') or '').strip() or str((order_row or {}).get('payment_method') or '').strip() or None,
        'callback_payload': normalize_callback_payload(),
    }
    updated_row = update_payment_order(out_trade_no, patch_payload)

    try:
        grant_payment_points_once(updated_row)
    except requests.RequestException:
        app.logger.exception('Failed to grant payment points after payment success: out_trade_no=%s', out_trade_no)

    if get_payment_pay_type(updated_row).lower() == 'subscription':
        user_id = str((updated_row or {}).get('user_id') or '').strip()
        subscribe_expire = get_payment_subscribe_expire(updated_row)
        if user_id and subscribe_expire:
            try:
                upsert_user_subscription_profile(user_id, subscribe_expire)
            except requests.RequestException:
                app.logger.exception('Failed to sync subscription profile after payment success: out_trade_no=%s user_id=%s', out_trade_no, user_id)
    return updated_row


def serialize_payment_order(order_row: dict, *, pay_type: str, subscription_days: int | None = None) -> dict:
    return {
        'id': order_row.get('id'),
        'out_trade_no': get_payment_order_no(order_row),
        'user_id': order_row.get('user_id'),
        'product_id': get_payment_package_id(order_row),
        'amount': str(order_row.get('amount') or ''),
        'status': str(order_row.get('status') or ''),
        'type': pay_type,
        'db_type': get_payment_pay_type(order_row),
        'trade_no': get_payment_trade_no(order_row),
        'subscribe_start': get_payment_subscribe_start(order_row),
        'subscribe_expire': get_payment_subscribe_expire(order_row),
        'created_at': order_row.get('created_at'),
        'updated_at': order_row.get('updated_at'),
        'subscription_days': subscription_days,
    }


def get_env_csv(name: str) -> set[str]:
    raw_value = os.getenv(name, '').strip()
    return {
        value.strip().lower()
        for value in raw_value.split(',')
        if value.strip()
    }


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


def _is_settings_user_allowed(session_data: dict | None = None) -> bool:
    allowed_emails = get_settings_allowed_emails()
    allowed_phones = {_normalize_phone_identifier(phone) for phone in get_settings_allowed_phones()}
    user_email = _get_supabase_user_email(session_data)
    user_phone = _get_supabase_user_phone(session_data)
    return bool(
        (user_email and user_email in allowed_emails)
        or (user_phone and user_phone in allowed_phones)
    )


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


def _get_supabase_user_email(session_data: dict | None = None) -> str:
    session_payload = session_data or g.get('supabase_session') or {}
    user = session_payload.get('user') or {}
    return str(user.get('email') or '').strip().lower()


def _get_supabase_user_phone(session_data: dict | None = None) -> str:
    session_payload = session_data or g.get('supabase_session') or {}
    user = session_payload.get('user') or {}
    metadata = user.get('user_metadata') or {}
    return _normalize_phone_identifier(user.get('phone') or metadata.get('phone') or metadata.get('phone_number'))


def _is_truthy_flag(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _fetch_supabase_user_admin_flag(user_id: str) -> bool:
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id or not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False

    try:
        response = requests.get(
            build_supabase_request_url(f'/rest/v1/{SUPABASE_USER_PROFILES_TABLE}'),
            headers=_build_supabase_service_headers(),
            params={
                'select': 'is_admin,user_id',
                'user_id': f'eq.{normalized_user_id}',
                'limit': '1',
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        app.logger.warning('Failed to fetch admin flag for %s: %s', normalized_user_id, exc)
        return False

    if not isinstance(payload, list) or not payload:
        return False

    row = payload[0]
    if not isinstance(row, dict):
        return False

    return _is_truthy_flag(row.get('is_admin'))


def _is_supabase_admin_user(session_data: dict | None = None) -> bool:
    session_payload = session_data or g.get('supabase_session') or {}
    user = session_payload.get('user') or {}
    if not isinstance(user, dict):
        return False

    if _is_truthy_flag(user.get('is_admin')):
        return True

    if str(user.get('role') or '').strip().lower() == 'admin':
        return True

    for metadata_key in ('app_metadata', 'user_metadata'):
        metadata = user.get(metadata_key) or {}
        if not isinstance(metadata, dict):
            continue
        if _is_truthy_flag(metadata.get('is_admin')) or _is_truthy_flag(metadata.get('admin')):
            return True
        if str(metadata.get('role') or '').strip().lower() == 'admin':
            return True

    user_id = str(user.get('id') or '').strip()
    if user_id and _fetch_supabase_user_admin_flag(user_id):
        return True

    return False


def build_admin_session_signature(identifier: str, expires_at: int) -> str:
    message = f'{identifier}:{expires_at}'.encode('utf-8')
    return hmac.new(get_admin_session_secret().encode('utf-8'), message, hashlib.sha256).hexdigest()


def create_admin_session_payload(identifier: str) -> dict:
    expires_at = int(time.time()) + 60 * 60 * 24
    normalized_identifier = _normalize_phone_identifier(identifier).lower()
    return {
        'identifier': normalized_identifier,
        'expires_at': expires_at,
        'signature': build_admin_session_signature(normalized_identifier, expires_at),
    }


def get_admin_session() -> dict | None:
    raw_cookie = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not raw_cookie:
        return None
    try:
        decoded_cookie = base64.urlsafe_b64decode(f'{raw_cookie}=='.encode('utf-8')).decode('utf-8')
        payload = json.loads(decoded_cookie)
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error):
        return None
    if not isinstance(payload, dict):
        return None
    identifier = _normalize_phone_identifier(payload.get('identifier')).lower()
    expires_at = int(payload.get('expires_at') or 0)
    signature = str(payload.get('signature') or '')
    if not identifier or expires_at < int(time.time()):
        return None
    expected_signature = build_admin_session_signature(identifier, expires_at)
    if not hmac.compare_digest(signature, expected_signature):
        return None
    allowed_phones = {_normalize_phone_identifier(phone).lower() for phone in get_settings_allowed_phones()}
    allowed_emails = {email.lower() for email in get_settings_allowed_emails()}
    if identifier not in allowed_phones and identifier not in allowed_emails:
        return None
    return {'identifier': identifier, 'expires_at': expires_at}


def set_admin_session_cookie(response, identifier: str):
    payload = create_admin_session_payload(identifier)
    encoded_cookie = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode('utf-8')).decode('utf-8').rstrip('=')
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        encoded_cookie,
        max_age=60 * 60 * 24,
        httponly=True,
        samesite='Lax',
        path='/',
    )


def clear_admin_session_cookie(response):
    response.delete_cookie(ADMIN_SESSION_COOKIE, path='/')


def verify_admin_credentials(identifier: str, password: str) -> bool:
    normalized_identifier = _normalize_phone_identifier(identifier).lower()
    allowed_phones = {_normalize_phone_identifier(phone).lower() for phone in get_settings_allowed_phones()}
    allowed_emails = {email.lower() for email in get_settings_allowed_emails()}
    admin_password = get_admin_password()
    if not normalized_identifier or not admin_password:
        return False
    if normalized_identifier not in allowed_phones and normalized_identifier not in allowed_emails:
        return False
    return hmac.compare_digest(str(password or ''), admin_password)



def normalize_app_mode(value: str | None) -> str:
    normalized_mode = str(value or '').strip().lower()
    return normalized_mode if normalized_mode in {'mode1', 'mode2', 'mode3'} else 'mode1'


def get_app_mode() -> str:
    return normalize_app_mode(get_supabase_setting('APP_MODE', 'mode1'))


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


DEFAULT_POINTS_RULES = {
    'suite': {
        'key': 'suite',
        'label': '套图',
        'unit_cost': 1,
        'minimum_cost': 1,
        'metric': 'output_count',
    },
    'mode2': {
        'key': 'mode2',
        'label': 'AI 生图',
        'unit_cost': 1,
        'minimum_cost': 1,
        'metric': 'output_count',
    },
    'aplus': {
        'key': 'aplus',
        'label': 'A+ 模块',
        'unit_cost': 1,
        'minimum_cost': 1,
        'metric': 'selected_modules_count',
    },
    'fashion': {
        'key': 'fashion',
        'label': '服饰场景',
        'unit_cost': 1,
        'minimum_cost': 1,
        'metric': 'selected_scene_count',
    },
}


ALLOWED_POINTS_RULE_METRICS = {
    'output_count',
    'selected_modules_count',
    'selected_scene_count',
}


POINTS_RULE_SETTING_KEYS = {
    'suite': 'POINTS_RULE_SUITE',
    'mode2': 'POINTS_RULE_MODE2',
    'aplus': 'POINTS_RULE_APLUS',
    'fashion': 'POINTS_RULE_FASHION',
}


def normalize_points_rule(mode: str, rule_payload) -> dict:
    default_rule = dict(DEFAULT_POINTS_RULES.get(mode, DEFAULT_POINTS_RULES['suite']))
    if not isinstance(rule_payload, dict):
        return default_rule

    normalized_rule = dict(default_rule)
    normalized_rule['key'] = str(rule_payload.get('key') or default_rule['key']).strip() or default_rule['key']
    normalized_rule['label'] = str(rule_payload.get('label') or default_rule['label']).strip() or default_rule['label']

    try:
        normalized_rule['unit_cost'] = max(int(rule_payload.get('unit_cost', default_rule['unit_cost'])), 0)
    except (TypeError, ValueError):
        normalized_rule['unit_cost'] = default_rule['unit_cost']

    try:
        normalized_rule['minimum_cost'] = max(int(rule_payload.get('minimum_cost', default_rule['minimum_cost'])), 0)
    except (TypeError, ValueError):
        normalized_rule['minimum_cost'] = default_rule['minimum_cost']

    metric = str(rule_payload.get('metric') or default_rule['metric']).strip()
    normalized_rule['metric'] = metric if metric in ALLOWED_POINTS_RULE_METRICS else default_rule['metric']
    return normalized_rule


def get_points_rules() -> dict[str, dict]:
    rules: dict[str, dict] = {}
    for mode, setting_key in POINTS_RULE_SETTING_KEYS.items():
        rules[mode] = normalize_points_rule(mode, get_supabase_setting_json(setting_key, DEFAULT_POINTS_RULES[mode]))
    return rules


def get_points_rule(mode: str) -> dict:
    normalized_mode = str(mode or '').strip().lower()
    rules = get_points_rules()
    return rules.get(normalized_mode, rules['suite'])


def calculate_points_cost(mode: str, *, output_count: int = 0, selected_modules_count: int = 0, selected_scene_count: int = 0) -> tuple[int, dict]:
    rule = get_points_rule(mode)
    metrics = {
        'output_count': max(int(output_count or 0), 0),
        'selected_modules_count': max(int(selected_modules_count or 0), 0),
        'selected_scene_count': max(int(selected_scene_count or 0), 0),
    }
    base_count = max(metrics.get(rule['metric'], 0), 1)
    unit_cost = max(int(rule.get('unit_cost') or 0), 0)
    minimum_cost = max(int(rule.get('minimum_cost') or 0), 0)
    total_cost = max(base_count * unit_cost, minimum_cost)
    return total_cost, {
        **rule,
        'base_count': base_count,
        'cost': total_cost,
        'metrics': metrics,
    }


def build_points_consume_payload(mode: str, *, output_count: int = 0, selected_modules_count: int = 0, selected_scene_count: int = 0, transaction_type: str = 'consume', reason: str = '', metadata: dict | None = None) -> dict:
    total_cost, rule_payload = calculate_points_cost(
        mode,
        output_count=output_count,
        selected_modules_count=selected_modules_count,
        selected_scene_count=selected_scene_count,
    )
    return {
        'amount': total_cost,
        'mode': str(mode or '').strip().lower() or 'suite',
        'type': str(transaction_type or 'consume').strip() or 'consume',
        'reason': str(reason or '').strip(),
        'metadata': metadata if isinstance(metadata, dict) else {},
        'rule': rule_payload,
    }


UPLOAD_MAX_BYTES = max(get_supabase_setting_int('UPLOAD_MAX_BYTES', 15 * 1024 * 1024), 1)
UPLOAD_MAX_FILE_BYTES = max(get_supabase_setting_int('UPLOAD_MAX_FILE_BYTES', 8 * 1024 * 1024), 1)
GENERATED_SUITE_RETENTION_DAYS = max(get_supabase_setting_int('GENERATED_SUITE_RETENTION_DAYS', 7), 0)
GENERATED_SUITE_RETENTION_COUNT = max(get_supabase_setting_int('GENERATED_SUITE_RETENTION_COUNT', 20), 0)
POINTS_SIGNUP_BONUS = max(get_supabase_setting_int('POINTS_SIGNUP_BONUS', 100), 0)
POINTS_DAILY_FREE = max(get_supabase_setting_int('POINTS_DAILY_FREE', 10), 0)
MODE2_ALLOWED_IMAGE_HOSTS = get_mode2_allowed_image_hosts()
app.config['MAX_CONTENT_LENGTH'] = UPLOAD_MAX_BYTES
SYSTEM_PROMPT = (
    '你是电商商品图识别与商品卖点文案专家。'
    '你必须同时参考用户提供的图片内容与已有文案，输出适合商品详情/作图使用的中文商品文案。'
    '如果图片中某些参数无法确认，可以使用“约”“预估”“图中可见”等保守表达，禁止编造明显精确但无依据的数据。'
)



PRODUCT_JSON_SYSTEM_PROMPT = (
    '你是商品主体不可变特征结构化提取专家。'
    '你必须严格根据商品图片与已有卖点文案，只提取后续生图保持商品主体一致性所需的主体信息。'
    '禁止提取或总结光线、场景、背景、道具、人物/模特、手部、姿势、镜头语言、构图、氛围等非商品主体信息。'
    '你只能输出合法 JSON，不要输出代码块、解释或额外文字。'
)

USER_PROMPT_TEMPLATE = """请结合以下信息，为该商品生成新的中文文案：

用户当前文案：
{selling_text}

要求：
1. 必须优先参考图片中可见内容，多张图片需要综合分析。
2. 同时吸收用户当前文案里的有效信息，但不要机械复述。
3. 只输出以下 5 段，不要添加前言、解释、备注、Markdown 代码块：
商品名称：
核心卖点：
适用人群：
期望场景：
规格参数：
4. 核心卖点尽量清晰、具体、适合电商展示。
5. 如果图片无法确认某项规格，请使用保守表达，不要虚构精确参数。
"""

PRODUCT_JSON_USER_PROMPT_TEMPLATE = """请结合当前商品图片与卖点信息，提取后续生图保持商品主体一致性所需的“不可变商品特征” JSON。

用户当前文案：
{selling_text}

要求：
1. 只返回 JSON，不要代码块，不要解释。
2. 只能提取图片中明确可见，或文案中明确给出的商品主体信息；不确定就写空字符串、空数组，不做臆测。
3. 该 JSON 只服务于锁定“商品主体是什么、哪些特征绝不能变”，不是营销摘要，也不是场景总结。
4. 严禁提取、概括或带入以下非商品主体信息：光线、打光、场景、背景、道具、人物/模特、手部、姿势、镜头语言、构图、氛围、情绪、文案排版、环境描述。
5. 输出结构必须适用于任意商品，不要偏向服装类；如果某些字段不适用，则保留空值或空数组。
6. must_keep 用于列出“后续所有图都必须保留的主体特征”；must_not_change 用于列出“不能漂移、不能弱化、不能替换的稳定主体信息”；forbidden_changes 用于列出“明确禁止出现的改动方向”。这三组规则必须只针对商品主体本身，不得写场景或镜头限制。
7. selling_points 仅用于提炼可在后续画面中表达的商品卖点，可引用用户文案里的重点，但不得覆盖主体一致性规则，也不得写成场景描述。
8. 所有字段都要尽量短句化、去修辞化、去营销化；优先写名词短语或硬规则短句，不要写大段完整描述。
9. structure 只写稳定结构组成，不要把颜色、氛围、场景、卖点解释混进去；优先写“门襟/开合方式、主体开口结构、连接结构、固定结构、主要分区、关键部件关系”。
10. consistency_rules、must_keep、must_not_change、forbidden_changes 必须写成可直接注入生图提示词的硬约束；每条只表达一个约束点，避免复合长句。
11. 若同一信息已在更具体字段中表达，不要在多个字段里重复展开；避免把同一句意思改写后重复出现在多个数组中。
12. 顶层结构必须为：
{{
  "product_name": "",
  "category": "",
  "core_subject": "",
  "subject_composition": {{
    "subject_count": "",
    "subject_units": [""],
    "assembly_form": ""
  }},
  "appearance": {{
    "primary_colors": [""],
    "secondary_colors": [""],
    "materials": [""],
    "textures_patterns": [""],
    "silhouette": "",
    "structure": "",
    "surface_finish": "",
    "craft_details": [""]
  }},
  "key_components": [""],
  "brand_identity": {{
    "brand_name": "",
    "logo_details": "",
    "text_markings": [""],
    "logo_positions": [""]
  }},
  "immutable_traits": [""],
  "consistency_rules": [""],
  "must_keep": [""],
  "must_not_change": [""],
  "forbidden_changes": [""],
  "selling_points": [""]
}}
13. consistency_rules 至少返回 4 条，必须明确哪些主体特征必须保持一致，例如主体品类、颜色体系、轮廓、结构、关键部件、logo/品牌位、稳定细节等。
14. must_keep、must_not_change、forbidden_changes 各至少返回 4 条，尽量短句化、硬规则化，便于直接注入后续生图提示词。
15. immutable_traits、key_components、craft_details、subject_units、textures_patterns、text_markings、logo_positions 最多各返回 6 条。
16. primary_colors、secondary_colors、materials 最多各返回 4 条；只写稳定且可见的主体特征。
17. consistency_rules、must_keep、must_not_change、forbidden_changes 最多各返回 8 条；selling_points 最多返回 6 条。
18. consistency_rules、must_keep、must_not_change、forbidden_changes 每条尽量控制在 6-16 个字，优先使用短规则，不要写解释句。
19. 禁止输出这类长句："主体必须保持为...不得变成..."、"颜色关系必须保持..."。改为更短的规则，例如："棒球领外套品类"、"深蓝衣身+浅蓝袖身"、"禁止改为拉链门襟"、"禁止删除双侧插袋"。
20. must_keep 只写需要保留的主体锚点；must_not_change 只写不能变化的稳定主体信息；forbidden_changes 只写明确禁止的改动方向。三者不要互相改写重复。
21. selling_points 只保留可视化卖点短语，例如“拼色层次清晰”“双侧插袋实用”；不要写完整营销句。
22. product_name、category、core_subject、silhouette、structure、logo_details 也必须尽量短，不要超过 18 个字；避免“经典、时尚、高级、氛围感”等修饰词。"""

STYLE_ANALYSIS_SYSTEM_PROMPT = (
    '你是多平台电商商品视觉策略分析专家，擅长根据商品图、核心卖点与目标平台，'
    '为不同平台的主图/辅图生成可执行的视觉风格方向。'
    '你必须输出适合前端直接渲染的 JSON，不要返回任何额外说明。'
)

STYLE_ANALYSIS_USER_PROMPT_TEMPLATE = """请结合当前商品图片与核心卖点，分析适合 {platform} 电商场景的视觉方向。

目标平台：
{platform}

核心卖点：
{selling_text}

输出要求：
1. 仅返回 JSON，不要代码块、不要前言、不要解释。
2. 返回 4 个明显不同的风格方案，避免只是同义改写。
3. 每个风格都必须包含：
   - title：简短风格标题
   - reasoning：一句适合直接展示在卡片上的简短理由
   - colors：恰好 3 个可直接用于前端的十六进制颜色值，例如 #F5C028
4. 风格必须明确贴合 {platform} 的商品主图/辅图策略，不是泛视觉概念。
5. 本次请尽量给出与常见默认答案不同的组合，方便用户重复点击时获得新方向。
6. 请严格按以下 JSON 结构返回：
{{"styles":[{{"title":"","reasoning":"","colors":["#000000","#FFFFFF","#CCCCCC"]}}]}}
"""

FASHION_OUTPUT_VERIFIER_SYSTEM_PROMPT = (
    '你是服饰穿搭成图质检助手。'
    '你会收到 3 张图片，顺序固定为：第 1 张是待检查的生成结果，第 2 张是必须出镜的模特参考图，第 3 张是必须穿到模特身上的商品图。'
    '你必须严格检查：生成结果里是否真的出现了清晰可见的人体/模特、是否与参考模特保持同一人物身份、是否让该模特穿上了商品图中的同一件服饰、是否出现了任何新增可见文字。'
    '只允许输出合法 JSON，不要输出代码块、解释或额外文字。'
)

FASHION_OUTPUT_VERIFIER_USER_PROMPT_TEMPLATE = """请严格检查这 3 张图片（顺序固定：1=生成结果，2=模特参考，3=商品图），并返回 JSON：
{{
  "model_present": true,
  "same_model_identity": true,
  "wearing_product": true,
  "extra_text_present": false,
  "passed": true,
  "score": 0,
  "failed_checks": [""],
  "reason": ""
}}

判定要求：
1. model_present：只有当第 1 张图里明显出现真实模特/人体主体时才为 true；如果只是衣服平铺、挂拍、白底单品、无头模特、裁切到看不出人物身份，都必须为 false。
2. same_model_identity：只有当第 1 张图中的出镜人物，与第 2 张参考图是同一模特身份时才为 true；若换人、性别不符、脸型发型明显不一致、只剩身体看不出是否同一人，都为 false。
3. wearing_product：只有当第 1 张图中的模特，穿着第 3 张商品图里的同一件服饰主体，且款式、颜色、结构、图案、logo/字样位置总体一致时才为 true；若只是相似衣服、只保留部分特征、没真正穿到人身上，都为 false。
4. extra_text_present：只要第 1 张图出现任何新增可见文字、数字、水印、海报字、标签字、背景招牌字、字幕或角标，就为 true。商品原本自带且与商品图一致的 logo / 印花文字不算新增文字。
5. passed：只有当 model_present=true、same_model_identity=true、wearing_product=true、extra_text_present=false 时才为 true。
6. score：0-100，越高表示越符合要求。
7. failed_checks：从 ["model_present", "same_model_identity", "wearing_product", "extra_text_present"] 中返回未通过项；若都通过则返回空数组。
8. reason：用一句中文简洁说明判定依据，20-80 字。

务必保守判定；不确定时按失败处理。"""

FASHION_OUTPUT_MAX_VERIFY_ATTEMPTS = 1

FASHION_SCENE_PLAN_SYSTEM_PROMPT = (
    '你是服饰穿搭视觉策划专家，擅长围绕服装主体一致性、模特外观、镜头语言与场景氛围，'
    '为前端生成可直接渲染的场景推荐 JSON。你必须只输出合法 JSON，不要附加解释。'
)

FASHION_SCENE_PLAN_USER_PROMPT_TEMPLATE = """请基于当前服装商品图与当前已选模特参考，为服饰穿搭生成推荐场景方案。

输出比例：
{image_size_ratio}

要求：
1. 商品图用于锁定服饰主体、颜色、材质、版型、图案与细节一致性，不得替换商品主体。
2. 当前已选模特参考图只用于锁定人物身份、外观、脸部特征、发型、肤感、体态比例与整体气质，后续最终成图必须继续沿用该模特，不得切换成其他人物。
3. 需要输出 4 组推荐场景，每组 4 个模块方案。
4. 场景描述要适合电商服饰穿搭图，避免过于复杂或喧宾夺主的背景。
5. 每个模块都要清楚区分姿态、构图与镜头感，便于前端做多选场景。
6. scene_prompt 与 poses.scene_prompt 都必须是可直接用于后续生图拼接的中文短句，突出服装一致性与模特一致性优先。
7. 只返回如下 JSON 结构，不要返回 Markdown：
{{
  "summary": "整体推荐说明",
  "scene_prompt": "适用于整组候选的总场景提示",
  "scene_groups": [
    {{
      "id": "scene-group-1",
      "title": "场景组标题",
      "description": "场景组说明",
      "scene_prompt": "该场景组提示词短句",
      "poses": [
        {{
          "id": "module-1",
          "title": "模块标题",
          "description": "模块说明",
          "scene_prompt": "该模块提示词短句"
        }}
      ]
    }}
  ]
}}
"""

SUITE_PLAN_SYSTEM_PROMPT = (
    '你是资深电商商品套图策划专家，擅长根据商品图、卖点、平台与固定图类型结构，'
    '产出可直接进入图生图执行阶段的套图规划 JSON。'
    '你必须只返回 JSON，不允许返回代码块、解释、说明文字。'
)

SUITE_PLAN_USER_PROMPT_TEMPLATE = """请根据参考商品图、平台和卖点，输出本次爆款套图的结构化规划 JSON。

你的任务不是简单罗列图类型，而是基于“用户决策路径”设计一组具有连贯视觉叙事的电商套图。
你必须先完成叙事定位，再按本次输出张数分配模块容量，最后为每张图指定明确的故事节点、决策任务和展示职责。

目标平台：
{platform}

国家参考：
{country}

说明文字种类：
{text_type}

图片尺寸比例参考：
{image_size_ratio}

用户当前核心关键词/卖点：
{selling_text}

商品主体结构化信息：
{product_json}

风格参考：
{style_reference}

本次输出张数：
{output_count}

后端固定图类型顺序（必须保留顺序，不要改数量）：
{type_list}

可用图类型说明：
{type_details}

你必须遵守以下视觉叙事规划逻辑：

一、先做精准叙事定位，再规划图片
1. 先根据商品主体、卖点和场景推断产品类型，并在 summary 的策略描述中体现其叙事重心：
   - 体验型产品：优先场景化情感叙事，再补充价值可视化。
   - 搜索型产品：优先参数/功能价值可视化，再用场景解释真实用途。
   - 高涉入耐用消费品：平衡品牌价值、场景代入、理性证明与风险消除。
2. 再推断目标用户的产品知识水平：
   - 低产品知识用户：降低认知负荷，更多使用完整场景叙事与结果可视化，减少生硬参数堆砌。
   - 高产品知识用户：提高价值可视化与参数解释密度，场景叙事只服务于证明参数对应的真实效果。
3. 再推断用户购物目标：
   - 享乐型目标：强化情绪共鸣、理想生活方式与人物代入感。
   - 功利型目标：缩短故事线，优先传达核心信息、性能证明与信任闭环。
4. 不需要显式输出“产品类型/用户知识/购物目标”字段，但必须把这些判断转化为 summary 与每张图的规划策略。

二、整套图必须遵循固定的 4 模块叙事顺序，不可打乱
1. 模块1：开场叙事模块。目标是在 1 秒内锁定目标用户、建立核心冲突，并让商品作为解决方案出现。
2. 模块2：场景化叙事模块。目标是按“痛点承接→使用动作→效果呈现→价值升华”的顺序推进故事，让用户完成自我代入。
3. 模块3：价值可视化叙事模块。目标是把功能、参数、卖点转化为用户能感知的视觉价值，而不是纯文字参数堆砌。
4. 模块4：信任叙事模块。目标是把评价、保障、配件、包装、售后或资质转化为视觉化的信任闭环，降低决策风险。
5. 不同图类型的职责可以映射到不同模块，但所有图片整体上必须遵守“开场→代入→证明→信任”的叙事推进顺序。

三、必须根据 output_count 自动分配叙事容量，而不是所有张数都套同一模板
1. output_count=1：只保留“开场叙事 + 核心价值暗示”的压缩版，一张图承担冲突建立与解决方案表达。
2. output_count=2：形成“开场叙事 → 价值可视化”的最短决策链。
3. output_count=3：形成“开场叙事 → 场景代入 → 价值证明”的最小完整叙事链。
4. output_count=4：四个模块各至少出现一次，形成完整闭环。
5. output_count=5：优先让模块2扩展为两张连续节点图，再补模块3与模块4。
6. output_count>=6：允许模块2发展为 3-4 个连续故事节点；剩余张数优先分配给模块3，其次模块4。
7. 体验型产品优先给模块2更多张数；搜索型产品优先给模块3更多张数；高涉入产品优先提升模块3和模块4的存在感。
8. 不允许因为张数增加就做无意义重复图；新增张数必须对应新的故事节点、决策任务或信任任务。

四、每张图都必须是“一个独立决策节点”，而不是简单换背景
1. 每张图只讲 1 个故事节点或 1 个决策问题，禁止一张图里同时堆多个痛点、多个卖点、多个参数主题。
2. 每张图必须明确回答一个问题，例如：
   - 这是什么，为什么与我有关？
   - 它如何解决我的具体问题？
   - 我会在什么场景使用它？
   - 效果/性能如何被看见？
   - 为什么值得信任、买后是否省心？
3. 你的规划重点不只是让图“看起来不同”，而是让图的认知角色不同、故事节点不同、转化任务不同。

五、开场叙事模块的强制规则
1. 首张图优先以目标用户/人物为视觉主体，产品作为解决问题的工具自然出现；除非品类确实不适合人物出现，否则不要做成纯产品孤立展示。
2. 开场图只允许“1 个核心痛点 + 1 个核心解决方案”，禁止多痛点堆砌。
3. 首张图必须确定整套图的人物设定、空间类型、时段、光线基调、色彩气质与风格方向，后续图必须延续这一叙事世界。
4. 首张图文案必须极简；如果说明文字种类为“无文字”，则必须明确画面中完全不出现任何文案。

六、场景化叙事模块的强制规则
1. 场景模块必须是有顺序的连续故事，而不是随机拼接场景。
2. 如果场景模块有多张图，优先按以下顺序扩展：痛点承接 → 使用动作 → 效果呈现 → 价值升华。
3. 场景模块中的人物、空间、服装、光线、时间与情绪要保持连续，像同一个故事的不同分镜。
4. 每张场景图只推进一个节点，不能把“使用动作”和“多个结果证明”混在一张图里。

七、价值可视化模块的强制规则
1. 禁止纯参数文本堆砌；所有核心指标都应尽量转成用户可感知的视觉结果。
2. 体验型产品优先做效果可视化，如使用前后、触感联想、氛围变化、便利性变化。
3. 搜索型产品优先做参数/功能对比可视化，如容量、续航、尺寸适配、效率、兼容关系。
4. 高产品知识用户可提升参数表达密度，但依然要以视觉化结构呈现，不做大段硬文案说明。

八、信任叙事模块的强制规则
1. 禁止单纯堆售后文案、资质长文本或空洞口碑语。
2. 信任内容必须视觉化、故事化，例如真实使用反馈感、包装清单、交付完整性、售后无忧场景、品牌可信线索。
3. 信任模块必须与前文风格统一，不能突然切换成完全不同的设计系统。
4. 若本次张数有限，信任模块可以压缩为 1 张；若张数更充足，可在配件、包装、保障、口碑之间做区分，但仍需保持简洁。

九、整套图的连续性与差异化规则必须同时成立
1. 商品主体一致性永远优先：必须优先执行 must_keep、must_not_change、forbidden_changes 与 consistency_rules；主体品类、主色/辅色、轮廓、结构、关键部件、logo/品牌位、稳定细节必须保持一致。
2. 允许变化的仅限背景、空间、道具、光线、构图、文案层级、人物动作和非主体装饰；不得把商品改成另一种结构、材质表现、颜色体系或品牌识别。
3. 人物、场景、风格的连续性必须存在：如果首图已经定义人物与生活场景，后续图不得无故切换成另一类人群、另一种空间系统或另一种审美气质。
4. 差异化也必须明显存在：每张图在镜头距离、主体朝向、人物动作、商品相对位置、版式骨架、信息密度上都必须承担不同职责。

十、必须严格规避以下负面设计
1. 禁止碎片化、无连贯的视觉内容堆砌。
2. 禁止整套图都变成产品绝对主体的纯展示页，缺少用户、场景或问题语境。
3. 禁止图文脱节：图像讲的故事与文案表达必须是同一个节点。
4. 禁止过长且无重点的故事链；新增张数必须服务新的叙事节点，而不是重复表演。
5. 禁止产品类型、人群知识水平、购物目标与叙事方式错配。

十一、文字版式规划必须具备电商详情页专属适配能力
1. 你是全品类电商详情页专属版式规划师，必须为每张图匹配符合 {platform} 平台表达习惯、贴合当前模块功能、适配商品调性的专属文字版式。
2. 文字版式不得模板化，不得把整套图都做成“底部居中粗白字+黑描边”的单一排版；整体风格可以统一，但每一页的标题位置、信息骨架、标签组织、留白关系都必须根据模块职责变化。
3. 配色必须与商品主色调和画面整体色调呼应，优先使用低饱和、克制、干净的配色；禁止刺眼高饱和文字、杂乱彩色字或明显不符合商品调性的撞色文案。
4. 字体气质必须与产品风格和模块语义匹配：简约/科技风优先无衬线，温柔/软萌风优先圆润软黑体或柔和手写感，高端/质感风优先纤细衬线或精致细体；禁止生硬粗黑体、廉价海报字或老旧土味字体。
5. 每张图都必须明确主标题、副标题、辅助说明的层级关系，字号至少拉开两个层级以上，形成清晰视觉焦点；禁止所有文字同等大小、同等粗细、同等权重。
6. 文字必须避开商品主体、模特面部、核心卖点细节和关键操作区域，优先使用画面空白区、结构边缘区、场景留白区承载排版；禁止大面积遮挡商品、人物或关键功能部位。
7. 不同模块必须使用具有电商语义辨识度的版式语言：首屏主视觉偏强记忆点与极简标题，场景图偏陪伴式信息，价值图偏结构化说明，信任图偏规整清爽的信息板；既保持统一审美，又不能版式重复。
8. 所有 prompt 里的文字表达都必须显式提醒模型：避免文字乱码、变形、模糊、重影、笔画断裂、字距失衡和水印感文字；确保文字清晰可辨、排版干净清爽。
9. 如果说明文字种类为“无文字”，则上述版式规则只作为“禁文”约束，必须明确整张图不出现任何标题、副标题、标签、角标、参数字或说明字。
10. 必须严格规避以下负面版式：文字乱码、文字变形、文字模糊、粗黑描边大字、底部居中文字堆砌、花哨文字特效、与产品不匹配的乱色文字、生硬水印感文字、遮挡主体的大面积文字、老旧土味排版、刺眼高饱和配色、字体不统一、无层次文字。

输出要求：
1. 只返回 JSON，不要代码块，不要解释。
2. 顶层结构必须为：
{{
  "summary": "",
  "output_count": {output_count},
  "items": [
    {{
      "sort": 1,
      "type": "",
      "title": "",
      "keywords": ["", "", ""],
      "prompt": "",
      "module": "",
      "story_role": "",
      "decision_task": "",
      "info_density": "",
      "scene_required": true,
      "scene_type": "",
      "camera_shot": "",
      "subject_angle": "",
      "human_presence": "",
      "action_type": "",
      "layout_anchor": "",
      "layout_style": "",
      "font_style": "",
      "color_scheme": "",
      "decor_elements": [""],
      "must_differ_from": [""]
    }}
  ]
}}
3. summary 用一句中文概括本次套图策略，必须体现：产品叙事重心、目标用户倾向、购物目标倾向，以及 output_count 下的模块分配逻辑。
4. items 长度必须严格等于 {output_count}，sort 必须从 1 开始递增。
5. type 必须严格使用后端给定的图类型，不得自创新 type，不得调整顺序，不得增删数量。
6. title 适合直接作为单张卡片标题，简洁明确，能对应当前图的故事节点或决策任务。
7. keywords 必须是 3-6 个短语，围绕当前图的故事节点、卖点主题、场景语义和视觉任务展开。
8. prompt 必须是适合图生图的中文指令，需明确：当前图的叙事模块、故事节点、决策任务、构图重点、场景/背景、人物关系、文案层级、视觉风格，以及商品主体保持一致的硬约束。
9. 如果用户卖点为空，也必须结合图片可见特征完成规划，但禁止虚构无法确认的精确参数。
10. 每张图都要贴合 {platform} 平台的电商展示逻辑，且彼此分工明确、避免重复。
11. 说明文字种类、图片尺寸比例、国家参考都必须体现在 summary 与每张图的 prompt 中；如果某些卖点或场景与地区强相关，必须优先参考国家信息。
12. 如果说明文字种类为“无文字”，prompt 中必须明确不要在图片中生成任何标题、卖点文案或说明文字；否则应按指定文字种类组织画面文案语言。
13. 如果提供了风格参考，必须优先吸收该风格的视觉气质、色彩倾向、版式氛围与信息层级，并把它们自然融入 summary 与每张图的 prompt；但平台规则、国家参考、文字类型、尺寸比例、商品主体与卖点约束始终优先。
14. product_json 只代表不可变商品特征，只能用于锁定商品主体本身；不得把场景、背景、光线、氛围、人物、姿势、镜头语言或文案排版写进该结构的解释中。
15. selling_points 只能作为卖点重点、标题重点或信息层级参考；不得覆盖主体一致性约束，不得推动商品变体化。
16. 首屏主视觉图、核心卖点图、使用场景图之间必须强制分化；如果它们共同承担模块1和模块2，必须明确各自对应“开场叙事 / 使用动作 / 效果证明”等不同节点，禁止只换背景和文案。
17. 对于首屏主视觉图、核心卖点图、使用场景图，prompt 必须直接写出各自禁止复用的对象：禁止同朝向、禁止同姿势、禁止同摆位、禁止同景别、禁止同版式骨架，避免模型仅做重复变体。
18. 每个 item 除自然语言 prompt 外，还必须补充结构化叙事字段：module、story_role、decision_task、info_density，以及结构化差异字段：scene_required、scene_type、camera_shot、subject_angle、human_presence、action_type、layout_anchor、must_differ_from。
19. module 只能填写 opening_narrative、scene_narrative、value_visualization、trust_narrative 之一；story_role 必须明确当前图在故事链中的节点，如核心冲突建立、痛点承接、使用动作、效果呈现、价值升华、理性证明、风险消除等。
20. decision_task 必须明确回答当前图要解决的用户判断问题；info_density 只能填写 low、medium、high，用来控制当前图的信息密度与文案负荷。
21. scene_required 必须为 true 或 false；scene_type 填该图主要场景类型；camera_shot 填景别或镜头策略；subject_angle 填商品主体朝向或观察角度。
22. human_presence 只能填写“none”“hand-only”“model”；action_type 填该图主要动作关系；layout_anchor 填构图重心；must_differ_from 必须列出当前图明确禁止复用的前序图类型，可填 1-3 个。
23. 还必须补充文字版式结构字段：layout_style、font_style、color_scheme、decor_elements。layout_style 必须明确当前图采用的真实电商版式模板语言，例如：单图分层、分栏线框、竖排多列、环绕标注、边角背书、参数信息板、对比双栏、吊牌角标、图标矩阵之一或其合理变体；font_style 必须明确当前图的字体气质并与其他图拉开差异；color_scheme 必须明确当前图的配色方案，如同色系深浅、低对比撞色、微渐变、浅底深字、深底浅字；decor_elements 必须列出 1-4 个辅助元素，如线框、细分隔线、图标、吊牌、角标、编号标签、数据徽章等。
24. 每张图片必须使用不同的排版逻辑、不同的字体样式、不同的配色方案，禁止重复模板化设计；至少要与 must_differ_from 指定前序图在版式结构、字体气质、颜色组织三项中拉开两项以上差异。
25. 必须显式参考真实电商详情页常见版式语言，不要只写“加一些文字”或“排版高级感”；要直接写出信息如何分层、是否分栏、是否线框包裹、是否竖排多列、是否环绕商品标注、是否采用边角背书与吊牌角标。
26. 这些结构化字段必须与 prompt 保持一致，不能互相矛盾；优先用它们明确区分叙事模块、故事节点、决策任务、信息密度、场景类型、景别、主体朝向、人物参与方式、动作关系、版式骨架、字体风格与配色方案。
"""



HEX_COLOR_PATTERN = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
SAFE_NAME_PATTERN = re.compile(r'[^0-9a-zA-Z\u4e00-\u9fff_-]+')

SUITE_TYPE_META = {
    '首屏主视觉图': {
        'tag': 'Hero',
        'detail': '首图担当，突出主体识别度、平台主图逻辑与强视觉记忆点。',
    },
    '核心卖点图': {
        'tag': 'Selling',
        'detail': '聚焦 1-3 个核心卖点，用主副标题和信息分层强化转化。',
    },
    '使用场景图': {
        'tag': 'Scene',
        'detail': '展示真实使用环境，让用户快速理解商品用途和适用情境。',
    },
    '商品细节图': {
        'tag': 'Detail',
        'detail': '放大展示材质、结构、做工、关键部件等细节。',
    },
    '参数图': {
        'tag': 'Specs',
        'detail': '承载尺寸、规格、适配信息、容量等参数型信息。',
    },
    '配件/售后图': {
        'tag': 'Support',
        'detail': '展示包装清单、附赠配件、售后承诺或服务亮点。',
    },
    '场景氛围图': {
        'tag': 'Mood',
        'detail': '强调氛围感、生活方式与审美调性，提升点击欲望。',
    },
    '图标卖点图': {
        'tag': 'Icons',
        'detail': '通过图标、短词和模块化布局快速说明多个卖点。',
    },
    '品牌故事图': {
        'tag': 'Brand',
        'detail': '通过品牌感叙事、理念与调性，补足认知与信任。',
    },
    '多角度图': {
        'tag': 'Angles',
        'detail': '展示产品多角度、多面信息或组合视角，补充完整认知。',
    },
}

SUITE_TYPE_RULES = {
    6: ['首屏主视觉图', '核心卖点图', '使用场景图', '商品细节图', '参数图', '配件/售后图'],
    7: ['首屏主视觉图', '核心卖点图', '使用场景图', '场景氛围图', '商品细节图', '参数图', '配件/售后图'],
    8: ['首屏主视觉图', '使用场景图', '场景氛围图', '核心卖点图', '图标卖点图', '商品细节图', '参数图', '配件/售后图'],
    9: ['首屏主视觉图', '使用场景图', '场景氛围图', '品牌故事图', '核心卖点图', '图标卖点图', '商品细节图', '参数图', '配件/售后图'],
    10: ['首屏主视觉图', '使用场景图', '场景氛围图', '品牌故事图', '核心卖点图', '图标卖点图', '商品细节图', '多角度图', '参数图', '配件/售后图'],
}

APLUS_PLAN_SYSTEM_PROMPT = (
    '你是资深电商 A+ 详情页策划专家，擅长根据商品图、卖点、平台与指定模块结构，'
    '产出可直接进入图生图执行阶段的 A+ 页面模块规划 JSON。'
    '你必须只返回 JSON，不允许返回代码块、解释、说明文字。'
)

APLUS_PLAN_USER_PROMPT_TEMPLATE = """请根据参考商品图、平台和卖点，输出本次 A+详情页模块的结构化规划 JSON。

目标平台：
{platform}

国家参考：
{country}

说明文字种类：
{text_type}

图片尺寸比例参考：
{image_size_ratio}

用户当前核心关键词/卖点：
{selling_text}

商品主体结构化信息：
{product_json}

风格参考：
{style_reference}

本次选中的 A+ 模块顺序（必须保留顺序，不要改数量）：
{module_list}

可用模块说明：
{module_details}

输出要求：
1. 只返回 JSON，不要代码块，不要解释。
2. 顶层结构必须为：
{{
  "summary": "",
  "module_count": {module_count},
  "items": [
    {{
      "sort": 1,
      "type": "",
      "title": "",
      "keywords": ["", "", ""],
      "prompt": ""
    }}
  ]
}}
3. summary 用一句中文概括本次 A+ 页面模块策略，体现模块结构、信息层级、平台语境，以及从首屏到转化说明的内容编排。
4. items 长度必须严格等于 {module_count}，sort 必须从 1 开始递增。
5. type 必须严格使用后端给定的模块名称，不得自创新 type。
6. title 适合直接作为单个模块卡片标题，简洁明确。
7. keywords 必须是 3-6 个短语，便于前端展示。
8. prompt 必须是适合图生图的中文指令，需明确：该模块的版式目标、信息层级、构图重点、文案位置或禁文要求、视觉风格、商品主体保持一致、不要偏离参考商品。
9. 这是 A+ 详情页模块规划，不是普通套图；模块之间必须承担不同的信息职责，并严格匹配本次选中的模块语义，例如：首屏主视觉负责第一屏吸引与核心价值、使用场景图负责真实使用展示、效果对比图负责前后差异表达、详细规格/参数表负责数据化说明、售后保障图负责质保退换与服务承诺。
10. 如果用户卖点为空，也必须结合图片可见特征完成规划，但禁止虚构无法确认的精确参数。
11. 每个模块都要贴合 {platform} 平台的 A+ 内容表达逻辑，且彼此分工明确、避免重复。
12. 说明文字种类、图片尺寸比例、国家参考都必须体现在 summary 与每个模块的 prompt 中；如果某些卖点或场景与地区强相关，必须优先参考国家信息。
13. 如果说明文字种类为“无文字”，prompt 中必须明确不要在图片中生成任何标题、卖点文案或说明文字；否则应按指定文字种类组织模块文案语言。
14. 如果提供了风格参考，必须优先吸收该风格的视觉气质、色彩倾向、版式氛围与信息层级，并把它们自然融入 summary 与每个模块的 prompt；但平台规则、国家参考、文字类型、尺寸比例、商品主体与卖点约束始终优先。
15. 选中的模块可能来自以下 16 类标准模块：首屏主视觉、使用场景图、场景氛围图、品牌故事图、效果对比图、工艺制作图、系列展示图、售后保障图、核心卖点图、多角度图、商品细节图、尺寸/容量/尺码图、详细规格/参数表、配件/赠品图、商品成分图、使用建议图。只有被选中的模块才可出现在 items 中。
16. 对于“首屏主视觉”“核心卖点图”，默认优先做场景化表达，不要只做白底商品、悬浮 cutout 或纯信息板；应尽量把商品放进真实使用环境中，通过人物、动作、空间、氛围来体现第一眼吸引力与核心卖点。如果卖点里包含期望场景，必须优先写入 prompt；如果是服饰、鞋包、配饰类商品，优先让商品穿在/背在/佩戴在人物身上，在咖啡店、通勤、街头、办公室、居家等合理生活场景中展示。
17. 对于“尺寸/容量/尺码图”“详细规格/参数表”“商品成分图”这类强信息模块，如图片或文案无法确认精确数据，必须使用保守表达，如“尺寸示意”“参数信息以实物为准”“图中可见材质/成分线索”，禁止编造具体数值。
18. 对于“配件/赠品图”“售后保障图”“效果对比图”这类容易误导的模块，如缺少依据，不要虚构额外赠品、售后政策或夸张功效，应采用克制、可信的表达。
19. 你必须同时承担全品类电商详情页专属版式规划职责：为每个模块匹配符合 {platform} 平台审美与模块功能的专属文字版式，不得套用统一模板化排版。
20. 文字/标签配色必须与商品主色调和整体画面色调呼应，优先使用低饱和、克制、清爽的配色；禁止刺眼高饱和色、杂乱彩色字或明显不符合产品调性的乱色文案。
21. 字体风格必须与产品调性匹配：简约/科技风优先无衬线，温柔/软萌风优先圆润软黑体或柔和手写感，高端/质感风优先纤细衬线或精致细体；禁止粗暴黑体、老旧土味字体和廉价海报字感。
22. 每个模块都必须区分主标题/副标题/辅助说明层级，字号、粗细、留白与对齐方式要有明显层次，禁止所有文字同权重堆叠。
23. 文字排版必须避开商品主体、模特面部、关键细节和重要结构区，优先放在画面空白区、边缘区、结构留白区；禁止用大面积文字遮挡主体信息。
24. 模块之间既要保持统一品牌感，也必须形成不同的版式语言：首屏主视觉强调记忆点与极简标题，场景图强调陪伴式说明，参数/规格模块强调规整的信息板结构，售后/信任模块强调清晰可信与易读性。
25. 若说明文字种类不为“无文字”，每个模块的 prompt 都必须显式提醒模型规避文字乱码、变形、模糊、粗黑描边大字、底部居中堆字、花哨特效字、水印感文字，并确保文字清晰可辨、版式干净清爽；若为“无文字”，则必须明确禁止出现任何标题、副标题、标签、角标、参数字或说明字。
26. 每个模块必须使用不同的排版逻辑、不同的字体样式、不同的配色方案，禁止重复模板化设计；至少要在信息骨架、字体气质、色彩组织三项中拉开两项以上差异。
27. 必须直接参考真实电商详情页常见版式语言并写入 prompt，例如：单图分层、分栏线框、竖排多列、环绕标注、边角背书、参数信息板、对比双栏、吊牌角标、图标矩阵；不要只写“高级排版”或“丰富文案”。
28. 配色与装饰元素必须增加多样性：可使用同色系深浅、低对比撞色、微渐变、浅底深字、深底浅字，并结合线框、细分隔线、图标、吊牌、角标、编号标签、数据徽章等元素，但必须克制、清爽、服务商品，不得抢夺主体。
"""

APLUS_MODULE_META = {
    'hero_value': {
        'name': '首屏主视觉',
        'tag': 'Hero',
        'detail': '页面开场主视觉，优先采用真实场景化表达，突出商品主体、品牌识别与核心价值主张；服饰、鞋包、配饰类优先让商品穿在/背在/佩戴在人物身上。',
    },
    'usage_scene': {
        'name': '使用场景图',
        'tag': 'Scene',
        'detail': '呈现真实使用场景，让用户快速理解商品用途、对象与使用方式。',
    },
    'mood_scene': {
        'name': '场景氛围图',
        'tag': 'Mood',
        'detail': '展示生活方式与情绪氛围，强化审美调性与场景代入感。',
    },
    'brand_story': {
        'name': '品牌故事图',
        'tag': 'Brand',
        'detail': '传达品牌理念、品牌调性、信任背书与故事化表达。',
    },
    'effect_compare': {
        'name': '效果对比图',
        'tag': 'Compare',
        'detail': '用于展示使用前后、升级前后或不同状态下的变化对比。',
    },
    'craft_process': {
        'name': '工艺制作图',
        'tag': 'Craft',
        'detail': '展示工艺制作过程、制造标准、做工流程与品质细节。',
    },
    'series_showcase': {
        'name': '系列展示图',
        'tag': 'Series',
        'detail': '展示多色、多规格、多 SKU 或系列化组合陈列。',
    },
    'after_sales': {
        'name': '售后保障图',
        'tag': 'Support',
        'detail': '说明质保、退换、客服响应、物流或服务承诺等保障信息。',
    },
    'core_selling': {
        'name': '核心卖点图',
        'tag': 'Selling',
        'detail': '聚焦关键差异点与竞争优势，优先通过真实使用场景、人物状态与环境氛围来演绎卖点，不要退化为纯信息板；服饰、鞋包、配饰类优先展示上身/佩戴效果。',
    },
    'multi_angle': {
        'name': '多角度图',
        'tag': 'Angles',
        'detail': '从多个角度呈现外观、轮廓、结构与整体形态。',
    },
    'detail_zoom': {
        'name': '商品细节图',
        'tag': 'Detail',
        'detail': '放大材质、纹理、接口、缝线、边角等局部细节与工艺。',
    },
    'size_capacity': {
        'name': '尺寸/容量/尺码图',
        'tag': 'Size',
        'detail': '展示尺寸、容量、尺码或适配范围等规格信息。',
    },
    'spec_table': {
        'name': '详细规格/参数表',
        'tag': 'Specs',
        'detail': '用表格或信息板形式承载更完整的商品参数与数据说明。',
    },
    'accessories_gifts': {
        'name': '配件/赠品图',
        'tag': 'Bundle',
        'detail': '明确收货包含的配件、赠品、包装内容与清单信息。',
    },
    'ingredients_materials': {
        'name': '商品成分图',
        'tag': 'Formula',
        'detail': '展示配方、材质、面料、成分构成或核心用料信息。',
    },
    'usage_tips': {
        'name': '使用建议图',
        'tag': 'Tips',
        'detail': '说明使用方法、注意事项、禁忌提醒与更佳使用建议。',
    },
}

IMAGE_SIZE_RATIO_MAP = {
    '1:1': '2048x2048',
    '3:4': '1728x2304',
    '9:16': '1440x2560',
    '16:9': '2560x1440',
}


def normalize_platform_label(platform: str) -> str:
    value = (platform or '').strip()
    if not value:
        return '亚马逊'
    if value == '速卖通速卖通':
        return '速卖通'
    return value


def get_env(name: str) -> str:
    value = os.getenv(name, '').strip()
    if not value:
        raise ValueError(f'缺少环境变量：{name}')
    return value


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


def build_supabase_auth_headers() -> dict:
    return {
        'apikey': SUPABASE_ANON_KEY,
        'Content-Type': 'application/json',
    }


def build_supabase_request_url(path: str) -> str:
    return f'{SUPABASE_URL.rstrip("/")}{path}'


def parse_supabase_session_cookie() -> dict | None:
    raw_cookie = request.cookies.get(SUPABASE_SESSION_COOKIE)
    if not raw_cookie:
        return None
    try:
        decoded_cookie = base64.urlsafe_b64decode(f'{raw_cookie}=='.encode('utf-8')).decode('utf-8')
        session_data = json.loads(decoded_cookie)
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error):
        return None
    if not isinstance(session_data, dict):
        return None
    return session_data



def refresh_supabase_session(session_data: dict) -> dict | None:
    refresh_token = str(session_data.get('refresh_token') or '').strip()
    if not refresh_token:
        return None

    try:
        response = requests.post(
            build_supabase_request_url('/auth/v1/token?grant_type=refresh_token'),
            headers=build_supabase_auth_headers(),
            json={'refresh_token': refresh_token},
            timeout=15,
        )
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    return normalize_supabase_session(payload)


def get_supabase_session() -> dict | None:
    session_data = parse_supabase_session_cookie()
    if not session_data:
        return None
    access_token = str(session_data.get('access_token') or '').strip()
    if not access_token:
        return None

    fallback_user = session_data.get('user') if isinstance(session_data.get('user'), dict) else None

    sync_cookie = str(request.cookies.get(SUPABASE_SESSION_SYNC_COOKIE) or '').strip()
    if sync_cookie == '1':
        try:
            response = requests.get(
                build_supabase_request_url('/auth/v1/user'),
                headers={
                    **build_supabase_auth_headers(),
                    'Authorization': f'Bearer {access_token}',
                },
                timeout=15,
            )
        except requests.RequestException:
            if fallback_user:
                session_data['user'] = fallback_user
            return session_data
        if response.status_code == 200:
            session_data['user'] = response.json()
            return session_data
        if fallback_user:
            session_data['user'] = fallback_user
        return session_data

    try:
        response = requests.get(
            build_supabase_request_url('/auth/v1/user'),
            headers={
                **build_supabase_auth_headers(),
                'Authorization': f'Bearer {access_token}',
            },
            timeout=15,
        )
    except requests.RequestException:
        response = None

    if response is not None and response.status_code == 200:
        payload = response.json()
        session_data['user'] = payload
        return session_data

    refreshed_session = refresh_supabase_session(session_data)
    if not refreshed_session:
        if fallback_user:
            session_data['user'] = fallback_user
            return session_data
        return None

    try:
        refreshed_response = requests.get(
            build_supabase_request_url('/auth/v1/user'),
            headers={
                **build_supabase_auth_headers(),
                'Authorization': f'Bearer {refreshed_session.get("access_token") or ""}',
            },
            timeout=15,
        )
    except requests.RequestException:
        if fallback_user and not refreshed_session.get('user'):
            refreshed_session['user'] = fallback_user
        return refreshed_session

    if refreshed_response.status_code != 200:
        if fallback_user and not refreshed_session.get('user'):
            refreshed_session['user'] = fallback_user
        return refreshed_session

    refreshed_session['user'] = refreshed_response.json()
    return refreshed_session


def set_auth_session_cookie(response, session_data: dict):
    user = session_data.get('user') or {}
    user_metadata = user.get('user_metadata') or {}
    cookie_data = {
        'access_token': session_data.get('access_token'),
        'refresh_token': session_data.get('refresh_token'),
        'user': {
            'id': user.get('id'),
            'phone': user.get('phone'),
            'email': user.get('email'),
            'user_metadata': {
                'phone': user_metadata.get('phone'),
                'phone_number': user_metadata.get('phone_number'),
                'email': user_metadata.get('email'),
            },
        },
    }
    encoded_cookie = base64.urlsafe_b64encode(
        json.dumps(cookie_data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    ).decode('utf-8').rstrip('=')
    response.set_cookie(
        SUPABASE_SESSION_COOKIE,
        encoded_cookie,
        max_age=60 * 60 * 24 * 7,
        httponly=True,
        samesite='Lax',
        path='/',
    )
    response.set_cookie(
        SUPABASE_SESSION_SYNC_COOKIE,
        '1',
        max_age=60,
        httponly=True,
        samesite='Lax',
        path='/',
    )
    return response


def clear_auth_session_cookie(response):
    response.delete_cookie(SUPABASE_SESSION_COOKIE, path='/')
    response.delete_cookie(SUPABASE_SESSION_SYNC_COOKIE, path='/')
    return response


def supabase_logout_session(session_data: dict) -> bool:
    access_token = str((session_data or {}).get('access_token') or '').strip()
    if not access_token or not SUPABASE_URL:
        return False

    try:
        response = requests.post(
            build_supabase_request_url('/auth/v1/logout?scope=local'),
            headers={
                **build_supabase_auth_headers(),
                'Authorization': f'Bearer {access_token}',
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        app.logger.warning('Failed to revoke Supabase session: %s', exc)
        return False

    if response.status_code not in {200, 204}:
        app.logger.warning('Supabase logout returned %s: %s', response.status_code, response.text[:200])
        return False

    return True


def auth_response_from_session(session_data: dict, redirect_path: str | None = None):
    target_path = redirect_path or '/suite'
    response = redirect(target_path)
    set_auth_session_cookie(response, session_data)
    return response


def supabase_auth_password(email: str, password: str, action: str) -> tuple[dict, int]:
    endpoint = '/auth/v1/signup' if action == 'signup' else '/auth/v1/token?grant_type=password'
    payload = {'email': email, 'password': password}
    try:
        response = requests.post(
            build_supabase_request_url(endpoint),
            headers=build_supabase_auth_headers(),
            json=payload,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f'Supabase 请求失败：{exc}') from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError('Supabase 返回了无效响应') from exc

    if response.status_code >= 400:
        message = data.get('msg') or data.get('message') or data.get('error_description') or data.get('error') or '认证失败'
        raise ValueError(message)

    if not isinstance(data, dict):
        raise RuntimeError('Supabase 响应格式错误')

    return data, response.status_code


def normalize_supabase_session(payload: dict) -> dict:
    user = payload.get('user') or {}
    return {
        'access_token': payload.get('access_token'),
        'refresh_token': payload.get('refresh_token'),
        'token_type': payload.get('token_type', 'bearer'),
        'expires_in': payload.get('expires_in'),
        'expires_at': payload.get('expires_at'),
        'user': user,
    }


def require_auth_session() -> dict | None:
    session_data = get_supabase_session()
    g.supabase_session = session_data
    g.supabase_user = (session_data or {}).get('user') if session_data else None
    return session_data


def build_task_name(platform: str, mode: str, count: int) -> str:
    if mode == 'aplus':
        mode_label = 'A+详情页'
        count_label = '模块'
        return f'{platform}{mode_label}-{count}{count_label}-{datetime.now().strftime("%m%d-%H%M%S")}'
    if mode == 'fashion':
        return f'服饰穿搭-{count}张-{datetime.now().strftime("%m%d-%H%M%S")}'
    mode_label = '爆款套图'
    count_label = '张'
    return f'{platform}{mode_label}-{count}{count_label}-{datetime.now().strftime("%m%d-%H%M%S")}'


def build_generated_at() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def guess_extension(mime_type: str, fallback: str = '.png') -> str:
    extension = mimetypes.guess_extension(mime_type or '')
    if extension == '.jpe':
        extension = '.jpg'
    return extension or fallback


def sanitize_filename_part(value: str, fallback: str = 'file') -> str:
    text = str(value or '').strip()
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', '-', text)
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'-{2,}', '-', text).strip('-. _')
    return (text or fallback)[:80]


def sniff_image_mime_type(content: bytes):
    if content.startswith(b'RIFF') and content[8:12] == b'WEBP':
        return 'image/webp'

    for mime_type, signatures in IMAGE_SIGNATURES.items():
        if any(content.startswith(signature) for signature in signatures):
            return mime_type
    return None


def validate_image_file(file_storage, content: bytes):
    filename = file_storage.filename or '未命名文件'
    extension = Path(filename).suffix.lower()
    declared_mime_type = (file_storage.mimetype or '').split(';', 1)[0].strip().lower()
    detected_mime_type = sniff_image_mime_type(content)

    if not content:
        raise ValueError(f'图片 {filename} 内容为空')
    if len(content) > UPLOAD_MAX_FILE_BYTES:
        raise ValueError(f'图片 {filename} 超过单张大小限制（{UPLOAD_MAX_FILE_BYTES // (1024 * 1024)}MB）')
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f'图片 {filename} 格式不受支持，仅支持 JPG、PNG、WEBP、GIF、BMP')
    if declared_mime_type and declared_mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValueError(f'图片 {filename} MIME 类型不受支持：{declared_mime_type}')
    if not detected_mime_type:
        raise ValueError(f'图片 {filename} 不是有效的图片文件')

    return detected_mime_type


def cleanup_generated_suites(active_task_id: str | None = None):
    if not GENERATED_SUITES_DIR.exists():
        return

    task_dirs = [path for path in GENERATED_SUITES_DIR.iterdir() if path.is_dir()]
    if not task_dirs:
        return

    now = datetime.now()
    removable_dirs = []
    for path in task_dirs:
        if active_task_id and path.name == active_task_id:
            continue
        modified_at = datetime.fromtimestamp(path.stat().st_mtime)
        removable_dirs.append((path, modified_at))

    if GENERATED_SUITE_RETENTION_DAYS > 0:
        expire_before = now - timedelta(days=GENERATED_SUITE_RETENTION_DAYS)
        for path, modified_at in removable_dirs:
            if modified_at < expire_before and path.exists():
                shutil.rmtree(path, ignore_errors=True)

    if GENERATED_SUITE_RETENTION_COUNT > 0:
        survivors = []
        for path in GENERATED_SUITES_DIR.iterdir():
            if not path.is_dir():
                continue
            if active_task_id and path.name == active_task_id:
                continue
            survivors.append((path, path.stat().st_mtime))
        survivors.sort(key=lambda item: item[1], reverse=True)
        for path, _ in survivors[GENERATED_SUITE_RETENTION_COUNT:]:
            shutil.rmtree(path, ignore_errors=True)


def resolve_image_size(image_size_ratio: str) -> str:
    ratio = (image_size_ratio or '').strip()
    if ratio in IMAGE_SIZE_RATIO_MAP:
        return IMAGE_SIZE_RATIO_MAP[ratio]
    return get_supabase_setting('ARK_IMAGE_SIZE', '2048x2048')


def file_to_data_url(file_storage) -> str:
    content = file_storage.read()
    if not content:
        raise ValueError(f'图片 {file_storage.filename or "未命名文件"} 内容为空')

    mime_type = file_storage.mimetype or mimetypes.guess_type(file_storage.filename or '')[0] or 'application/octet-stream'
    encoded = base64.b64encode(content).decode('utf-8')
    return f'data:{mime_type};base64,{encoded}'


def create_image_payload(file_storage):
    content = file_storage.read()
    mime_type = validate_image_file(file_storage, content)
    filename = file_storage.filename or 'image'
    encoded = base64.b64encode(content).decode('utf-8')
    return {
        'filename': filename,
        'mime_type': mime_type,
        'bytes': content,
        'base64': encoded,
        'data_url': f'data:{mime_type};base64,{encoded}',
    }




def parse_string_list(value: str, field_label: str):
    raw = (value or '').strip()
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f'{field_label} 参数格式异常') from exc

    if not isinstance(parsed, list):
        raise ValueError(f'{field_label} 参数必须为数组')

    return [str(item).strip() for item in parsed if str(item).strip()]


def get_image_payloads_from_request(field_name: str = 'images', limit: int = MAX_IMAGE_UPLOADS):
    image_files = request.files.getlist(field_name)
    if len(image_files) > limit:
        raise ValueError(f'最多仅支持上传 {limit} 张图片')

    payloads = []
    for image_file in image_files:
        payloads.append(create_image_payload(image_file))
    return payloads


def build_multimodal_content(prompt_text: str, image_files):
    content = [{'type': 'text', 'text': prompt_text}]

    for image_file in image_files:
        if isinstance(image_file, dict):
            image_url = image_file.get('data_url')
        else:
            image_url = file_to_data_url(image_file)
        content.append(
            {
                'type': 'image_url',
                'image_url': {'url': image_url},
            }
        )

    return content


CHAT_COMPLETION_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
CHAT_COMPLETION_FALLBACK_ERROR_TOKENS = (
    'Your request was blocked',
    'AccountOverdueError',
    'overdue balance',
    'usage limit',
    'usage_limit_reached',
    'HTTPSConnectionPool',
    'SSLError',
    'SSLEOFError',
    'EOF occurred in violation of protocol',
    'Max retries exceeded',
)


def create_chat_completion_session():
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.8,
        allowed_methods=frozenset({'POST'}),
        status_forcelist=CHAT_COMPLETION_RETRYABLE_STATUS_CODES,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


def _create_chat_client(api_key: str, base_url: str) -> OpenAI:
    normalized_base_url = str(base_url or '').strip().rstrip('/') + '/'
    return OpenAI(api_key=api_key, base_url=normalized_base_url)


def _run_chat_completion(client: OpenAI, model: str, system_prompt: str, user_content, temperature: float, timeout_seconds: int):
    return client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_content},
        ],
        temperature=temperature,
        timeout=timeout_seconds,
    )


def _run_chat_completion_http(api_key: str, base_url: str, model: str, system_prompt: str, user_content, temperature: float, timeout_seconds: int):
    normalized_base_url = str(base_url or '').strip().rstrip('/') + '/'
    session = create_chat_completion_session()
    try:
        response = session.post(
            f'{normalized_base_url}chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_content},
                ],
                'temperature': temperature,
            },
            timeout=timeout_seconds,
        )
    finally:
        session.close()
    if response.status_code >= 400:
        raise RuntimeError(f'Error code: {response.status_code} - {response.text}')
    return response.json()


def should_enable_chat_fallback_to_ark() -> bool:
    fallback_mode = str(get_supabase_setting('CHAT_FALLBACK_TO_ARK', get_optional_env('CHAT_FALLBACK_TO_ARK', 'auto')) or 'auto').strip().lower()
    if fallback_mode in {'on', 'true', '1', 'yes'}:
        return True
    if fallback_mode in {'off', 'false', '0', 'no'}:
        return False
    return get_app_mode() != 'mode3'


def get_suite_plan_timeout_seconds() -> int:
    return max(get_supabase_setting_int('SUITE_PLAN_TIMEOUT_SECONDS', get_optional_int_env('SUITE_PLAN_TIMEOUT_SECONDS', 180)), 60)


def call_chat_completion(system_prompt: str, user_content, temperature: float = 0.7, timeout_seconds: int = 60):
    primary_api_key = get_supabase_setting('OPENAI_API_KEY', get_env('OPENAI_API_KEY'))
    primary_base_url = get_supabase_setting('OPENAI_BASE_URL', get_env('OPENAI_BASE_URL'))
    primary_model = get_supabase_setting('OPENAI_MODEL', get_env('OPENAI_MODEL'))

    try:
        response = _run_chat_completion_http(
            primary_api_key,
            primary_base_url,
            primary_model,
            system_prompt,
            user_content,
            temperature,
            timeout_seconds,
        )
        model = primary_model
    except Exception as exc:
        error_text = str(exc)
        should_fallback_to_ark = should_enable_chat_fallback_to_ark() and any(token in error_text for token in CHAT_COMPLETION_FALLBACK_ERROR_TOKENS)
        if not should_fallback_to_ark:
            raise

        fallback_api_key = get_supabase_setting('ARK_CHAT_API_KEY', get_optional_env('ARK_CHAT_API_KEY', '')) or get_supabase_setting('ARK_API_KEY', get_optional_env('ARK_API_KEY', ''))
        fallback_base_url = get_supabase_setting('ARK_CHAT_BASE_URL', get_optional_env('ARK_CHAT_BASE_URL', '')) or get_supabase_setting('ARK_BASE_URL', get_optional_env('ARK_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3'))
        fallback_model = get_supabase_setting('ARK_CHAT_MODEL', get_optional_env('ARK_CHAT_MODEL', 'doubao-1-5-lite-32k-250115'))
        if not fallback_api_key:
            raise

        app.logger.warning(
            'Primary chat completion failed with fallbackable error, fallback to Ark chat model=%s base_url=%s original_error=%s',
            fallback_model,
            fallback_base_url,
            error_text,
        )
        try:
            response = _run_chat_completion(
                _create_chat_client(fallback_api_key, fallback_base_url),
                fallback_model,
                system_prompt,
                user_content,
                temperature,
                timeout_seconds,
            )
        except Exception as fallback_exc:
            raise RuntimeError(f'主AI接口失败且备用AI接口也失败。主接口错误：{error_text}；备用接口错误：{fallback_exc}') from fallback_exc
        model = fallback_model

    try:
        raw_response_text = json.dumps(response, ensure_ascii=False, indent=2) if isinstance(response, dict) else response.model_dump_json(indent=2)
    except Exception:
        raw_response_text = str(response)
    app.logger.warning(
        'Chat completion response: model=%s body=%s',
        model,
        raw_response_text,
    )

    if isinstance(response, dict):
        choice = ((response.get('choices') or [None])[0] or {})
        message = choice.get('message') or {}
        text = message.get('content') or ''
    else:
        message = ((getattr(response, 'choices', None) or [None])[0] or {}).message
        text = getattr(message, 'content', '') if message else ''
    if isinstance(text, list):
        text = ''.join(part.text for part in text if getattr(part, 'text', None))
    elif text is None:
        text = ''
    text = str(text).strip() if text else ''

    if not text:
        fallback_fields = ['reasoning_content']
        for field in fallback_fields:
            fallback_text = message.get(field, '') if isinstance(message, dict) else (getattr(message, field, '') if message else '')
            if isinstance(fallback_text, list):
                fallback_text = ''.join(part.text for part in fallback_text if getattr(part, 'text', None))
            elif fallback_text is None:
                fallback_text = ''
            fallback_text = str(fallback_text).strip() if fallback_text else ''
            if fallback_text:
                text = fallback_text
                break

    if not text:
        raise ValueError('模型接口未返回内容（已记录原始响应日志，便于排查）')
    return text


def parse_runtime_error(exc: RuntimeError):
    try:
        payload = json.loads(str(exc))
    except ValueError:
        return {'success': False, 'error': str(exc)}, 502
    return {'success': False, **payload}, 502


def parse_ark_exception(exc: Exception):
    status_code = 502
    details = None

    if isinstance(exc, APIStatusError):
        status_code = exc.status_code or 502
        details = exc.response.text if getattr(exc, 'response', None) else None
    elif isinstance(exc, APIError):
        details = str(exc)
    else:
        details = str(exc)

    app.logger.exception('ARK image generation failed: status=%s details=%s', status_code, details)

    return {
        'success': False,
        'error': '图像生成接口调用失败',
        'details': details,
    }, status_code


def strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```[a-zA-Z0-9_-]*\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
    return cleaned.strip()


def extract_json_candidate(text: str) -> str:
    cleaned = strip_code_fences(str(text or ''))
    if not cleaned:
        return cleaned
    start_indexes = [index for index in [cleaned.find('{'), cleaned.find('[')] if index >= 0]
    if not start_indexes:
        return cleaned
    start = min(start_indexes)
    opener = cleaned[start]
    closer = '}' if opener == '{' else ']'
    end = cleaned.rfind(closer)
    if end <= start:
        return cleaned
    return cleaned[start:end + 1].strip()


def remove_trailing_json_commas(text: str) -> str:
    return re.sub(r',\s*([}\]])', r'\1', text)


def parse_json_candidate(text: str, error_prefix: str):
    candidates = []
    raw_candidate = strip_code_fences(str(text or ''))
    extracted_candidate = extract_json_candidate(raw_candidate)
    for candidate in [raw_candidate, extracted_candidate, remove_trailing_json_commas(extracted_candidate)]:
        normalized = str(candidate or '').strip()
        if normalized and normalized not in candidates:
            candidates.append(normalized)
    last_error = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
    raise ValueError(f'{error_prefix}：{last_error}') from last_error


def build_json_repair_prompt(raw_text: str, error_message: str) -> str:
    return (
        '下面内容本应是 JSON，但格式不合法。请只返回修复后的合法 JSON，不要解释，不要 Markdown 代码块。\n'
        f'解析错误：{error_message}\n'
        '原始内容：\n'
        f'{str(raw_text or "")}'
    )


def call_chat_json_with_repair(
    system_prompt: str,
    user_content,
    parser,
    error_prefix: str,
    temperature: float = 0.3,
    timeout_seconds: int = 60,
    repair_attempts: int = 1,
):
    response_text = call_chat_completion(system_prompt, user_content, temperature=temperature, timeout_seconds=timeout_seconds)
    try:
        return parser(response_text), response_text
    except ValueError as first_exc:
        last_exc = first_exc
        repaired_text = response_text
        for attempt in range(max(int(repair_attempts or 0), 0)):
            try:
                repaired_text = call_chat_completion(
                    '你是严格的 JSON 修复器，只能输出合法 JSON。',
                    build_json_repair_prompt(repaired_text, str(last_exc)),
                    temperature=0,
                    timeout_seconds=min(max(timeout_seconds, 60), 120),
                )
                return parser(repaired_text), repaired_text
            except ValueError as exc:
                last_exc = exc
                app.logger.warning('%s JSON repair attempt %s failed: %s', error_prefix, attempt + 1, exc)
        raise last_exc


def normalize_hex_color(value: str) -> str:
    color = (value or '').strip()
    if not color:
        raise ValueError('颜色值为空')
    if not color.startswith('#'):
        color = f'#{color}'
    if not HEX_COLOR_PATTERN.fullmatch(color):
        raise ValueError(f'颜色值格式非法：{value}')
    if len(color) == 4:
        color = '#' + ''.join(ch * 2 for ch in color[1:])
    return color.upper()


def parse_style_analysis(text: str):
    payload = parse_json_candidate(text, '风格分析结果格式异常')

    styles = payload.get('styles')
    if not isinstance(styles, list) or len(styles) != 4:
        raise ValueError('风格分析结果格式异常：styles 必须为长度 4 的数组')

    normalized_styles = []
    for item in styles:
        if not isinstance(item, dict):
            raise ValueError('风格分析结果格式异常：单个风格必须为对象')

        title = str(item.get('title', '')).strip()
        reasoning = str(item.get('reasoning', '')).strip()
        colors = item.get('colors')

        if not title or not reasoning:
            raise ValueError('风格分析结果格式异常：title 和 reasoning 不能为空')
        if not isinstance(colors, list) or len(colors) != 3:
            raise ValueError('风格分析结果格式异常：colors 必须包含 3 个颜色值')

        normalized_styles.append(
            {
                'title': title,
                'reasoning': reasoning,
                'colors': [normalize_hex_color(color) for color in colors],
            }
        )

    return normalized_styles


def get_suite_type_rules(output_count: int):
    try:
        count = int(output_count)
    except (TypeError, ValueError) as exc:
        raise ValueError('输出数量必须为 6-10 之间的整数') from exc

    if count not in SUITE_TYPE_RULES:
        raise ValueError('输出数量必须为 6-10 之间的整数')
    return count, SUITE_TYPE_RULES[count]


def parse_selected_modules(modules_raw: str):
    try:
        parsed = json.loads((modules_raw or '').strip() or '[]')
    except json.JSONDecodeError as exc:
        raise ValueError('A+ 模块参数格式异常') from exc

    if not isinstance(parsed, list) or not parsed:
        raise ValueError('请至少选择 1 个 A+ 模块')

    selected_keys = []
    seen = set()
    for item in parsed:
        key = str(item or '').strip()
        if not key or key in seen:
            continue
        if key not in APLUS_MODULE_META:
            raise ValueError(f'A+ 模块参数非法：{key}')
        selected_keys.append(key)
        seen.add(key)

    if not selected_keys:
        raise ValueError('请至少选择 1 个 A+ 模块')
    return selected_keys



def parse_selected_style(title: str, reasoning: str, colors_raw: str):
    normalized_title = (title or '').strip()
    normalized_reasoning = (reasoning or '').strip()
    raw_colors = (colors_raw or '').strip()

    if not normalized_title and not normalized_reasoning and not raw_colors:
        return None

    if not normalized_title or not normalized_reasoning:
        raise ValueError('所选风格参数不完整，请重新选择风格后再试')

    try:
        parsed_colors = json.loads(raw_colors or '[]')
    except json.JSONDecodeError as exc:
        raise ValueError('所选风格颜色参数格式异常') from exc

    if not isinstance(parsed_colors, list) or len(parsed_colors) != 3:
        raise ValueError('所选风格颜色参数必须包含 3 个颜色值')

    return {
        'title': normalized_title,
        'reasoning': normalized_reasoning,
        'colors': [normalize_hex_color(color) for color in parsed_colors],
    }


def build_style_reference_text(selected_style) -> str:
    if not selected_style:
        return '未指定风格，请基于平台、卖点、国家、文字类型、尺寸比例与参考图自行规划。'

    color_list = ' / '.join(selected_style.get('colors') or []) or '未提供颜色'
    return (
        f'已选风格标题：{selected_style.get("title", "") or "未命名风格"}\n'
        f'风格说明：{selected_style.get("reasoning", "") or "未提供"}\n'
        f'参考配色：{color_list}'
    )


PRODUCT_JSON_FALLBACK = {
    'product_name': '',
    'category': '',
    'core_subject': '',
    'subject_composition': {
        'subject_count': '',
        'subject_units': [],
        'assembly_form': '',
    },
    'appearance': {
        'primary_colors': [],
        'secondary_colors': [],
        'materials': [],
        'textures_patterns': [],
        'silhouette': '',
        'structure': '',
        'surface_finish': '',
        'craft_details': [],
    },
    'key_components': [],
    'brand_identity': {
        'brand_name': '',
        'logo_details': '',
        'text_markings': [],
        'logo_positions': [],
    },
    'immutable_traits': [],
    'consistency_rules': [],
    'must_keep': [],
    'must_not_change': [],
    'forbidden_changes': [],
    'selling_points': [],
}


PRODUCT_JSON_PROMPT_TEMPLATE = (
    '不可变商品特征（仅用于锁定商品主体，若为空则代表暂未提取）：\n{product_json_text}\n\n'
    '执行要求：\n'
    '1. 上述结构只代表商品主体本身，不包含也不得反向推导场景、背景、光线、氛围、人物、姿势、镜头语言或文案排版。\n'
    '2. 后续所有规划与生图都必须优先遵守以上不可变商品特征，尤其优先执行 must_keep、must_not_change、forbidden_changes 与 consistency_rules。\n'
    '3. must_keep 代表每张图都必须保留的主体锚点；must_not_change 代表绝不允许漂移、弱化或替换的主体信息；forbidden_changes 代表明确禁止出现的变体方向。\n'
    '4. selling_points 仅用于补充画面表达重点、信息层级与卖点文案，不得覆盖或削弱主体一致性约束。\n'
    '5. 允许变化的仅限背景、道具、光线、构图、文案排版与非主体装饰；禁止把商品改成另一种外观、材质、结构或颜色体系。\n'
    '6. 若某些字段为空，只能依据参考图可见主体信息保守补足，不能臆测或改造成另一种商品。'
)


def normalize_product_json(raw_value):
    payload = raw_value if isinstance(raw_value, dict) else {}
    subject_composition = payload.get('subject_composition') if isinstance(payload.get('subject_composition'), dict) else {}
    appearance = payload.get('appearance') if isinstance(payload.get('appearance'), dict) else {}
    brand_identity = payload.get('brand_identity') if isinstance(payload.get('brand_identity'), dict) else {}
    visible_attributes = payload.get('visible_attributes') if isinstance(payload.get('visible_attributes'), dict) else {}

    def clean_list(value, limit=6):
        if not isinstance(value, list):
            return []
        normalized = []
        seen = set()
        for item in value:
            text = str(item).strip()
            if not text or text in seen:
                continue
            normalized.append(text)
            seen.add(text)
            if limit and len(normalized) >= limit:
                break
        return normalized

    primary_colors = clean_list(appearance.get('primary_colors'), limit=4)
    secondary_colors = clean_list(appearance.get('secondary_colors'), limit=4)
    materials = clean_list(appearance.get('materials'), limit=4)
    textures_patterns = clean_list(appearance.get('textures_patterns'))
    craft_details = clean_list(appearance.get('craft_details'))
    key_components = clean_list(payload.get('key_components'))
    immutable_traits = clean_list(payload.get('immutable_traits'))
    consistency_rules = clean_list(payload.get('consistency_rules'), limit=8)
    must_keep = clean_list(payload.get('must_keep'), limit=8)
    must_not_change = clean_list(payload.get('must_not_change'), limit=8)
    forbidden_changes = clean_list(payload.get('forbidden_changes'), limit=8)
    selling_points = clean_list(payload.get('selling_points'))
    subject_units = clean_list(subject_composition.get('subject_units'))
    text_markings = clean_list(brand_identity.get('text_markings'))
    logo_positions = clean_list(brand_identity.get('logo_positions'))

    legacy_color = str(visible_attributes.get('color', '')).strip()
    legacy_material = str(visible_attributes.get('material', '')).strip()
    legacy_pattern = str(visible_attributes.get('pattern', '')).strip()
    legacy_shape = str(visible_attributes.get('shape', '')).strip()
    legacy_structure = str(visible_attributes.get('structure', '')).strip()
    legacy_craft_details = clean_list(visible_attributes.get('craft_details'))

    if not primary_colors and legacy_color:
        primary_colors = [legacy_color]
    if not materials and legacy_material:
        materials = [legacy_material]
    if not textures_patterns and legacy_pattern:
        textures_patterns = [legacy_pattern]
    if not craft_details and legacy_craft_details:
        craft_details = legacy_craft_details

    silhouette = str(appearance.get('silhouette', '')).strip() or legacy_shape
    structure = str(appearance.get('structure', '')).strip() or legacy_structure
    category = str(payload.get('category', '')).strip()
    core_subject = str(payload.get('core_subject', '')).strip()

    if not must_keep:
        must_keep = clean_list([
            category,
            core_subject,
            *primary_colors[:2],
            silhouette,
            *key_components[:2],
        ], limit=8)

    if not must_not_change:
        must_not_change = clean_list([
            structure,
            *materials[:2],
            *immutable_traits[:4],
            *logo_positions[:2],
        ], limit=8)

    if not forbidden_changes:
        auto_forbidden = []
        if category:
            auto_forbidden.append('禁止替换为其他商品品类或其他主体对象')
        if primary_colors:
            auto_forbidden.append('禁止把主体主色与辅色改成另一套明显不同的颜色体系')
        if materials:
            auto_forbidden.append('禁止把主体材质表现替换成另一种明显不同的材质')
        if structure or silhouette:
            auto_forbidden.append('禁止改变主体轮廓、结构比例或关键造型')
        if key_components:
            auto_forbidden.append('禁止删减、替换或新增会改变商品识别度的关键部件')
        if logo_positions or text_markings:
            auto_forbidden.append('禁止改动品牌标识、文字标记或 logo 位置')
        forbidden_changes = clean_list(auto_forbidden, limit=8)

    return {
        'product_name': str(payload.get('product_name', '')).strip(),
        'category': category,
        'core_subject': core_subject,
        'subject_composition': {
            'subject_count': str(subject_composition.get('subject_count', '')).strip(),
            'subject_units': subject_units,
            'assembly_form': str(subject_composition.get('assembly_form', '')).strip(),
        },
        'appearance': {
            'primary_colors': primary_colors,
            'secondary_colors': secondary_colors,
            'materials': materials,
            'textures_patterns': textures_patterns,
            'silhouette': silhouette,
            'structure': structure,
            'surface_finish': str(appearance.get('surface_finish', '')).strip(),
            'craft_details': craft_details,
        },
        'key_components': key_components,
        'brand_identity': {
            'brand_name': str(brand_identity.get('brand_name', '')).strip(),
            'logo_details': str(brand_identity.get('logo_details', '')).strip(),
            'text_markings': text_markings,
            'logo_positions': logo_positions,
        },
        'immutable_traits': immutable_traits,
        'consistency_rules': consistency_rules,
        'must_keep': must_keep,
        'must_not_change': must_not_change,
        'forbidden_changes': forbidden_changes,
        'selling_points': selling_points,
    }



def parse_product_json(text: str):
    try:
        payload = parse_json_candidate(text, '商品结构化信息格式异常')
    except ValueError:
        payload = extract_json_object_from_text(strip_code_fences(text))
        if payload is None:
            raise ValueError('商品结构化信息格式异常：无法解析为 JSON 对象')
    if not isinstance(payload, dict):
        raise ValueError('商品结构化信息格式异常：顶层必须为对象')
    return normalize_product_json(payload)



def parse_product_json_payload(raw_value: str):
    normalized_raw = (raw_value or '').strip()
    if not normalized_raw:
        return None
    try:
        payload = json.loads(normalized_raw)
    except json.JSONDecodeError:
        payload = extract_json_object_from_text(normalized_raw)
        if payload is None:
            raise ValueError('商品结构化信息参数格式异常')
    if not isinstance(payload, dict):
        raise ValueError('商品结构化信息参数格式异常：顶层必须为对象')
    return normalize_product_json(payload)



def extract_json_object_from_text(text: str):
    if not text:
        return None
    candidate_patterns = [
        r'\{[\s\S]*\}',
    ]
    for pattern in candidate_patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = match.group(0).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None



def extract_product_json_from_image_payloads(selling_text: str, image_payloads):
    if not image_payloads:
        return None
    product_json, _response_text = call_chat_json_with_repair(
        PRODUCT_JSON_SYSTEM_PROMPT,
        build_multimodal_content(
            PRODUCT_JSON_USER_PROMPT_TEMPLATE.format(selling_text=selling_text or '（未填写）'),
            image_payloads,
        ),
        parse_product_json,
        '商品结构化信息格式异常',
        temperature=0.2,
        timeout_seconds=get_suite_plan_timeout_seconds(),
        repair_attempts=1,
    )
    try:
        return normalize_product_json(product_json)
    except ValueError as exc:
        app.logger.warning('商品结构化信息解析失败，已降级为空结构：%s', exc)
        return normalize_product_json(PRODUCT_JSON_FALLBACK)



def serialize_product_json(product_json) -> str:
    normalized = normalize_product_json(product_json or PRODUCT_JSON_FALLBACK)
    return json.dumps(normalized, ensure_ascii=False, indent=2)



def build_product_json_prompt_text(product_json) -> str:
    if not product_json:
        return '未提供不可变商品特征。'
    return PRODUCT_JSON_PROMPT_TEMPLATE.format(product_json_text=serialize_product_json(product_json))



def build_suite_plan_prompt(platform: str, selling_text: str, output_count: int, type_rules, country: str, text_type: str, image_size_ratio: str, selected_style=None, mode: str = 'suite', product_json=None):
    type_list = '\n'.join(f'{index + 1}. {item}' for index, item in enumerate(type_rules))
    type_details = '\n'.join(
        f'- {name}：{SUITE_TYPE_META[name]["detail"]}'
        for name in type_rules
    )
    prompt_template = SUITE_PLAN_USER_PROMPT_TEMPLATE
    if mode == 'fashion':
        prompt_template = (
            SUITE_PLAN_USER_PROMPT_TEMPLATE
            + '\n18. 当前为服饰穿搭场景：商品图只用于锁定服饰主体的不可变特征，如品类、颜色、材质、版型、结构与稳定细节；如同时提供穿搭参考图，则只用于吸收模特姿态、穿搭方式、镜头语言、氛围与版式方向，不得替换商品主体本身。\n'
            + '19. 服饰场景下，prompt 必须优先保证商品主体与商品图一致，其次再融合参考图里的姿态、氛围与构图灵感。'
        )
    product_json_text = build_product_json_prompt_text(product_json)
    return prompt_template.format(
        platform=platform,
        country=country or '中国',
        text_type=text_type or '中文',
        image_size_ratio=image_size_ratio or '1:1',
        selling_text=selling_text or '（未填写）',
        style_reference=build_style_reference_text(selected_style),
        product_json=product_json_text,
        output_count=output_count,
        type_list=type_list,
        type_details=type_details,
    )


def parse_suite_plan(text: str, expected_output_count: int, allowed_types):
    payload = parse_json_candidate(text, '套图规划结果格式异常')

    summary = str(payload.get('summary', '')).strip()
    output_count = payload.get('output_count')
    items = payload.get('items')

    if not summary:
        raise ValueError('套图规划结果格式异常：summary 不能为空')
    if output_count != expected_output_count:
        raise ValueError('套图规划结果格式异常：output_count 与请求不一致')
    if not isinstance(items, list) or len(items) != expected_output_count:
        raise ValueError('套图规划结果格式异常：items 数量与输出张数不一致')

    normalized_items = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError('套图规划结果格式异常：单个套图项必须为对象')

        sort = item.get('sort')
        image_type = str(item.get('type', '')).strip()
        title = str(item.get('title', '')).strip()
        prompt = str(item.get('prompt', '')).strip()
        keywords = item.get('keywords')

        if sort != index:
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 sort 非法')
        if image_type not in allowed_types:
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 type 非法')
        if not title:
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 title 不能为空')
        if not prompt:
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 prompt 不能为空')
        if not isinstance(keywords, list) or not (3 <= len(keywords) <= 6):
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 keywords 数量必须为 3-6 个')

        normalized_keywords = [str(keyword).strip() for keyword in keywords if str(keyword).strip()]
        if len(normalized_keywords) < 3:
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 keywords 不能为空')

        module = normalize_plan_enum(
            item.get('module'),
            {'opening_narrative', 'scene_narrative', 'value_visualization', 'trust_narrative'},
            'scene_narrative',
        )
        story_role = normalize_plan_short_text(item.get('story_role'), '未指定故事节点')
        decision_task = normalize_plan_short_text(item.get('decision_task'), '未指定决策任务')
        info_density = normalize_plan_enum(item.get('info_density'), {'low', 'medium', 'high'}, 'medium')

        scene_required_raw = item.get('scene_required')
        if not isinstance(scene_required_raw, bool):
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 scene_required 必须为布尔值')

        human_presence = normalize_plan_enum(item.get('human_presence'), {'none', 'hand-only', 'model'}, 'none')
        scene_type = normalize_plan_short_text(item.get('scene_type'), '未指定场景')
        camera_shot = normalize_plan_short_text(item.get('camera_shot'), '未指定景别')
        subject_angle = normalize_plan_short_text(item.get('subject_angle'), '未指定角度')
        action_type = normalize_plan_short_text(item.get('action_type'), '静态陈列')
        layout_anchor = normalize_plan_short_text(item.get('layout_anchor'), '主体居中放大')
        layout_style = normalize_plan_short_text(item.get('layout_style'), '单图分层')
        font_style = normalize_plan_short_text(item.get('font_style'), '清晰无衬线')
        color_scheme = normalize_plan_short_text(item.get('color_scheme'), '低饱和同色系')
        decor_elements = item.get('decor_elements') if isinstance(item.get('decor_elements'), list) else []
        decor_elements = [normalize_plan_short_text(value) for value in decor_elements]
        decor_elements = [value for value in decor_elements if value][:4]
        must_differ_from = normalize_plan_type_list(item.get('must_differ_from'), allowed_types)
        must_differ_from = [name for name in must_differ_from if name != image_type]

        normalized_items.append(
            {
                'sort': sort,
                'type': image_type,
                'title': title,
                'keywords': normalized_keywords,
                'prompt': prompt,
                'type_tag': SUITE_TYPE_META.get(image_type, {}).get('tag', 'Board'),
                'module': module,
                'story_role': story_role,
                'decision_task': decision_task,
                'info_density': info_density,
                'scene_required': scene_required_raw,
                'scene_type': scene_type,
                'camera_shot': camera_shot,
                'subject_angle': subject_angle,
                'human_presence': human_presence,
                'action_type': action_type,
                'layout_anchor': layout_anchor,
                'layout_style': layout_style,
                'font_style': font_style,
                'color_scheme': color_scheme,
                'decor_elements': decor_elements,
                'must_differ_from': must_differ_from,
            }
        )

    return {
        'summary': summary,
        'output_count': expected_output_count,
        'items': normalized_items,
    }




def normalize_plan_short_text(value: str, fallback: str = '') -> str:
    return str(value or '').strip() or fallback


def normalize_plan_enum(value: str, allowed_values, fallback: str) -> str:
    text = normalize_plan_short_text(value, fallback)
    return text if text in allowed_values else fallback


def normalize_plan_type_list(raw_value, allowed_types, limit=3):
    if not isinstance(raw_value, list):
        return []
    normalized = []
    seen = set()
    for item in raw_value:
        text = str(item or '').strip()
        if not text or text in seen or text not in allowed_types:
            continue
        normalized.append(text)
        seen.add(text)
        if limit and len(normalized) >= limit:
            break
    return normalized


def build_suite_plan(platform: str, selling_text: str, output_count: int, image_payloads, country: str, text_type: str, image_size_ratio: str, selected_style=None, mode: str = 'suite', product_json=None):
    _, type_rules = get_suite_type_rules(output_count)
    prompt = build_suite_plan_prompt(platform, selling_text, output_count, type_rules, country, text_type, image_size_ratio, selected_style, mode, product_json)
    plan, _response_text = call_chat_json_with_repair(
        SUITE_PLAN_SYSTEM_PROMPT,
        build_multimodal_content(prompt, image_payloads),
        lambda text: parse_suite_plan(text, output_count, type_rules),
        '套图规划结果格式异常',
        temperature=0.3,
        timeout_seconds=get_suite_plan_timeout_seconds(),
        repair_attempts=1,
    )
    return plan



def parse_fashion_scene_plan(text: str):
    payload = parse_json_candidate(text, '场景规划结果格式异常')

    summary = str(payload.get('summary', '')).strip()
    scene_prompt = str(payload.get('scene_prompt', '')).strip()
    scene_groups = payload.get('scene_groups')

    if not summary:
        raise ValueError('场景规划结果格式异常：summary 不能为空')
    if not scene_prompt:
        raise ValueError('场景规划结果格式异常：scene_prompt 不能为空')
    if not isinstance(scene_groups, list) or len(scene_groups) != 4:
        raise ValueError('场景规划结果格式异常：scene_groups 必须严格返回 4 组场景')

    normalized_groups = []
    for group_index, group in enumerate(scene_groups, start=1):
        if not isinstance(group, dict):
            raise ValueError(f'场景规划结果格式异常：第 {group_index} 组必须为对象')

        group_id = str(group.get('id', '')).strip() or f'scene-group-{group_index}'
        title = str(group.get('title', '')).strip()
        description = str(group.get('description', '')).strip()
        group_scene_prompt = str(group.get('scene_prompt', '')).strip()
        poses = group.get('poses')

        if not title:
            raise ValueError(f'场景规划结果格式异常：第 {group_index} 组 title 不能为空')
        if not description:
            raise ValueError(f'场景规划结果格式异常：第 {group_index} 组 description 不能为空')
        if not group_scene_prompt:
            raise ValueError(f'场景规划结果格式异常：第 {group_index} 组 scene_prompt 不能为空')
        if not isinstance(poses, list) or len(poses) != 4:
            raise ValueError(f'场景规划结果格式异常：第 {group_index} 组 poses 必须严格返回 4 个模块')

        normalized_poses = []
        for pose_index, pose in enumerate(poses, start=1):
            if not isinstance(pose, dict):
                raise ValueError(f'场景规划结果格式异常：第 {group_index} 组第 {pose_index} 个姿态必须为对象')

            raw_pose_id = str(pose.get('id', '')).strip()
            pose_id = raw_pose_id if raw_pose_id.startswith(f'{group_id}-') else f'{group_id}-pose-{pose_index}'
            pose_title = str(pose.get('title', '')).strip()
            pose_description = str(pose.get('description', '')).strip()
            pose_scene_prompt = str(pose.get('scene_prompt', '')).strip()

            if not pose_title:
                raise ValueError(f'场景规划结果格式异常：第 {group_index} 组第 {pose_index} 个姿态 title 不能为空')
            if not pose_description:
                raise ValueError(f'场景规划结果格式异常：第 {group_index} 组第 {pose_index} 个姿态 description 不能为空')
            if not pose_scene_prompt:
                raise ValueError(f'场景规划结果格式异常：第 {group_index} 组第 {pose_index} 个姿态 scene_prompt 不能为空')

            normalized_poses.append(
                {
                    'id': pose_id,
                    'title': pose_title,
                    'description': pose_description,
                    'scene_prompt': pose_scene_prompt,
                }
            )

        normalized_groups.append(
            {
                'id': group_id,
                'title': title,
                'description': description,
                'scene_prompt': group_scene_prompt,
                'poses': normalized_poses,
            }
        )

    return {
        'summary': summary,
        'scene_prompt': scene_prompt,
        'scene_groups': normalized_groups,
    }


FASHION_DEFAULT_PLATFORM = '服饰穿搭'
FASHION_DEFAULT_COUNTRY = '中国'
FASHION_DEFAULT_TEXT_TYPE = '中文'
FASHION_DEFAULT_SELLING_TEXT = ''
FASHION_DEFAULT_SELECTED_STYLE = None



def build_fashion_scene_plan_prompt(platform: str, selling_text: str, country: str, text_type: str, image_size_ratio: str, selected_style=None):
    return FASHION_SCENE_PLAN_USER_PROMPT_TEMPLATE.format(
        image_size_ratio=image_size_ratio or '1:1',
    )



FASHION_SCENE_PLAN_MODEL_TIMEOUT_SECONDS = 120


def build_fashion_scene_plan(platform: str, selling_text: str, image_payloads, country: str, text_type: str, image_size_ratio: str, selected_style=None):
    prompt = build_fashion_scene_plan_prompt(platform, selling_text, country, text_type, image_size_ratio, selected_style)
    plan, _response_text = call_chat_json_with_repair(
        FASHION_SCENE_PLAN_SYSTEM_PROMPT,
        build_multimodal_content(prompt, image_payloads),
        parse_fashion_scene_plan,
        '服饰场景规划结果格式异常',
        temperature=0.3,
        timeout_seconds=FASHION_SCENE_PLAN_MODEL_TIMEOUT_SECONDS,
        repair_attempts=1,
    )
    return plan



def parse_json_string_list(raw_value: str, field_label: str):
    try:
        parsed = json.loads((raw_value or '').strip() or '[]')
    except json.JSONDecodeError as exc:
        raise ValueError(f'{field_label}参数格式异常') from exc

    if not isinstance(parsed, list):
        raise ValueError(f'{field_label}参数格式异常')

    normalized = []
    seen = set()
    for item in parsed:
        value = str(item or '').strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized



def parse_fashion_scene_plan_payload(raw_value: str):
    normalized = (raw_value or '').strip()
    if not normalized:
        raise ValueError('场景规划数据不能为空，请重新生成推荐场景')

    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ValueError('场景规划数据格式异常，请重新生成推荐场景') from exc

    return parse_fashion_scene_plan(json.dumps(payload, ensure_ascii=False))



def find_fashion_scene_selection(scene_groups, scene_group_id: str, pose_id: str):
    selected_group = None
    selected_pose = None

    for group in scene_groups:
        if group.get('id') != scene_group_id:
            continue
        selected_group = group
        for pose in group.get('poses') or []:
            if pose.get('id') == pose_id:
                selected_pose = pose
                break
        break

    if not selected_group:
        raise ValueError('请选择有效的场景组')
    if not selected_pose:
        raise ValueError('请选择有效的姿态方案')

    return selected_group, selected_pose



def parse_fashion_scene_selections(scene_groups, scene_group_ids, pose_ids):
    normalized_group_ids = []
    seen_group_ids = set()
    for scene_group_id in scene_group_ids or []:
        normalized_group_id = str(scene_group_id or '').strip()
        if not normalized_group_id or normalized_group_id in seen_group_ids:
            continue
        normalized_group_ids.append(normalized_group_id)
        seen_group_ids.add(normalized_group_id)

    normalized_pose_ids = []
    seen_pose_ids = set()
    for pose_id in pose_ids or []:
        normalized_pose_id = str(pose_id or '').strip()
        if not normalized_pose_id or normalized_pose_id in seen_pose_ids:
            continue
        normalized_pose_ids.append(normalized_pose_id)
        seen_pose_ids.add(normalized_pose_id)

    if not normalized_pose_ids:
        raise ValueError('请至少选择 1 个场景')

    normalized_entries = []
    matched_group_ids = set()

    for normalized_pose_id in normalized_pose_ids:
        matched_group = None
        matched_pose = None

        for group in scene_groups or []:
            for pose in group.get('poses') or []:
                if pose.get('id') == normalized_pose_id:
                    matched_group = group
                    matched_pose = pose
                    break
            if matched_group and matched_pose:
                break

        if not matched_group or not matched_pose:
            raise ValueError('请选择有效的姿态方案')

        matched_group_id = str(matched_group.get('id') or '').strip()
        if normalized_group_ids and matched_group_id not in seen_group_ids:
            raise ValueError('请选择有效的场景组')

        normalized_entries.append(
            {
                'scene_group_id': matched_group_id,
                'pose_id': normalized_pose_id,
                'group': matched_group,
                'pose': matched_pose,
            }
        )
        matched_group_ids.add(matched_group_id)

    unused_group_ids = [group_id for group_id in normalized_group_ids if group_id not in matched_group_ids]
    if unused_group_ids:
        raise ValueError('请选择有效的场景和姿态')

    return normalized_entries



def infer_fashion_pose_shot_size(selected_group: dict, selected_pose: dict) -> str:
    text = ' '.join(
        str(value or '').strip()
        for value in [
            selected_group.get('title'),
            selected_group.get('description'),
            selected_group.get('scene_prompt'),
            selected_pose.get('title'),
            selected_pose.get('description'),
            selected_pose.get('scene_prompt'),
        ]
        if str(value or '').strip()
    )
    if re.search(r'特写|近景|局部|细节|拉链|袖口|领口|纽扣|面料|纹理', text):
        return '特写'
    if re.search(r'半身|上半身|胸像', text):
        return '半身'
    if re.search(r'四分之三|3/4|七分身|中景', text):
        return '四分之三'
    if re.search(r'全身|全景|站立|直立|完整|通身|落地', text):
        return '全身'
    return '半身'



def infer_fashion_pose_view_angle(selected_group: dict, selected_pose: dict) -> str:
    text = ' '.join(
        str(value or '').strip()
        for value in [
            selected_group.get('title'),
            selected_group.get('description'),
            selected_group.get('scene_prompt'),
            selected_pose.get('title'),
            selected_pose.get('description'),
            selected_pose.get('scene_prompt'),
        ]
        if str(value or '').strip()
    )
    if re.search(r'3/4|四分之三|45度|斜侧|侧前方', text):
        return '3/4侧'
    if re.search(r'背面|背影|后背|背部', text):
        return '背面'
    if re.search(r'侧面|侧身|侧向', text):
        return '侧面'
    if re.search(r'正面|正向|正对', text):
        return '正面'
    return '正面'



def build_fashion_pose_camera_setting(selected_group: dict, selected_pose: dict, current_setting=None):
    setting = current_setting if isinstance(current_setting, dict) else {}
    shot_size = str(setting.get('shot_size') or '').strip() or infer_fashion_pose_shot_size(selected_group, selected_pose)
    view_angle = str(setting.get('view_angle') or '').strip() or infer_fashion_pose_view_angle(selected_group, selected_pose)
    return {
        'shot_size': shot_size,
        'view_angle': view_angle,
    }



def parse_fashion_pose_camera_settings(raw_value: str, selections):
    normalized = (raw_value or '').strip()
    if not normalized:
        return {
            str(selection.get('pose_id') or '').strip(): build_fashion_pose_camera_setting(
                selection.get('group') or {},
                selection.get('pose') or {},
            )
            for selection in (selections or [])
            if str(selection.get('pose_id') or '').strip()
        }

    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ValueError('场景镜头参数格式异常，请重新选择') from exc

    if not isinstance(payload, list):
        raise ValueError('场景镜头参数格式异常，请重新选择')

    selection_map = {
        str(selection.get('pose_id') or '').strip(): selection
        for selection in (selections or [])
        if str(selection.get('pose_id') or '').strip()
    }
    camera_settings = {}

    for item in payload:
        if not isinstance(item, dict):
            continue
        pose_id = str(item.get('pose_id') or '').strip()
        if not pose_id or pose_id not in selection_map:
            continue
        selection = selection_map[pose_id]
        camera_settings[pose_id] = build_fashion_pose_camera_setting(
            selection.get('group') or {},
            selection.get('pose') or {},
            {
                'shot_size': str(item.get('shot_size') or '').strip(),
                'view_angle': str(item.get('view_angle') or '').strip(),
            },
        )

    for selection in selections or []:
        pose_id = str(selection.get('pose_id') or '').strip()
        if pose_id and pose_id not in camera_settings:
            camera_settings[pose_id] = build_fashion_pose_camera_setting(
                selection.get('group') or {},
                selection.get('pose') or {},
            )

    return camera_settings



def parse_fashion_selected_model_payload(form):
    selected_payloads = get_image_payloads_from_request('fashion_selected_model_image', limit=1)
    return parse_fashion_selected_model_payload_from_data(form, selected_payloads)


def parse_fashion_selected_model_payload_from_data(form, selected_payloads):
    source = (form.get('fashion_selected_model_source', '') or '').strip()
    model_id = (form.get('fashion_selected_model_id', '') or '').strip()
    model_name = (form.get('fashion_selected_model_name', '') or '').strip()
    gender = (form.get('fashion_selected_model_gender', '') or '').strip()
    age = (form.get('fashion_selected_model_age', '') or '').strip()
    ethnicity = (form.get('fashion_selected_model_ethnicity', '') or '').strip()
    body_type = (form.get('fashion_selected_model_body_type', '') or '').strip()
    appearance_details = (form.get('fashion_selected_model_appearance_details', '') or '').strip()
    summary = (form.get('fashion_selected_model_summary', '') or '').strip()
    detail_text = (form.get('fashion_selected_model_detail_text', '') or '').strip()

    if not source:
        raise ValueError('缺少当前已选模特来源，请重新选择模特后再生成')
    if source not in {'ai', 'custom'}:
        raise ValueError('当前已选模特来源无效，请重新选择模特后再生成')
    if not model_id:
        raise ValueError('缺少当前已选模特 ID，请重新选择模特后再生成')

    if not selected_payloads:
        raise ValueError('缺少当前已选模特图片，请重新选择模特后再生成')

    selected_payload = selected_payloads[0]
    filename = str(selected_payload.get('filename') or '').strip()
    if source == 'ai' and not filename:
        raise ValueError('AI 基准模特图片信息异常，请重新生成或重新选择后再试')
    if source == 'custom' and not filename:
        raise ValueError('自定义模特图片信息异常，请重新上传或重新选择后再试')

    return {
        'source': source,
        'id': model_id,
        'name': model_name,
        'gender': gender,
        'age': age,
        'ethnicity': ethnicity,
        'body_type': body_type,
        'appearance_details': appearance_details,
        'summary': summary,
        'detail_text': detail_text,
        'payload': selected_payload,
        'debug': {
            'source': source,
            'id': model_id,
            'name': model_name,
            'filename': filename,
            'mime_type': str(selected_payload.get('mime_type') or '').strip(),
            'byte_size': len(selected_payload.get('bytes') or b''),
            'gender': gender,
            'age': age,
            'ethnicity': ethnicity,
            'body_type': body_type,
        },
    }


def build_fashion_selected_model_identity_text(selected_model: dict):
    model_name = str((selected_model or {}).get('name') or '').strip()
    gender = str((selected_model or {}).get('gender') or '').strip()
    age = str((selected_model or {}).get('age') or '').strip()
    ethnicity = str((selected_model or {}).get('ethnicity') or '').strip()
    body_type = str((selected_model or {}).get('body_type') or '').strip()
    appearance_details = str((selected_model or {}).get('appearance_details') or '').strip()
    summary = str((selected_model or {}).get('summary') or '').strip()
    detail_text = str((selected_model or {}).get('detail_text') or '').strip()

    identity_parts = [value for value in [gender, age, ethnicity, body_type] if value]
    identity_summary = '、'.join(identity_parts) if identity_parts else '未提供'
    appearance_summary = appearance_details or detail_text or summary or '未提供'
    model_label = model_name or '当前已选模特'
    return (
        f'模特名称：{model_label}\n'
        f'模特身份标签：{identity_summary}\n'
        f'模特外观补充：{appearance_summary}'
    )


def build_fashion_generation_prompt(platform: str, selling_text: str, country: str, text_type: str, image_size_ratio: str, selected_style, selected_model: dict, scene_plan: dict, selected_group: dict, selected_pose: dict, shot_sizes, view_angles):
    shot_text = '、'.join(shot_sizes) if shot_sizes else '未指定'
    angle_text = '、'.join(view_angles) if view_angles else '未指定'
    scene_summary = str(scene_plan.get('summary', '')).strip() or '未提供'
    scene_prompt = str(scene_plan.get('scene_prompt', '')).strip() or ''
    group_prompt = str(selected_group.get('scene_prompt', '')).strip() or ''
    pose_prompt = str(selected_pose.get('scene_prompt', '')).strip() or ''
    selected_model_identity_text = build_fashion_selected_model_identity_text(selected_model)

    return (
        f'请生成 1 张服饰穿戴图。产品穿在模特身上，必须清晰可见真人模特完整上身展示该商品，不能只出衣服。\n\n'
        f'图片尺寸比例参考：{image_size_ratio or "1:1"}\n'
        f'当前已选模特身份锚点：\n{selected_model_identity_text}\n'
        f'场景规划摘要：{scene_summary}\n'
        f'整组场景提示：{scene_prompt or "未提供"}\n'
        f'已选场景组：{selected_group.get("title", "未命名场景组")}\n'
        f'场景组说明：{selected_group.get("description", "未提供")}\n'
        f'场景组提示：{group_prompt or "未提供"}\n'
        f'已选姿态：{selected_pose.get("title", "未命名姿态")}\n'
        f'姿态说明：{selected_pose.get("description", "未提供")}\n'
        f'姿态提示：{pose_prompt or "未提供"}\n'
        f'镜头景别：{shot_text}\n'
        f'视角选择：{angle_text}\n\n'
        f'执行要求：\n'
        f'1. 严格使用提供的模特图作为最终出镜人物，保持同一张脸、发型、气质、肤感与身形特征；禁止换人、禁止变性别、禁止混入其他模特特征。\n'
        f'2. 严格使用提供的商品图作为服饰主体，保持款式、颜色、结构、材质、版型、图案、logo 位置与细节一致；禁止替换商品本身。\n'
        f'3. 商品图只负责锁定衣服，模特图只负责锁定穿着者，二者必须同时生效；不能只参考商品图，也不能只参考模特图。\n'
        f'4. 最终人物必须与“当前已选模特身份锚点”一致；若场景、姿态、镜头与模特身份锚点冲突，必须优先服从模特身份锚点。\n'
        f'5. 画面必须体现已选场景组、姿态、镜头景别与视角信息，背景简洁，服务于服装展示，不得让背景喧宾夺主。\n'
        f'6. 必须输出适合电商展示的真人模特穿搭成图，禁止只生成衣服、禁止平铺挂拍、禁止无头模特、禁止把人物裁切到无法识别身份。\n'
        f'7. 优先突出模特穿着商品后的上身效果、版型、面料垂感与真实穿搭氛围，让人一眼看出“这是当前已选模特穿着当前商品图中的同一件服饰”。\n'
        f'8. 严禁生成任何新增可见文字元素：汉字、英文、数字、logo 文案、水印、字幕、角标、标签字样、吊牌字样、排版字、海报字、印刷覆盖字都不允许出现。\n'
        f'9. 若商品本体原始设计中自带品牌标识、logo、印花文字或标签细节，只能按商品图原样保留，不得新增、篡改、放大、改写或替换成新的文字内容。\n'
        f'10. 不要出现海报排版、广告字、背景标牌、店招、墙面文字、包装外额外字样、吊牌放大展示、字幕条、水印角标。'
    )



def build_fashion_generation_prompts(platform: str, selling_text: str, country: str, text_type: str, image_size_ratio: str, selected_style, selected_model: dict, scene_plan: dict, selections, pose_camera_settings):
    if not selections:
        raise ValueError('请至少选择 1 个场景')

    prompts = []
    for selection in selections:
        pose_id = str(selection.get('pose_id') or '').strip()
        camera_setting = pose_camera_settings.get(pose_id) or {}
        shot_size = str(camera_setting.get('shot_size') or '').strip()
        view_angle = str(camera_setting.get('view_angle') or '').strip()
        if not shot_size:
            raise ValueError('请为每个场景选择景别')
        if not view_angle:
            raise ValueError('请为每个场景选择视角')
        prompts.append(
            {
                'scene_group_id': selection['scene_group_id'],
                'pose_id': pose_id,
                'group': selection['group'],
                'pose': selection['pose'],
                'shot_size': shot_size,
                'view_angle': view_angle,
                'prompt': build_fashion_generation_prompt(
                    platform,
                    selling_text,
                    country,
                    text_type,
                    image_size_ratio,
                    selected_style,
                    selected_model,
                    scene_plan,
                    selection['group'],
                    selection['pose'],
                    [shot_size] if shot_size else [],
                    [view_angle] if view_angle else [],
                ),
            }
        )
    return prompts



def parse_fashion_output_verification(text: str):
    payload = parse_json_candidate(text, '服饰成图质检结果格式异常')

    if not isinstance(payload, dict):
        raise ValueError('服饰成图质检结果格式异常：返回值必须为对象')

    failed_checks = payload.get('failed_checks')
    if not isinstance(failed_checks, list):
        failed_checks = []
    normalized_failed_checks = []
    allowed_failed_checks = {'model_present', 'same_model_identity', 'wearing_product', 'extra_text_present'}
    for item in failed_checks:
        value = str(item or '').strip()
        if value in allowed_failed_checks and value not in normalized_failed_checks:
            normalized_failed_checks.append(value)

    reason = str(payload.get('reason', '')).strip()
    if not reason:
        raise ValueError('服饰成图质检结果格式异常：reason 不能为空')

    try:
        score = int(payload.get('score', 0))
    except (TypeError, ValueError):
        raise ValueError('服饰成图质检结果格式异常：score 必须为整数') from None
    score = max(0, min(score, 100))

    result = {
        'model_present': bool(payload.get('model_present')),
        'same_model_identity': bool(payload.get('same_model_identity')),
        'wearing_product': bool(payload.get('wearing_product')),
        'extra_text_present': bool(payload.get('extra_text_present')),
        'passed': bool(payload.get('passed')),
        'score': score,
        'failed_checks': normalized_failed_checks,
        'reason': reason,
    }

    expected_passed = (
        result['model_present']
        and result['same_model_identity']
        and result['wearing_product']
        and not result['extra_text_present']
    )
    result['passed'] = expected_passed

    if expected_passed:
        result['failed_checks'] = []
    else:
        computed_failed_checks = []
        if not result['model_present']:
            computed_failed_checks.append('model_present')
        if not result['same_model_identity']:
            computed_failed_checks.append('same_model_identity')
        if not result['wearing_product']:
            computed_failed_checks.append('wearing_product')
        if result['extra_text_present']:
            computed_failed_checks.append('extra_text_present')
        result['failed_checks'] = computed_failed_checks

    return result



def verify_fashion_generated_output(generated_payload: dict, selected_model_payload: dict, product_payloads):
    if not generated_payload:
        raise ValueError('缺少待质检的服饰生成结果')
    if not selected_model_payload:
        raise ValueError('缺少模特参考图，无法执行服饰成图质检')
    if not product_payloads:
        raise ValueError('缺少商品图，无法执行服饰成图质检')

    verification_payloads = [generated_payload, selected_model_payload, product_payloads[0]]
    verification, _response_text = call_chat_json_with_repair(
        FASHION_OUTPUT_VERIFIER_SYSTEM_PROMPT,
        build_multimodal_content(FASHION_OUTPUT_VERIFIER_USER_PROMPT_TEMPLATE, verification_payloads),
        parse_fashion_output_verification,
        '服饰成图质检结果格式异常',
        temperature=0,
        timeout_seconds=90,
        repair_attempts=1,
    )
    return verification



FASHION_MODEL_APPEARANCE_FALLBACK = '五官自然立体，肤质真实细腻，整体形象干净利落'


def get_request_value(payload: dict, form, key: str, default: str = '') -> str:
    if key in payload:
        return str(payload.get(key, default) or '').strip()
    return str(form.get(key, default) or '').strip()


def build_fashion_model_prompt(gender: str, age: str, ethnicity: str, body_type: str, appearance_details: str) -> str:
    normalized_gender = gender or '女'
    normalized_age = age or '青年'
    normalized_ethnicity = ethnicity or '欧美白人'
    normalized_body_type = body_type or '标准'
    normalized_details = appearance_details or FASHION_MODEL_APPEARANCE_FALLBACK
    identity_summary = '，'.join([
        normalized_gender,
        normalized_age,
        normalized_ethnicity,
        normalized_body_type,
    ])

    return (
        '请生成 1 张写实风格电商基准模特图，用于后续服饰穿搭展示与人物一致性锁定。\n\n'
        f'人物基础身份：{identity_summary}。\n'
        f'外貌细节：{normalized_details}。\n\n'
        '画面要求：\n'
        '1. 单人出镜，正面站立，自然表情，看向镜头，姿态放松。\n'
        '2. 以写实摄影质感呈现，电商棚拍风格，光线均匀柔和，背景简洁干净，适合作为电商展示基准模特。\n'
        '3. 人物整体形象真实自然，面部、皮肤、发型与体态细节清晰，保留真实质感。\n'
        '4. 构图优先完整展示人物穿搭承载状态，便于后续继续用于服饰上身生成。\n\n'
        '限制项：\n'
        '1. 不要多人，不要儿童陪衬，不要宠物。\n'
        '2. 不要复杂背景，不要街拍环境，不要凌乱道具。\n'
        '3. 不要夸张动作，不要大幅扭身，不要跳跃或戏剧化姿势。\n'
        '4. 不要卡通、插画、二次元、3D 渲染风。\n'
        '5. 不要畸形肢体、异常手指、面部崩坏或比例错误。\n'
        '6. 不要过度磨皮、过强滤镜、过分美颜或塑料皮肤。'
    )


def build_fashion_model_summary(gender: str, age: str, ethnicity: str, body_type: str) -> str:
    return ' · '.join([value for value in [gender, age, ethnicity, body_type] if value])


def build_fashion_model_response(task_id: str, model_id: str, gender: str, age: str, ethnicity: str, body_type: str, appearance_details: str, prompt: str, image_url: str, image_path: str, download_name: str):
    detail_text = appearance_details or FASHION_MODEL_APPEARANCE_FALLBACK
    summary = build_fashion_model_summary(gender, age, ethnicity, body_type)
    return {
        'id': model_id,
        'name': 'AI 基准模特',
        'summary': summary,
        'detailText': detail_text,
        'previewLabel': 'AI',
        'previewUrl': image_url,
        'createdAt': int(datetime.now().timestamp() * 1000),
        'task_id': task_id,
        'prompt': prompt,
        'gender': gender,
        'age': age,
        'ethnicity': ethnicity,
        'body_type': body_type,
        'appearance_details': appearance_details,
        'image_url': image_url,
        'image_path': image_path,
        'download_name': download_name,
    }


def build_aplus_plan_prompt(platform: str, selling_text: str, selected_module_keys, country: str, text_type: str, image_size_ratio: str, selected_style=None, product_json=None):
    module_names = [APLUS_MODULE_META[key]['name'] for key in selected_module_keys]
    module_list = '\n'.join(f'{index + 1}. {name}' for index, name in enumerate(module_names))
    module_details = '\n'.join(
        f'- {APLUS_MODULE_META[key]["name"]}：{APLUS_MODULE_META[key]["detail"]}'
        for key in selected_module_keys
    )
    return APLUS_PLAN_USER_PROMPT_TEMPLATE.format(
        platform=platform,
        country=country or '中国',
        text_type=text_type or '中文',
        image_size_ratio=image_size_ratio or '1:1',
        selling_text=selling_text or '（未填写）',
        product_json=build_product_json_prompt_text(product_json),
        style_reference=build_style_reference_text(selected_style),
        module_list=module_list,
        module_details=module_details,
        module_count=len(selected_module_keys),
    )


def parse_aplus_plan(text: str, selected_module_keys):
    payload = parse_json_candidate(text, 'A+ 规划结果格式异常')

    summary = str(payload.get('summary', '')).strip()
    module_count = payload.get('module_count')
    items = payload.get('items')
    expected_types = [APLUS_MODULE_META[key]['name'] for key in selected_module_keys]

    if not summary:
        raise ValueError('A+ 规划结果格式异常：summary 不能为空')
    if module_count != len(expected_types):
        raise ValueError('A+ 规划结果格式异常：module_count 与请求不一致')
    if not isinstance(items, list) or len(items) != len(expected_types):
        raise ValueError('A+ 规划结果格式异常：items 数量与模块数量不一致')

    normalized_items = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError('A+ 规划结果格式异常：单个模块项必须为对象')

        sort = item.get('sort')
        module_type = str(item.get('type', '')).strip()
        title = str(item.get('title', '')).strip()
        prompt = str(item.get('prompt', '')).strip()
        keywords = item.get('keywords')
        expected_type = expected_types[index - 1]

        if sort != index:
            raise ValueError(f'A+ 规划结果格式异常：第 {index} 项 sort 非法')
        if module_type != expected_type:
            raise ValueError(f'A+ 规划结果格式异常：第 {index} 项 type 必须为 {expected_type}')
        if not title:
            raise ValueError(f'A+ 规划结果格式异常：第 {index} 项 title 不能为空')
        if not prompt:
            raise ValueError(f'A+ 规划结果格式异常：第 {index} 项 prompt 不能为空')
        if not isinstance(keywords, list) or not (3 <= len(keywords) <= 6):
            raise ValueError(f'A+ 规划结果格式异常：第 {index} 项 keywords 数量必须为 3-6 个')

        normalized_keywords = [str(keyword).strip() for keyword in keywords if str(keyword).strip()]
        if len(normalized_keywords) < 3:
            raise ValueError(f'A+ 规划结果格式异常：第 {index} 项 keywords 不能为空')

        meta = APLUS_MODULE_META[selected_module_keys[index - 1]]
        normalized_items.append(
            {
                'sort': sort,
                'type': module_type,
                'title': title,
                'keywords': normalized_keywords,
                'prompt': prompt,
                'type_tag': meta.get('tag', 'Module'),
            }
        )

    return {
        'summary': summary,
        'module_count': len(expected_types),
        'items': normalized_items,
    }


def build_aplus_plan(platform: str, selling_text: str, selected_module_keys, image_payloads, country: str, text_type: str, image_size_ratio: str, selected_style=None, product_json=None):
    prompt = build_aplus_plan_prompt(platform, selling_text, selected_module_keys, country, text_type, image_size_ratio, selected_style, product_json)
    plan, _response_text = call_chat_json_with_repair(
        APLUS_PLAN_SYSTEM_PROMPT,
        build_multimodal_content(prompt, image_payloads),
        lambda text: parse_aplus_plan(text, selected_module_keys),
        'A+ 规划结果格式异常',
        temperature=0.3,
        timeout_seconds=90,
        repair_attempts=1,
    )
    return plan


def get_ark_client() -> OpenAI:
    return OpenAI(
        api_key=get_supabase_setting('ARK_API_KEY', get_env('ARK_API_KEY')),
        base_url=get_supabase_setting('ARK_BASE_URL', get_optional_env('ARK_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')).rstrip('/'),
    )


def get_mode2_client() -> OpenAI:
    return OpenAI(
        api_key=get_supabase_setting('MODE2_OPENAI_API_KEY', get_optional_env('MODE2_OPENAI_API_KEY', 'any-value')),
        base_url=get_supabase_setting('MODE2_OPENAI_BASE_URL', get_optional_env('MODE2_OPENAI_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')).rstrip('/'),
    )


def resolve_mode2_image_resolution(resolution: str) -> str:
    normalized_resolution = (resolution or '').strip() or get_supabase_setting('MODE2_DEFAULT_RESOLUTION', get_optional_env('MODE2_DEFAULT_RESOLUTION', '2k'))
    compact_resolution = normalized_resolution.lower().replace(' ', '')
    if compact_resolution in {'1k', '2k', '4k'}:
        return compact_resolution
    if compact_resolution in {'1024x1024', '1328x1328'}:
        return '1k'
    if compact_resolution in {'2048x2048', '2304x2304'}:
        return '2k'
    if compact_resolution in {'4096x4096'}:
        return '4k'
    return compact_resolution


def resolve_mode2_image_ratio(ratio: str) -> str:
    normalized_ratio = (ratio or '').strip() or get_supabase_setting('MODE2_DEFAULT_RATIO', get_optional_env('MODE2_DEFAULT_RATIO', '1:1'))
    return normalized_ratio or '1:1'


def resolve_mode2_image_size(ratio: str, resolution: str) -> str:
    normalized_resolution = (resolution or '').strip()
    if normalized_resolution:
        return normalized_resolution
    normalized_ratio = resolve_mode2_image_ratio(ratio)
    if normalized_ratio in IMAGE_SIZE_RATIO_MAP:
        return IMAGE_SIZE_RATIO_MAP[normalized_ratio]
    return get_supabase_setting('MODE2_DEFAULT_RESOLUTION', get_optional_env('MODE2_DEFAULT_RESOLUTION', '2048x2048'))


def get_mode2_retry_attempts() -> int:
    return max(get_supabase_setting_int('MODE2_RETRY_ATTEMPTS', get_optional_int_env('MODE2_RETRY_ATTEMPTS', 2)), 0)


def get_mode2_retry_delay_seconds() -> float:
    raw_value = get_supabase_setting('MODE2_RETRY_DELAY_SECONDS', get_optional_env('MODE2_RETRY_DELAY_SECONDS', '1.5'))
    try:
        return max(float(raw_value), 0.0)
    except ValueError:
        return 1.5


def get_mode3_retry_attempts() -> int:
    return max(get_supabase_setting_int('MODE3_RETRY_ATTEMPTS', get_optional_int_env('MODE3_RETRY_ATTEMPTS', 2)), 0)


def get_mode3_retry_delay_seconds() -> float:
    raw_value = get_supabase_setting('MODE3_RETRY_DELAY_SECONDS', get_optional_env('MODE3_RETRY_DELAY_SECONDS', '1.5'))
    try:
        return max(float(raw_value), 0.0)
    except ValueError:
        return 1.5


def get_mode3_parallel_workers() -> int:
    return max(get_supabase_setting_int('MODE3_PARALLEL_WORKERS', get_optional_int_env('MODE3_PARALLEL_WORKERS', 3)), 1)


def get_mode3_partial_retry_attempts() -> int:
    return max(get_supabase_setting_int('MODE3_PARTIAL_RETRY_ATTEMPTS', get_optional_int_env('MODE3_PARTIAL_RETRY_ATTEMPTS', 2)), 0)


def get_mode3_timeout_seconds() -> int:
    return max(get_supabase_setting_int('MODE3_TIMEOUT_SECONDS', get_optional_int_env('MODE3_TIMEOUT_SECONDS', 180)), 30)


def get_mode3_suite_batch_size() -> int:
    return max(get_supabase_setting_int('MODE3_SUITE_BATCH_SIZE', get_optional_int_env('MODE3_SUITE_BATCH_SIZE', 1)), 1)


def should_mode3_use_sequential_generation(target_count: int, image_payloads) -> bool:
    mode = str(get_supabase_setting('MODE3_SEQUENTIAL_GENERATION', get_optional_env('MODE3_SEQUENTIAL_GENERATION', 'auto')) or 'auto').strip().lower()
    if mode in {'on', 'true', '1', 'yes'}:
        return True
    if mode in {'off', 'false', '0', 'no'}:
        return False
    return int(target_count or 0) <= 1


def is_retryable_mode2_error(exc: Exception) -> bool:
    message = str(exc or '')
    retryable_fragments = (
        'Unexpected end of JSON input',
        'sessions.json',
        'JSONDecodeError',
        'Expecting value',
        'Read timed out',
        'Connection aborted',
        'Connection reset',
        'temporarily unavailable',
        '积分不足或没有相关权益',
        '没有相关权益',
        '请求jimeng失败',
    )
    if any(fragment.lower() in message.lower() for fragment in retryable_fragments):
        return True
    status_code = getattr(exc, 'status_code', None)
    return status_code in {408, 409, 425, 429, 500, 502, 503, 504}


def get_mode2_response_error(response) -> str:
    if response is None:
        return ''
    error_code = getattr(response, 'code', None)
    error_message = getattr(response, 'message', None)
    if isinstance(response, dict):
        error_code = response.get('code', error_code)
        error_message = response.get('message') or response.get('error') or error_message
    if error_message:
        return str(error_message)
    if error_code not in (None, 0):
        return f'错误码：{error_code}'
    return ''


class RetryableMode2ResponseError(RuntimeError):
    pass


def call_mode2_images_generate_with_retry(client: OpenAI, request_payload: dict):
    retry_attempts = get_mode2_retry_attempts()
    retry_delay_seconds = get_mode2_retry_delay_seconds()
    total_attempts = retry_attempts + 1
    last_exc = None
    for attempt_index in range(total_attempts):
        try:
            response = client.images.generate(**request_payload)
            response_error = get_mode2_response_error(response)
            if response_error and is_retryable_mode2_error(Exception(response_error)):
                raise RetryableMode2ResponseError(response_error)
            return response
        except Exception as exc:
            last_exc = exc
            should_retry = attempt_index < retry_attempts and is_retryable_mode2_error(exc)
            if not should_retry:
                raise
            wait_seconds = retry_delay_seconds * (attempt_index + 1)
            app.logger.warning('Mode2 image generation failed, retrying in %.2fs (%s/%s): %s', wait_seconds, attempt_index + 1, retry_attempts, exc)
            time.sleep(wait_seconds)
    raise last_exc


def get_mode2_sample_strength(sample_strength: str) -> float:
    raw_value = (sample_strength or '').strip() or get_supabase_setting('MODE2_DEFAULT_SAMPLE_STRENGTH', get_optional_env('MODE2_DEFAULT_SAMPLE_STRENGTH', '0.65'))
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError('sample_strength 必须为数字') from exc


def is_private_ip_address(hostname: str) -> bool:
    try:
        addresses = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError('参考图片链接域名解析失败') from exc

    for address_family, _, _, _, sockaddr in addresses:
        if address_family == socket.AF_INET:
            ip = ipaddress.ip_address(sockaddr[0])
        elif address_family == socket.AF_INET6:
            ip = ipaddress.ip_address(sockaddr[0])
        else:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            return True
    return False


def validate_mode2_remote_image_url(image_url: str) -> str:
    normalized_url = (image_url or '').strip()
    if not normalized_url:
        raise ValueError('参考图片链接不能为空')

    allowed_hosts = get_mode2_allowed_image_hosts()
    if not allowed_hosts:
        raise ValueError('MODE2_ALLOWED_IMAGE_HOSTS 未配置，暂不支持远程参考图片')

    parsed_url = urlparse(normalized_url)
    if parsed_url.scheme not in {'http', 'https'}:
        raise ValueError('参考图片链接仅支持 http 或 https')
    if not parsed_url.hostname:
        raise ValueError('参考图片链接缺少主机名')

    hostname = parsed_url.hostname.lower()
    if hostname not in allowed_hosts:
        raise ValueError('参考图片链接域名未被允许')

    return normalized_url



def build_remote_image_payload(image_url: str):
    normalized_url = validate_mode2_remote_image_url(image_url)
    response = requests.get(normalized_url, timeout=120, allow_redirects=False)
    if 300 <= response.status_code < 400:
        raise ValueError('参考图片链接不允许重定向')
    response.raise_for_status()
    content = response.content
    filename = Path(normalized_url.split('?', 1)[0]).name or 'reference-image'
    mime_type = sniff_image_mime_type(content)
    if not mime_type:
        header_mime_type = response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
        if header_mime_type in ALLOWED_IMAGE_MIME_TYPES:
            mime_type = header_mime_type
    if not mime_type:
        raise ValueError('参考图片链接不是有效的图片文件')
    if len(content) > UPLOAD_MAX_FILE_BYTES:
        raise ValueError(f'参考图片超过单张大小限制（{UPLOAD_MAX_FILE_BYTES // (1024 * 1024)}MB）')

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        extension = guess_extension(mime_type)
        filename = f'{Path(filename).stem or "reference-image"}{extension}'

    encoded = base64.b64encode(content).decode('utf-8')
    return {
        'filename': filename,
        'mime_type': mime_type,
        'bytes': content,
        'base64': encoded,
        'data_url': f'data:{mime_type};base64,{encoded}',
        'source_url': normalized_url,
    }




def normalize_generated_image_item(item):
    if hasattr(item, 'model_dump'):
        item = item.model_dump()
    elif hasattr(item, 'dict'):
        item = item.dict()

    if not isinstance(item, dict):
        raise ValueError('图像生成接口返回格式异常')
    return item


def pick_generated_image_item(response):
    data = getattr(response, 'data', None)
    if data is None and isinstance(response, dict):
        data = response.get('data')
    if not isinstance(data, list) or not data:
        error_code = getattr(response, 'code', None)
        error_message = getattr(response, 'message', None)
        if isinstance(response, dict):
            error_code = response.get('code', error_code)
            error_message = response.get('message') or response.get('error') or error_message
        if error_message:
            raise ValueError(f'图像生成接口返回错误：{error_message}')
        if error_code not in (None, 0):
            raise ValueError(f'图像生成接口返回错误码：{error_code}')
        raise ValueError('图像生成接口未返回图片数据')
    return normalize_generated_image_item(data[0])


def pick_generated_image_items(response, max_images: int = 1):
    data = getattr(response, 'data', None)
    if data is None and isinstance(response, dict):
        data = response.get('data')
    if not isinstance(data, list) or not data:
        return [pick_generated_image_item(response)]
    limit = max(1, int(max_images or 1))
    items = []
    for item in data[:limit]:
        try:
            normalized_item = normalize_generated_image_item(item)
            if normalized_item.get('b64_json') or normalized_item.get('url'):
                items.append(normalized_item)
        except ValueError:
            continue
    if not items:
        return [pick_generated_image_item(response)]
    return items


def extract_generated_image_from_content(content):
    if isinstance(content, str):
        data_url_match = re.search(r'data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+', content)
        if data_url_match:
            data_url = re.sub(r'\s+', '', data_url_match.group(0))
            return {'b64_json': data_url.split(',', 1)[1]}
        base64_match = re.search(r'(?<![A-Za-z0-9+/=])([A-Za-z0-9+/]{800,}={0,2})(?![A-Za-z0-9+/=])', content)
        if base64_match:
            return {'b64_json': base64_match.group(1)}
        image_url_match = re.search(r'https?://[^\s\]})"\']+\.(?:png|jpe?g|webp|gif)(?:\?[^\s\]})"\']*)?', content, re.IGNORECASE)
        if image_url_match:
            return {'url': image_url_match.group(0)}
        return None

    if isinstance(content, list):
        for part in content:
            if hasattr(part, 'model_dump'):
                part = part.model_dump()
            elif hasattr(part, 'dict'):
                part = part.dict()
            if not isinstance(part, dict):
                continue
            if part.get('type') in {'image_url', 'input_image'}:
                image_url = part.get('image_url') or part.get('url')
                if isinstance(image_url, dict):
                    image_url = image_url.get('url')
                if isinstance(image_url, str) and image_url.startswith('data:image/') and ',' in image_url:
                    return {'b64_json': image_url.split(',', 1)[1]}
                if isinstance(image_url, str) and image_url:
                    return {'url': image_url}
            if part.get('type') in {'image', 'output_image'}:
                image_data = part.get('image') or part.get('data') or part.get('b64_json')
                if isinstance(image_data, dict):
                    image_data = image_data.get('b64_json') or image_data.get('data') or image_data.get('url')
                if isinstance(image_data, str) and image_data.startswith('data:image/') and ',' in image_data:
                    return {'b64_json': image_data.split(',', 1)[1]}
                if isinstance(image_data, str) and image_data.startswith(('http://', 'https://')):
                    return {'url': image_data}
                if isinstance(image_data, str) and image_data:
                    return {'b64_json': image_data}
            nested = extract_generated_image_from_content(part.get('text') or part.get('content'))
            if nested:
                return nested
    return None


def normalize_chat_completion_image_response(response):
    if hasattr(response, 'model_dump'):
        response_dict = response.model_dump()
    elif hasattr(response, 'dict'):
        response_dict = response.dict()
    elif isinstance(response, dict):
        response_dict = response
    else:
        return response

    choices = response_dict.get('choices') if isinstance(response_dict, dict) else None
    if not isinstance(choices, list) or not choices:
        return response
    message = (choices[0] or {}).get('message') or {}
    generated_item = extract_generated_image_from_content(message.get('content'))
    if generated_item:
        return {'data': [generated_item]}
    return response


def call_mode3_single_image(prompt: str, image_payloads, image_size_ratio: str = '', text_type: str = '', country: str = '', product_json=None, image_type: str = '', plan_item=None, all_plan_types=None):
    generated_item, _model = call_mode3_image_edit(get_mode3_client(), prompt, image_payloads or [create_mode3_blank_canvas_payload(image_size_ratio)], image_size_ratio)
    return generated_item


def call_mode3_images_parallel_with_partial_retry(prompt: str, image_payloads, max_images: int, image_size_ratio: str = '', text_type: str = '', country: str = '', product_json=None, image_type: str = '', plan_item=None, all_plan_types=None):
    target_count = max(1, int(max_images or 1))
    enriched_prompt = build_enriched_image_prompt(prompt, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types)
    if target_count == 1:
        return [call_mode3_single_image(enriched_prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types)]

    if should_mode3_use_sequential_generation(target_count, image_payloads):
        generated_items = []
        retry_attempts = get_mode3_retry_attempts()
        retry_delay_seconds = get_mode3_retry_delay_seconds()
        for index in range(target_count):
            last_exc = None
            for attempt in range(retry_attempts + 1):
                try:
                    item = call_mode3_single_image(enriched_prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types)
                    generated_items.append(item)
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < retry_attempts:
                        time.sleep(retry_delay_seconds * (attempt + 1))
            if last_exc and len(generated_items) <= index:
                raise last_exc
        return generated_items[:target_count]

    workers = min(target_count, get_mode3_parallel_workers())
    partial_retry_attempts = get_mode3_partial_retry_attempts()
    retry_delay_seconds = get_mode3_retry_delay_seconds()
    generated_items = []
    failures = []

    def run_one(global_index: int):
        return call_mode3_single_image(enriched_prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types)

    for attempt_index in range(partial_retry_attempts + 1):
        missing_count = target_count - len(generated_items)
        if missing_count <= 0:
            break
        failures = []
        batch_workers = min(missing_count, workers)
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_workers) as executor:
            futures = [executor.submit(run_one, len(generated_items) + index + 1) for index in range(missing_count)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    generated_items.append(future.result())
                except Exception as exc:
                    failures.append(exc)
        missing_count = target_count - len(generated_items)
        if missing_count > 0 and attempt_index < partial_retry_attempts:
            app.logger.warning('Mode3 partial generation missing %s/%s images, retrying failed parts in %.2fs (%s/%s): %s', missing_count, target_count, retry_delay_seconds * (attempt_index + 1), attempt_index + 1, partial_retry_attempts, '; '.join(str(exc) for exc in failures[:3]))
            time.sleep(retry_delay_seconds * (attempt_index + 1))

    if len(generated_items) < target_count:
        error_text = '; '.join(str(exc) for exc in failures[:3]) or '部分图片生成失败'
        raise ValueError(f'mode3 部分图片生成失败，已成功 {len(generated_items)}/{target_count}：{error_text}')
    return generated_items[:target_count]


def call_mode2_image_edit(client: OpenAI, prompt: str, image_payloads, ratio: str, resolution: str, sample_strength: str):
    model = get_supabase_setting('MODE2_IMAGE_EDIT_MODEL', get_optional_env('MODE2_IMAGE_EDIT_MODEL', 'doubao-seedream-5-0-260128'))
    request_payload = {
        'model': model,
        'prompt': prompt,
        'response_format': 'url',
        'extra_body': {
            'image': [image_payload['data_url'] for image_payload in image_payloads],
            'sample_strength': get_mode2_sample_strength(sample_strength),
            'ratio': resolve_mode2_image_ratio(ratio),
            'resolution': resolve_mode2_image_resolution(resolution),
        },
    }
    request_extra_body = dict(request_payload['extra_body'])
    request_extra_body['image_count'] = len(image_payloads)
    app.logger.warning('Mode2 image edit request extra_body image_count=%s ratio=%s resolution=%s', request_extra_body['image_count'], request_extra_body['ratio'], request_extra_body['resolution'])
    response = call_mode2_images_generate_with_retry(client, request_payload)
    return pick_generated_image_item(response), model


def call_mode2_text2image(client: OpenAI, prompt: str, ratio: str, resolution: str):
    model = get_supabase_setting('MODE2_TEXT2IMAGE_MODEL', get_optional_env('MODE2_TEXT2IMAGE_MODEL', 'doubao-seedream-5-0-260128'))
    request_payload = {
        'model': model,
        'prompt': prompt,
        'response_format': 'url',
        'extra_body': {
            'ratio': resolve_mode2_image_ratio(ratio),
            'resolution': resolve_mode2_image_resolution(resolution),
        },
    }
    app.logger.warning('Mode2 text2image request ratio=%s resolution=%s model=%s', request_payload['extra_body']['ratio'], request_payload['extra_body']['resolution'], model)
    response = call_mode2_images_generate_with_retry(client, request_payload)
    return pick_generated_image_item(response), model


def get_mode3_api_key() -> str:
    api_key = get_supabase_setting('MODE3_OPENAI_API_KEY', get_optional_env('MODE3_OPENAI_API_KEY', ''))
    if not api_key:
        api_key = get_supabase_setting('OPENAI_API_KEY', get_optional_env('OPENAI_API_KEY', ''))
    return api_key


def get_mode3_base_url() -> str:
    return get_supabase_setting('MODE3_OPENAI_BASE_URL', get_optional_env('MODE3_OPENAI_BASE_URL', 'https://code.ciyuanapi.xyz/v1')).rstrip('/')


def get_mode3_image_edit_size(image_size_ratio: str = '') -> str:
    configured_size = get_supabase_setting('MODE3_IMAGE_EDIT_SIZE', get_optional_env('MODE3_IMAGE_EDIT_SIZE', '2048x2048')).strip()
    if configured_size:
        return configured_size
    return '2048x2048'


def create_mode3_blank_canvas_payload(image_size_ratio: str = ''):
    size = get_mode3_image_edit_size(image_size_ratio)
    width, height = 2048, 2048
    match = re.fullmatch(r'(\d+)x(\d+)', size)
    if match:
        width, height = int(match.group(1)), int(match.group(2))
    image = Image.new('RGB', (width, height), (255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    image_bytes = buffer.getvalue()
    return {
        'filename': f'mode3-blank-{width}x{height}.png',
        'mime_type': 'image/png',
        'bytes': image_bytes,
        'data_url': f'data:image/png;base64,{base64.b64encode(image_bytes).decode("ascii")}',
    }


def get_mode3_client() -> OpenAI:
    return OpenAI(
        api_key=get_mode3_api_key(),
        base_url=get_mode3_base_url(),
    )




def call_mode3_text2image(client: OpenAI, prompt: str):
    model = get_supabase_setting('MODE3_IMAGE_MODEL', get_optional_env('MODE3_IMAGE_MODEL', 'gpt-image-2'))
    blank_payload = create_mode3_blank_canvas_payload()
    generated_item, _model = call_mode3_image_edit(client, prompt, [blank_payload], get_mode3_image_edit_size())
    return generated_item, model


def build_mode1_reference_anchor_prompt(reference_count: int) -> str:
    return (
        f'参考图执行约束（按 mode1 当前图生图模板执行，已接收 {max(reference_count or 0, 0)} 张参考图）：\n'
        '- 以下 multipart image 文件中的图片必须作为商品主体唯一锚点，不是风格灵感图，也不是可替换示例图。\n'
        '- 若提供了参考商品图，必须把参考图视为主体锚点，优先复用其主体外观、颜色关系、材质质感、结构比例、边缘轮廓、关键部件、logo/品牌位与稳定细节。\n'
        '- 产品一致性是最高优先级，高于场景变化、版式变化、卖点表达和同套图差异；如果差异化要求与产品一致性冲突，必须优先保持商品主体一致。\n'
        '- 若提供了不可变商品特征，必须将其中的主体品类、核心主体、颜色体系、材质、轮廓、结构、关键部件、品牌标识、logo位置、稳定细节、must_keep、must_not_change、forbidden_changes 与 consistency_rules 视为最高优先级约束。\n'
        '- 生成时只能改变背景、道具、光线、构图、文字版式、人物动作和非主体装饰；不得重新设计商品，不得替换商品品类，不得改变商品颜色体系、材质质感、结构比例、关键部件组合、logo/品牌位置或包装识别。\n'
        '- selling_points 只能用于补充文案重点、信息层级与卖点表达，不得推动商品变成其他颜色、其他材质、其他结构、其他部件方案或其他品牌观感。\n'
        '- 允许变化的仅限背景、道具、光线、构图、文案排版与非主体装饰；禁止把商品改成另一种外观、另一种材质表现、另一种结构、另一种颜色体系、另一种关键部件组合或另一种品牌识别。\n'
        '- 不要把场景氛围、背景纯度、人物气质或镜头语言误当作商品主体特征；它们只能作为从属变化，不能覆盖主体锁定要求。\n'
        '- 如果参考图商品带有文字、logo、印花、包装标识或品牌图案，这些内容属于商品主体外观，必须尽量保持位置、大小关系、颜色关系、朝向和识别感；不要新增、替换、重写或随机改造商品本身已有标识。\n'
        '- 当前任务必须基于参考图做图生图延展，而不是根据场景 prompt 重新想象一个新商品。\n\n'
    )



def call_mode3_image_edit(client: OpenAI, prompt: str, image_payloads, image_size_ratio: str = ''):
    model = get_supabase_setting('MODE3_IMAGE_MODEL', get_optional_env('MODE3_IMAGE_MODEL', 'gpt-image-2'))
    size = get_mode3_image_edit_size(image_size_ratio)
    watermark = get_supabase_setting_bool('MODE3_IMAGE_WATERMARK', get_optional_bool_env('MODE3_IMAGE_WATERMARK', False))
    reference_instruction = build_mode1_reference_anchor_prompt(len(image_payloads or []))
    base_url = get_mode3_base_url()
    api_key = get_mode3_api_key()
    if not api_key:
        raise ValueError('mode3 图生图缺少 MODE3_OPENAI_API_KEY')
    request_url = f'{base_url}/images/edits'
    data = {
        'model': model,
        'prompt': reference_instruction + prompt,
        'size': size,
        'response_format': 'url',
    }
    quality = get_supabase_setting('MODE3_IMAGE_QUALITY', get_optional_env('MODE3_IMAGE_QUALITY', '')).strip()
    if quality:
        data['quality'] = quality
    if watermark:
        data['watermark'] = 'true'
    files = []
    for index, payload in enumerate(image_payloads or [], start=1):
        filename = str(payload.get('filename') or f'image-{index}.png')
        mime_type = str(payload.get('mime_type') or 'image/png')
        image_bytes = payload.get('bytes')
        if not isinstance(image_bytes, (bytes, bytearray)) or not image_bytes:
            raise ValueError(f'mode3 图生图参考图 {filename} 内容为空')
        files.append(('image', (filename, bytes(image_bytes), mime_type)))
    app.logger.warning(
        'Mode3 image edit request via images/edits multipart model=%s size=%s reference_count=%s base_url=%s template=mode1_reference_anchor',
        model,
        size,
        len(files),
        base_url,
    )
    response = requests.post(
        request_url,
        headers={'Authorization': f'Bearer {api_key}'},
        data=data,
        files=files,
        timeout=get_mode3_timeout_seconds(),
    )
    if response.status_code >= 400:
        raise ValueError(f'mode3 图生图接口错误 {response.status_code}：{response.text[:500]}')
    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError('mode3 图生图接口返回了无效 JSON') from exc
    return pick_generated_image_item(payload), model


def call_app_mode_image_generation(client: OpenAI, prompt: str, image_payloads, image_size_ratio: str, text_type: str, country: str, product_json=None, image_type: str = '', plan_item=None, all_plan_types=None, max_images: int = 1):
    app_mode = get_app_mode()
    if app_mode == 'mode2':
        mode2_client = get_mode2_client()
        if image_payloads:
            generated_item, _model = call_mode2_image_edit(
                mode2_client,
                prompt,
                image_payloads,
                image_size_ratio,
                '',
                '',
            )
        else:
            generated_item, _model = call_mode2_text2image(
                mode2_client,
                prompt,
                image_size_ratio,
                '',
            )
        return [generated_item]

    if app_mode == 'mode3':
        return call_mode3_images_parallel_with_partial_retry(
            prompt,
            image_payloads,
            max_images,
            image_size_ratio,
            text_type,
            country,
            product_json,
            image_type,
            plan_item,
            all_plan_types,
        )

    return call_image_generation(
        client,
        prompt,
        image_payloads,
        image_size_ratio,
        text_type,
        country,
        product_json,
        image_type,
        plan_item,
        all_plan_types,
        max_images=max_images,
    )


def build_mode2_success_response(task_id: str, mode: str, prompt: str, model: str, generated_item: dict):
    image_bytes, mime_type = decode_generated_image(generated_item)
    download_name, relative_path, image_url = save_generated_image(task_id, 1, mode, image_bytes, mime_type)
    return {
        'success': True,
        'task_id': task_id,
        'image_url': image_url,
        'image_path': relative_path,
        'download_name': download_name,
        'prompt': prompt,
        'model': model,
        'mode': mode,
    }


def pick_image_data_entry(data):
    if not isinstance(data, list) or not data:
        raise ValueError('图像生成接口未返回图片数据')
    first_item = data[0]
    if not isinstance(first_item, dict):
        raise ValueError('图像生成接口返回格式异常')
    return first_item


def decode_generated_image(item: dict):
    if item.get('url'):
        response = requests.get(item['url'], timeout=120)
        response.raise_for_status()
        image_bytes = response.content
        header_mime_type = response.headers.get('Content-Type', 'image/png').split(';', 1)[0].strip()
        detected_mime_type = sniff_image_mime_type(image_bytes)
        return image_bytes, detected_mime_type or header_mime_type or 'image/png'

    if item.get('b64_json'):
        image_bytes = base64.b64decode(item['b64_json'])
        detected_mime_type = sniff_image_mime_type(image_bytes)
        return image_bytes, detected_mime_type or 'image/png'

    raise ValueError('图像生成接口未返回可用图片内容')



def collect_generated_images(response):
    data = getattr(response, 'data', None)
    if data is None and isinstance(response, dict):
        data = response.get('data')
    if not isinstance(data, list) or not data:
        raise ValueError('图像生成接口未返回图片数据')
    return [normalize_generated_image_item(item) for item in data]


def save_generated_image(task_id: str, sort: int, image_type: str, image_bytes: bytes, mime_type: str):
    cleanup_generated_suites(active_task_id=task_id)
    output_dir = GENERATED_SUITES_DIR / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    extension = guess_extension(mime_type)
    filename = f'{sort:02d}-{sanitize_filename_part(image_type, "image")}{extension}'
    output_path = output_dir / filename
    output_path.write_bytes(image_bytes)
    relative_path = output_path.relative_to(GENERATED_SUITES_DIR).as_posix()
    return filename, relative_path, f'/generated/{relative_path}'


def save_reference_image(task_id: str, sort: int, filename: str, image_bytes: bytes, mime_type: str):
    cleanup_generated_suites(active_task_id=task_id)
    output_dir = GENERATED_SUITES_DIR / task_id / 'references'
    output_dir.mkdir(parents=True, exist_ok=True)
    extension = guess_extension(mime_type)
    source_stem = Path(filename or 'reference').stem
    safe_stem = sanitize_filename_part(source_stem, f'reference-{sort:02d}')
    output_name = f'{sort:02d}-{safe_stem}{extension}'
    output_path = output_dir / output_name
    output_path.write_bytes(image_bytes)
    relative_path = output_path.relative_to(GENERATED_SUITES_DIR).as_posix()
    return output_name, relative_path, f'/generated/{relative_path}'


def build_reference_images(task_id: str, image_payloads, source: str = 'product', start_sort: int = 1):
    reference_images = []
    source_meta = {
        'product': {'type': '商品原图', 'type_tag': 'Prod', 'reference_source': 'product'},
        'reference': {'type': '参考图', 'type_tag': 'Ref', 'reference_source': 'reference'},
        'fashion_reference': {'type': '穿搭参考图', 'type_tag': 'Look', 'reference_source': 'fashion_reference'},
    }
    meta = source_meta.get(source, source_meta['product'])

    for offset, payload in enumerate(image_payloads):
        sort = start_sort + offset
        download_name, relative_path, image_url = save_reference_image(
            task_id,
            sort,
            payload.get('filename', ''),
            payload.get('bytes', b''),
            payload.get('mime_type', 'image/png'),
        )
        original_name = Path(payload.get('filename') or f'{meta["type"]} {sort}').stem.strip()
        title = original_name or f'{meta["type"]} {sort}'
        reference_images.append(
            {
                'sort': sort,
                'kind': 'reference',
                'type': meta['type'],
                'type_tag': meta['type_tag'],
                'reference_source': meta['reference_source'],
                'title': title,
                'keywords': [],
                'image_url': image_url,
                'image_path': relative_path,
                'download_name': download_name,
            }
        )

    return reference_images


def build_plan_control_prompt(item: dict, all_types) -> str:
    module = str(item.get('module', '')).strip() or 'scene_narrative'
    story_role = str(item.get('story_role', '')).strip() or '未指定故事节点'
    decision_task = str(item.get('decision_task', '')).strip() or '未指定决策任务'
    info_density = str(item.get('info_density', '')).strip() or 'medium'
    scene_required = bool(item.get('scene_required'))
    scene_type = str(item.get('scene_type', '')).strip() or '未指定场景'
    camera_shot = str(item.get('camera_shot', '')).strip() or '未指定景别'
    subject_angle = str(item.get('subject_angle', '')).strip() or '未指定角度'
    human_presence = str(item.get('human_presence', '')).strip() or 'none'
    action_type = str(item.get('action_type', '')).strip() or '静态陈列'
    layout_anchor = str(item.get('layout_anchor', '')).strip() or '主体居中放大'
    layout_style = str(item.get('layout_style', '')).strip() or '单图分层'
    font_style = str(item.get('font_style', '')).strip() or '清晰无衬线'
    color_scheme = str(item.get('color_scheme', '')).strip() or '低饱和同色系'
    decor_elements = [str(value).strip() for value in (item.get('decor_elements') or []) if str(value).strip()]
    must_differ_from = [
        str(name).strip()
        for name in (item.get('must_differ_from') or [])
        if str(name).strip() and str(name).strip() in all_types and str(name).strip() != item.get('type')
    ]
    module_map = {
        'opening_narrative': '开场叙事模块',
        'scene_narrative': '场景化叙事模块',
        'value_visualization': '价值可视化叙事模块',
        'trust_narrative': '信任叙事模块',
    }
    info_density_map = {
        'low': '低信息密度，文案与元素必须克制，优先保证一眼理解。',
        'medium': '中等信息密度，允许 1-2 个重点信息层级，但仍需保持清晰阅读路径。',
        'high': '高信息密度，但仍需模块化组织信息，避免杂乱堆砌。',
    }
    human_presence_map = {
        'none': '本图不应出现人物或手部，只通过商品自身展示完成表达。',
        'hand-only': '本图仅允许出现手部或局部操作关系，禁止出现完整人物主体。',
        'model': '本图允许出现人物/模特，但人物只能服务商品表达，不能抢夺主体。',
    }
    scene_rule = '必须使用明确场景，且场景类型需与下述规划一致。' if scene_required else '优先采用非场景或弱场景表达，不要强塞生活化环境。'
    differ_rule = '、'.join(must_differ_from) if must_differ_from else '无指定前序图'
    decor_rule = '、'.join(decor_elements) if decor_elements else '无额外装饰元素'
    return '\n'.join(
        [
            '结构化叙事与差异控制：',
            f'- module：{module}（{module_map.get(module, "场景化叙事模块")}）。',
            f'- story_role：{story_role}。',
            f'- decision_task：{decision_task}。',
            f'- info_density：{info_density}。{info_density_map.get(info_density, info_density_map["medium"])}',
            f'- scene_required：{"true" if scene_required else "false"}。{scene_rule}',
            f'- scene_type：{scene_type}。',
            f'- camera_shot：{camera_shot}。',
            f'- subject_angle：{subject_angle}。',
            f'- human_presence：{human_presence}。{human_presence_map.get(human_presence, human_presence_map["none"])}',
            f'- action_type：{action_type}。',
            f'- layout_anchor：{layout_anchor}。',
            f'- layout_style：{layout_style}。必须采用明确的真实电商版式模板语言，不可退化成通用大字压图。',
            f'- font_style：{font_style}。必须与其他图拉开字体气质差异，不可整套图只用同一种粗黑字。',
            f'- color_scheme：{color_scheme}。必须与当前图的功能和产品气质匹配，并与指定前序图形成色彩组织差异。',
            f'- decor_elements：{decor_rule}。可使用线框、细分隔线、图标、吊牌、角标、编号标签、数据徽章等，但必须克制服务主体。',
            f'- must_differ_from：{differ_rule}。必须与这些图在场景类型、景别、主体朝向、人物参与方式、动作关系、构图骨架、版式结构、字体风格、色彩组织中至少拉开三项差异。',
            '- 每张图必须使用不同的排版逻辑、不同的字体样式、不同的配色方案，禁止重复模板化设计。',
            '- 必须显式参考真实电商详情页常见版式语言，例如单图分层、分栏线框、竖排多列、环绕标注、边角背书、参数信息板、对比双栏、吊牌角标、图标矩阵。',
            '- 上述结构化字段优先级高于自由描述；若自由 prompt 与结构化字段冲突，以结构化字段为准。',
        ]
    )


def build_enriched_image_prompt(prompt: str, image_size_ratio: str, text_type: str, country: str, product_json=None, image_type: str = '', plan_item=None, all_plan_types=None) -> str:
    normalized_product_json = normalize_product_json(product_json) if product_json else None
    product_json_text = build_product_json_prompt_text(normalized_product_json)
    must_keep = '；'.join((normalized_product_json or {}).get('must_keep') or []) or '未单独提取'
    must_not_change = '；'.join((normalized_product_json or {}).get('must_not_change') or []) or '未单独提取'
    forbidden_changes = '；'.join((normalized_product_json or {}).get('forbidden_changes') or []) or '未单独提取'
    selling_points = '；'.join((normalized_product_json or {}).get('selling_points') or []) or '未单独提取'
    image_type = str(image_type or '').strip()
    plan_control_prompt = ''
    if isinstance(plan_item, dict):
        plan_control_prompt = build_plan_control_prompt(plan_item, all_plan_types or [])
    type_specific_rules = ''
    if image_type == '首屏主视觉图':
        type_specific_rules = (
            '- 当前图类型：首屏主视觉图。必须使用有场景的主视觉画面，并采用“大场景 + 单主体强聚焦”构图：场景需要真实存在且能承接商品气质，但商品主体仍必须是绝对视觉中心；禁止做成纯白底棚拍、纯色背景孤立陈列或空场静物图。\n'
            '- 优先保留完整环境信息、空间纵深或前后景层次，让用户一眼感知使用语境，但场景元素不得比商品更抢眼；禁止与核心卖点图、使用场景图复用同一站姿、同一手持关系、同一商品朝向、同一景别或同一构图骨架。\n'
        )
    elif image_type == '核心卖点图':
        type_specific_rules = (
            '- 当前图类型：核心卖点图。必须使用有场景的画面，并围绕一个核心卖点采用“场景内功能动作 / 局部卖点展示”结构重构视角；可采用场景中的局部放大、半身持握、俯拍陈列、剖面感或结构展示，但禁止继续沿用首屏主视觉图的同姿势、同朝向、同主体位置、同镜头距离。\n'
            '- 该图的场景必须直接服务卖点表达，例如收纳、清洁、使用前后、桌面操作、随身携带、厨房备餐等；优先出现操作关系、功能触发点、局部放大区域或利益点对应动作，禁止仅把首图换个背景后继续展示整件商品。即使保留人物，也必须让人物动作、身体朝向、持握关系、商品位置至少两项明显变化。\n'
        )
    elif image_type == '使用场景图':
        type_specific_rules = (
            '- 当前图类型：使用场景图。必须表现商品正在被真实使用，而不是静态拿着展示；优先采用操作中、接触中、桌面使用中、收纳取用中等动态关系。\n'
            '- 这张图禁止复用首屏主视觉图或核心卖点图的站位、朝向、裁切、商品位置与版式骨架，人物姿势、商品相对位置、镜头距离必须明显不同。\n'
        )
    elif image_type == 'fashion-look':
        type_specific_rules = (
            '- 当前图类型：服饰穿搭图。最终画面必须是“清晰可见的真人模特穿着商品”的完整穿搭成图；禁止只出衣服、禁止平铺挂拍、禁止无头模特、禁止裁切到看不出人物身份、禁止把商品单独陈列当成最终结果。\n'
            '- 若同时提供商品图与模特参考图，必须优先使用商品图锁定服饰主体，使用模特参考图锁定最终出镜人物身份、脸部、发型、肤感、体态比例与整体气质；禁止替换为其他人物，禁止混入其他模特特征。\n'
            '- 该图是服饰最终成图，不允许生成任何新增可见文字元素：标题、卖点文案、说明字、logo 文案、水印、字幕、角标、标签字样、吊牌字样、排版字、海报字都禁止出现。\n'
            '- 若商品本体原始设计自带品牌标识、logo、印花文字或标签细节，只能按商品图原样保留，不得新增、改写、放大或替换。\n'
        )
    text_layout_control_prompt = ''
    if (text_type or '').strip() == '无文字':
        text_layout_control_prompt = (
            '- 本张图为无文字模式：禁止生成任何标题、副标题、卖点文案、说明文字、标签字、角标字、参数字、水印字或海报字；只允许保留商品原本自带且与参考图一致的品牌标识、logo 或印花文字。\n'
        )
    else:
        text_layout_control_prompt = (
            '- 你同时承担全品类电商详情页专属文字版式规划职责：必须为当前画面设计符合电商行业规范、适配当前模块功能、贴合产品调性的专属文字版式，拒绝模板化排版。\n'
            '- 每张图片必须使用不同的排版逻辑、不同的字体样式、不同的配色方案，禁止重复模板化设计；至少要在信息骨架、字体气质、色彩组织三项中与同套图其他图片拉开两项以上差异。\n'
            '- 严禁使用“底部居中粗白字+黑描边”的默认排版，不得整页堆砌单一粗黑大字；整体风格可以统一，但每张图的标题位置、信息骨架、标签组织和留白关系都必须根据模块职责变化。\n'
            '- 必须直接参考真实电商详情页常见版式语言来组织信息，例如单图分层、分栏线框、竖排多列、环绕标注、边角背书、参数信息板、对比双栏、吊牌角标、图标矩阵，不要只生成普通居中压字排版。\n'
            '- 文字/标签配色必须与商品主色调、背景氛围和整体画面色调呼应，优先使用低饱和、克制、干净的配色；同时允许使用同色系深浅、低对比撞色、微渐变、浅底深字、深底浅字等方案形成变化，但禁止刺眼高饱和色、杂乱彩色字、强烈撞色字或与商品不匹配的文字配色。\n'
            '- 字体气质必须匹配产品风格：简约/科技风优先无衬线，温柔/软萌风优先圆润软黑体或柔和手写感，高端/质感风优先纤细衬线或精致细体；同时不同页面要主动拉开字体样式差异，禁止整套图只使用同一种生硬粗黑体、廉价海报字或老旧土味字体。\n'
            '- 必须清晰区分主标题、副标题、辅助说明至少两级以上层次，字号、字重、字距和留白要有明显差异，确保视觉焦点明确，禁止所有文字同样大小、同样粗细、同样位置逻辑。\n'
            '- 文字排版必须避开商品主体、模特面部、关键部件、核心细节和主要操作区域，优先放在画面空白区、结构边缘区或场景留白区，禁止大面积遮挡主体。\n'
            '- 允许克制地搭配线框、细分隔线、图标、吊牌、角标、编号标签、数据徽章等装饰元素，增强真实电商版式质感，但这些元素只能服务信息识别，不得抢夺商品主体。\n'
            '- 不同功能模块要使用不同的电商通用版式语言：主视觉图偏极简记忆点，场景图偏陪伴式信息，价值图偏结构化说明，信任图偏规整可信的信息板；保持统一风格但版式绝不重复。\n'
            '- 所有生成文字必须清晰可辨，严格规避文字乱码、变形、模糊、重影、笔画断裂、字距失衡、花哨特效字、水印感文字与脏乱排版。\n'
        )
    return (
        f'{prompt}\n\n'
        f'当前图类型：{image_type or "未指定"}\n\n'
        f'不可变商品特征：\n{product_json_text}\n\n'
        f'{plan_control_prompt}\n\n'
        f'文字版式执行约束：\n{text_layout_control_prompt}\n'
        f'额外执行约束：\n'
        f'- 图片尺寸比例参考：{image_size_ratio or "1:1"}\n'
        f'- 说明文字种类：{text_type or "中文"}\n'
        f'- 国家参考：{country or "中国"}\n'
        f'- 必须保留（must_keep）：{must_keep}\n'
        f'- 绝对不可改变（must_not_change）：{must_not_change}\n'
        f'- 明确禁止出现（forbidden_changes）：{forbidden_changes}\n'
        f'- 可表达卖点（selling_points）：{selling_points}\n'
        f'- 产品一致性是最高优先级，高于场景变化、版式变化、卖点表达和同套图差异；如果差异化要求与产品一致性冲突，必须优先保持商品主体一致。\n'
        f'- 若提供了不可变商品特征，必须将其中的主体品类、核心主体、颜色体系、材质、轮廓、结构、关键部件、品牌标识、logo位置、稳定细节、must_keep、must_not_change、forbidden_changes 与 consistency_rules 视为最高优先级约束。\n'
        f'- 若提供了参考商品图，必须把参考图视为主体锚点，优先复用其主体外观、颜色关系、材质质感、结构比例、边缘轮廓、关键部件、logo/品牌位与稳定细节。\n'
        f'- 生成时只能改变背景、道具、光线、构图、文字版式、人物动作和非主体装饰；不得重新设计商品，不得替换商品品类，不得改变商品颜色体系、材质质感、结构比例、关键部件组合、logo/品牌位置或包装识别。\n'
        f'- selling_points 只能用于补充文案重点、信息层级与卖点表达，不得推动商品变成其他颜色、其他材质、其他结构、其他部件方案或其他品牌观感。\n'
        f'- 允许变化的仅限背景、道具、光线、构图、文案排版与非主体装饰；禁止把商品改成另一种外观、另一种材质表现、另一种结构、另一种颜色体系、另一种关键部件组合或另一种品牌识别。\n'
        f'- 不要把场景氛围、背景纯度、人物气质或镜头语言误当作商品主体特征；它们只能作为从属变化，不能覆盖主体锁定要求。\n'
        f'- 本张图必须与同套图中的其他图形成明显展示差异，不能复用相同的商品朝向、相同的人物动作、相同的持握方式、相同的商品摆位、相同的景别或相同的版式骨架。\n'
        f'- 若本张图包含人物、手部或模特，它们只能服务当前图类型表达，且应与其他图的人物姿势、身体朝向、商品相对位置明显不同。\n'
        f'- 若本张图不包含人物，则必须通过商品朝向、远近景切换、局部特写、平铺/立放/悬浮/包装展开等摆放方式变化，主动与其他图区分。\n'
        f'- 主图、卖点图、细节图、参数图、售后图至少应在展示角度、构图重心与商品摆法上明显不同，禁止做成同一参考姿势的连续换背景或加字版本。\n'
        f'- 首屏主视觉图、核心卖点图、使用场景图三张图尤其要避免同姿势复用；宁可牺牲部分背景统一感，也必须优先拉开商品朝向、人物动作、手持关系、远近景和商品在画面中的位置差异。\n'
        f'{type_specific_rules}'
        f'- 若卖点、生活方式、消费场景、节日氛围或合规表达与地区有关，优先按国家参考进行画面设计与文案表达。'
    )


def call_image_generation(client: OpenAI, prompt: str, image_payloads, image_size_ratio: str, text_type: str, country: str, product_json=None, image_type: str = '', plan_item=None, all_plan_types=None, max_images: int = 1):
    model = get_supabase_setting('ARK_IMAGE_MODEL', get_optional_env('ARK_IMAGE_MODEL', 'doubao-seedream-5-0-260128'))
    size = resolve_image_size(image_size_ratio)
    quality = get_supabase_setting('ARK_IMAGE_QUALITY', get_optional_env('ARK_IMAGE_QUALITY', ''))
    watermark = get_supabase_setting_bool('ARK_IMAGE_WATERMARK', get_optional_bool_env('ARK_IMAGE_WATERMARK', False))
    sequential_mode = get_supabase_setting('ARK_SEQUENTIAL_IMAGE_GENERATION', get_optional_env('ARK_SEQUENTIAL_IMAGE_GENERATION', 'auto'))
    sequential_max_images = get_supabase_setting_int('ARK_SEQUENTIAL_MAX_IMAGES', get_optional_int_env('ARK_SEQUENTIAL_MAX_IMAGES', 1))
    enriched_prompt = build_enriched_image_prompt(prompt, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types)
    request_payload = {
        'model': model,
        'prompt': enriched_prompt,
        'size': size,
        'response_format': 'b64_json',
    }

    extra_body = {
        'watermark': watermark,
        'sequential_image_generation': sequential_mode,
        'sequential_image_generation_options': {
            'max_images': max(1, min(max_images, sequential_max_images)),
        },
    }
    if image_payloads:
        extra_body['image'] = [payload['data_url'] for payload in image_payloads]
    if quality:
        extra_body['quality'] = quality
    request_payload['extra_body'] = extra_body
    app.logger.warning('ARK image request extra_body: %s', json.dumps(extra_body, ensure_ascii=False))

    response = client.images.generate(**request_payload)
    return collect_generated_images(response)


def generate_suite_images(plan: dict, image_payloads, task_id: str, image_size_ratio: str, text_type: str, country: str, product_json=None):
    client = get_ark_client()
    images = []
    all_plan_types = [str(item.get('type', '')).strip() for item in plan.get('items', []) if str(item.get('type', '')).strip()]
    plan_items = list(plan.get('items') or [])
    app_mode = get_app_mode()
    batch_limit = max(get_mode3_suite_batch_size(), 1) if app_mode == 'mode3' else max(get_supabase_setting_int('ARK_SEQUENTIAL_MAX_IMAGES', get_optional_int_env('ARK_SEQUENTIAL_MAX_IMAGES', 1)), 1)
    index = 0

    while index < len(plan_items):
        item = plan_items[index]
        remaining_items = plan_items[index:]
        generated_items = call_app_mode_image_generation(
            client,
            item['prompt'],
            image_payloads,
            image_size_ratio,
            text_type,
            country,
            product_json,
            item['type'],
            item,
            all_plan_types,
            max_images=min(len(remaining_items), batch_limit),
        )

        consumed_count = 0
        for generated_item, plan_item in zip(generated_items, remaining_items):
            image_bytes, mime_type = decode_generated_image(generated_item)
            download_name, relative_path, image_url = save_generated_image(task_id, plan_item['sort'], plan_item['type'], image_bytes, mime_type)
            images.append(
                {
                    'sort': plan_item['sort'],
                    'kind': 'generated',
                    'type': plan_item['type'],
                    'type_tag': plan_item['type_tag'],
                    'title': plan_item['title'],
                    'keywords': plan_item['keywords'],
                    'prompt': plan_item['prompt'],
                    'module': plan_item.get('module', ''),
                    'story_role': plan_item.get('story_role', ''),
                    'decision_task': plan_item.get('decision_task', ''),
                    'info_density': plan_item.get('info_density', ''),
                    'layout_style': plan_item.get('layout_style', ''),
                    'font_style': plan_item.get('font_style', ''),
                    'color_scheme': plan_item.get('color_scheme', ''),
                    'decor_elements': plan_item.get('decor_elements', []),
                    'image_url': image_url,
                    'image_path': relative_path,
                    'download_name': download_name,
                }
            )
            consumed_count += 1

        if consumed_count < 1:
            raise ValueError('图像生成接口未返回可用图片内容')

        index += consumed_count

    return images



def generate_aplus_images(plan: dict, image_payloads, task_id: str, image_size_ratio: str, text_type: str, country: str, product_json=None):
    client = get_ark_client()
    images = []

    for item in plan['items']:
        generated_items = call_app_mode_image_generation(
            client,
            item['prompt'],
            image_payloads,
            image_size_ratio,
            text_type,
            country,
            product_json,
            item['type'],
            max_images=1,
        )
        generated_item = generated_items[0]
        image_bytes, mime_type = decode_generated_image(generated_item)
        download_name, relative_path, image_url = save_generated_image(task_id, item['sort'], item['type'], image_bytes, mime_type)
        images.append(
            {
                'sort': item['sort'],
                'kind': 'generated',
                'type': item['type'],
                'type_tag': item['type_tag'],
                'title': item['title'],
                'keywords': item['keywords'],
                'prompt': item['prompt'],
                'module': item.get('module', ''),
                'story_role': item.get('story_role', ''),
                'decision_task': item.get('decision_task', ''),
                'info_density': item.get('info_density', ''),
                'layout_style': item.get('layout_style', ''),
                'font_style': item.get('font_style', ''),
                'color_scheme': item.get('color_scheme', ''),
                'decor_elements': item.get('decor_elements', []),
                'image_url': image_url,
                'image_path': relative_path,
                'download_name': download_name,
            }
        )

    return images


@app.before_request
def guard_authentication():
    path = request.path.rstrip('/') or '/'
    if path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
        g.supabase_session = get_supabase_session()
        g.supabase_user = (g.supabase_session or {}).get('user') if g.supabase_session else None
        g.admin_session = get_admin_session()
        return None

    if any(path.startswith(prefix) for prefix in PUBLIC_API_PREFIXES):
        g.supabase_session = get_supabase_session()
        g.supabase_user = (g.supabase_session or {}).get('user') if g.supabase_session else None
        g.admin_session = get_admin_session()
        return None

    if path == '/settings' or path.startswith('/api/settings'):
        admin_session = get_admin_session()
        if admin_session:
            g.admin_session = admin_session
            g.supabase_session = None
            g.supabase_user = None
            return None

    if path in PROTECTED_PAGE_PATHS or path.startswith('/generated') or path.startswith('/api/'):
        session_data = get_supabase_session()
        g.supabase_session = session_data
        g.supabase_user = (session_data or {}).get('user') if session_data else None
        if not session_data:
            if path.startswith('/api/'):
                return jsonify({'success': False, 'error': '请先登录'}), 401
            g.auth_required = True
            return None
        if path == '/settings' or path.startswith('/api/settings'):
            if not _is_settings_user_allowed(session_data):
                if path.startswith('/api/'):
                    return jsonify({'success': False, 'error': '无权访问设置页面'}), 403
                return make_response('无权访问设置页面', 403)
        return None

    g.supabase_session = get_supabase_session()
    g.supabase_user = (g.supabase_session or {}).get('user') if g.supabase_session else None
    g.admin_session = get_admin_session()
    return None


@app.get('/auth')
def auth_page():
    response = redirect('/')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.get('/api/app-mode')
def app_mode_api():
    app_mode = get_app_mode()
    return jsonify({'success': True, 'app_mode': app_mode, 'default_next_path': '/suite'})


@app.post('/api/auth/session-sync')
def auth_session_sync_api():
    payload = request.get_json(silent=True) or {}
    session = payload.get('session')
    response = jsonify({'success': True})
    if not session:
        clear_auth_session_cookie(response)
        return response
    if not isinstance(session, dict):
        return jsonify({'success': False, 'error': 'session 格式错误'}), 400
    normalized_session = normalize_supabase_session(session)
    if not normalized_session.get('access_token') or not normalized_session.get('refresh_token'):
        clear_auth_session_cookie(response)
        return response
    set_auth_session_cookie(response, normalized_session)
    return response


@app.post('/api/auth/session')
def auth_session_api():
    session_data = g.get('supabase_session') or get_supabase_session()
    admin_session = g.get('admin_session') or get_admin_session()
    if admin_session and not session_data:
        return jsonify({'success': True, 'authenticated': True, 'user': {'id': 'local-admin', 'phone': admin_session.get('identifier'), 'role': 'admin'}, 'session': None, 'admin': True})
    if not session_data:
        return jsonify({'success': True, 'authenticated': False, 'user': None})
    return jsonify({'success': True, 'authenticated': True, 'user': session_data.get('user'), 'session': session_data})


@app.post('/api/admin/login')
def admin_login_api():
    payload = request.get_json(silent=True) or {}
    identifier = str(payload.get('identifier') or payload.get('phone') or payload.get('email') or '').strip()
    password = str(payload.get('password') or '')
    if not verify_admin_credentials(identifier, password):
        return jsonify({'success': False, 'error': '管理员账号或密码错误'}), 401
    response = jsonify({'success': True, 'authenticated': True, 'admin': True, 'user': {'id': 'local-admin', 'phone': _normalize_phone_identifier(identifier), 'role': 'admin'}})
    set_admin_session_cookie(response, identifier)
    return response


@app.post('/api/admin/logout')
def admin_logout_api():
    response = jsonify({'success': True})
    clear_admin_session_cookie(response)
    return response


@app.post('/api/admin/session')
def admin_session_api():
    admin_session = g.get('admin_session') or get_admin_session()
    if not admin_session:
        return jsonify({'success': True, 'authenticated': False, 'admin': False})
    return jsonify({'success': True, 'authenticated': True, 'admin': True, 'user': {'id': 'local-admin', 'phone': admin_session.get('identifier'), 'role': 'admin'}})


@app.post('/api/pay/create')
def create_pay_order_api():
    session_data = g.get('supabase_session') or get_supabase_session()
    user = session_data.get('user') if isinstance(session_data, dict) else None
    user_id = str((user or {}).get('id') or '').strip()
    if not user_id:
        return jsonify({'error': 'UNAUTHORIZED', 'message': '未登录或登录状态已失效'}), 401

    try:
        payload = request.get_json(silent=True) or {}
        request_user_id = str(payload.get('user_id') or '').strip()
        product_id = str(payload.get('product_id') or '').strip()
        pay_type = str(payload.get('pay_type') or '').strip()
        amount = parse_money_amount(payload.get('amount'))

        if not request_user_id:
            return jsonify({'error': 'MISSING_USER_ID', 'message': '缺少 user_id'}), 400
        if request_user_id != user_id:
            return jsonify({'error': 'USER_MISMATCH', 'message': 'user_id 与当前登录用户不匹配'}), 403
        if not product_id:
            return jsonify({'error': 'MISSING_PRODUCT_ID', 'message': '缺少 product_id'}), 400
        if pay_type not in {'one_time', 'subscribe'}:
            return jsonify({'error': 'INVALID_PAY_TYPE', 'message': 'pay_type 只能是 one_time 或 subscribe'}), 400

        out_trade_no = generate_payment_order_no()
        db_type = 'one_time'
        subscribe_start = None
        subscribe_expire = None
        subscription_days = None

        if pay_type == 'subscribe':
            db_type = 'subscription'
            subscribe_start_dt, subscribe_expire_dt, subscription_days = compute_subscription_period(user_id, product_id)
            subscribe_start = subscribe_start_dt.astimezone(timezone.utc).isoformat()
            subscribe_expire = subscribe_expire_dt.astimezone(timezone.utc).isoformat()

        order_payload = {
            'order_no': out_trade_no,
            'user_id': user_id,
            'amount': f'{amount:.2f}',
            'status': 'pending',
            'pay_type': db_type,
            'package_id': product_id,
            'zpay_trade_no': None,
            'subscribe_start_at': subscribe_start,
            'subscribe_expire_at': subscribe_expire,
            'payment_method': ZPAY_DEFAULT_CHANNEL or 'alipay',
        }
        order_row = create_payment_order_record(order_payload)
        payment_url = build_zpay_payment_url(
            out_trade_no=out_trade_no,
            product_id=product_id,
            amount=amount,
            pay_type=pay_type,
            user_id=user_id,
        )
        return jsonify({
            'success': True,
            'message': '支付订单创建成功',
            'data': {
                'payment_url': payment_url,
                'order': serialize_payment_order(
                    order_row,
                    pay_type=pay_type,
                    subscription_days=subscription_days,
                ),
            },
        })
    except ValueError as exc:
        return jsonify({'error': 'VALIDATION_ERROR', 'message': str(exc)}), 400
    except requests.RequestException as exc:
        app.logger.exception('Failed to create payment order')
        return jsonify({'error': 'SUPABASE_REQUEST_FAILED', 'message': f'支付订单创建失败：{exc}'}), 502
    except RuntimeError as exc:
        return jsonify({'error': 'PAYMENT_CONFIG_ERROR', 'message': str(exc)}), 500
    except Exception as exc:
        app.logger.exception('Unexpected error while creating payment order')
        return jsonify({'error': 'CREATE_PAY_ORDER_FAILED', 'message': f'创建支付订单失败：{exc}'}), 500


@app.route('/api/pay/notify', methods=['GET', 'POST'])
def pay_notify_api():
    try:
        payload = normalize_callback_payload()
        out_trade_no = str(payload.get('out_trade_no') or '').strip()
        callback_trade_no = str(payload.get('trade_no') or '').strip()
        callback_money = str(payload.get('money') or '').strip()
        trade_status = str(payload.get('trade_status') or '').strip().upper()

        app.logger.warning('ZPAY notify received: method=%s out_trade_no=%s trade_no=%s trade_status=%s payload=%s', request.method, out_trade_no, callback_trade_no, trade_status, payload)

        if not verify_zpay_callback_signature(payload):
            app.logger.warning('ZPAY notify invalid sign: out_trade_no=%s payload=%s', out_trade_no, payload)
            return 'fail', 400
        if not out_trade_no:
            app.logger.warning('ZPAY notify missing out_trade_no: payload=%s', payload)
            return 'fail', 400
        if trade_status not in ZPAY_SUCCESS_STATUSES:
            app.logger.warning('ZPAY notify invalid trade_status: out_trade_no=%s trade_status=%s payload=%s', out_trade_no, trade_status, payload)
            return 'fail', 400

        order_row = fetch_payment_order_by_out_trade_no(out_trade_no)
        if not order_row:
            app.logger.warning('ZPAY notify order not found: out_trade_no=%s payload=%s', out_trade_no, payload)
            return 'fail', 404
        if is_order_success(order_row):
            return 'success', 200

        validate_callback_amount(order_row, callback_money)
        process_success_payment(order_row, callback_trade_no)
        app.logger.warning('ZPAY notify processed success: out_trade_no=%s trade_no=%s', out_trade_no, callback_trade_no)
        return 'success', 200
    except ValueError as exc:
        app.logger.warning('ZPAY notify validation error: %s; payload=%s', exc, request.values.to_dict(flat=True) if request.values else {})
        return 'fail', 400
    except requests.RequestException as exc:
        app.logger.exception('Failed to process payment callback')
        return 'fail', 502
    except RuntimeError as exc:
        app.logger.warning('ZPAY notify config error: %s', exc)
        return 'fail', 500
    except Exception as exc:
        app.logger.exception('Unexpected error while processing payment callback')
        return 'fail', 500


@app.post('/api/auth/login')
def auth_login():
    try:
        payload = request.get_json(silent=True) or {}
        email = str(payload.get('email') or '').strip().lower()
        password = str(payload.get('password') or '')
        if not email or not password:
            return jsonify({'success': False, 'error': '请输入邮箱和密码'}), 400
        data, _status_code = supabase_auth_password(email, password, 'login')
        session_data = normalize_supabase_session(data)
        user_id = _get_supabase_user_id(session_data)
        points_row = ensure_user_points_balance(user_id) if user_id else None
        if not points_row and user_id:
            points_row = get_user_points_balance(user_id)
        response_payload = {
            'success': True,
            'user': session_data.get('user'),
            'points': serialize_points_payload(points_row),
        }
        response = jsonify(response_payload)
        set_auth_session_cookie(response, session_data)
        return response
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 502


@app.post('/api/auth/register')
def auth_register():
    try:
        payload = request.get_json(silent=True) or {}
        email = str(payload.get('email') or '').strip().lower()
        password = str(payload.get('password') or '')
        if not email or not password:
            return jsonify({'success': False, 'error': '请输入邮箱和密码'}), 400
        data, _status_code = supabase_auth_password(email, password, 'signup')
        session_data = normalize_supabase_session(data)
        user_id = _get_supabase_user_id(session_data)
        points_row = ensure_user_points_balance(user_id) if user_id else None
        signup_result = award_signup_bonus_points(user_id, POINTS_SIGNUP_BONUS) if user_id else None
        if isinstance(signup_result, dict):
            points_row = (signup_result.get('balance_row') or points_row or {}) if isinstance(signup_result.get('balance_row'), dict) else points_row
        if not points_row and user_id:
            points_row = get_user_points_balance(user_id)
        response = jsonify({
            'success': True,
            'user': session_data.get('user'),
            'points': {
                **serialize_points_payload(points_row),
                'signup_bonus_awarded': bool((signup_result or {}).get('awarded')) if isinstance(signup_result, dict) else False,
            }
        })
        set_auth_session_cookie(response, session_data)
        return response
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 502


@app.get('/logout')
def auth_logout_page():
    session_data = g.get('supabase_session') or get_supabase_session() or {}
    supabase_logout_session(session_data)
    response = redirect('/')
    clear_auth_session_cookie(response)
    clear_admin_session_cookie(response)
    return response


@app.post('/api/auth/logout')
def auth_logout_api():
    session_data = g.get('supabase_session') or get_supabase_session() or {}
    logout_ok = supabase_logout_session(session_data)
    response = jsonify({'success': True, 'logout_synced': logout_ok})
    clear_auth_session_cookie(response)
    clear_admin_session_cookie(response)
    return response


@app.get('/')
def index():
    return render_html_page('landing.html')


def render_html_page(filename: str):
    html = (BASE_DIR / filename).read_text(encoding='utf-8')
    runtime_config = {
        'supabaseUrl': SUPABASE_URL,
        'supabaseAnonKey': SUPABASE_ANON_KEY,
    }
    config_script = f'<script>window.AI_IMAGE_CONFIG = {json.dumps(runtime_config, ensure_ascii=False)};</script>'
    if '</head>' in html:
        html = html.replace('</head>', f'{config_script}\n</head>', 1)
    else:
        html = f'{config_script}\n{html}'
    if g.get('auth_required'):
        html = re.sub(r'<body([^>]*)>', r'<body\1 data-auth-required="true">', html, count=1)
    response = make_response(html)
    if g.get('auth_required'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


@app.get('/suite')
def suite_page():
    return render_html_page('suite.html')


@app.get('/aplus')
def aplus_page():
    return render_html_page('aplus.html')


@app.get('/fashion')
def fashion_page():
    return render_html_page('fashion.html')


@app.get('/settings')
def settings_page():
    admin_session = g.get('admin_session') or get_admin_session()
    if not admin_session:
        return redirect('/')
    return render_html_page('settings.html')


@app.get('/generated/<path:path>')
def serve_generated_file(path: str):
    return send_from_directory(GENERATED_SUITES_DIR, path)


@app.get('/api/settings')
def settings_list_api():
    admin_session = g.get('admin_session') or get_admin_session()
    if not admin_session:
        return jsonify({'success': False, 'error': '未授权'}), 401
    scope = request.args.get('scope', 'global')
    records = []
    for key, value in LOCAL_CONFIG.items():
        normalized_key = _normalize_supabase_setting_key(key)
        records.append({
            'scope': scope,
            'setting_key': normalized_key,
            'setting_value': '' if _supabase_setting_is_sensitive(normalized_key) else str(value),
            'value_preview': _mask_supabase_setting_value(str(value)),
            'description': '',
            'updated_at': datetime.now(timezone.utc).isoformat(),
        })
    for key, value in os.environ.items():
        normalized_key = _normalize_supabase_setting_key(key)
        if normalized_key not in {r['setting_key'] for r in records}:
            records.append({
                'scope': scope,
                'setting_key': normalized_key,
                'setting_value': '' if _supabase_setting_is_sensitive(normalized_key) else str(value),
                'value_preview': _mask_supabase_setting_value(str(value)),
                'description': '',
                'updated_at': '',
            })
    return jsonify({'success': True, 'scope': scope, 'records': records})


@app.patch('/api/settings')
def settings_update_api():
    admin_session = g.get('admin_session') or get_admin_session()
    if not admin_session:
        return jsonify({'success': False, 'error': '未授权'}), 401
    payload = request.get_json(silent=True) or {}
    setting_key = str(payload.get('setting_key') or '').strip()
    if not setting_key:
        return jsonify({'success': False, 'error': 'setting_key 不能为空'}), 400
    if 'setting_value' not in payload:
        return jsonify({'success': False, 'error': 'setting_value 不能为空'}), 400
    setting_value = str(payload.get('setting_value') or '')
    LOCAL_CONFIG[setting_key.upper()] = setting_value
    save_local_config(LOCAL_CONFIG)
    return jsonify({
        'success': True,
        'record': {
            'scope': str(payload.get('scope') or 'global'),
            'setting_key': setting_key.upper(),
            'setting_value': '' if _supabase_setting_is_sensitive(setting_key.upper()) else setting_value,
            'value_preview': _mask_supabase_setting_value(setting_value),
            'description': '',
            'updated_at': datetime.now(timezone.utc).isoformat(),
        },
    })


@app.post('/api/settings/refresh')
def settings_refresh_api():
    admin_session = g.get('admin_session') or get_admin_session()
    if not admin_session:
        return jsonify({'success': False, 'error': '未授权'}), 401
    global LOCAL_CONFIG
    LOCAL_CONFIG = load_local_config()
    return jsonify({'success': True})


def find_refundable_spend_transaction(user_id: str, request_id: str, amount: int | None = None, transaction_type: str = '') -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    normalized_request_id = str(request_id or '').strip()
    normalized_transaction_type = str(transaction_type or '').strip()
    if not normalized_user_id or not normalized_request_id:
        return None
    params = {
        'select': '*',
        'user_id': f'eq.{normalized_user_id}',
        'metadata->>request_id': f'eq.{normalized_request_id}',
        'order': 'created_at.desc',
        'limit': '1',
    }
    if normalized_transaction_type:
        params['transaction_type'] = f'eq.{normalized_transaction_type}'
    if amount is not None:
        params['amount'] = f'eq.-{abs(int(amount))}'
    response = requests.get(
        build_supabase_request_url('/rest/v1/user_points_transactions'),
        headers=_build_supabase_service_headers(),
        params=params,
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return _extract_single_supabase_row(payload)


def find_refund_transaction_for_request(user_id: str, request_id: str) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    normalized_request_id = str(request_id or '').strip()
    if not normalized_user_id or not normalized_request_id:
        return None
    response = requests.get(
        build_supabase_request_url('/rest/v1/user_points_transactions'),
        headers=_build_supabase_service_headers(),
        params={
            'select': '*',
            'user_id': f'eq.{normalized_user_id}',
            'transaction_type': 'eq.refund',
            'metadata->>request_id': f'eq.{normalized_request_id}',
            'limit': '1',
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return _extract_single_supabase_row(payload)


@app.get('/api/points/balance')
def points_balance_api():
    try:
        session_data = g.get('supabase_session') or get_supabase_session()
        user_id = _get_supabase_user_id(session_data)
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录'}), 401
        points_row = ensure_user_points_balance(user_id) or get_user_points_balance(user_id) or {}
        user_profile_row = fetch_user_profile_by_user_id(user_id) or {}
        return jsonify({
            'success': True,
            'points': {
                'user_id': user_id,
                **serialize_points_payload(points_row, user_profile_row),
            },
        })
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'读取积分失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'读取积分失败：{exc}'}), 500


@app.post('/api/points/daily-claim')
def points_daily_claim_api():
    try:
        session_data = g.get('supabase_session') or get_supabase_session()
        user_id = _get_supabase_user_id(session_data)
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录'}), 401
        claim_result = claim_daily_free_points(user_id, POINTS_DAILY_FREE)
        if not isinstance(claim_result, dict):
            return jsonify({'success': False, 'error': '领取失败，请稍后重试'}), 502
        balance_row = claim_result.get('balance_row') or {}
        if claim_result.get('claimed'):
            return jsonify({
                'success': True,
                'claimed': POINTS_DAILY_FREE,
                'points': {
                    'user_id': user_id,
                    **serialize_points_payload(balance_row),
                },
            })
        error_message = str(claim_result.get('error') or '').strip()
        reason = str(claim_result.get('reason') or '').strip().lower()
        if reason == 'already_claimed_today' or '已领取' in error_message:
            return jsonify({
                'success': False,
                'claimed': False,
                'error': '今日已领取',
                'points': {
                    'user_id': user_id,
                    **serialize_points_payload(balance_row),
                },
            }), 409
        return jsonify({
            'success': False,
            'claimed': False,
            'error': error_message or '领取失败，请稍后重试',
            'points': {
                'user_id': user_id,
                **serialize_points_payload(balance_row),
            },
        }), 502
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'领取失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'领取失败：{exc}'}), 500


@app.get('/api/points/rules')
def points_rules_api():
    try:
        rules = get_points_rules()
        return jsonify({
            'success': True,
            'rules': rules,
        })
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'success': False, 'error': f'读取积分规则失败：{exc}'}), 500


@app.post('/api/points/quote')
def points_quote_api():
    try:
        payload = request.get_json(silent=True) or {}
        mode = str(payload.get('mode') or 'suite').strip().lower() or 'suite'
        consume_payload = build_points_consume_payload(
            mode,
            output_count=int(payload.get('output_count') or 0),
            selected_modules_count=int(payload.get('selected_modules_count') or 0),
            selected_scene_count=int(payload.get('selected_scene_count') or 0),
            transaction_type=str(payload.get('type') or 'consume').strip() or 'consume',
            reason=str(payload.get('reason') or '').strip(),
            metadata=payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {},
        )
        return jsonify({
            'success': True,
            'quote': consume_payload,
        })
    except ValueError:
        return jsonify({'success': False, 'error': '积分规则参数必须是数字'}), 400
    except Exception as exc:
        return jsonify({'success': False, 'error': f'计算积分失败：{exc}'}), 500


@app.post('/api/points/spend')
def points_spend_api():
    try:
        payload = request.get_json(silent=True) or {}
        session_data = g.get('supabase_session') or get_supabase_session()
        user_id = _get_supabase_user_id(session_data)
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录'}), 401

        mode = str(payload.get('mode') or 'suite').strip().lower() or 'suite'
        transaction_type = str(payload.get('type') or 'consume').strip() or 'consume'
        reason = str(payload.get('reason') or '').strip()
        metadata = payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {}
        consume_payload = build_points_consume_payload(
            mode,
            output_count=int(payload.get('output_count') or 0),
            selected_modules_count=int(payload.get('selected_modules_count') or 0),
            selected_scene_count=int(payload.get('selected_scene_count') or 0),
            transaction_type=transaction_type,
            reason=reason,
            metadata=metadata,
        )
        amount = int(consume_payload['amount'])
        if amount <= 0:
            return jsonify({'success': False, 'error': '扣减积分必须大于 0'}), 400

        spend_result = spend_user_points(user_id, amount, transaction_type, reason, metadata)
        if not isinstance(spend_result, dict):
            return jsonify({'success': False, 'error': '扣减积分失败'}), 502

        balance_row = spend_result.get('balance_row') or spend_result
        if spend_result.get('error') == 'INSUFFICIENT_POINTS':
            return jsonify({
                'success': False,
                'spent': False,
                'error': '积分不足',
                'points': {
                    'user_id': user_id,
                    **serialize_points_payload(balance_row),
                },
                'consume': consume_payload,
            }), 409
        if not spend_result.get('spent'):
            return jsonify({
                'success': False,
                'spent': False,
                'error': str(spend_result.get('error') or '扣减积分失败').strip() or '扣减积分失败',
                'points': {
                    'user_id': user_id,
                    **serialize_points_payload(balance_row),
                },
                'consume': consume_payload,
            }), 502

        return jsonify({
            'success': True,
            'spent': True,
            'points': {
                'user_id': user_id,
                **serialize_points_payload(balance_row),
            },
            'consume': consume_payload,
        })
    except ValueError:
        return jsonify({'success': False, 'error': '积分规则参数必须是数字'}), 400
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'扣减积分失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'扣减积分失败：{exc}'}), 500


@app.post('/api/points/refund')
def points_refund_api():
    try:
        payload = request.get_json(silent=True) or {}
        session_data = g.get('supabase_session') or get_supabase_session()
        user_id = _get_supabase_user_id(session_data)
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录'}), 401

        amount = int(payload.get('amount') or 0)
        if amount <= 0:
            return jsonify({'success': False, 'error': '返还积分必须大于 0'}), 400

        metadata = payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {}
        request_id = str(payload.get('request_id') or metadata.get('request_id') or '').strip()
        if not request_id:
            return jsonify({'success': False, 'error': '缺少 request_id，无法校验原始扣费记录'}), 400

        existing_refund = find_refund_transaction_for_request(user_id, request_id)
        if existing_refund:
            balance_result = get_user_points_balance(user_id)
            balance_row = (balance_result or {}).get('balance_row') or balance_result or {}
            return jsonify({
                'success': True,
                'refunded': False,
                'duplicate': True,
                'points': {
                    'user_id': user_id,
                    **serialize_points_payload(balance_row),
                },
                'transaction': existing_refund,
            })

        refund_source_type = str(payload.get('type') or metadata.get('type') or '').strip()
        if refund_source_type.endswith('_refund'):
            refund_source_type = refund_source_type[:-7]
        spend_row = find_refundable_spend_transaction(user_id, request_id, amount, refund_source_type)
        if not spend_row:
            spend_row = find_refundable_spend_transaction(user_id, request_id, amount)
        if not spend_row:
            return jsonify({'success': False, 'error': '未找到匹配的原始扣费记录，拒绝返还'}), 400
        original_amount = abs(int(spend_row.get('amount') or 0))
        if original_amount != amount:
            return jsonify({'success': False, 'error': '返还金额与原始扣费不匹配'}), 400

        reason = str(payload.get('reason') or '生成失败返还积分').strip()
        refund_metadata = {
            **metadata,
            'request_id': request_id,
            'refunded_spend_transaction_id': spend_row.get('id'),
        }
        refund_result = add_user_points(user_id, original_amount, 'refund', reason, refund_metadata, spend_row.get('id'))
        if not isinstance(refund_result, dict):
            return jsonify({'success': False, 'error': '返还积分失败'}), 502
        balance_row = (refund_result or {}).get('balance_row') or refund_result

        return jsonify({
            'success': True,
            'refunded': True,
            'points': {
                'user_id': user_id,
                **serialize_points_payload(balance_row),
            },
            'refund': {
                'amount': original_amount,
                'type': 'refund',
                'reason': reason,
                'metadata': refund_metadata,
            },
            'transaction': (refund_result or {}).get('transaction_row'),
        })
    except ValueError:
        return jsonify({'success': False, 'error': 'amount 必须是数字'}), 400
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'返还积分失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'返还积分失败：{exc}'}), 500


@app.post('/api/download-zip')
def download_zip():
    try:
        payload = request.get_json(silent=True) or {}
        image_paths = payload.get('image_paths')
        if not isinstance(image_paths, list) or not image_paths:
            return jsonify({'success': False, 'error': '请至少选择 1 张图片后再下载'}), 400

        zip_buffer = io.BytesIO()
        used_names = set()

        with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for index, raw_path in enumerate(image_paths, start=1):
                relative_path = str(raw_path or '').strip().replace('\\', '/').lstrip('/')
                if not relative_path:
                    continue
                file_path = (GENERATED_SUITES_DIR / relative_path).resolve()
                try:
                    file_path.relative_to(GENERATED_SUITES_DIR.resolve())
                except ValueError:
                    continue
                if not file_path.is_file():
                    continue

                base_name = Path(relative_path).name or f'image-{index:02d}{file_path.suffix or ".png"}'
                stem = Path(base_name).stem or f'image-{index:02d}'
                suffix = Path(base_name).suffix or file_path.suffix or '.png'
                archive_name = f'{stem}{suffix}'
                duplicate_index = 2
                while archive_name in used_names:
                    archive_name = f'{stem}-{duplicate_index}{suffix}'
                    duplicate_index += 1
                used_names.add(archive_name)
                archive.write(file_path, arcname=archive_name)

        if not used_names:
            return jsonify({'success': False, 'error': '未找到可下载的图片文件'}), 404

        zip_buffer.seek(0)
        download_name = f'ai-images-{datetime.now().strftime("%Y%m%d-%H%M%S")}.zip'
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name=download_name)
    except Exception as exc:
        return jsonify({'success': False, 'error': f'打包下载失败：{exc}'}), 500


@app.post('/api/ai-write')
def ai_write():
    try:
        selling_text = request.form.get('selling_text', '').strip()
        image_payloads = get_image_payloads_from_request()

        if not selling_text and not image_payloads:
            return jsonify({'success': False, 'error': '请至少提供核心卖点文案或上传 1 张图片'}), 400

        text = call_chat_completion(
            SYSTEM_PROMPT,
            build_multimodal_content(
                USER_PROMPT_TEMPLATE.format(selling_text=selling_text or '（未填写）'),
                image_payloads,
            ),
            temperature=0.7,
        )
        product_json = None
        if image_payloads or text:
            product_json, _response_text = call_chat_json_with_repair(
                PRODUCT_JSON_SYSTEM_PROMPT,
                build_multimodal_content(
                    PRODUCT_JSON_USER_PROMPT_TEMPLATE.format(selling_text=text or selling_text or '（未填写）'),
                    image_payloads,
                ),
                parse_product_json,
                '商品结构化信息格式异常',
                temperature=0.2,
                timeout_seconds=60,
                repair_attempts=1,
            )

        return jsonify({'success': True, 'text': text, 'product_json': product_json})
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        payload, status_code = parse_runtime_error(exc)
        return jsonify(payload), status_code
    except requests.Timeout:
        return jsonify({'success': False, 'error': '模型接口请求超时，请稍后重试'}), 504
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'模型接口请求失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


@app.post('/api/style-analysis')
def style_analysis():
    try:
        selling_text = request.form.get('selling_text', '').strip()
        platform = normalize_platform_label(request.form.get('platform', '亚马逊'))
        image_payloads = get_image_payloads_from_request()

        if not selling_text and not image_payloads:
            return jsonify({'success': False, 'error': '请至少提供核心卖点文案或上传 1 张图片'}), 400

        styles, _response_text = call_chat_json_with_repair(
            STYLE_ANALYSIS_SYSTEM_PROMPT,
            build_multimodal_content(
                STYLE_ANALYSIS_USER_PROMPT_TEMPLATE.format(
                    platform=platform,
                    selling_text=selling_text or '（未填写）',
                ),
                image_payloads,
            ),
            parse_style_analysis,
            '风格分析结果格式异常',
            temperature=0.3,
            timeout_seconds=60,
            repair_attempts=1,
        )
        return jsonify({'success': True, 'styles': styles})
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        payload, status_code = parse_runtime_error(exc)
        return jsonify(payload), status_code
    except requests.Timeout:
        return jsonify({'success': False, 'error': '模型接口请求超时，请稍后重试'}), 504
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'模型接口请求失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


@app.post('/api/generate-fashion-model')
def generate_fashion_model():
    try:
        payload = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(payload, dict):
            payload = {}

        gender = get_request_value(payload, request.form, 'gender', '女') or '女'
        age = get_request_value(payload, request.form, 'age', '青年') or '青年'
        ethnicity = get_request_value(payload, request.form, 'ethnicity', '欧美白人') or '欧美白人'
        body_type = get_request_value(payload, request.form, 'body_type', '标准') or '标准'
        appearance_details = get_request_value(payload, request.form, 'appearance_details', '')
        image_size_ratio = get_request_value(payload, request.form, 'image_size_ratio', '3:4') or '3:4'

        task_id = uuid.uuid4().hex
        prompt = build_fashion_model_prompt(gender, age, ethnicity, body_type, appearance_details)
        generated_item = call_app_mode_image_generation(
            get_ark_client(),
            prompt,
            [],
            image_size_ratio,
            '无文字',
            '中国',
            None,
            'fashion-model',
            max_images=1,
        )[0]
        image_bytes, mime_type = decode_generated_image(generated_item)
        download_name, relative_path, image_url = save_generated_image(task_id, 1, 'fashion-model', image_bytes, mime_type)
        model_id = f'ai-{task_id}'
        model = build_fashion_model_response(
            task_id,
            model_id,
            gender,
            age,
            ethnicity,
            body_type,
            appearance_details,
            prompt,
            image_url,
            relative_path,
            download_name,
        )

        return jsonify(
            {
                'success': True,
                'task_id': task_id,
                'model': model,
                'image_url': image_url,
                'image_path': relative_path,
                'download_name': download_name,
            }
        )
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        payload, status_code = parse_runtime_error(exc)
        return jsonify(payload), status_code
    except (APIError, APIStatusError) as exc:
        payload, status_code = parse_ark_exception(exc)
        return jsonify(payload), status_code
    except requests.Timeout:
        return jsonify({'success': False, 'error': '请求超时，请稍后重试'}), 504
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'请求失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


@app.post('/api/generate-mode2-image-edit')
def generate_mode2_image_edit():
    try:
        if get_app_mode() != 'mode2':
            return jsonify({'success': False, 'error': '当前模式未开启 mode2'}), 404

        payload = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(payload, dict):
            payload = {}

        prompt = get_request_value(payload, request.form, 'prompt', '')
        ratio = get_request_value(payload, request.form, 'image_size_ratio', '') or get_request_value(payload, request.form, 'ratio', '')
        resolution = get_request_value(payload, request.form, 'resolution', '')
        sample_strength = get_request_value(payload, request.form, 'sample_strength', '')
        image_url = get_request_value(payload, request.form, 'image_url', '')
        uploaded_payloads = get_image_payloads_from_request('images')

        if not prompt:
            return jsonify({'success': False, 'error': 'prompt 不能为空'}), 400
        if uploaded_payloads and image_url:
            return jsonify({'success': False, 'error': '上传图片与 image_url 二选一'}), 400
        if uploaded_payloads:
            image_payloads = uploaded_payloads
        elif image_url:
            image_payloads = [build_remote_image_payload(image_url)]
        else:
            return jsonify({'success': False, 'error': '请上传 1 张或多张参考图片，或提供 image_url'}), 400

        task_id = uuid.uuid4().hex
        generated_item, model = call_mode2_image_edit(
            get_mode2_client(),
            prompt,
            image_payloads,
            ratio,
            resolution,
            sample_strength,
        )
        return jsonify(build_mode2_success_response(task_id, 'mode2-image-edit', prompt, model, generated_item))
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        payload, status_code = parse_runtime_error(exc)
        return jsonify(payload), status_code
    except (APIError, APIStatusError) as exc:
        payload, status_code = parse_ark_exception(exc)
        return jsonify(payload), status_code
    except requests.Timeout:
        return jsonify({'success': False, 'error': '请求超时，请稍后重试'}), 504
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'请求失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


@app.post('/api/generate-mode2-text2image')
def generate_mode2_text2image():
    try:
        if get_app_mode() != 'mode2':
            return jsonify({'success': False, 'error': '当前模式未开启 mode2'}), 404

        payload = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(payload, dict):
            payload = {}

        prompt = get_request_value(payload, request.form, 'prompt', '')
        ratio = get_request_value(payload, request.form, 'image_size_ratio', '') or get_request_value(payload, request.form, 'ratio', '')
        resolution = get_request_value(payload, request.form, 'resolution', '')

        if not prompt:
            return jsonify({'success': False, 'error': 'prompt 不能为空'}), 400

        task_id = uuid.uuid4().hex
        generated_item, model = call_mode2_text2image(
            get_mode2_client(),
            prompt,
            ratio,
            resolution,
        )
        return jsonify(build_mode2_success_response(task_id, 'mode2-text2image', prompt, model, generated_item))
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        payload, status_code = parse_runtime_error(exc)
        return jsonify(payload), status_code
    except (APIError, APIStatusError) as exc:
        payload, status_code = parse_ark_exception(exc)
        return jsonify(payload), status_code
    except requests.Timeout:
        return jsonify({'success': False, 'error': '请求超时，请稍后重试'}), 504
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'请求失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


@app.post('/api/generate-mode3-image-edit')
def generate_mode3_image_edit():
    try:
        if get_app_mode() != 'mode3':
            return jsonify({'success': False, 'error': '当前模式未开启 mode3'}), 404

        payload = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(payload, dict):
            payload = {}

        prompt = get_request_value(payload, request.form, 'prompt', '')
        image_url = get_request_value(payload, request.form, 'image_url', '')
        uploaded_payloads = get_image_payloads_from_request('images')

        if not prompt:
            return jsonify({'success': False, 'error': 'prompt 不能为空'}), 400
        if uploaded_payloads and image_url:
            return jsonify({'success': False, 'error': '上传图片与 image_url 二选一'}), 400
        if uploaded_payloads:
            image_payloads = uploaded_payloads
        elif image_url:
            image_payloads = [build_remote_image_payload(image_url)]
        else:
            return jsonify({'success': False, 'error': '请上传 1 张或多张参考图片，或提供 image_url'}), 400

        task_id = uuid.uuid4().hex
        image_size_ratio = request.form.get('image_size_ratio', '1:1')
        product_json = extract_product_json_from_image_payloads(prompt, image_payloads)
        enriched_prompt = build_enriched_image_prompt(prompt, image_size_ratio, '中文', '中国', product_json, 'mode3-image-edit')
        generated_item, model = call_mode3_image_edit(get_mode3_client(), enriched_prompt, image_payloads, image_size_ratio)
        return jsonify(build_mode2_success_response(task_id, 'mode3-image-edit', enriched_prompt, model, generated_item))
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        payload, status_code = parse_runtime_error(exc)
        return jsonify(payload), status_code
    except (APIError, APIStatusError) as exc:
        payload, status_code = parse_ark_exception(exc)
        return jsonify(payload), status_code
    except requests.Timeout:
        return jsonify({'success': False, 'error': '请求超时，请稍后重试'}), 504
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'请求失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


@app.post('/api/generate-mode3-text2image')
def generate_mode3_text2image():
    try:
        if get_app_mode() != 'mode3':
            return jsonify({'success': False, 'error': '当前模式未开启 mode3'}), 404

        payload = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(payload, dict):
            payload = {}

        prompt = get_request_value(payload, request.form, 'prompt', '')
        if not prompt:
            return jsonify({'success': False, 'error': 'prompt 不能为空'}), 400

        task_id = uuid.uuid4().hex
        generated_item, model = call_mode3_text2image(get_mode3_client(), prompt)
        return jsonify(build_mode2_success_response(task_id, 'mode3-text2image', prompt, model, generated_item))
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        payload, status_code = parse_runtime_error(exc)
        return jsonify(payload), status_code
    except (APIError, APIStatusError) as exc:
        payload, status_code = parse_ark_exception(exc)
        return jsonify(payload), status_code
    except requests.Timeout:
        return jsonify({'success': False, 'error': '请求超时，请稍后重试'}), 504
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'请求失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


def build_generation_result_from_payload(form_payload: dict, file_payloads: dict):
    form = form_payload if isinstance(form_payload, dict) else {}
    payloads = file_payloads if isinstance(file_payloads, dict) else {}
    selling_text = str(form.get('selling_text') or '').strip()
    platform = normalize_platform_label(form.get('platform', '亚马逊'))
    mode = (str(form.get('mode') or 'suite').strip() or 'suite')
    image_payloads = list(payloads.get('images') or [])
    reference_payloads = list(payloads.get('reference_images') or [])
    country = str(form.get('country') or '中国').strip() or '中国'
    text_type = str(form.get('text_type') or '中文').strip() or '中文'
    image_size_ratio = str(form.get('image_size_ratio') or '1:1').strip() or '1:1'
    product_json = parse_product_json_payload(str(form.get('product_json') or ''))
    selected_style = parse_selected_style(
        str(form.get('selected_style_title') or ''),
        str(form.get('selected_style_reasoning') or ''),
        str(form.get('selected_style_colors') or ''),
    )

    if not selling_text and not image_payloads and not reference_payloads:
        raise ValueError('请至少提供核心卖点文案或上传 1 张图片')

    if mode == 'fashion':
        fashion_action = (str(form.get('fashion_action') or 'generate').strip() or 'generate')
        fashion_platform = FASHION_DEFAULT_PLATFORM
        fashion_selling_text = FASHION_DEFAULT_SELLING_TEXT
        fashion_country = FASHION_DEFAULT_COUNTRY
        fashion_text_type = FASHION_DEFAULT_TEXT_TYPE
        fashion_selected_style = FASHION_DEFAULT_SELECTED_STYLE
        selected_model_payloads = list(payloads.get('fashion_selected_model_image') or [])
        if fashion_action == 'scene_plan':
            selected_model = parse_fashion_selected_model_payload_from_data(form, selected_model_payloads)
            planning_payloads = image_payloads + [selected_model['payload']]
        else:
            selected_model = None
            planning_payloads = image_payloads
        if not planning_payloads:
            raise ValueError('请至少上传商品图或模特参考图')

        if fashion_action == 'scene_plan':
            scene_plan = build_fashion_scene_plan(
                fashion_platform,
                fashion_selling_text,
                planning_payloads,
                fashion_country,
                fashion_text_type,
                image_size_ratio,
                fashion_selected_style,
            )
            fashion_debug = {
                'selected_model': selected_model.get('debug'),
                'product_image_count': len(image_payloads),
                'generation_payload_order': ['images'] * len(image_payloads) + ['fashion_selected_model_image'],
            }
            return {
                'success': True,
                'mode': 'fashion',
                'fashion_action': 'scene_plan',
                'plan': scene_plan,
                'selected_style': fashion_selected_style,
                'fashion_debug': fashion_debug,
                'fashion_selection': {
                    'selected_model': {
                        'source': selected_model['source'],
                        'id': selected_model['id'],
                        'name': selected_model['name'],
                    },
                },
            }

        selected_model = parse_fashion_selected_model_payload_from_data(form, selected_model_payloads)
        selected_model_payload = selected_model['payload']
        scene_plan = parse_fashion_scene_plan_payload(str(form.get('fashion_scene_plan') or ''))
        scene_group_ids = parse_json_string_list(str(form.get('fashion_scene_group_ids') or ''), '场景')
        pose_ids = parse_json_string_list(str(form.get('fashion_pose_ids') or ''), '姿态')

        selections = parse_fashion_scene_selections(scene_plan.get('scene_groups') or [], scene_group_ids, pose_ids)
        pose_camera_settings = parse_fashion_pose_camera_settings(str(form.get('fashion_pose_camera_settings') or ''), selections)
        prompt_entries = build_fashion_generation_prompts(
            fashion_platform,
            fashion_selling_text,
            fashion_country,
            fashion_text_type,
            image_size_ratio,
            fashion_selected_style,
            selected_model,
            scene_plan,
            selections,
            pose_camera_settings,
        )

        task_id = uuid.uuid4().hex
        task_name = build_task_name(fashion_platform, 'fashion', len(prompt_entries))
        generated_at = build_generated_at()
        reference_images = build_reference_images(task_id, image_payloads, source='product')
        reference_images.extend(
            build_reference_images(
                task_id,
                [selected_model_payload],
                source='fashion_reference',
                start_sort=len(reference_images) + 1,
            )
        )

        fashion_generation_payloads = image_payloads + [selected_model_payload]
        fashion_debug = {
            'selected_model': selected_model.get('debug'),
            'product_image_count': len(image_payloads),
            'generation_payload_order': ['images'] * len(image_payloads) + ['fashion_selected_model_image'],
        }
        max_verify_attempts = max(1, get_optional_int_env('FASHION_OUTPUT_MAX_VERIFY_ATTEMPTS', FASHION_OUTPUT_MAX_VERIFY_ATTEMPTS))
        images = []
        failed_prompt_entries = []
        for index, prompt_entry in enumerate(prompt_entries, start=1):
            app.logger.warning(
                'Fashion image generation start: index=%s total=%s title=%s shot_size=%s view_angle=%s',
                index,
                len(prompt_entries),
                prompt_entry['pose'].get('title') or f'服饰穿搭图 {index}',
                prompt_entry.get('shot_size', ''),
                prompt_entry.get('view_angle', ''),
            )
            verification = None
            generated_items = []
            image_bytes = None
            mime_type = 'image/png'
            for attempt in range(1, max_verify_attempts + 1):
                generated_items = call_app_mode_image_generation(
                    get_ark_client(),
                    prompt_entry['prompt'],
                    fashion_generation_payloads,
                    image_size_ratio,
                    '无文字',
                    fashion_country,
                    product_json,
                    'fashion-look',
                    max_images=1,
                )
                generated_count = len(generated_items) if isinstance(generated_items, list) else 0
                app.logger.warning(
                    'Fashion image generation result: index=%s total=%s attempt=%s generated_count=%s title=%s',
                    index,
                    len(prompt_entries),
                    attempt,
                    generated_count,
                    prompt_entry['pose'].get('title') or f'服饰穿搭图 {index}',
                )
                if not generated_items:
                    continue
                image_bytes, mime_type = decode_generated_image(generated_items[0])
                generated_payload = {
                    'filename': f'fashion-look-{index:02d}.png',
                    'mime_type': mime_type,
                    'bytes': image_bytes,
                    'base64': base64.b64encode(image_bytes).decode('utf-8'),
                    'data_url': f'data:{mime_type};base64,{base64.b64encode(image_bytes).decode("utf-8")}',
                }
                verification = verify_fashion_generated_output(
                    generated_payload,
                    selected_model_payload,
                    image_payloads,
                )
                app.logger.warning(
                    'Fashion output verification: index=%s attempt=%s passed=%s score=%s failed_checks=%s reason=%s',
                    index,
                    attempt,
                    verification.get('passed'),
                    verification.get('score'),
                    ','.join(verification.get('failed_checks') or []),
                    verification.get('reason', ''),
                )
                if verification.get('passed'):
                    break
            if not generated_items or image_bytes is None:
                failed_prompt_entries.append(
                    {
                        'index': index,
                        'title': prompt_entry['pose'].get('title') or f'服饰穿搭图 {index}',
                        'reason': '生成结果为空',
                    }
                )
                continue
            if not verification or not verification.get('passed'):
                failed_prompt_entries.append(
                    {
                        'index': index,
                        'title': prompt_entry['pose'].get('title') or f'服饰穿搭图 {index}',
                        'reason': (verification or {}).get('reason', '质检未通过'),
                        'failed_checks': (verification or {}).get('failed_checks', []),
                    }
                )
                continue
            download_name, relative_path, image_url = save_generated_image(task_id, index, 'fashion-look', image_bytes, mime_type)
            images.append(
                {
                    'sort': index,
                    'kind': 'generated',
                    'type': '服饰穿搭图',
                    'type_tag': 'Look',
                    'title': prompt_entry['pose'].get('title') or f'服饰穿搭图 {index}',
                    'keywords': [prompt_entry.get('shot_size', ''), prompt_entry.get('view_angle', '')],
                    'prompt': prompt_entry['prompt'],
                    'image_url': image_url,
                    'image_path': relative_path,
                    'download_name': download_name,
                    'verification': verification,
                }
            )

        if not images:
            failure_titles = '、'.join(item['title'] for item in failed_prompt_entries[:3])
            failure_reason = '；'.join(
                item['reason'] for item in failed_prompt_entries[:2] if str(item.get('reason') or '').strip()
            )
            failure_hint = f'（失败场景：{failure_titles}）' if failure_titles else ''
            failure_reason_hint = f'：{failure_reason}' if failure_reason else ''
            raise RuntimeError(f'生成结果未通过模特/文字质检，请稍后重试{failure_hint}{failure_reason_hint}')

        return {
            'success': True,
            'mode': 'fashion',
            'fashion_action': 'generate',
            'task_id': task_id,
            'task_name': task_name,
            'generated_at': generated_at,
            'selected_style': fashion_selected_style,
            'fashion_debug': fashion_debug,
            'reference_images': reference_images,
            'images': images,
            'fashion_selection': {
                'selected_model': {
                    'source': selected_model['source'],
                    'id': selected_model['id'],
                    'name': selected_model['name'],
                    'gender': selected_model.get('gender', ''),
                    'age': selected_model.get('age', ''),
                    'ethnicity': selected_model.get('ethnicity', ''),
                    'body_type': selected_model.get('body_type', ''),
                },
                'scene_group_ids': scene_group_ids,
                'pose_ids': pose_ids,
                'pose_camera_settings': pose_camera_settings,
            },
        }

    output_count, _ = get_suite_type_rules(form.get('output_count', '8'))
    task_id = uuid.uuid4().hex
    task_name = build_task_name(platform, 'suite', output_count)
    generated_at = build_generated_at()
    reference_images = build_reference_images(task_id, image_payloads, source='product')
    if reference_payloads:
        reference_images.extend(
            build_reference_images(
                task_id,
                reference_payloads,
                source='reference',
                start_sort=len(reference_images) + 1,
            )
        )
    planning_payloads = image_payloads + reference_payloads
    if product_json is None and planning_payloads:
        app.logger.warning('Suite generation extracting product_json from uploaded reference images: mode=%s image_count=%s', mode, len(planning_payloads))
        product_json = extract_product_json_from_image_payloads(selling_text, planning_payloads)
    app.logger.warning(
        'Suite generation upload payloads: mode=%s product_count=%s reference_count=%s total_generation_count=%s product_json_ready=%s',
        mode,
        len(image_payloads),
        len(reference_payloads),
        len(planning_payloads),
        bool(product_json),
    )
    plan = build_suite_plan(
        platform,
        selling_text,
        output_count,
        planning_payloads,
        country,
        text_type,
        image_size_ratio,
        selected_style,
        mode,
        product_json,
    )
    images = generate_suite_images(plan, planning_payloads, task_id, image_size_ratio, text_type, country, product_json)

    return {
        'success': True,
        'mode': mode,
        'task_id': task_id,
        'task_name': task_name,
        'generated_at': generated_at,
        'plan': plan,
        'selected_style': selected_style,
        'reference_images': reference_images,
        'images': images,
    }


@app.post('/api/generate-suite')
def generate_suite():
    try:
        form_payload = {key: request.form.get(key, '') for key in request.form.keys()}
        file_payloads = {
            'images': get_image_payloads_from_request('images'),
            'reference_images': get_image_payloads_from_request('reference_images'),
            'fashion_selected_model_image': get_image_payloads_from_request('fashion_selected_model_image', limit=1),
        }
        run_async = str(form_payload.get('async_task') or '').strip().lower() in {'1', 'true', 'yes'}
        if run_async:
            session_data = g.get('supabase_session') or get_supabase_session()
            user_id = _get_supabase_user_id(session_data)
            if not user_id:
                return jsonify({'success': False, 'error': '请先登录'}), 401
            spend_record = None
            spend_payload = form_payload.get('spend_record')
            if spend_payload:
                try:
                    parsed_spend_record = json.loads(spend_payload)
                    if isinstance(parsed_spend_record, dict):
                        spend_record = parsed_spend_record
                except (TypeError, ValueError):
                    spend_record = None
            request_id = str(form_payload.get('points_request_id') or (spend_record or {}).get('requestId') or '').strip()
            task = create_generation_task(user_id, str(form_payload.get('mode') or 'suite'), request_id, spend_record)
            GENERATION_TASK_EXECUTOR.submit(run_generation_task, task['task_id'], form_payload, file_payloads)
            return jsonify({'success': True, 'async_task': True, 'task': task, 'task_id': task['task_id']}), 202
        result = build_generation_result_from_payload(form_payload, file_payloads)
        return jsonify(result)
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        payload, status_code = parse_runtime_error(exc)
        return jsonify(payload), status_code
    except (APIError, APIStatusError) as exc:
        payload, status_code = parse_ark_exception(exc)
        return jsonify(payload), status_code
    except requests.Timeout:
        return jsonify({'success': False, 'error': '请求超时，请稍后重试'}), 504
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'请求失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


@app.get('/api/generation-tasks/<task_id>')
def generation_task_status(task_id):
    session_data = g.get('supabase_session') or get_supabase_session()
    user_id = _get_supabase_user_id(session_data)
    if not user_id:
        return jsonify({'success': False, 'error': '请先登录'}), 401
    task = get_generation_task(task_id)
    if not task:
        return jsonify({'success': False, 'error': '生成任务不存在或已过期'}), 404
    if str(task.get('user_id') or '') != str(user_id):
        return jsonify({'success': False, 'error': '无权访问该生成任务'}), 403
    return jsonify({'success': True, 'task': serialize_generation_task(task)})


@app.post('/api/generation-tasks/<task_id>/cancel')
def generation_task_cancel(task_id):
    session_data = g.get('supabase_session') or get_supabase_session()
    user_id = _get_supabase_user_id(session_data)
    if not user_id:
        return jsonify({'success': False, 'error': '请先登录'}), 401
    task = get_generation_task(task_id)
    if not task:
        return jsonify({'success': False, 'error': '生成任务不存在或已过期'}), 404
    if str(task.get('user_id') or '') != str(user_id):
        return jsonify({'success': False, 'error': '无权访问该生成任务'}), 403
    if task.get('status') in {'succeeded', 'failed'}:
        return jsonify({'success': True, 'task': serialize_generation_task(task)})
    fail_generation_task_with_refund(task_id, '生成已取消')
    updated_task = get_generation_task(task_id)
    return jsonify({'success': True, 'task': serialize_generation_task(updated_task)})


@app.post('/api/generate-aplus')
def generate_aplus():
    try:
        selling_text = request.form.get('selling_text', '').strip()
        platform = normalize_platform_label(request.form.get('platform', '亚马逊'))
        image_payloads = get_image_payloads_from_request()
        reference_payloads = get_image_payloads_from_request('reference_images')
        country = request.form.get('country', '中国').strip() or '中国'
        text_type = request.form.get('text_type', '中文').strip() or '中文'
        image_size_ratio = request.form.get('image_size_ratio', '1:1').strip() or '1:1'
        product_json = parse_product_json_payload(request.form.get('product_json', ''))
        selected_modules = parse_selected_modules(request.form.get('selected_modules', ''))
        selected_style = parse_selected_style(
            request.form.get('selected_style_title', ''),
            request.form.get('selected_style_reasoning', ''),
            request.form.get('selected_style_colors', ''),
        )

        if not selling_text and not image_payloads and not reference_payloads:
            return jsonify({'success': False, 'error': '请至少提供核心卖点文案或上传 1 张图片'}), 400

        task_id = uuid.uuid4().hex
        task_name = build_task_name(platform, 'aplus', len(selected_modules))
        generated_at = build_generated_at()
        reference_images = build_reference_images(task_id, image_payloads, source='product')
        if reference_payloads:
            reference_images.extend(
                build_reference_images(
                    task_id,
                    reference_payloads,
                    source='reference',
                    start_sort=len(reference_images) + 1,
                )
            )
        planning_payloads = image_payloads + reference_payloads
        if product_json is None and planning_payloads:
            app.logger.warning('A+ generation extracting product_json from uploaded reference images: product_count=%s reference_count=%s total_generation_count=%s', len(image_payloads), len(reference_payloads), len(planning_payloads))
            product_json = extract_product_json_from_image_payloads(selling_text, planning_payloads)
        app.logger.warning(
            'A+ generation upload payloads: product_count=%s reference_count=%s total_generation_count=%s product_json_ready=%s',
            len(image_payloads),
            len(reference_payloads),
            len(planning_payloads),
            bool(product_json),
        )
        plan = build_aplus_plan(platform, selling_text, selected_modules, planning_payloads, country, text_type, image_size_ratio, selected_style, product_json)
        images = generate_aplus_images(plan, planning_payloads, task_id, image_size_ratio, text_type, country, product_json)

        return jsonify(
            {
                'success': True,
                'mode': 'aplus',
                'task_id': task_id,
                'task_name': task_name,
                'generated_at': generated_at,
                'plan': plan,
                'selected_style': selected_style,
                'reference_images': reference_images,
                'images': images,
            }
        )
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        payload, status_code = parse_runtime_error(exc)
        return jsonify(payload), status_code
    except (APIError, APIStatusError) as exc:
        payload, status_code = parse_ark_exception(exc)
        return jsonify(payload), status_code
    except requests.Timeout:
        return jsonify({'success': False, 'error': '请求超时，请稍后重试'}), 504
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'请求失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


if __name__ == '__main__':
    host = get_supabase_setting('HOST', get_optional_env('HOST', '0.0.0.0')) or '0.0.0.0'
    port = get_supabase_setting_int('PORT', get_optional_int_env('PORT', 5078))
    debug = get_supabase_setting_bool('FLASK_DEBUG', get_optional_bool_env('FLASK_DEBUG', False))
    app.run(host=host, port=port, debug=debug)
