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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO, emit, join_room, leave_room
from openai import APIError, APIStatusError, OpenAI
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge
from cos_utils import upload_to_cos, generate_cos_key, is_cos_enabled, get_cos_url_prefix

from supabase_client import (
    _fetch_user_points_row, _normalize_points_row, _build_legacy_points_balance_row,
    _create_legacy_points_balance_row, _ensure_points_balance_row_direct,
    _claim_daily_free_points_direct, _spend_user_points_direct, add_user_points_direct,
    get_user_points_balance, fetch_vip_plan_config, grant_payment_points_once,
    is_generation_task_persistence_enabled, build_generation_task_db_payload,
    persist_generation_task, fetch_generation_task_row, normalize_generation_task_row,
    fetch_user_generation_tasks, fetch_user_generation_history_images, upsert_generation_history_images,
    fetch_latest_active_subscription, create_payment_order_record,
    fetch_payment_order_by_out_trade_no, update_payment_order,
    fetch_user_profile_by_user_id, upsert_user_subscription_profile,
    _fetch_supabase_user_admin_flag,
    find_refundable_spend_transaction, find_refund_transaction_for_request,
    build_supabase_auth_headers, normalize_supabase_session,
    refresh_supabase_session, supabase_logout_session, supabase_auth_password,
)
from generation import (
    get_ark_client, get_mode1_client, get_mode2_client, get_mode3_client,
    get_mode3_api_key,
    call_mode1_image_edit, call_mode1_text2image,
    call_mode2_image_edit, call_mode2_text2image, call_mode2_images_generate_with_retry,
    call_mode3_image_edit, call_mode3_text2image,
    call_mode1_single_image, call_mode1_single_image_with_retry,
    call_mode1_images_parallel_with_partial_retry,
    call_mode2_single_image, call_mode2_single_image_with_retry,
    call_mode2_images_parallel_with_partial_retry,
    call_mode3_single_image, call_mode3_single_image_with_retry,
    call_mode3_images_parallel_with_partial_retry,
    call_app_mode_image_generation, call_image_generation,
    create_mode1_blank_canvas_payload, create_mode2_blank_canvas_payload, create_mode3_blank_canvas_payload,
    create_replicate_layout_canvas_payload,
    build_mode1_reference_anchor_prompt,
    generate_suite_images,
    generate_mode1_suite_images_parallel, generate_mode2_suite_images_parallel,
    generate_mode3_suite_images_parallel,
    generate_aplus_images,
    _get_parallel_config,
    get_suite_plan_timeout_seconds,
    call_chat_completion, call_chat_json_with_repair,
    parse_style_analysis, get_suite_type_rules, parse_selected_modules,
    parse_selected_style, build_style_reference_text,
    parse_product_json, parse_product_json_payload,
    build_suite_plan, build_main_image_cover_plan, build_aplus_plan,
    parse_fashion_selected_model_payload_from_data, build_fashion_scene_plan,
    build_fashion_model_prompt, parse_fashion_scene_plan_payload,
    parse_fashion_scene_selections, parse_fashion_pose_camera_settings,
    build_fashion_generation_prompts, verify_fashion_generated_output,
    extract_product_json_from_image_payloads,
    get_request_value,
    PRODUCT_JSON_FALLBACK, PRODUCT_JSON_PROMPT_TEMPLATE,
    FASHION_SCENE_PLAN_MODEL_TIMEOUT_SECONDS, FASHION_MODEL_APPEARANCE_FALLBACK,
)

from config import (
    BASE_DIR, CONFIG_FILE, LOCAL_CONFIG, load_local_config, save_local_config,
    get_first_env, get_env_csv, get_supabase_setting, get_supabase_setting_int,
    get_supabase_setting_float, get_supabase_setting_bool, get_supabase_setting_csv,
    get_supabase_setting_json, get_optional_env, get_optional_int_env, get_optional_bool_env,
    build_supabase_request_url, _get_supabase_user_id, _build_supabase_service_headers,
    _post_supabase_rpc, get_mode2_allowed_image_hosts, get_settings_allowed_emails,
    get_settings_allowed_phones, _normalize_supabase_setting_key, _supabase_setting_is_sensitive,
    _mask_supabase_setting_value, get_admin_password, get_admin_session_secret,
    _normalize_phone_identifier, _is_truthy_flag, normalize_app_mode, get_app_mode,
    GENERATED_SUITES_DIR, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_SESSION_COOKIE, SUPABASE_SESSION_SYNC_COOKIE, ADMIN_SESSION_COOKIE,
    PROTECTED_PAGE_PATHS, PUBLIC_API_PREFIXES, PUBLIC_PATH_PREFIXES, PUBLIC_PATHS,
    SUPABASE_USER_PROFILES_TABLE, SUPABASE_POINTS_TABLE, SUPABASE_PAYMENTS_TABLE,
    SUPABASE_GENERATION_TASKS_TABLE, GENERATION_TASK_TTL_SECONDS,
    GENERATION_TASK_POLL_RETENTION_SECONDS, GENERATION_TASKS, GENERATION_TASKS_LOCK,
    GENERATION_TASK_CANCEL_EVENTS, GENERATION_TASK_EXECUTOR, ZPAY_PID, ZPAY_KEY, ZPAY_GATEWAY, ZPAY_NOTIFY_URL,
    ZPAY_RETURN_URL, ZPAY_DEFAULT_CHANNEL, ZPAY_SUCCESS_STATUSES, VIP_PLAN_CONFIG_TABLE,
    MAX_IMAGE_UPLOADS, ALLOWED_IMAGE_MIME_TYPES, ALLOWED_IMAGE_EXTENSIONS, IMAGE_SIGNATURES,
)
from utils import (
    parse_money_amount, normalize_vip_plan_key, _resolve_configured_plan_key,
    parse_iso_datetime, normalize_platform_label, build_task_name, build_generated_at,
    resolve_image_size, parse_string_list, strip_code_fences, remove_trailing_json_commas,
    parse_json_candidate, normalize_hex_color, parse_runtime_error, parse_ark_exception,
    normalize_plan_short_text, normalize_plan_enum, normalize_plan_type_list,
    parse_json_string_list, _extract_single_supabase_row, _safe_json_payload,
)
from image_utils import (
    guess_extension, sanitize_filename_part, sniff_image_mime_type, validate_image_file,
    cleanup_generated_suites, file_to_data_url, create_image_payload, LazyImagePayload,
    build_multimodal_content, is_private_ip_address, validate_mode2_remote_image_url,
    build_remote_image_payload, _fetch_url_to_image_payload, _download_image_url_with_retry,
    decode_generated_image, save_generated_image, save_reference_image,
    build_reference_images, build_mode2_success_response, build_generated_suite_image_item,
    build_fashion_model_summary, build_fashion_model_response,
    normalize_product_json, serialize_product_json, build_product_json_prompt_text,
    build_plan_control_prompt, build_enriched_image_prompt,
)
from points_rules import (
    DEFAULT_POINTS_RULES, ALLOWED_POINTS_RULE_METRICS, POINTS_RULE_SETTING_KEYS,
    normalize_points_rule, _get_env_points_rule_json, get_points_rules, get_points_rule,
    calculate_points_cost, build_points_consume_payload,
)
from prompts import (
    HEX_COLOR_PATTERN, SAFE_NAME_PATTERN,
    SYSTEM_PROMPT, PRODUCT_JSON_SYSTEM_PROMPT, USER_PROMPT_TEMPLATE,
    PRODUCT_JSON_USER_PROMPT_TEMPLATE, STYLE_ANALYSIS_SYSTEM_PROMPT,
    STYLE_ANALYSIS_USER_PROMPT_TEMPLATE, FASHION_OUTPUT_VERIFIER_SYSTEM_PROMPT,
    FASHION_OUTPUT_VERIFIER_USER_PROMPT_TEMPLATE, FASHION_OUTPUT_MAX_VERIFY_ATTEMPTS,
    FASHION_SCENE_PLAN_SYSTEM_PROMPT, FASHION_SCENE_PLAN_USER_PROMPT_TEMPLATE,
    SUITE_PLAN_SYSTEM_PROMPT, SUITE_PLAN_USER_PROMPT_TEMPLATE,
    SUITE_TYPE_META, SUITE_TYPE_RULES,
    APLUS_PLAN_SYSTEM_PROMPT, APLUS_PLAN_USER_PROMPT_TEMPLATE, APLUS_MODULE_META,
    IMAGE_SIZE_RATIO_MAP,
    FASHION_DEFAULT_PLATFORM, FASHION_DEFAULT_COUNTRY, FASHION_DEFAULT_TEXT_TYPE,
    FASHION_DEFAULT_SELLING_TEXT, FASHION_DEFAULT_SELECTED_STYLE,
    FASHION_SCENE_PLAN_MODEL_TIMEOUT_SECONDS, FASHION_MODEL_APPEARANCE_FALLBACK,
)


import logging
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=str(BASE_DIR / 'static'), static_url_path='/static')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri="memory://",
)

_SESSION_CACHE: dict[str, tuple[float, dict]] = {}
_SESSION_CACHE_LOCK = threading.Lock()
_SESSION_CACHE_TTL = 300
_BAD_REQUEST_LOG_SAMPLE_RATE = max(1, get_optional_int_env('BAD_REQUEST_LOG_SAMPLE_RATE', 20))


def _log_bad_request_sample(exc: Exception) -> None:
    try:
        path = request.path or '/'
        fingerprint_source = '|'.join([
            request.method or '',
            path,
            request.host or '',
            request.headers.get('User-Agent', ''),
            request.headers.get('Referer', ''),
            request.headers.get('X-Forwarded-For', ''),
            request.headers.get('X-Forwarded-Proto', ''),
            request.headers.get('CF-Connecting-IP', ''),
        ])
        digest = hashlib.sha1(fingerprint_source.encode('utf-8', errors='ignore')).hexdigest()
        if int(digest[:8], 16) % _BAD_REQUEST_LOG_SAMPLE_RATE != 0:
            return
        logger.warning(
            '400_sample path=%s method=%s host=%s remote=%s forwarded_for=%s forwarded_proto=%s cf_ip=%s ua=%s referer=%s query_keys=%s content_type=%s content_length=%s exc=%s',
            path,
            request.method,
            request.host,
            request.remote_addr,
            request.headers.get('X-Forwarded-For', ''),
            request.headers.get('X-Forwarded-Proto', ''),
            request.headers.get('CF-Connecting-IP', ''),
            request.headers.get('User-Agent', '')[:240],
            request.headers.get('Referer', '')[:240],
            sorted(list(request.args.keys()))[:20],
            request.content_type or '',
            request.content_length,
            str(exc)[:240],
        )
    except Exception as log_exc:
        logger.debug('Failed to log 400 sample: %s', log_exc)


@app.after_request
def set_static_file_cache(response):
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=3600'
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


@app.errorhandler(BadRequest)
def handle_bad_request(exc):
    _log_bad_request_sample(exc)
    return exc


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
        logger.warning('Failed to ensure user points balance for %s: %s', normalized_user_id, exc)
    except RuntimeError as exc:
        logger.warning('Failed to ensure user points balance for %s: %s', normalized_user_id, exc)
    return _ensure_points_balance_row_direct(normalized_user_id)


def award_signup_bonus_points(user_id: str, amount: int) -> dict | None:
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id:
        return None
    try:
        payload = _post_supabase_rpc('award_signup_bonus_points', {'p_user_id': normalized_user_id, 'p_amount': int(amount)})
    except requests.RequestException as exc:
        logger.warning('Failed to award signup bonus for %s: %s', normalized_user_id, exc)
        return None
    except RuntimeError as exc:
        logger.warning('Failed to award signup bonus for %s: %s', normalized_user_id, exc)
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
        logger.warning('Failed to claim daily points for %s: %s', normalized_user_id, exc)
        try:
            fallback_payload = _claim_daily_free_points_direct(normalized_user_id, amount)
            if fallback_payload:
                logger.warning('Claim daily points fallback applied for %s after RPC HTTP failure', normalized_user_id)
                return fallback_payload
        except requests.RequestException as fallback_exc:
            logger.warning('Daily points fallback failed for %s: %s', normalized_user_id, fallback_exc)
        return {
            'success': False,
            'claimed': False,
            'error': error_text or '领取失败，请稍后重试',
            'balance_row': get_user_points_balance(normalized_user_id) or ensure_user_points_balance(normalized_user_id) or {},
        }
    except requests.RequestException as exc:
        logger.warning('Failed to claim daily points for %s: %s', normalized_user_id, exc)
        try:
            fallback_payload = _claim_daily_free_points_direct(normalized_user_id, amount)
            if fallback_payload:
                logger.warning('Claim daily points fallback applied for %s after RPC request failure', normalized_user_id)
                return fallback_payload
        except requests.RequestException as fallback_exc:
            logger.warning('Daily points fallback failed for %s: %s', normalized_user_id, fallback_exc)
        return {
            'success': False,
            'claimed': False,
            'error': '领取失败，请稍后重试',
            'balance_row': get_user_points_balance(normalized_user_id) or ensure_user_points_balance(normalized_user_id) or {},
        }
    except RuntimeError as exc:
        logger.warning('Failed to claim daily points for %s: %s', normalized_user_id, exc)
        try:
            fallback_payload = _claim_daily_free_points_direct(normalized_user_id, amount)
            if fallback_payload:
                logger.warning('Claim daily points fallback applied for %s after RPC runtime failure', normalized_user_id)
                return fallback_payload
        except requests.RequestException as fallback_exc:
            logger.warning('Daily points fallback failed for %s: %s', normalized_user_id, fallback_exc)
        return {
            'success': False,
            'claimed': False,
            'error': str(exc) or '领取失败，请稍后重试',
            'balance_row': get_user_points_balance(normalized_user_id) or ensure_user_points_balance(normalized_user_id) or {},
        }


def _record_points_transaction(user_id: str, amount: int, transaction_type: str, reason: str, metadata: dict | None) -> None:
    try:
        requests.post(
            build_supabase_request_url('/rest/v1/user_points_transactions'),
            headers=_build_supabase_service_headers(),
            json={
                'user_id': user_id,
                'amount': amount,
                'transaction_type': transaction_type,
                'reason': reason,
                'metadata': metadata or {},
            },
            timeout=10,
        )
    except Exception as e:
        logger.warning('Failed to record points transaction for %s: %s', user_id, e)


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
        },
    ]
    last_error_text = ''
    last_exception = None
    for rpc_payload in rpc_payloads:
        try:
            payload = _post_supabase_rpc('spend_user_points', rpc_payload)
            if isinstance(payload, dict):
                _record_points_transaction(
                    normalized_user_id,
                    -normalized_amount,
                    normalized_transaction_type,
                    normalized_reason,
                    normalized_metadata,
                )
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
                '积分余额不足' in error_text or 'INSUFFICIENT_POINTS' in error_text or 'Insufficient points' in error_text
            ):
                balance_row = get_user_points_balance(normalized_user_id) or ensure_user_points_balance(normalized_user_id) or {}
                return {
                    'success': False,
                    'spent': False,
                    'error': 'INSUFFICIENT_POINTS',
                    'balance_row': balance_row,
                }
            if response is not None and response.status_code == 404 and 'Could not find the function' in error_text:
                continue
            logger.warning('Failed to spend user points for %s: %s', normalized_user_id, exc)
            return build_spend_failure(error_text or str(exc))
        except requests.RequestException as exc:
            logger.warning('Failed to spend user points for %s: %s', normalized_user_id, exc)
            return build_spend_failure(str(exc))
        except RuntimeError as exc:
            last_exception = exc
            last_error_text = str(exc)
            if '返回了无效响应' in last_error_text:
                continue
            logger.warning('Failed to spend user points for %s: %s', normalized_user_id, exc)
            return build_spend_failure(last_error_text)
    logger.warning('Failed to spend user points for %s after trying compatible RPC payloads: %s', normalized_user_id, last_exception or last_error_text)
    return build_spend_failure(last_error_text or str(last_exception or '扣减积分失败'))


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
            logger.warning('Failed to add user points for %s: %s', normalized_user_id, exc)
            break
        except (requests.RequestException, RuntimeError) as exc:
            last_exception = exc
            logger.warning('Failed to add user points for %s: %s', normalized_user_id, exc)
            break
    try:
        return add_user_points_direct(normalized_user_id, normalized_amount, transaction_type, reason, normalized_metadata, related_transaction_id)
    except requests.RequestException as fallback_exc:
        logger.warning('Direct add user points fallback failed for %s after %s: %s', normalized_user_id, last_exception, fallback_exc)
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








def _get_vip_plan_config_int(config: dict, field_name: str) -> int:
    try:
        return max(int(config.get(field_name) or 0), 0)
    except (TypeError, ValueError):
        return 0


def _get_vip_plan_config_str(config: dict, field_name: str) -> str:
    return str((config or {}).get(field_name) or '').strip()


def resolve_vip_plan_pay_type(config: dict, product_id: str) -> str:
    normalized_product_id = normalize_vip_plan_key(product_id)
    if not normalized_product_id:
        return 'one_time'
    try:
        plan_index = int(normalized_product_id.split('_', 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f'无效的套餐标识: {normalized_product_id}') from exc

    configured_pay_type = _get_vip_plan_config_str(config, f'pay_type_{plan_index}').lower()
    if configured_pay_type in {'one_time', 'subscribe'}:
        return configured_pay_type

    subscription_days = _get_vip_plan_config_int(config, f'validity_days_{plan_index}')
    if subscription_days <= 0:
        subscription_days = _get_vip_plan_config_int(config, f'duration_days_{plan_index}')
    if subscription_days <= 0:
        subscription_days = _get_vip_plan_config_int(config, f'subscription_days_{plan_index}')
    return 'subscribe' if subscription_days > 0 else 'one_time'


def resolve_default_vip_plan_key(config: dict) -> str:
    for field_name in ('default_plan', 'default_plan_key', 'default_product_id', 'selected_plan', 'recommended_plan'):
        normalized_value = _resolve_configured_plan_key(_get_vip_plan_config_str(config, field_name))
        if normalized_value:
            return normalized_value
    return ''


def get_vip_plan_config_snapshot(product_id: str) -> tuple[dict, str, int]:
    normalized_product_id = normalize_vip_plan_key(product_id)
    if not normalized_product_id:
        raise ValueError('缺少套餐标识')
    config = fetch_vip_plan_config()
    plan_index = int(normalized_product_id.split('_', 1)[1])
    return config, normalized_product_id, plan_index


def get_vip_plan_benefits(product_id: str) -> dict:
    config, normalized_product_id, plan_index = get_vip_plan_config_snapshot(product_id)
    if not normalized_product_id.startswith('plan_'):
        raise ValueError(f'无效的套餐标识: {normalized_product_id or product_id}')
    subscription_days = _get_vip_plan_config_int(config, f'validity_days_{plan_index}')
    if subscription_days <= 0:
        subscription_days = _get_vip_plan_config_int(config, f'duration_days_{plan_index}')
    if subscription_days <= 0:
        subscription_days = _get_vip_plan_config_int(config, f'subscription_days_{plan_index}')
    points = _get_vip_plan_config_int(config, f'points_{plan_index}')
    pay_type = resolve_vip_plan_pay_type(config, normalized_product_id)
    discount_price = parse_money_amount(_get_vip_plan_config_str(config, f'discount_price_{plan_index}'))
    return {
        'product_id': normalized_product_id,
        'subscription_days': subscription_days,
        'points': points,
        'pay_type': pay_type,
        'discount_price': discount_price,
    }


def get_payment_points_amount(package_id: str) -> int:
    benefits = get_vip_plan_benefits(package_id)
    return max(int(benefits.get('points') or 0), 0)


def get_subscription_days(product_id: str) -> int:
    benefits = get_vip_plan_benefits(product_id)
    subscription_days = max(int(benefits.get('subscription_days') or 0), 0)
    normalized_product_id = str(benefits.get('product_id') or '').strip()
    if subscription_days <= 0:
        raise ValueError(f'订阅商品 {normalized_product_id or product_id} 未配置有效时长')
    return subscription_days


def generate_payment_order_no() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:12]}"[:32]






def _iso_utc_from_ts(timestamp: float | int | None) -> str:
    try:
        normalized = float(timestamp)
    except (TypeError, ValueError):
        normalized = time.time()
    return datetime.fromtimestamp(normalized, timezone.utc).isoformat()



def _build_task_trace_patch(task: dict | None, stage: str, now_ts: float | None = None, extra: dict | None = None) -> dict:
    normalized_now = float(now_ts) if isinstance(now_ts, (int, float)) else time.time()
    payload = task if isinstance(task, dict) else {}
    trace = payload.get('trace') if isinstance(payload.get('trace'), dict) else {}
    trace_events = list(trace.get('events') or [])
    event = {
        'stage': str(stage or '').strip() or 'unknown',
        'ts': normalized_now,
        'at': _iso_utc_from_ts(normalized_now),
    }
    if isinstance(extra, dict):
        for key, value in extra.items():
            if value is not None:
                event[key] = value
    trace_events.append(event)
    next_trace = dict(trace)
    next_trace['events'] = trace_events[-40:]
    if trace_events:
        next_trace['last_stage'] = trace_events[-1].get('stage') or ''
        next_trace['last_at'] = trace_events[-1].get('at') or ''
        next_trace['last_ts'] = trace_events[-1].get('ts') or normalized_now
    return {'trace': next_trace}


def _trace_ts(event: dict | None) -> float | None:
    if not isinstance(event, dict):
        return None
    try:
        return float(event.get('ts'))
    except (TypeError, ValueError):
        return None


def _elapsed_ms_between(start_event: dict | None, end_event: dict | None) -> int | None:
    start_ts = _trace_ts(start_event)
    end_ts = _trace_ts(end_event)
    if start_ts is None or end_ts is None:
        return None
    return int(max((end_ts - start_ts) * 1000, 0))


def _first_trace_event(events: list, stage: str) -> dict | None:
    return next((event for event in events if isinstance(event, dict) and event.get('stage') == stage), None)


def _last_trace_event(events: list, stage: str) -> dict | None:
    return next((event for event in reversed(events) if isinstance(event, dict) and event.get('stage') == stage), None)


def summarize_generation_task_trace(task: dict | None) -> dict:
    payload = task if isinstance(task, dict) else {}
    task_trace = payload.get('trace') if isinstance(payload.get('trace'), dict) else {}
    result_payload = payload.get('result') if isinstance(payload.get('result'), dict) else {}
    result_trace = result_payload.get('trace') if isinstance(result_payload.get('trace'), dict) else {}
    events = [event for event in list(task_trace.get('events') or []) + list(result_trace.get('events') or []) if isinstance(event, dict)]
    events.sort(key=lambda event: _trace_ts(event) or 0)
    task_created = _first_trace_event(events, 'task_created')
    task_running = _first_trace_event(events, 'task_running')
    storage_started = _first_trace_event(events, 'image_storage_started')
    storage_completed = _last_trace_event(events, 'image_storage_completed')
    result_ready = _last_trace_event(events, 'task_result_ready')
    task_succeeded = _last_trace_event(events, 'task_succeeded')
    task_polled = _last_trace_event(events, 'task_polled')
    return {
        'task_id': payload.get('task_id') or '',
        'mode': payload.get('mode') or '',
        'status': payload.get('status') or '',
        'event_count': len(events),
        'task_queue_ms': _elapsed_ms_between(task_created, task_running),
        'backend_until_ready_ms': _elapsed_ms_between(task_running, result_ready),
        'storage_ms': _elapsed_ms_between(storage_started, storage_completed),
        'ready_to_succeeded_ms': _elapsed_ms_between(result_ready, task_succeeded),
        'task_total_ms': _elapsed_ms_between(task_created, task_succeeded),
        'poll_after_success_ms': _elapsed_ms_between(task_succeeded, task_polled),
        'created_at': task_created.get('at') if isinstance(task_created, dict) else payload.get('created_at') or '',
        'result_ready_at': result_ready.get('at') if isinstance(result_ready, dict) else '',
        'succeeded_at': task_succeeded.get('at') if isinstance(task_succeeded, dict) else payload.get('completed_at') or '',
        'last_stage': task_trace.get('last_stage') or result_trace.get('last_stage') or '',
    }


def log_generation_task_trace_summary(task: dict | None, label: str = 'task_summary') -> dict:
    summary = summarize_generation_task_trace(task)
    logger.info('Generation task trace summary %s: %s', label, json.dumps(summary, ensure_ascii=False, separators=(',', ':')))
    return summary



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


def _start_periodic_cleanup():
    def _run():
        while True:
            time.sleep(600)
            cleanup_generation_tasks()

    t = threading.Thread(target=_run, daemon=True)
    t.start()


_start_periodic_cleanup()


def create_generation_task(user_id: str, mode: str, request_id: str = '', spend_record: dict | None = None) -> dict:
    now = time.time()
    created_at_iso = _iso_utc_from_ts(now)
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
        'created_at': created_at_iso,
        'updated_at': created_at_iso,
        'created_at_ts': now,
        'updated_at_ts': now,
        'trace': {
            'events': [
                {
                    'stage': 'task_created',
                    'ts': now,
                    'at': created_at_iso,
                    'mode': str(mode or 'suite').strip() or 'suite',
                }
            ],
            'last_stage': 'task_created',
            'last_at': created_at_iso,
            'last_ts': now,
        },
    }
    cache_generation_task(task)
    persist_generation_task(task)
    with GENERATION_TASKS_LOCK:
        GENERATION_TASK_CANCEL_EVENTS[task_id] = threading.Event()
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
        now_ts = time.time()
        task['updated_at'] = _iso_utc_from_ts(now_ts)
        task['updated_at_ts'] = now_ts
        snapshot = dict(task)
    persist_generation_task(snapshot)
    return snapshot


def get_generation_task(task_id: str, prefer_cache: bool = False) -> dict | None:
    normalized_task_id = str(task_id or '').strip()
    if not normalized_task_id:
        return None
    if prefer_cache:
        with GENERATION_TASKS_LOCK:
            task = GENERATION_TASKS.get(normalized_task_id)
            if task:
                return dict(task)
    db_task = normalize_generation_task_row(fetch_generation_task_row(normalized_task_id))
    if db_task:
        with GENERATION_TASKS_LOCK:
            cached_task = GENERATION_TASKS.get(normalized_task_id)
            if cached_task and cached_task.get('updated_at_ts') and db_task.get('updated_at_ts'):
                if float(cached_task.get('updated_at_ts') or 0) >= float(db_task.get('updated_at_ts') or 0):
                    return dict(cached_task)
        cache_generation_task(db_task)
        return db_task
    with GENERATION_TASKS_LOCK:
        task = GENERATION_TASKS.get(normalized_task_id)
        return dict(task) if task else None


def maybe_fail_stale_generation_task(task: dict | None) -> dict | None:
    if not isinstance(task, dict):
        return task
    status = str(task.get('status') or '').strip().lower()
    if status not in {'pending', 'running'}:
        return task
    now_ts = time.time()
    created_ts = float(task.get('created_at_ts') or task.get('updated_at_ts') or now_ts)
    elapsed_seconds = max(now_ts - created_ts, 0)
    queue_timeout_seconds = max(int(os.getenv('GENERATION_TASK_QUEUE_TIMEOUT_SECONDS') or 180), 180)
    running_timeout_seconds = max(int(os.getenv('GENERATION_TASK_RUNNING_TIMEOUT_SECONDS') or 600), 300)
    timeout_seconds = queue_timeout_seconds if status == 'pending' else running_timeout_seconds
    if elapsed_seconds < timeout_seconds:
        return task
    error = '生成任务排队超时，请重新发起生成；如已扣分，系统已自动发起退回。' if status == 'pending' else '生成任务执行超时，请重新发起生成；如已扣分，系统已自动发起退回。'
    details = 'task queue timeout before worker start' if status == 'pending' else 'task running timeout watchdog'
    stage = 'task_queue_timeout' if status == 'pending' else 'task_running_timeout_watchdog'
    failed_at = now_ts
    updated_task = update_generation_task(
        task.get('task_id'),
        status='failed',
        error=error,
        details=details,
        completed_at=_iso_utc_from_ts(failed_at),
        completed_at_ts=failed_at,
    )
    updated_task = update_generation_task(
        task.get('task_id'),
        **_build_task_trace_patch(
            updated_task,
            stage,
            now_ts=failed_at,
            extra={'elapsed_ms': int(elapsed_seconds * 1000), 'timeout_seconds': timeout_seconds},
        ),
    )
    refund_task_points(str(task.get('task_id') or ''))
    logger.warning('Generation task %s stale timeout: status=%s elapsed=%ss timeout=%ss', task.get('task_id'), status, int(elapsed_seconds), timeout_seconds)
    return updated_task or get_generation_task(str(task.get('task_id') or ''), prefer_cache=True)


def serialize_generation_task(task: dict | None) -> dict:
    payload = task if isinstance(task, dict) else {}
    trace = payload.get('trace') if isinstance(payload.get('trace'), dict) else {}
    return {
        'task_id': payload.get('task_id'),
        'mode': payload.get('mode'),
        'request_id': payload.get('request_id') or '',
        'status': payload.get('status') or 'missing',
        'result': payload.get('result') if isinstance(payload.get('result'), dict) else None,
        'reference_analysis': payload.get('reference_analysis') if isinstance(payload.get('reference_analysis'), dict) else None,
        'error': payload.get('error') or '',
        'details': payload.get('details') or '',
        'refunded': bool(payload.get('refunded')),
        'refund_error': payload.get('refund_error') or '',
        'created_at': payload.get('created_at'),
        'created_at_ts': payload.get('created_at_ts'),
        'updated_at': payload.get('updated_at'),
        'updated_at_ts': payload.get('updated_at_ts'),
        'completed_at': payload.get('completed_at'),
        'completed_at_ts': payload.get('completed_at_ts'),
        'trace': trace,
    }


def _extract_history_image_url(image: dict) -> str:
    if not isinstance(image, dict):
        return ''
    for key in ('image_url', 'url', 'cos_url', 'src', 'href', 'download_url', 'thumbnail_url', 'thumb_url'):
        value = str(image.get(key) or '').strip()
        if value:
            return value
    return ''


def _is_displayable_history_image_url(image_url: str) -> bool:
    normalized_url = str(image_url or '').strip()
    if not normalized_url:
        return False
    return normalized_url.startswith(('http://', 'https://'))


def _build_history_webp_url(image_url: str) -> str:
    normalized_url = str(image_url or '').strip()
    if not normalized_url:
        return ''
    if 'aiimg.86969678.xyz' in normalized_url and 'imageMogr2/' not in normalized_url:
        separator = '&' if '?' in normalized_url else '?'
        return f'{normalized_url}{separator}imageMogr2/format/webp'
    return normalized_url


def _build_history_thumb_url(image_url: str) -> str:
    normalized_url = str(image_url or '').strip()
    if not normalized_url:
        return ''
    if 'aiimg.86969678.xyz' in normalized_url and 'imageMogr2/' not in normalized_url:
        separator = '&' if '?' in normalized_url else '?'
        return f'{normalized_url}{separator}imageMogr2/thumbnail/800x800/format/webp'
    return normalized_url


def _strip_history_image_process_query(image_url: str) -> str:
    normalized_url = str(image_url or '').strip()
    if not normalized_url:
        return ''
    marker = '?imageMogr2/'
    marker_index = normalized_url.find(marker)
    if marker_index >= 0:
        return normalized_url[:marker_index]
    marker = '&imageMogr2/'
    marker_index = normalized_url.find(marker)
    if marker_index >= 0:
        return normalized_url[:marker_index]
    return normalized_url


def _build_history_download_filename(url: str, index: int) -> str:
    parsed = urlparse(str(url or ''))
    basename = os.path.basename(parsed.path or '')
    name = sanitize_filename_part(os.path.splitext(basename)[0] or f'image-{index + 1}')
    ext = os.path.splitext(basename)[1].lower()
    if not ext or len(ext) > 8:
        ext = '.jpg'
    return f'{index + 1:03d}-{name}{ext}'


def _download_history_image(url: str) -> tuple[bytes, str]:
    normalized_url = _strip_history_image_process_query(url)
    response = requests.get(normalized_url, timeout=20)
    response.raise_for_status()
    content_type = str(response.headers.get('content-type') or '').lower()
    if content_type and not content_type.startswith('image/'):
        raise ValueError('下载地址不是图片')
    content = response.content or b''
    if not content:
        raise ValueError('图片内容为空')
    return content, normalized_url


def _guess_history_image_mimetype(url: str) -> str:
    guessed_type = mimetypes.guess_type(urlparse(str(url or '')).path or '')[0]
    if guessed_type and guessed_type.startswith('image/'):
        return guessed_type
    return 'application/octet-stream'


def serialize_generation_history_item(task: dict | None, image: dict | None, index: int) -> dict | None:
    payload = task if isinstance(task, dict) else {}
    image_payload = image if isinstance(image, dict) else {}
    image_url = _extract_history_image_url(image_payload)
    if not _is_displayable_history_image_url(image_url):
        return None
    task_id = str(payload.get('task_id') or payload.get('id') or '').strip()
    title = str(image_payload.get('title') or image_payload.get('label') or payload.get('details') or payload.get('mode') or '历史图片').strip()
    tags = image_payload.get('tags') if isinstance(image_payload.get('tags'), list) else []
    return {
        'id': str(image_payload.get('id') or image_payload.get('key') or f'{task_id}-{index}'),
        'user_id': str(payload.get('user_id') or '').strip(),
        'task_id': task_id,
        'mode': payload.get('mode') or '',
        'status': payload.get('status') or '',
        'title': title,
        'tags': [str(tag) for tag in tags if str(tag or '').strip()],
        'original_url': image_url,
        'image_url': _build_history_webp_url(image_url),
        'thumb_url': _build_history_thumb_url(image_url),
        'source': 'COS' if image_url.startswith(('http://', 'https://')) else 'generated',
        'created_at': payload.get('created_at'),
        'created_at_ts': payload.get('created_at_ts'),
        'completed_at': payload.get('completed_at'),
        'completed_at_ts': payload.get('completed_at_ts'),
    }


def serialize_generation_history_items(task: dict | None) -> list[dict]:
    payload = task if isinstance(task, dict) else {}
    if payload.get('status') != 'succeeded':
        return []
    result = payload.get('result') if isinstance(payload.get('result'), dict) else {}
    items = []
    for key in ('images', 'items', 'outputs'):
        pool = result.get(key)
        if not isinstance(pool, list):
            continue
        for image in pool:
            item = serialize_generation_history_item(payload, image, len(items))
            if item:
                items.append(item)
    return items


def fail_generation_task_with_refund(task_id: str, error: str, details: str = '', skip_refund: bool = False):
    failed_at = time.time()
    task = update_generation_task(
        task_id,
        status='failed',
        error=str(error or '生成失败'),
        details=str(details or ''),
        completed_at=_iso_utc_from_ts(failed_at),
        completed_at_ts=failed_at,
    )
    if task:
        task = update_generation_task(task_id, **_build_task_trace_patch(task, 'task_failed', now_ts=failed_at, extra={'error': str(error or '生成失败')}))
        logger.warning('Generation task %s failed: mode=%s error=%s', task_id, (task or {}).get('mode') or '', str(error or '生成失败'))
    if not task:
        return
    if skip_refund:
        update_generation_task(task_id, refund_error='任务已在执行中取消，积分不予返还')
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
        logger.warning('Failed to refund generation task %s: %s', task_id, exc)
        update_generation_task(task_id, refund_error=str(exc))


def _run_with_timeout(fn, timeout: int, error_message: str):
    import threading as _threading
    result_container = []
    err_container = []
    done = _threading.Event()

    def _worker():
        try:
            result_container.append(fn())
        except Exception as exc:
            err_container.append(exc)
        done.set()

    _threading.Thread(target=_worker, daemon=True).start()
    if not done.wait(timeout):
        raise TimeoutError(error_message)
    if err_container:
        raise err_container[0]
    return result_container[0]


def is_generation_task_cancelled(task_id: str) -> bool:
    cancel_event = GENERATION_TASK_CANCEL_EVENTS.get(task_id)
    return cancel_event is not None and cancel_event.is_set()


def check_generation_task_cancelled(task_id: str) -> None:
    if is_generation_task_cancelled(task_id):
        raise RuntimeError('生成任务已取消')


def run_background_generation_task(task_id: str, builder, timeout: int = 600, timeout_error: str = '生成任务执行超时（10分钟），请稍后重试'):
    cancel_event = GENERATION_TASK_CANCEL_EVENTS.get(task_id)
    if cancel_event and cancel_event.is_set():
        logger.info('Generation task %s was cancelled before starting', task_id)
        return
    task = update_generation_task(task_id, status='running', generation_started=False)
    task = update_generation_task(task_id, **_build_task_trace_patch(task, 'task_running', extra={'timeout_seconds': timeout}))
    started_at = time.time()
    logger.info('Generation task %s started: mode=%s timeout=%ss', task_id, (task or {}).get('mode') or '', timeout)
    try:
        result = _run_with_timeout(
            builder,
            timeout=timeout,
            error_message=timeout_error,
        )
        finished_at = time.time()
        current_task = get_generation_task(task_id)
        if current_task and current_task.get('status') == 'failed':
            logger.info('Generation task %s was cancelled, discarding result', task_id)
            return
        result_payload = result if isinstance(result, dict) else {'value': result}
        trace_payload = result_payload.get('trace') if isinstance(result_payload.get('trace'), dict) else {}
        trace_events = list(trace_payload.get('events') or [])
        image_items = []
        if isinstance(result_payload.get('images'), list):
            image_items.extend(item for item in result_payload.get('images') if isinstance(item, dict))
        model_payload = result_payload.get('model') if isinstance(result_payload.get('model'), dict) else None
        if model_payload and isinstance(model_payload.get('trace'), dict):
            image_items.append(model_payload)
        if isinstance(result_payload.get('image_url'), str) and isinstance(result_payload.get('trace'), dict):
            image_items.append(result_payload)
        merged_trace_events = []
        for item in image_items:
            item_trace = item.get('trace') if isinstance(item.get('trace'), dict) else {}
            for event in item_trace.get('events') or []:
                if isinstance(event, dict):
                    merged_trace_events.append(event)
        if merged_trace_events:
            merged_trace_events.sort(key=lambda item: float(item.get('ts') or 0))
            trace_events.extend(merged_trace_events)
        trace_events.append({
            'stage': 'task_result_ready',
            'ts': finished_at,
            'at': _iso_utc_from_ts(finished_at),
            'elapsed_ms': int(max((finished_at - started_at) * 1000, 0)),
        })
        trace_payload['events'] = trace_events[-40:]
        trace_payload['last_stage'] = 'task_result_ready'
        trace_payload['last_at'] = _iso_utc_from_ts(finished_at)
        trace_payload['last_ts'] = finished_at
        result_payload['trace'] = trace_payload
        task = update_generation_task(
            task_id,
            status='succeeded',
            result=result_payload,
            reference_analysis=result_payload.get('reference_analysis'),
            error='',
            details='',
            completed_at=_iso_utc_from_ts(finished_at),
            completed_at_ts=finished_at,
        )
        task = update_generation_task(task_id, **_build_task_trace_patch(task, 'task_succeeded', now_ts=finished_at, extra={'elapsed_ms': int(max((finished_at - started_at) * 1000, 0))}))
        history_items = serialize_generation_history_items(task)
        if history_items:
            upsert_generation_history_images(history_items, logger)
        log_generation_task_trace_summary(task, 'succeeded')
        logger.info('Generation task %s succeeded: mode=%s elapsed=%sms', task_id, (task or {}).get('mode') or '', int(max((finished_at - started_at) * 1000, 0)))
    except TimeoutError:
        failed_at = time.time()
        task = update_generation_task(task_id, status='failed', error=timeout_error, details='task execution timeout', completed_at=_iso_utc_from_ts(failed_at), completed_at_ts=failed_at)
        update_generation_task(task_id, **_build_task_trace_patch(task, 'task_timeout', now_ts=failed_at, extra={'elapsed_ms': int(max((failed_at - started_at) * 1000, 0)), 'timeout_seconds': timeout}))
        refund_task_points(task_id)
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
        logger.exception('Generation task failed: %s', task_id)
        fail_generation_task_with_refund(task_id, f'服务端异常：{exc}', str(exc))
    finally:
        import gc
        gc.collect()


def update_generation_task_partial_result(task_id: str, result_patch: dict | None = None, stage: str = '', extra: dict | None = None) -> dict | None:
    patch = {}
    if isinstance(result_patch, dict):
        patch['result'] = result_patch
    task = update_generation_task(task_id, **patch) if patch else get_generation_task(task_id)
    if stage:
        task = update_generation_task(task_id, **_build_task_trace_patch(task, stage, extra=extra))
    return task



def run_generation_task(task_id: str, form_payload: dict, file_payloads: dict):
    run_background_generation_task(
        task_id,
        lambda: build_generation_result_from_payload(form_payload, file_payloads),
        timeout=600,
        timeout_error='生成任务执行超时（10分钟），请稍后重试',
    )


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
    normalized_status = str((order_row or {}).get('status') or '').strip().lower()
    return normalized_status in {'paid', 'success'}


def validate_callback_amount(order_row: dict, callback_money: str) -> None:
    order_amount = parse_money_amount((order_row or {}).get('amount'))
    paid_amount = parse_money_amount(callback_money)
    if order_amount != paid_amount:
        raise ValueError('订单金额不匹配')


def process_success_payment(order_row: dict, callback_trade_no: str) -> dict:
    out_trade_no = get_payment_order_no(order_row)
    if not out_trade_no:
        raise ValueError('订单号缺失')
    callback_payload = normalize_callback_payload()
    payment_method = str((callback_payload or {}).get('type') or '').strip() or str((order_row or {}).get('payment_method') or '').strip() or None
    patch_payload = {
        'status': 'success',
        'zpay_trade_no': str(callback_trade_no or '').strip() or None,
        'paid_at': datetime.now(timezone.utc).isoformat(),
        'payment_method': payment_method,
        'callback_payload': callback_payload,
    }

    try:
        grant_payment_points_once(order_row)
    except (requests.RequestException, RuntimeError, ValueError):
        logger.exception('Failed to grant payment points after payment success: out_trade_no=%s', out_trade_no)

    updated_row = update_payment_order(out_trade_no, patch_payload)

    if get_payment_pay_type(updated_row).lower() == 'subscription':
        user_id = str((updated_row or {}).get('user_id') or '').strip()
        subscribe_expire = get_payment_subscribe_expire(updated_row)
        if user_id and subscribe_expire:
            try:
                upsert_user_subscription_profile(user_id, subscribe_expire)
            except requests.RequestException:
                logger.exception('Failed to sync subscription profile after payment success: out_trade_no=%s user_id=%s', out_trade_no, user_id)
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










def _is_settings_user_allowed(session_data: dict | None = None) -> bool:
    allowed_emails = get_settings_allowed_emails()
    allowed_phones = {_normalize_phone_identifier(phone) for phone in get_settings_allowed_phones()}
    user_email = _get_supabase_user_email(session_data)
    user_phone = _get_supabase_user_phone(session_data)
    return bool(
        (user_email and user_email in allowed_emails)
        or (user_phone and user_phone in allowed_phones)
    )














def _get_supabase_user_email(session_data: dict | None = None) -> str:
    session_payload = session_data or g.get('supabase_session') or {}
    user = session_payload.get('user') or {}
    return str(user.get('email') or '').strip().lower()


def _get_supabase_user_phone(session_data: dict | None = None) -> str:
    session_payload = session_data or g.get('supabase_session') or {}
    user = session_payload.get('user') or {}
    metadata = user.get('user_metadata') or {}
    return _normalize_phone_identifier(user.get('phone') or metadata.get('phone') or metadata.get('phone_number'))




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


















UPLOAD_MAX_BYTES = max(get_supabase_setting_int('UPLOAD_MAX_BYTES', 15 * 1024 * 1024), 1)
UPLOAD_MAX_FILE_BYTES = max(get_supabase_setting_int('UPLOAD_MAX_FILE_BYTES', 8 * 1024 * 1024), 1)
GENERATED_SUITE_RETENTION_DAYS = max(get_supabase_setting_int('GENERATED_SUITE_RETENTION_DAYS', 7), 0)
GENERATED_SUITE_RETENTION_COUNT = max(get_supabase_setting_int('GENERATED_SUITE_RETENTION_COUNT', 20), 0)
POINTS_SIGNUP_BONUS = max(get_supabase_setting_int('POINTS_SIGNUP_BONUS', 100), 0)
POINTS_DAILY_FREE = max(get_supabase_setting_int('POINTS_DAILY_FREE', 10), 0)
MODE2_ALLOWED_IMAGE_HOSTS = get_mode2_allowed_image_hosts()
app.config['MAX_CONTENT_LENGTH'] = UPLOAD_MAX_BYTES










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


def get_supabase_session() -> dict | None:
    session_data = parse_supabase_session_cookie()
    if not session_data:
        return None
    access_token = str(session_data.get('access_token') or '').strip()
    if not access_token:
        return None

    fallback_user = session_data.get('user') if isinstance(session_data.get('user'), dict) else None
    user_id = str((fallback_user or {}).get('id') or '').strip()
    cache_key = f'{user_id}:{access_token[-20:]}'

    with _SESSION_CACHE_LOCK:
        cached = _SESSION_CACHE.get(cache_key)
        if cached and time.time() - cached[0] < _SESSION_CACHE_TTL:
            return dict(cached[1])

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
            fallback_result = dict(session_data)
            if fallback_user:
                fallback_result['user'] = fallback_user
            return fallback_result
        if response.status_code == 200:
            session_data['user'] = response.json()
        elif fallback_user:
            session_data['user'] = fallback_user
    else:
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
            session_data['user'] = response.json()
        else:
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
                result = dict(refreshed_session)
                _cache_session(cache_key, result)
                return result
            if refreshed_response.status_code == 200:
                refreshed_session['user'] = refreshed_response.json()
            elif fallback_user and not refreshed_session.get('user'):
                refreshed_session['user'] = fallback_user
            result = dict(refreshed_session)
            _cache_session(cache_key, result)
            return result

    result = dict(session_data)
    _cache_session(cache_key, result)
    return result


def _cache_session(cache_key: str, session_data: dict) -> None:
    with _SESSION_CACHE_LOCK:
        _SESSION_CACHE[cache_key] = (time.time(), dict(session_data))
        stale = [k for k, v in _SESSION_CACHE.items() if time.time() - v[0] > _SESSION_CACHE_TTL]
        for k in stale:
            _SESSION_CACHE.pop(k, None)


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


def auth_response_from_session(session_data: dict, redirect_path: str | None = None):
    target_path = redirect_path or '/suite'
    response = redirect(target_path)
    set_auth_session_cookie(response, session_data)
    return response


def require_auth_session() -> dict | None:
    session_data = get_supabase_session()
    g.supabase_session = session_data
    g.supabase_user = (session_data or {}).get('user') if session_data else None
    return session_data
























def build_local_or_remote_image_payload(image_url: str):
    normalized_url = str(image_url or '').strip()
    if normalized_url.startswith('/generated/'):
        relative_path = normalized_url[len('/generated/'):].lstrip('/').replace('\\', '/')
        candidate_path = (GENERATED_SUITES_DIR / relative_path).resolve()
        generated_root = GENERATED_SUITES_DIR.resolve()
        if generated_root not in candidate_path.parents and candidate_path != generated_root:
            raise ValueError('参考图片路径无效')
        if not candidate_path.exists() or not candidate_path.is_file():
            raise ValueError('参考图片文件不存在')
        content = candidate_path.read_bytes()
        mime_type = sniff_image_mime_type(content)
        if not mime_type:
            raise ValueError('参考图片不是有效的图片文件')
        if len(content) > UPLOAD_MAX_FILE_BYTES:
            raise ValueError(f'参考图片超过单张大小限制（{UPLOAD_MAX_FILE_BYTES // (1024 * 1024)}MB）')
        filename = candidate_path.name or 'reference-image'
        return LazyImagePayload(filename=filename, mime_type=mime_type, content=content)
    return build_remote_image_payload(normalized_url)


def get_image_payloads_from_request(field_name: str = 'images', limit: int = MAX_IMAGE_UPLOADS, url_field_name: str | None = None):
    image_files = request.files.getlist(field_name)
    image_urls = []
    if url_field_name:
        image_urls = [str(item or '').strip() for item in request.form.getlist(url_field_name) if str(item or '').strip()]
    total_count = len(image_files) + len(image_urls)
    if total_count > limit:
        raise ValueError(f'最多仅支持上传 {limit} 张图片')
    payloads = []
    for image_file in image_files:
        payloads.append(create_image_payload(image_file))
    for image_url in image_urls:
        payloads.append(build_local_or_remote_image_payload(image_url))
    return payloads




FASHION_DEFAULT_PLATFORM = '服饰穿搭'
FASHION_DEFAULT_COUNTRY = '中国'
FASHION_DEFAULT_TEXT_TYPE = '中文'
FASHION_DEFAULT_SELLING_TEXT = ''
FASHION_DEFAULT_SELECTED_STYLE = None


FASHION_SCENE_PLAN_MODEL_TIMEOUT_SECONDS = 120


def parse_fashion_selected_model_payload(form):
    selected_payloads = get_image_payloads_from_request('fashion_selected_model_image', limit=1)
    if not selected_payloads:
        model_image_url = str(form.get('fashion_selected_model_image_url') or '').strip()
        if model_image_url:
            selected_payloads = [build_local_or_remote_image_payload(model_image_url)]
    return parse_fashion_selected_model_payload_from_data(form, selected_payloads)


FASHION_MODEL_APPEARANCE_FALLBACK = '五官自然立体，肤质真实细腻，整体形象干净利落'


class RetryableMode2ResponseError(RuntimeError):
    pass
























@app.before_request
def guard_authentication():
    path = request.path.rstrip('/') or '/'
    if path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
        g.supabase_session = get_supabase_session()
        g.supabase_user = (g.supabase_session or {}).get('user') if g.supabase_session else None
        g.admin_session = get_admin_session()
        return None

    if path in {'/api/generate-mode2-image-edit-test', '/api/fashion-models/upload', '/api/fashion-products/upload', '/api/reference-images/upload'} and request.method == 'POST':
        g.supabase_session = get_supabase_session()
        g.supabase_user = (g.supabase_session or {}).get('user') if g.supabase_session else None
        g.admin_session = get_admin_session()
        return None

    if any(path.startswith(prefix) for prefix in PUBLIC_API_PREFIXES):
        g.supabase_session = get_supabase_session()
        g.supabase_user = (g.supabase_session or {}).get('user') if g.supabase_session else None
        g.admin_session = get_admin_session()
        return None

    if path == '/api/generate-replicate' and request.method == 'POST':
        async_task = str(request.form.get('async_task') or '').strip().lower() in {'1', 'true', 'yes'}
        if not async_task:
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

    if path in {'/api/generate-mode2-image-edit-test', '/api/fashion-models/upload', '/api/fashion-products/upload', '/api/reference-images/upload'} and request.method == 'POST':
        g.supabase_session = get_supabase_session()
        g.supabase_user = (g.supabase_session or {}).get('user') if g.supabase_session else None
        g.admin_session = get_admin_session()
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
        requested_amount = parse_money_amount(payload.get('amount'))

        if not request_user_id:
            return jsonify({'error': 'MISSING_USER_ID', 'message': '缺少 user_id'}), 400
        if request_user_id != user_id:
            return jsonify({'error': 'USER_MISMATCH', 'message': 'user_id 与当前登录用户不匹配'}), 403
        if not product_id:
            return jsonify({'error': 'MISSING_PRODUCT_ID', 'message': '缺少 product_id'}), 400

        plan_benefits = get_vip_plan_benefits(product_id)
        product_id = str(plan_benefits.get('product_id') or product_id).strip()
        pay_type = str(plan_benefits.get('pay_type') or 'one_time').strip()
        amount = parse_money_amount(plan_benefits.get('discount_price'))
        if requested_amount != amount:
            return jsonify({'error': 'AMOUNT_MISMATCH', 'message': '支付金额与套餐配置不一致'}), 400
        if pay_type not in {'one_time', 'subscribe'}:
            return jsonify({'error': 'INVALID_PAY_TYPE', 'message': 'Supabase 套餐 pay_type 配置无效'}), 400

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
        logger.exception('Failed to create payment order')
        return jsonify({'error': 'SUPABASE_REQUEST_FAILED', 'message': f'支付订单创建失败：{exc}'}), 502
    except RuntimeError as exc:
        return jsonify({'error': 'PAYMENT_CONFIG_ERROR', 'message': str(exc)}), 500
    except Exception as exc:
        logger.exception('Unexpected error while creating payment order')
        return jsonify({'error': 'CREATE_PAY_ORDER_FAILED', 'message': f'创建支付订单失败：{exc}'}), 500


@app.route('/api/pay/notify', methods=['GET', 'POST'])
def pay_notify_api():
    try:
        payload = normalize_callback_payload()
        out_trade_no = str(payload.get('out_trade_no') or '').strip()
        callback_trade_no = str(payload.get('trade_no') or '').strip()
        callback_money = str(payload.get('money') or '').strip()
        trade_status = str(payload.get('trade_status') or '').strip().upper()

        logger.warning('ZPAY notify received: method=%s out_trade_no=%s trade_no=%s trade_status=%s payload=%s', request.method, out_trade_no, callback_trade_no, trade_status, payload)

        if not verify_zpay_callback_signature(payload):
            logger.warning('ZPAY notify invalid sign: out_trade_no=%s payload=%s', out_trade_no, payload)
            return 'fail', 400
        if not out_trade_no:
            logger.warning('ZPAY notify missing out_trade_no: payload=%s', payload)
            return 'fail', 400
        if trade_status not in ZPAY_SUCCESS_STATUSES:
            logger.warning('ZPAY notify invalid trade_status: out_trade_no=%s trade_status=%s payload=%s', out_trade_no, trade_status, payload)
            return 'fail', 400

        order_row = fetch_payment_order_by_out_trade_no(out_trade_no)
        if not order_row:
            logger.warning('ZPAY notify order not found: out_trade_no=%s payload=%s', out_trade_no, payload)
            return 'fail', 404
        if is_order_success(order_row):
            existing_trade_no = get_payment_trade_no(order_row)
            if existing_trade_no and callback_trade_no and existing_trade_no == callback_trade_no:
                logger.warning('ZPAY notify duplicate success ignored: out_trade_no=%s trade_no=%s', out_trade_no, callback_trade_no)
                return 'success', 200
            try:
                grant_payment_points_once(order_row)
            except Exception:
                logger.exception('Failed to grant payment points on retry: out_trade_no=%s', out_trade_no)
            return 'success', 200

        validate_callback_amount(order_row, callback_money)
        process_success_payment(order_row, callback_trade_no)
        logger.warning('ZPAY notify processed success: out_trade_no=%s trade_no=%s', out_trade_no, callback_trade_no)
        return 'success', 200
    except ValueError as exc:
        logger.warning('ZPAY notify validation error: %s; payload=%s', exc, request.values.to_dict(flat=True) if request.values else {})
        return 'fail', 400
    except requests.RequestException as exc:
        logger.exception('Failed to process payment callback')
        return 'fail', 502
    except RuntimeError as exc:
        logger.warning('ZPAY notify config error: %s', exc)
        return 'fail', 500
    except Exception as exc:
        logger.exception('Unexpected error while processing payment callback')
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
    html = (BASE_DIR / 'pages' / filename).read_text(encoding='utf-8')
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


@app.get('/replicate')
def replicate_page():
    return render_html_page('replicate.html')


@app.get('/batch')
def batch_page():
    return render_html_page('batch.html')


@app.post('/api/batch/create')
def create_batch_task():
    try:
        session_data = g.get('supabase_session') or get_supabase_session()
        user_id = _get_supabase_user_id(session_data)
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录'}), 401
        
        config_str = request.form.get('config')
        tasks_str = request.form.get('tasks')
        
        if not config_str or not tasks_str:
            return jsonify({'success': False, 'error': '参数缺失'}), 400
        
        config = json.loads(config_str)
        tasks = json.loads(tasks_str)
        
        gen_type = config.get('genType', 'suite')
        output_count = int(config.get('outputCount', 6))
        
        total_output_count = len(tasks) * output_count
        
        consume_payload = build_points_consume_payload(
            gen_type,
            output_count=total_output_count,
            transaction_type='consume',
            reason=f'批量生图-{gen_type}',
            metadata={'batch_task_count': len(tasks), 'output_per_task': output_count},
        )
        points_cost = int(consume_payload['amount'])
        
        balance_row = get_user_points_balance(user_id)
        current_balance = int(balance_row.get('balance', 0)) if balance_row else 0
        
        if current_balance < points_cost:
            return jsonify({
                'success': False,
                'error': f'积分不足，需要 {points_cost} 积分，当前余额 {current_balance} 积分',
                'required': points_cost,
                'balance': current_balance,
            }), 400
        
        spend_result = spend_user_points(
            user_id,
            points_cost,
            'consume',
            f'批量生图-{gen_type}',
            {'batch_task_count': len(tasks), 'output_per_task': output_count, 'gen_type': gen_type},
        )
        
        if not spend_result or not spend_result.get('spent'):
            error_msg = spend_result.get('error', '积分扣除失败') if spend_result else '积分扣除失败'
            return jsonify({'success': False, 'error': error_msg}), 400
        
        from batch_models import create_batch_record, create_task_record
        import base64
        
        batch_result = create_batch_record(
            user_id=user_id,
            gen_type=gen_type,
            platform=config.get('platform'),
            country=config.get('country'),
            text_type=config.get('textType'),
            ratio=config.get('ratio'),
            selling_points=config.get('sellingPoints'),
            prompt_config=config.get('promptConfig'),
            total_tasks=len(tasks),
            points_cost=points_cost,
        )
        
        batch_id = batch_result['batch_id']
        
        for task in tasks:
            task_index = task.get('taskId')
            image_count = task.get('imageCount', 0)
            
            input_images = []
            for i in range(image_count):
                file_key = f'images_{task_index}_{i}'
                if file_key in request.files:
                    file = request.files[file_key]
                    if file and file.filename:
                        file_data = file.read()
                        image_data = {
                            'name': file.filename,
                            'type': file.content_type,
                            'data': base64.b64encode(file_data).decode('utf-8'),
                            'bytes': file_data,
                            'mime_type': file.content_type,
                        }
                        input_images.append(image_data)
            
            create_task_record(
                batch_id=batch_id,
                task_index=task_index,
                input_images=[{'name': img['name'], 'type': img['type']} for img in input_images],
            )
            
            from batch_worker import add_task_to_queue
            add_task_to_queue(
                batch_id=batch_id,
                task_id=f"{batch_id}_task_{task_index}",
                config=config,
                input_images=input_images,
                _logger=logger,
            )
        
        from batch_worker import start_task_processor
        start_task_processor(_logger=logger)
        
        return jsonify({
            'success': True,
            'data': {
                'batchId': batch_id,
                'taskCount': len(tasks),
                'status': 'pending',
                'createdAt': datetime.now(timezone.utc).isoformat(),
                'pointsCost': points_cost,
                'balance': spend_result.get('balance_row', {}).get('balance', 0),
            }
        })
    
    except Exception as e:
        logger.error(f"创建批量任务失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.get('/api/batch/<batch_id>/progress')
def get_batch_progress(batch_id: str):
    try:
        session_data = g.get('supabase_session') or get_supabase_session()
        user_id = _get_supabase_user_id(session_data)
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录'}), 401
        
        from batch_models import fetch_batch_progress
        
        progress = fetch_batch_progress(batch_id, user_id)
        
        if not progress:
            return jsonify({'success': False, 'error': '批次不存在'}), 404
        
        return jsonify({
            'success': True,
            'data': progress
        })
    
    except Exception as e:
        logger.error(f"查询批次进度失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.post('/api/batch/<batch_id>/cancel')
def cancel_batch_task(batch_id: str):
    try:
        session_data = g.get('supabase_session') or get_supabase_session()
        user_id = _get_supabase_user_id(session_data)
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录'}), 401
        
        from batch_models import cancel_batch as cancel_batch_db
        from batch_worker import cancel_batch as cancel_batch_queue
        
        db_result = cancel_batch_db(batch_id, user_id)
        
        queue_cancelled = cancel_batch_queue(batch_id, _logger=logger)
        
        return jsonify({
            'success': True,
            'data': {
                'batchId': batch_id,
                'status': 'cancelled',
                'queueCancelled': queue_cancelled
            }
        })
    
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"取消批次失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.get('/api/batch/queue/status')
def get_queue_status():
    try:
        session_data = g.get('supabase_session') or get_supabase_session()
        user_id = _get_supabase_user_id(session_data)
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录'}), 401
        
        from batch_worker import get_queue_status
        status = get_queue_status()
        
        return jsonify({
            'success': True,
            'data': status
        })
    
    except Exception as e:
        logger.error(f"获取队列状态失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.get('/api/batch/list')
def get_batch_list():
    try:
        session_data = g.get('supabase_session') or get_supabase_session()
        user_id = _get_supabase_user_id(session_data)
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录'}), 401

        from batch_models import BATCH_TABLE, TASK_TABLE
        
        batch_response = requests.get(
            build_supabase_request_url(f'/rest/v1/{BATCH_TABLE}'),
            headers=_build_supabase_service_headers(),
            params={
                'user_id': f'eq.{user_id}',
                'select': 'batch_id,status,total_tasks,completed_tasks,created_at,gen_type',
                'order': 'created_at.desc',
                'limit': '50'
            },
            timeout=20,
        )
        batches = batch_response.json()
        
        result = []
        for batch in batches:
            batch_id = batch.get('batch_id')
            
            tasks_response = requests.get(
                build_supabase_request_url(f'/rest/v1/{TASK_TABLE}'),
                headers=_build_supabase_service_headers(),
                params={
                    'batch_id': f'eq.{batch_id}',
                    'select': 'task_id,task_index,status,progress,current_step,result_images',
                    'order': 'task_index.asc'
                },
                timeout=20,
            )
            tasks = tasks_response.json()
            
            task_list = []
            for task in tasks:
                task_data = {
                    'taskId': task.get('task_index'),
                    'status': task.get('status'),
                    'progress': task.get('progress', 0),
                    'currentStep': task.get('current_step', ''),
                    'resultImages': json.loads(task.get('result_images', '[]')) if task.get('result_images') else [],
                }
                task_list.append(task_data)
            
            result.append({
                'batchId': batch_id,
                'status': batch.get('status'),
                'totalTasks': batch.get('total_tasks', 0),
                'completedTasks': batch.get('completed_tasks', 0),
                'createdAt': batch.get('created_at'),
                'genType': batch.get('gen_type'),
                'tasks': task_list
            })
        
        return jsonify({'success': True, 'data': result})
    
    except Exception as e:
        logger.error(f"获取批次列表失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.get('/api/batch/<batch_id>/download')
def download_batch_zip(batch_id: str):
    try:
        session_data = g.get('supabase_session') or get_supabase_session()
        user_id = _get_supabase_user_id(session_data)
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录'}), 401

        from batch_models import BATCH_TABLE, TASK_TABLE
        
        batch_response = requests.get(
            build_supabase_request_url(f'/rest/v1/{BATCH_TABLE}'),
            headers=_build_supabase_service_headers(),
            params={'batch_id': f'eq.{batch_id}', 'user_id': f'eq.{user_id}', 'select': 'batch_id,status'},
            timeout=20,
        )
        batch_data = batch_response.json()
        if not batch_data:
            return jsonify({'success': False, 'error': '批次不存在或无权限'}), 404

        tasks_response = requests.get(
            build_supabase_request_url(f'/rest/v1/{TASK_TABLE}'),
            headers=_build_supabase_service_headers(),
            params={'batch_id': f'eq.{batch_id}', 'select': 'result_images,status', 'status': 'eq.completed'},
            timeout=20,
        )
        tasks = tasks_response.json()

        image_urls = []
        for task in tasks:
            result_images_str = task.get('result_images')
            if not result_images_str:
                continue
            try:
                result_images = json.loads(result_images_str)
                for img in result_images:
                    img_url = img.get('url') or img.get('imagePath')
                    if img_url:
                        if img_url.startswith('/generated/'):
                            img_url = img_url[len('/generated/'):]
                        image_urls.append(img_url)
            except (json.JSONDecodeError, TypeError):
                continue

        if not image_urls:
            return jsonify({'success': False, 'error': '没有可下载的图片'}), 404

        run_async = str(request.args.get('async_task', '') or '').strip().lower() in {'1', 'true', 'yes'}

        if run_async:
            task = create_generation_task(user_id, 'download-zip')
            GENERATION_TASK_EXECUTOR.submit(
                run_background_generation_task,
                task['task_id'],
                lambda: build_zip_archive_result(image_urls),
                300,
                '图片打包超时（5分钟），请稍后重试',
            )
            return jsonify({'success': True, 'async_task': True, 'task': task, 'task_id': task['task_id']}), 202

        zip_result = build_zip_archive_result(image_urls)
        zip_file_path = (GENERATED_SUITES_DIR / zip_result['download_path']).resolve()

        return send_file(
            zip_file_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'batch_{batch_id}.zip'
        )

    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 404
    except Exception as exc:
        logger.error(f'批量下载失败: {exc}')
        return jsonify({'success': False, 'error': f'下载失败：{exc}'}), 500


@app.get('/settings')
def settings_page():
    return render_html_page('settings.html')


@app.get('/generation-record')
def generation_record_page():
    return render_html_page('generation-record.html')


@app.get('/generated/<path:path>')
def serve_generated_file(path: str):
    if is_cos_enabled() and not (GENERATED_SUITES_DIR / path).is_file():
        cos_url = f"{get_cos_url_prefix()}/{path}"
        return redirect(cos_url)
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
    existing_keys = {r['setting_key'] for r in records}
    if 'APP_MODE' not in existing_keys:
        current_mode = get_app_mode()
        records.append({
            'scope': scope,
            'setting_key': 'APP_MODE',
            'setting_value': current_mode,
            'value_preview': current_mode,
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


def build_zip_archive_result(image_paths: list[str]) -> dict:
    zip_id = uuid.uuid4().hex
    download_dir = GENERATED_SUITES_DIR / 'downloads'
    download_dir.mkdir(parents=True, exist_ok=True)
    zip_file_path = download_dir / f'ai-images-{datetime.now().strftime("%Y%m%d-%H%M%S")}-{zip_id[:8]}.zip'
    used_names = set()

    with zipfile.ZipFile(zip_file_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for index, raw_path in enumerate(image_paths, start=1):
            relative_path = str(raw_path or '').strip().replace('\\', '/').lstrip('/')
            if not relative_path:
                continue

            if relative_path.startswith('http://') or relative_path.startswith('https://'):
                try:
                    img_resp = requests.get(relative_path, timeout=30)
                    img_resp.raise_for_status()
                    img_bytes = img_resp.content
                    url_path = urlparse(relative_path).path
                    base_name = Path(url_path).name or f'image-{index:02d}.jpg'
                    stem = Path(base_name).stem or f'image-{index:02d}'
                    suffix = Path(base_name).suffix or '.jpg'
                    archive_name = f'{stem}{suffix}'
                    duplicate_index = 2
                    while archive_name in used_names:
                        archive_name = f'{stem}-{duplicate_index}{suffix}'
                        duplicate_index += 1
                    used_names.add(archive_name)
                    archive.writestr(archive_name, img_bytes)
                except Exception as exc:
                    logger.warning('Failed to download image for zip: %s', exc)
                continue

            file_path = (GENERATED_SUITES_DIR / relative_path).resolve()
            try:
                file_path.relative_to(GENERATED_SUITES_DIR.resolve())
            except ValueError:
                continue
            if file_path.is_file():
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
                continue

            if is_cos_enabled():
                try:
                    cos_url = f"{get_cos_url_prefix()}/{relative_path}"
                    img_resp = requests.get(cos_url, timeout=30)
                    img_resp.raise_for_status()
                    img_bytes = img_resp.content
                    base_name = Path(relative_path).name or f'image-{index:02d}.jpg'
                    stem = Path(base_name).stem or f'image-{index:02d}'
                    suffix = Path(base_name).suffix or '.jpg'
                    archive_name = f'{stem}{suffix}'
                    duplicate_index = 2
                    while archive_name in used_names:
                        archive_name = f'{stem}-{duplicate_index}{suffix}'
                        duplicate_index += 1
                    used_names.add(archive_name)
                    archive.writestr(archive_name, img_bytes)
                except Exception as exc:
                    logger.warning('Failed to download COS image for zip: %s', exc)
                continue

    if not used_names:
        try:
            zip_file_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise ValueError('未找到可下载的图片文件')

    relative_zip_path = zip_file_path.relative_to(GENERATED_SUITES_DIR).as_posix()
    download_name = zip_file_path.name
    return {
        'success': True,
        'mode': 'download-zip',
        'task_id': zip_id,
        'download_name': download_name,
        'download_path': relative_zip_path,
        'download_url': f'/generated/{relative_zip_path}',
        'total_files': len(used_names),
    }


@app.post('/api/download-zip')
def download_zip():
    try:
        payload = request.get_json(silent=True) or {}
        image_paths = payload.get('image_paths')
        if not isinstance(image_paths, list) or not image_paths:
            return jsonify({'success': False, 'error': '请至少选择 1 张图片后再下载'}), 400
        run_async = str(payload.get('async_task') or '').strip().lower() in {'1', 'true', 'yes'}

        if run_async:
            session_data = g.get('supabase_session') or get_supabase_session()
            user_id = _get_supabase_user_id(session_data)
            if not user_id:
                return jsonify({'success': False, 'error': '请先登录'}), 401
            task = create_generation_task(user_id, 'download-zip')
            GENERATION_TASK_EXECUTOR.submit(
                run_background_generation_task,
                task['task_id'],
                lambda: build_zip_archive_result(image_paths),
                300,
                '图片打包超时（5分钟），请稍后重试',
            )
            return jsonify({'success': True, 'async_task': True, 'task': task, 'task_id': task['task_id']}), 202

        zip_result = build_zip_archive_result(image_paths)
        zip_file_path = (GENERATED_SUITES_DIR / zip_result['download_path']).resolve()
        return send_file(zip_file_path, mimetype='application/zip', as_attachment=True, download_name=zip_result['download_name'])
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 404
    except Exception as exc:
        return jsonify({'success': False, 'error': f'打包下载失败：{exc}'}), 500


@app.post('/api/ai-write')
def ai_write():
    try:
        selling_text = request.form.get('selling_text', '').strip()
        image_payloads = get_image_payloads_from_request()
        run_async = str(request.form.get('async_task', '') or '').strip().lower() in {'1', 'true', 'yes'}

        if not selling_text and not image_payloads:
            return jsonify({'success': False, 'error': '请至少提供核心卖点文案或上传 1 张图片'}), 400

        def build_ai_write_result():
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
            return {'success': True, 'mode': 'ai-write', 'text': text, 'product_json': product_json}

        def build_ai_write_async_result(task_id: str):
            text_container: dict[str, str] = {}

            def build_text_result() -> str:
                text_value = call_chat_completion(
                    SYSTEM_PROMPT,
                    build_multimodal_content(
                        USER_PROMPT_TEMPLATE.format(selling_text=selling_text or '（未填写）'),
                        image_payloads,
                    ),
                    temperature=0.7,
                )
                text_container['text'] = text_value
                update_generation_task_partial_result(
                    task_id,
                    {
                        'success': True,
                        'mode': 'ai-write',
                        'text': text_value,
                        'product_json': None,
                        'product_json_pending': True,
                    },
                    'ai_write_text_ready',
                    {'product_json_pending': True},
                )
                return text_value

            def build_product_json_result() -> dict | None:
                product_selling_text = selling_text or '（未填写）'
                if not image_payloads and not product_selling_text:
                    return None
                product_json, _response_text = call_chat_json_with_repair(
                    PRODUCT_JSON_SYSTEM_PROMPT,
                    build_multimodal_content(
                        PRODUCT_JSON_USER_PROMPT_TEMPLATE.format(selling_text=product_selling_text),
                        image_payloads,
                    ),
                    parse_product_json,
                    '商品结构化信息格式异常',
                    temperature=0.2,
                    timeout_seconds=60,
                    repair_attempts=1,
                )
                return product_json

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                text_future = executor.submit(build_text_result)
                product_json_future = executor.submit(build_product_json_result)
                text = text_future.result()
                text_container['text'] = text
                product_json = product_json_future.result()

            return {
                'success': True,
                'mode': 'ai-write',
                'text': text_container.get('text') or '',
                'product_json': product_json,
                'product_json_pending': False,
            }

        if run_async:
            session_data = g.get('supabase_session') or get_supabase_session()
            user_id = _get_supabase_user_id(session_data)
            if not user_id:
                return jsonify({'success': False, 'error': '请先登录'}), 401
            task = create_generation_task(user_id, 'ai-write')
            GENERATION_TASK_EXECUTOR.submit(
                run_background_generation_task,
                task['task_id'],
                lambda: build_ai_write_async_result(task['task_id']),
                180,
                'AI 文案生成超时（3分钟），请稍后重试',
            )
            return jsonify({'success': True, 'async_task': True, 'task': task, 'task_id': task['task_id']}), 202

        return jsonify(build_ai_write_result())
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
        run_async = str(request.form.get('async_task', '') or '').strip().lower() in {'1', 'true', 'yes'}

        if not selling_text and not image_payloads:
            return jsonify({'success': False, 'error': '请至少提供核心卖点文案或上传 1 张图片'}), 400

        def build_style_analysis_result():
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
            return {'success': True, 'mode': 'style-analysis', 'styles': styles}

        if run_async:
            session_data = g.get('supabase_session') or get_supabase_session()
            user_id = _get_supabase_user_id(session_data)
            if not user_id:
                return jsonify({'success': False, 'error': '请先登录'}), 401
            task = create_generation_task(user_id, 'style-analysis')
            GENERATION_TASK_EXECUTOR.submit(
                run_background_generation_task,
                task['task_id'],
                build_style_analysis_result,
                180,
                '风格分析超时（3分钟），请稍后重试',
            )
            return jsonify({'success': True, 'async_task': True, 'task': task, 'task_id': task['task_id']}), 202

        return jsonify(build_style_analysis_result())
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


@app.post('/api/reference-images/upload')
def upload_reference_image_asset():
    try:
        image_file = request.files.get('file')
        if image_file is None:
            return jsonify({'success': False, 'error': '请上传参考图片文件'}), 400

        storage_group = str(request.form.get('storage_group') or 'temp').strip().strip('/').replace('..', '') or 'temp'
        if storage_group not in {'products', 'temp', 'fashion-models'}:
            storage_group = 'temp'
        storage_subdir = str(request.form.get('storage_subdir') or 'uploads').strip().strip('/').replace('..', '') or 'uploads'

        content = image_file.read()
        detected_mime_type = validate_image_file(image_file, content)
        safe_stem = sanitize_filename_part(Path(image_file.filename or 'reference-image').stem, 'reference-image')
        extension = guess_extension(detected_mime_type)
        filename = f'{safe_stem}{extension}'
        task_id = uuid.uuid4().hex

        if is_cos_enabled():
            try:
                image_key = generate_cos_key(task_id, filename, storage_group=storage_group)
                image_url = upload_to_cos(content, image_key, detected_mime_type)
                return jsonify({
                    'success': True,
                    'image_url': image_url,
                    'image_path': image_key,
                    'download_name': filename,
                    'mime_type': detected_mime_type,
                    'storage_backend': 'cos',
                    'storage_group': storage_group,
                })
            except Exception as exc:
                logger.warning('Reference image COS upload failed, falling back to local: %s', exc)

        download_name, relative_path, image_url = save_reference_image(
            task_id,
            1,
            filename,
            content,
            detected_mime_type,
            storage_group=storage_group,
            storage_subdir=storage_subdir,
        )
        return jsonify({
            'success': True,
            'image_url': image_url,
            'image_path': relative_path,
            'download_name': download_name,
            'mime_type': detected_mime_type,
            'storage_backend': 'local',
            'storage_group': storage_group,
        })
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


@app.post('/api/fashion-products/upload')
def upload_fashion_product_image():
    try:
        image_file = request.files.get('file')
        if image_file is None:
            return jsonify({'success': False, 'error': '请上传商品图片文件'}), 400

        content = image_file.read()
        detected_mime_type = validate_image_file(image_file, content)
        safe_stem = sanitize_filename_part(Path(image_file.filename or 'fashion-product').stem, 'fashion-product')
        extension = guess_extension(detected_mime_type)
        filename = f'{safe_stem}{extension}'
        task_id = uuid.uuid4().hex

        if is_cos_enabled():
            try:
                image_key = generate_cos_key(task_id, filename, storage_group='products')
                image_url = upload_to_cos(content, image_key, detected_mime_type)
                return jsonify({
                    'success': True,
                    'image_url': image_url,
                    'image_path': image_key,
                    'download_name': filename,
                    'mime_type': detected_mime_type,
                    'storage_backend': 'cos',
                })
            except Exception as exc:
                logger.warning('Fashion product COS upload failed, falling back to local: %s', exc)

        download_name, relative_path, image_url = save_reference_image(
            task_id,
            1,
            filename,
            content,
            detected_mime_type,
            storage_group='products',
            storage_subdir='uploads',
        )
        return jsonify({
            'success': True,
            'image_url': image_url,
            'image_path': relative_path,
            'download_name': download_name,
            'mime_type': detected_mime_type,
            'storage_backend': 'local',
        })
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


@app.post('/api/fashion-models/upload')
def upload_fashion_model_image():
    try:
        image_file = request.files.get('file')
        if image_file is None:
            return jsonify({'success': False, 'error': '请上传模特图片文件'}), 400

        content = image_file.read()
        detected_mime_type = validate_image_file(image_file, content)
        safe_stem = sanitize_filename_part(Path(image_file.filename or 'fashion-model').stem, 'fashion-model')
        extension = guess_extension(detected_mime_type)
        filename = f'{safe_stem}{extension}'
        task_id = uuid.uuid4().hex

        if is_cos_enabled():
            try:
                image_key = generate_cos_key(task_id, filename, storage_group='fashion-models')
                image_url = upload_to_cos(content, image_key, detected_mime_type)
                return jsonify({
                    'success': True,
                    'image_url': image_url,
                    'image_path': image_key,
                    'download_name': filename,
                    'mime_type': detected_mime_type,
                    'storage_backend': 'cos',
                })
            except Exception as exc:
                logger.warning('Fashion model COS upload failed, falling back to local: %s', exc)

        download_name, relative_path, image_url = save_reference_image(
            task_id,
            1,
            filename,
            content,
            detected_mime_type,
            storage_group='fashion-models',
            storage_subdir='uploads',
        )
        return jsonify({
            'success': True,
            'image_url': image_url,
            'image_path': relative_path,
            'download_name': download_name,
            'mime_type': detected_mime_type,
            'storage_backend': 'local',
        })
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


@app.post('/api/generate-fashion-model')
def generate_fashion_model():
    try:
        payload = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(payload, dict):
            payload = {}

        gender = get_request_value(payload, request.form, 'gender', '女') or '女'
        age = get_request_value(payload, request.form, 'age', '青年（18-35岁）') or '青年（18-35岁）'
        ethnicity = get_request_value(payload, request.form, 'ethnicity', '欧美白人') or '欧美白人'
        body_type = get_request_value(payload, request.form, 'body_type', '标准') or '标准'
        appearance_details = get_request_value(payload, request.form, 'appearance_details', '')
        image_size_ratio = get_request_value(payload, request.form, 'image_size_ratio', '3:4') or '3:4'
        run_async = str(get_request_value(payload, request.form, 'async_task', '') or '').strip().lower() in {'1', 'true', 'yes'}

        def build_fashion_model_result(task_id: str):
            prompt = build_fashion_model_prompt(gender, age, ethnicity, body_type, appearance_details)
            generated_item = call_app_mode_image_generation(
                None,
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
            download_name, relative_path, image_url, storage_trace = save_generated_image(task_id, 1, 'fashion-model', image_bytes, mime_type, storage_group='fashion-models')
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
            model['trace'] = storage_trace
            return {
                'success': True,
                'mode': 'fashion-model',
                'task_id': task_id,
                'model': model,
                'image_url': image_url,
                'image_path': relative_path,
                'download_name': download_name,
                'trace': storage_trace,
            }

        if run_async:
            session_data = g.get('supabase_session') or get_supabase_session()
            user_id = _get_supabase_user_id(session_data)
            if not user_id:
                return jsonify({'success': False, 'error': '请先登录'}), 401
            task = create_generation_task(user_id, 'fashion-model')
            GENERATION_TASK_EXECUTOR.submit(
                run_background_generation_task,
                task['task_id'],
                lambda: build_fashion_model_result(task['task_id']),
                600,
                '基准模特生成超时（10分钟），请稍后重试',
            )
            return jsonify({'success': True, 'async_task': True, 'task': task, 'task_id': task['task_id']}), 202

        task_id = uuid.uuid4().hex
        return jsonify(build_fashion_model_result(task_id))
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


@app.post('/api/generate-mode1-image-edit')
def generate_mode1_image_edit():
    try:
        if get_app_mode() != 'mode1':
            return jsonify({'success': False, 'error': '当前模式未开启 mode1'}), 404

        payload = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(payload, dict):
            payload = {}

        prompt = get_request_value(payload, request.form, 'prompt', '')
        image_url = get_request_value(payload, request.form, 'image_url', '')
        uploaded_payloads = get_image_payloads_from_request('images', url_field_name='image_urls')
        run_async = str(get_request_value(payload, request.form, 'async_task', '') or '').strip().lower() in {'1', 'true', 'yes'}

        if not prompt:
            return jsonify({'success': False, 'error': 'prompt 不能为空'}), 400
        if uploaded_payloads and image_url:
            return jsonify({'success': False, 'error': '上传图片与 image_url 二选一'}), 400
        if uploaded_payloads:
            image_payloads = uploaded_payloads
        elif image_url:
            image_payloads = [build_local_or_remote_image_payload(image_url)]
        else:
            return jsonify({'success': False, 'error': '请上传 1 张或多张参考图片，或提供 image_url'}), 400

        image_size_ratio = request.form.get('image_size_ratio', '1:1')

        def build_mode1_image_edit_result(task_id: str):
            product_json = extract_product_json_from_image_payloads(prompt, image_payloads)
            enriched_prompt = build_enriched_image_prompt(prompt, image_size_ratio, '中文', '中国', product_json, 'mode1-image-edit')
            generated_item, model = call_mode1_image_edit(get_mode1_client(), enriched_prompt, image_payloads, image_size_ratio)
            response = build_mode2_success_response(task_id, 'mode1-image-edit', enriched_prompt, model, generated_item)
            response['mode'] = 'mode1-image-edit'
            return response

        if run_async:
            session_data = g.get('supabase_session') or get_supabase_session()
            user_id = _get_supabase_user_id(session_data)
            if not user_id:
                return jsonify({'success': False, 'error': '请先登录'}), 401
            task = create_generation_task(user_id, 'mode1-image-edit')
            GENERATION_TASK_EXECUTOR.submit(
                run_background_generation_task,
                task['task_id'],
                lambda: build_mode1_image_edit_result(task['task_id']),
                600,
                '模式1图生图超时（10分钟），请稍后重试',
            )
            return jsonify({'success': True, 'async_task': True, 'task': task, 'task_id': task['task_id']}), 202

        task_id = uuid.uuid4().hex
        return jsonify(build_mode1_image_edit_result(task_id))
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


@app.post('/api/generate-mode1-text2image')
def generate_mode1_text2image():
    try:
        if get_app_mode() != 'mode1':
            return jsonify({'success': False, 'error': '当前模式未开启 mode1'}), 404

        payload = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(payload, dict):
            payload = {}

        prompt = get_request_value(payload, request.form, 'prompt', '')
        if not prompt:
            return jsonify({'success': False, 'error': 'prompt 不能为空'}), 400

        task_id = uuid.uuid4().hex
        generated_item, model = call_mode1_text2image(get_mode1_client(), prompt)
        return jsonify(build_mode2_success_response(task_id, 'mode1-text2image', prompt, model, generated_item))
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
        uploaded_payloads = get_image_payloads_from_request('images', url_field_name='image_urls')
        run_async = str(get_request_value(payload, request.form, 'async_task', '') or '').strip().lower() in {'1', 'true', 'yes'}

        if not prompt:
            return jsonify({'success': False, 'error': 'prompt 不能为空'}), 400
        if uploaded_payloads and image_url:
            return jsonify({'success': False, 'error': '上传图片与 image_url 二选一'}), 400
        if uploaded_payloads:
            image_payloads = uploaded_payloads
        elif image_url:
            image_payloads = [build_local_or_remote_image_payload(image_url)]
        else:
            return jsonify({'success': False, 'error': '请上传 1 张或多张参考图片，或提供 image_url'}), 400

        def build_mode2_image_edit_result(task_id: str):
            generated_item, model = call_mode2_image_edit(
                get_mode2_client(),
                prompt,
                image_payloads,
                ratio,
                resolution,
                sample_strength,
            )
            response = build_mode2_success_response(task_id, 'mode2-image-edit', prompt, model, generated_item)
            response['mode'] = 'mode2-image-edit'
            return response

        if run_async:
            session_data = g.get('supabase_session') or get_supabase_session()
            user_id = _get_supabase_user_id(session_data)
            if not user_id:
                return jsonify({'success': False, 'error': '请先登录'}), 401
            task = create_generation_task(user_id, 'mode2-image-edit')
            GENERATION_TASK_EXECUTOR.submit(
                run_background_generation_task,
                task['task_id'],
                lambda: build_mode2_image_edit_result(task['task_id']),
                600,
                '模式2图生图超时（10分钟），请稍后重试',
            )
            return jsonify({'success': True, 'async_task': True, 'task': task, 'task_id': task['task_id']}), 202

        task_id = uuid.uuid4().hex
        return jsonify(build_mode2_image_edit_result(task_id))
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


@app.post('/api/generate-mode2-image-edit-test')
def generate_mode2_image_edit_test():
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
        uploaded_payloads = get_image_payloads_from_request('images', url_field_name='image_urls')

        if not prompt:
            return jsonify({'success': False, 'error': 'prompt 不能为空'}), 400
        if uploaded_payloads and image_url:
            return jsonify({'success': False, 'error': '上传图片与 image_url 二选一'}), 400
        if uploaded_payloads:
            image_payloads = uploaded_payloads
        elif image_url:
            image_payloads = [build_local_or_remote_image_payload(image_url)]
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
        response = build_mode2_success_response(task_id, 'mode2-image-edit-test', prompt, model, generated_item)
        response['mode'] = 'mode2-image-edit-test'
        return jsonify(response)
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
        run_async = str(get_request_value(payload, request.form, 'async_task', '') or '').strip().lower() in {'1', 'true', 'yes'}

        if not prompt:
            return jsonify({'success': False, 'error': 'prompt 不能为空'}), 400

        def build_mode2_text2image_result(task_id: str):
            generated_item, model = call_mode2_text2image(
                get_mode2_client(),
                prompt,
                ratio,
                resolution,
            )
            response = build_mode2_success_response(task_id, 'mode2-text2image', prompt, model, generated_item)
            response['mode'] = 'mode2-text2image'
            return response

        if run_async:
            session_data = g.get('supabase_session') or get_supabase_session()
            user_id = _get_supabase_user_id(session_data)
            if not user_id:
                return jsonify({'success': False, 'error': '请先登录'}), 401
            task = create_generation_task(user_id, 'mode2-text2image')
            GENERATION_TASK_EXECUTOR.submit(
                run_background_generation_task,
                task['task_id'],
                lambda: build_mode2_text2image_result(task['task_id']),
                600,
                '模式2文生图超时（10分钟），请稍后重试',
            )
            return jsonify({'success': True, 'async_task': True, 'task': task, 'task_id': task['task_id']}), 202

        task_id = uuid.uuid4().hex
        return jsonify(build_mode2_text2image_result(task_id))
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
        uploaded_payloads = get_image_payloads_from_request('images', url_field_name='image_urls')
        run_async = str(get_request_value(payload, request.form, 'async_task', '') or '').strip().lower() in {'1', 'true', 'yes'}

        if not prompt:
            return jsonify({'success': False, 'error': 'prompt 不能为空'}), 400
        if uploaded_payloads and image_url:
            return jsonify({'success': False, 'error': '上传图片与 image_url 二选一'}), 400
        if uploaded_payloads:
            image_payloads = uploaded_payloads
        elif image_url:
            image_payloads = [build_local_or_remote_image_payload(image_url)]
        else:
            return jsonify({'success': False, 'error': '请上传 1 张或多张参考图片，或提供 image_url'}), 400

        image_size_ratio = request.form.get('image_size_ratio', '1:1')

        def build_mode3_image_edit_result(task_id: str):
            product_json = extract_product_json_from_image_payloads(prompt, image_payloads)
            enriched_prompt = build_enriched_image_prompt(prompt, image_size_ratio, '中文', '中国', product_json, 'mode3-image-edit')
            generated_item, model = call_mode3_image_edit(get_mode3_api_key(), enriched_prompt, image_payloads, image_size_ratio)
            response = build_mode2_success_response(task_id, 'mode3-image-edit', enriched_prompt, model, generated_item)
            response['mode'] = 'mode3-image-edit'
            return response

        if run_async:
            session_data = g.get('supabase_session') or get_supabase_session()
            user_id = _get_supabase_user_id(session_data)
            if not user_id:
                return jsonify({'success': False, 'error': '请先登录'}), 401
            task = create_generation_task(user_id, 'mode3-image-edit')
            GENERATION_TASK_EXECUTOR.submit(
                run_background_generation_task,
                task['task_id'],
                lambda: build_mode3_image_edit_result(task['task_id']),
                600,
                '模式3图生图超时（10分钟），请稍后重试',
            )
            return jsonify({'success': True, 'async_task': True, 'task': task, 'task_id': task['task_id']}), 202

        task_id = uuid.uuid4().hex
        return jsonify(build_mode3_image_edit_result(task_id))
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
        generated_item, model = call_mode3_text2image(get_mode3_api_key(), prompt)
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
        if not selected_model_payloads:
            model_image_url = str(form.get('fashion_selected_model_image_url') or '').strip()
            if model_image_url:
                selected_model_payloads = [build_local_or_remote_image_payload(model_image_url)]
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

        def _generate_one_fashion_look(index: int, prompt_entry: dict):
            logger.warning(
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
                    None,
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
                logger.warning(
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
                from image_utils import LazyImagePayload
                generated_payload = LazyImagePayload(
                    filename=f'fashion-look-{index:02d}.png',
                    mime_type=mime_type,
                    content=image_bytes,
                )
                verification = verify_fashion_generated_output(
                    generated_payload,
                    selected_model_payload,
                    image_payloads,
                )
                logger.warning(
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
                raise ValueError('生成结果为空')
            download_name, relative_path, image_url, storage_trace = save_generated_image(task_id, index, 'fashion-look', image_bytes, mime_type)
            return {
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
                'verification_passed': verification.get('passed') if verification else False,
                'trace': storage_trace,
            }

        images = []
        failed_prompt_entries = []
        workers, partial_retry_attempts, retry_delay_seconds = _get_parallel_config(get_app_mode(), len(prompt_entries))

        pending_entries = list(enumerate(prompt_entries, start=1))
        for attempt_index in range(partial_retry_attempts + 1):
            if not pending_entries:
                break
            batch_workers = min(len(pending_entries), workers)
            batch_failures = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=batch_workers) as executor:
                future_map = {executor.submit(_generate_one_fashion_look, idx, entry): (idx, entry) for idx, entry in pending_entries}
                for future in concurrent.futures.as_completed(future_map):
                    idx, entry = future_map[future]
                    try:
                        images.append(future.result())
                    except Exception as exc:
                        batch_failures.append((idx, entry, str(exc)))
            for idx, entry, msg in batch_failures:
                failed_prompt_entries.append({
                    'index': idx,
                    'title': entry['pose'].get('title') or f'服饰穿搭图 {idx}',
                    'reason': msg,
                })
            pending_entries = [(idx, entry) for idx, entry, _msg in batch_failures]
            if pending_entries and attempt_index < partial_retry_attempts:
                failures_brief = [msg for _idx, _entry, msg in batch_failures[:3]]
                logger.warning(
                    'Fashion parallel partial generation missing %s/%s, retrying in %.2fs (%s/%s): %s',
                    len(pending_entries), len(prompt_entries), retry_delay_seconds * (attempt_index + 1),
                    attempt_index + 1, partial_retry_attempts,
                    '; '.join(failures_brief),
                )
                time.sleep(retry_delay_seconds * (attempt_index + 1))

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

    generation_task_type = str(form.get('generate_task_type') or '').strip()
    is_main_image_task = generation_task_type == 'main_image'
    if is_main_image_task:
        try:
            output_count = min(max(int(str(form.get('output_count') or '1').strip()), 1), 10)
        except ValueError:
            output_count = 1
    else:
        output_count, _ = get_suite_type_rules(form.get('output_count', '8'))
    task_id = uuid.uuid4().hex
    task_name = build_task_name(platform, 'main_image' if is_main_image_task else 'suite', output_count)
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
        logger.warning('Suite generation extracting product_json from uploaded reference images: mode=%s image_count=%s', mode, len(planning_payloads))
        product_json = extract_product_json_from_image_payloads(selling_text, planning_payloads)
    logger.warning(
        'Suite generation upload payloads: mode=%s task_type=%s product_count=%s reference_count=%s total_generation_count=%s product_json_ready=%s',
        mode,
        generation_task_type or 'detail_image',
        len(image_payloads),
        len(reference_payloads),
        len(planning_payloads),
        bool(product_json),
    )
    if is_main_image_task:
        plan = build_main_image_cover_plan(
            platform,
            selling_text,
            output_count,
            country,
            '无文字',
            image_size_ratio,
            selected_style,
            product_json,
        )
        generation_text_type = '无文字'
    else:
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
        generation_text_type = text_type
    images = generate_suite_images(plan, planning_payloads, task_id, image_size_ratio, generation_text_type, country, product_json)

    return {
        'success': True,
        'mode': 'main_image' if is_main_image_task else mode,
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
            'images': get_image_payloads_from_request('images', url_field_name='image_urls'),
            'reference_images': get_image_payloads_from_request('reference_images', url_field_name='reference_image_urls'),
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


@app.post('/api/generate-replicate')
def generate_replicate():
    try:
        form_payload = {key: request.form.get(key, '') for key in request.form.keys()}
        replicate_mode = str(form_payload.get('replicate_mode') or 'single').strip() or 'single'
        if replicate_mode not in ('single', 'batch', 'sku'):
            replicate_mode = 'single'
        form_payload['replicate_mode'] = replicate_mode
        form_payload['replicate_version'] = 'reference-analysis-v2'

        if replicate_mode == 'batch':
            file_payloads = {
                'reference_image': get_image_payloads_from_request('reference_image', limit=20),
                'product_images': get_image_payloads_from_request('product_images'),
            }
        else:
            file_payloads = {
                'reference_image': get_image_payloads_from_request('reference_image', limit=1),
                'product_images': get_image_payloads_from_request('product_images'),
            }

        run_async = str(form_payload.get('async_task') or '').strip().lower() in {'1', 'true', 'yes'}

        if run_async:
            session_data = g.get('supabase_session') or get_supabase_session()
            user_id = _get_supabase_user_id(session_data)
            if not user_id:
                return jsonify({'success': False, 'error': '请先登录'}), 401

            task = create_generation_task(user_id, f'replicate-{replicate_mode}', '', None)
            GENERATION_TASK_EXECUTOR.submit(run_replicate_generation_task, task['task_id'], form_payload, file_payloads)
            return jsonify({'success': True, 'async_task': True, 'task': task, 'task_id': task['task_id']}), 202

        result = build_replicate_generation_result(form_payload, file_payloads)
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


def run_replicate_generation_task(task_id: str, form_payload: dict, file_payloads: dict):
    run_background_generation_task(
        task_id,
        lambda: build_replicate_generation_result(form_payload, file_payloads, task_id),
        timeout=600,
        timeout_error='生成任务执行超时（10分钟），请稍后重试',
    )


REPLICATE_REFERENCE_ANALYSIS_SYSTEM_PROMPT = '你是电商主图参考图结构化解析专家。你只能分析参考图里的版式、文案、视觉结构、色块、促销信息和商品占位区域。禁止提取参考图中商品主体的品类、品牌、颜色、材质、造型、结构、功能、卖点或外观细节；参考图商品只能作为占位和陈列区域，不是待生成商品来源。你必须只输出合法 JSON，不要代码块、解释或额外文字。'


REPLICATE_REFERENCE_ANALYSIS_USER_PROMPT = """请只分析这张参考图，提取用于复刻的文案和版式 JSON。

要求：
1. 只分析当前参考图里的文案、版式、视觉结构、促销信息、色块关系和商品占位区域，不要推断任何待替换产品的信息。
2. 必须提取图片中可见中文文案，尽量保留原文、位置、字号层级和色块关系。
3. 可以描述商品占位数量、排列区域、顶部标题区、底部促销条、右下角标签、背景、边距、主色、强调色。
4. 严禁描述参考图商品主体本身，不能提取参考图商品的品类、品牌、颜色、材质、造型、结构、功能、卖点、外观细节或包装识别。
5. 如果需要描述商品区域，只能写成“商品占位区域/商品槽位/陈列位置”，不能写参考图商品是什么、长什么样、什么颜色、什么材质。
6. 如果某项看不清，写空字符串或空数组，不要臆测。
7. 只返回 JSON，不要 Markdown。

JSON 结构：
{
  "copywriting": {
    "headline": "",
    "sub_headline": "",
    "bottom_banner_text": "",
    "corner_badge_text": "",
    "other_texts": []
  },
  "layout": {
    "canvas_ratio": "",
    "background": "",
    "main_grid": "",
    "product_count": "",
    "product_arrangement": "",
    "headline_position": "",
    "bottom_banner_position": "",
    "corner_badge_position": "",
    "spacing_margins": ""
  },
  "visual_style": {
    "primary_colors": [],
    "accent_colors": [],
    "font_style": "",
    "lighting_shadow": "",
    "commerce_style": ""
  },
  "replicate_rules": []
}
"""


def parse_replicate_reference_analysis(text: str):
    payload = parse_json_candidate(text, '参考图结构化信息格式异常')
    if not isinstance(payload, dict):
        raise ValueError('参考图结构化信息格式异常：顶层必须为对象')
    copywriting = payload.get('copywriting') if isinstance(payload.get('copywriting'), dict) else {}
    layout = payload.get('layout') if isinstance(payload.get('layout'), dict) else {}
    visual_style = payload.get('visual_style') if isinstance(payload.get('visual_style'), dict) else {}
    subject_guard_rules = [
        '参考图中的商品主体只作为占位区域和陈列结构，不作为待生成商品特征来源',
        '禁止从参考图商品主体继承品类、品牌、颜色、材质、造型、结构、功能、卖点、外观细节或包装识别',
        '最终商品主体必须只来自用户上传的产品图或当前 SKU 产品图',
        '如果结构化 JSON 中出现疑似参考图商品主体特征，生成时必须忽略这些主体特征，只保留其位置、大小、数量和排列关系',
    ]
    replicate_rules = [str(item).strip() for item in payload.get('replicate_rules') or [] if str(item).strip()]
    for rule in subject_guard_rules:
        if rule not in replicate_rules:
            replicate_rules.append(rule)
    return {
        'copywriting': {
            'headline': str(copywriting.get('headline') or '').strip(),
            'sub_headline': str(copywriting.get('sub_headline') or '').strip(),
            'bottom_banner_text': str(copywriting.get('bottom_banner_text') or '').strip(),
            'corner_badge_text': str(copywriting.get('corner_badge_text') or '').strip(),
            'other_texts': [str(item).strip() for item in copywriting.get('other_texts') or [] if str(item).strip()],
        },
        'layout': {
            'canvas_ratio': str(layout.get('canvas_ratio') or '').strip(),
            'background': str(layout.get('background') or '').strip(),
            'main_grid': str(layout.get('main_grid') or '').strip(),
            'product_count': str(layout.get('product_count') or '').strip(),
            'product_arrangement': str(layout.get('product_arrangement') or '').strip(),
            'headline_position': str(layout.get('headline_position') or '').strip(),
            'bottom_banner_position': str(layout.get('bottom_banner_position') or '').strip(),
            'corner_badge_position': str(layout.get('corner_badge_position') or '').strip(),
            'spacing_margins': str(layout.get('spacing_margins') or '').strip(),
        },
        'visual_style': {
            'primary_colors': [str(item).strip() for item in visual_style.get('primary_colors') or [] if str(item).strip()],
            'accent_colors': [str(item).strip() for item in visual_style.get('accent_colors') or [] if str(item).strip()],
            'font_style': str(visual_style.get('font_style') or '').strip(),
            'lighting_shadow': str(visual_style.get('lighting_shadow') or '').strip(),
            'commerce_style': str(visual_style.get('commerce_style') or '').strip(),
        },
        'replicate_rules': replicate_rules,
    }


def extract_replicate_reference_analysis(reference_payloads):
    if not reference_payloads:
        return {}
    analysis, _response_text = call_chat_json_with_repair(
        REPLICATE_REFERENCE_ANALYSIS_SYSTEM_PROMPT,
        build_multimodal_content(REPLICATE_REFERENCE_ANALYSIS_USER_PROMPT, reference_payloads[:1]),
        parse_replicate_reference_analysis,
        '参考图结构化信息格式异常',
        temperature=0.1,
        timeout_seconds=90,
        repair_attempts=1,
    )
    return analysis


def build_replicate_reference_analysis_text(reference_analysis: dict) -> str:
    if not isinstance(reference_analysis, dict) or not reference_analysis:
        return '参考图结构化信息未提取成功，请直接依据参考图进行版式复刻。'
    return json.dumps(reference_analysis, ensure_ascii=False, indent=2)


def build_replicate_prompt(user_prompt: str, output_index: int, output_count: int, reference_analysis: dict | None = None) -> str:
    reference_analysis_text = build_replicate_reference_analysis_text(reference_analysis or {})
    prompt_parts = [
        '执行主图详情页复刻商品图任务，目标是复刻参考图的电商模板，同时把产品图商品主体作为最高优先级锁定对象。',
        '输入图片角色必须严格区分：第 1 张是产品主体锚定草图，只用于辅助锁定产品主体轮廓和大致摆放；第 2 张是原始产品图，是唯一商品主体一致性锚点。原始参考图不会作为生图视觉输入，只能使用下方已提取的参考图文案和版式 JSON。',
        '最高优先级：第 2 张产品图决定商品主体。生成结果必须保持产品图商品的品类、外观造型、颜色体系、材质质感、核心结构、关键轮廓、比例、部件数量、部件位置、包装识别和可见细节，不得被参考图影响而改变。',
        '参考图商品主体不是商品来源。严禁复制、继承或吸收参考图商品的品类、品牌、颜色、材质、造型、结构、功能、卖点、外观细节、包装形态或商品身份。',
        '如果参考图中的商品和产品图商品不一致，必须无条件以第 2 张产品图为准；参考图商品只能被理解为商品槽位、占位面积、陈列数量和排列方向。',
        '产品图只用于锁定商品主体，不从产品图提取文案、卖点、营销信息或版式信息；不得把产品图中的环境、台面、水流、墙面、道具当作复刻内容。',
        '必须强参考已提取 JSON 的非商品主体信息：顶部标题区域、商品占位陈列方式、底部促销条、标签位置、背景色、边距、色块比例、字体层级都要尽量保留。',
        '参考图文案和版式 JSON如下，只能来自参考图，不包含产品图解析；如果 JSON 中出现疑似参考图商品主体特征，必须忽略这些主体特征，只保留位置、大小、数量和排列关系：',
        reference_analysis_text,
        '生成时把第 2 张产品图商品放入参考图商品槽位。允许为了匹配多规格陈列复制同一产品主体并做轻微角度、大小、间距或排列变化，但不能改变商品品类、主色、材质、核心结构、关键轮廓、部件组合和包装识别。',
        '输出必须是完整电商主图或详情页模块，不是单个产品场景图；不要展示对比图、不要分屏、不要水印、不要无关界面元素。',
    ]
    if output_count > 1:
        prompt_parts.append(f'这是第 {output_index} 张结果，在保持同一参考版式和同一产品主体一致的前提下，做轻微构图、光影或文案表达差异。')
    if user_prompt:
        prompt_parts.append(f'用户补充要求：{user_prompt}')
    return '\n'.join(prompt_parts)


def build_replicate_generation_result(form_payload: dict, file_payloads: dict, task_id: str | None = None):
    form = form_payload if isinstance(form_payload, dict) else {}
    payloads = file_payloads if isinstance(file_payloads, dict) else {}

    reference_payloads = list(payloads.get('reference_image') or [])
    product_payloads = list(payloads.get('product_images') or [])
    replicate_mode = str(form.get('replicate_mode') or 'single').strip() or 'single'
    if str(form.get('replicate_version') or '').strip() != 'reference-analysis-v2':
        raise ValueError('服务未加载最新复刻逻辑，请重启服务后重试')

    if not reference_payloads:
        raise ValueError('请上传参考设计图')
    if not product_payloads:
        raise ValueError('请至少上传一张产品素材图')

    if replicate_mode == 'batch':
        return _build_batch_replicate_result(form, payloads, reference_payloads, product_payloads, task_id)
    if replicate_mode == 'sku':
        return _build_sku_replicate_result(form, payloads, reference_payloads, product_payloads, task_id)
    return _build_single_replicate_result(form, payloads, reference_payloads, product_payloads, task_id)


def _build_single_replicate_result(form: dict, payloads: dict, reference_payloads: list, product_payloads: list, task_id: str | None = None):
    reference_analysis = extract_replicate_reference_analysis(reference_payloads)

    prompt = str(form.get('prompt') or '').strip()
    image_size_ratio = str(form.get('image_size_ratio') or '1:1').strip() or '1:1'
    try:
        output_count = int(form.get('output_count') or 1)
    except (TypeError, ValueError):
        raise ValueError('生成数量必须是数字')
    output_count = max(1, min(output_count, 4))

    current_task_id = str(task_id or '').strip() or uuid.uuid4().hex
    task_name = f'单图复刻-{current_task_id[:8]}'
    generated_at = build_generated_at()
    layout_canvas_payload = create_replicate_layout_canvas_payload(product_payloads, reference_payloads[0], image_size_ratio)
    generation_payloads = [layout_canvas_payload] + product_payloads[:1]
    reference_images = build_reference_images(current_task_id, reference_payloads[:1], source='replicate_reference')
    reference_images.extend(
        build_reference_images(
            current_task_id,
            product_payloads,
            source='product',
            start_sort=len(reference_images) + 1,
        )
    )

    images = []
    model = ''
    generated_items = call_app_mode_image_generation(
        None,
        build_replicate_prompt(prompt, 1, output_count, reference_analysis),
        generation_payloads,
        image_size_ratio,
        '中文',
        '中国',
        None,
        'replicate',
        max_images=output_count,
    )
    if len(generated_items or []) < output_count:
        raise ValueError(f'图像生成接口返回数量不足，期望 {output_count} 张，实际 {len(generated_items or [])} 张')

    for index, generated_item in enumerate(generated_items[:output_count], start=1):
        image_bytes, mime_type = decode_generated_image(generated_item)
        download_name, relative_path, image_url, storage_trace = save_generated_image(current_task_id, index, 'replicate', image_bytes, mime_type)
        model = str(generated_item.get('model') or generated_item.get('revised_prompt') or model or '')
        images.append({
            'url': image_url,
            'image_url': image_url,
            'download_url': image_url,
            'download_name': download_name,
            'path': relative_path,
            'type': 'replicate',
            'sort': index,
            'prompt': build_replicate_prompt(prompt, index, output_count, reference_analysis),
            'reference_analysis': reference_analysis,
            'trace': storage_trace,
        })

    reference_image_url = None
    first_reference = reference_payloads[0] if reference_payloads else None
    if first_reference:
        reference_image_url = first_reference.get('data_url') if isinstance(first_reference, dict) else getattr(first_reference, 'data_url', None)

    return {
        'success': True,
        'mode': 'replicate',
        'replicate_mode': 'single',
        'task_id': current_task_id,
        'task_name': task_name,
        'generated_at': generated_at,
        'reference_image': {
            'url': reference_image_url,
        } if reference_image_url else None,
        'reference_images': reference_images,
        'reference_analysis': reference_analysis,
        'images': images,
        'prompt': prompt,
        'image_size_ratio': image_size_ratio,
        'output_count': output_count,
        'model': model,
    }


def _build_batch_replicate_result(form: dict, payloads: dict, reference_payloads: list, product_payloads: list, task_id: str | None = None):
    if len(reference_payloads) > 20:
        raise ValueError('批量参考图最多20张')
    if len(reference_payloads) == 0:
        raise ValueError('请至少上传一张参考图')

    prompt = str(form.get('prompt') or '').strip()
    image_size_ratio = str(form.get('image_size_ratio') or '1:1').strip() or '1:1'
    try:
        output_count = int(form.get('output_count') or 1)
    except (TypeError, ValueError):
        raise ValueError('生成数量必须是数字')
    output_count = max(1, min(output_count, 4))

    current_task_id = str(task_id or '').strip() or uuid.uuid4().hex
    task_name = f'批量复刻-{current_task_id[:8]}'
    generated_at = build_generated_at()

    all_images = []
    all_reference_images = []
    model = ''
    total_sort = 0

    for ref_index, ref_payload in enumerate(reference_payloads):
        reference_analysis = extract_replicate_reference_analysis([ref_payload])
        layout_canvas_payload = create_replicate_layout_canvas_payload(product_payloads, ref_payload, image_size_ratio)
        generation_payloads = [layout_canvas_payload] + product_payloads[:1]

        ref_reference_images = build_reference_images(current_task_id, [ref_payload], source='replicate_reference', start_sort=len(all_reference_images) + 1)
        ref_reference_images.extend(
            build_reference_images(
                current_task_id,
                product_payloads,
                source='product',
                start_sort=len(all_reference_images) + len(ref_reference_images) + 1,
            )
        )
        all_reference_images.extend(ref_reference_images)

        generated_items = call_app_mode_image_generation(
            None,
            build_replicate_prompt(prompt, 1, output_count, reference_analysis),
            generation_payloads,
            image_size_ratio,
            '中文',
            '中国',
            None,
            'replicate',
            max_images=output_count,
        )
        if len(generated_items or []) < output_count:
            raise ValueError(f'批量复刻第 {ref_index + 1} 张参考图生成数量不足，期望 {output_count} 张，实际 {len(generated_items or [])} 张')

        for index, generated_item in enumerate(generated_items[:output_count], start=1):
            total_sort += 1
            image_bytes, mime_type = decode_generated_image(generated_item)
            download_name, relative_path, image_url, storage_trace = save_generated_image(current_task_id, total_sort, 'replicate', image_bytes, mime_type)
            model = str(generated_item.get('model') or generated_item.get('revised_prompt') or model or '')
            all_images.append({
                'url': image_url,
                'image_url': image_url,
                'download_url': image_url,
                'download_name': download_name,
                'path': relative_path,
                'type': 'replicate',
                'sort': total_sort,
                'prompt': build_replicate_prompt(prompt, index, output_count, reference_analysis),
                'reference_analysis': reference_analysis,
                'batch_reference_index': ref_index,
                'trace': storage_trace,
            })

    reference_image_url = None
    first_reference = reference_payloads[0] if reference_payloads else None
    if first_reference:
        reference_image_url = first_reference.get('data_url') if isinstance(first_reference, dict) else getattr(first_reference, 'data_url', None)

    return {
        'success': True,
        'mode': 'replicate',
        'replicate_mode': 'batch',
        'task_id': current_task_id,
        'task_name': task_name,
        'generated_at': generated_at,
        'reference_image': {
            'url': reference_image_url,
        } if reference_image_url else None,
        'reference_images': all_reference_images,
        'reference_analysis': all_images[0].get('reference_analysis') if all_images else None,
        'images': all_images,
        'prompt': prompt,
        'image_size_ratio': image_size_ratio,
        'output_count': len(all_images),
        'batch_reference_count': len(reference_payloads),
        'model': model,
    }


def _build_sku_replicate_result(form: dict, payloads: dict, reference_payloads: list, product_payloads: list, task_id: str | None = None):
    if len(product_payloads) > 20:
        raise ValueError('SKU产品图最多20张')

    reference_analysis = extract_replicate_reference_analysis(reference_payloads)

    prompt = str(form.get('prompt') or '').strip()
    image_size_ratio = str(form.get('image_size_ratio') or '1:1').strip() or '1:1'

    current_task_id = str(task_id or '').strip() or uuid.uuid4().hex
    task_name = f'SKU复刻-{current_task_id[:8]}'
    generated_at = build_generated_at()

    all_images = []
    all_reference_images = []
    model = ''
    total_sort = 0

    all_reference_images = build_reference_images(current_task_id, reference_payloads[:1], source='replicate_reference')
    all_reference_images.extend(
        build_reference_images(
            current_task_id,
            product_payloads,
            source='product',
            start_sort=len(all_reference_images) + 1,
        )
    )

    sku_info_list = []
    for sku_index in range(len(product_payloads)):
        sku_info_val = str(form.get(f'sku_info_{sku_index}') or '').strip()
        sku_info_list.append(sku_info_val)

    for sku_index, sku_product in enumerate(product_payloads):
        sku_info = sku_info_list[sku_index] if sku_index < len(sku_info_list) else ''
        sku_prompt_part = f'，SKU变体：{sku_info}' if sku_info else ''

        layout_canvas_payload = create_replicate_layout_canvas_payload([sku_product], reference_payloads[0], image_size_ratio)
        generation_payloads = [layout_canvas_payload, sku_product]

        generated_items = call_app_mode_image_generation(
            None,
            build_replicate_prompt(prompt + sku_prompt_part, 1, 1, reference_analysis),
            generation_payloads,
            image_size_ratio,
            '中文',
            '中国',
            None,
            'replicate',
            max_images=1,
        )
        if len(generated_items or []) < 1:
            raise ValueError(f'SKU复刻第 {sku_index + 1} 个产品生成失败')

        total_sort += 1
        generated_item = generated_items[0]
        image_bytes, mime_type = decode_generated_image(generated_item)
        download_name, relative_path, image_url, storage_trace = save_generated_image(current_task_id, total_sort, 'replicate', image_bytes, mime_type)
        model = str(generated_item.get('model') or generated_item.get('revised_prompt') or model or '')
        all_images.append({
            'url': image_url,
            'image_url': image_url,
            'download_url': image_url,
            'download_name': download_name,
            'path': relative_path,
            'type': 'replicate',
            'sort': total_sort,
            'prompt': build_replicate_prompt(prompt + sku_prompt_part, 1, 1, reference_analysis),
            'reference_analysis': reference_analysis,
            'sku_product_index': sku_index,
            'sku_info': sku_info,
            'trace': storage_trace,
        })

    reference_image_url = None
    first_reference = reference_payloads[0] if reference_payloads else None
    if first_reference:
        reference_image_url = first_reference.get('data_url') if isinstance(first_reference, dict) else getattr(first_reference, 'data_url', None)

    return {
        'success': True,
        'mode': 'replicate',
        'replicate_mode': 'sku',
        'task_id': current_task_id,
        'task_name': task_name,
        'generated_at': generated_at,
        'reference_image': {
            'url': reference_image_url,
        } if reference_image_url else None,
        'reference_images': all_reference_images,
        'reference_analysis': reference_analysis,
        'images': all_images,
        'prompt': prompt,
        'image_size_ratio': image_size_ratio,
        'output_count': len(all_images),
        'sku_product_count': len(product_payloads),
        'model': model,
    }


@app.get('/api/generation-tasks')
def generation_tasks_list():
    session_data = g.get('supabase_session') or get_supabase_session()
    user_id = _get_supabase_user_id(session_data)
    if not user_id:
        return jsonify({'success': False, 'error': '请先登录'}), 401
    limit = request.args.get('limit', 20)
    offset = request.args.get('offset', 0)
    mode = request.args.get('mode') or None
    status = request.args.get('status') or None
    try:
        tasks = fetch_user_generation_tasks(user_id, limit=int(limit), offset=int(offset), mode=mode, status=status)
        return jsonify({'success': True, 'tasks': [serialize_generation_task(task) for task in tasks]})
    except ValueError:
        return jsonify({'success': False, 'error': '分页参数无效'}), 400


HISTORY_IMAGE_ALLOWED_HOST = 'aiimg.86969678.xyz'
ZIP_DOWNLOAD_MAX_ITEMS = 50
ZIP_TASK_TTL_SECONDS = 1800
ZIP_TASKS = {}
ZIP_TASKS_LOCK = threading.RLock()
ZIP_TASK_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix='history_zip')


def _is_allowed_history_download_url(image_url: str) -> bool:
    normalized_url = str(image_url or '').strip()
    if not normalized_url:
        return False
    parsed = urlparse(_strip_history_image_process_query(normalized_url))
    return parsed.scheme in {'http', 'https'} and parsed.netloc.lower() == HISTORY_IMAGE_ALLOWED_HOST


def _build_history_zip_buffer(urls: list[str]) -> tuple[io.BytesIO, int]:
    buffer = io.BytesIO()
    success_count = 0
    used_names = set()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for url in urls:
            try:
                content, normalized_url = _download_history_image(url)
            except Exception as exc:
                logger.warning('Failed to download history image for zip: %s %s', url, exc)
                continue
            archive_name = _build_history_download_filename(normalized_url, success_count)
            duplicate_index = 2
            while archive_name in used_names:
                path = Path(archive_name)
                archive_name = f'{path.stem}-{duplicate_index}{path.suffix or ".png"}'
                duplicate_index += 1
            used_names.add(archive_name)
            archive.writestr(archive_name, content)
            success_count += 1
    buffer.seek(0)
    return buffer, success_count


def _cleanup_zip_tasks() -> None:
    now = time.time()
    with ZIP_TASKS_LOCK:
        expired_ids = [task_id for task_id, task in ZIP_TASKS.items() if now - float(task.get('created_at') or now) > ZIP_TASK_TTL_SECONDS]
        for task_id in expired_ids:
            ZIP_TASKS.pop(task_id, None)


def _run_zip_task(task_id: str, urls: list[str]) -> None:
    try:
        buffer, success_count = _build_history_zip_buffer(urls)
        if success_count <= 0:
            with ZIP_TASKS_LOCK:
                task = ZIP_TASKS.get(task_id)
                if task:
                    task.update({'status': 'failed', 'error': '选中的图片下载失败，请稍后重试', 'updated_at': time.time()})
            return
        with ZIP_TASKS_LOCK:
            task = ZIP_TASKS.get(task_id)
            if task:
                task.update({
                    'status': 'succeeded',
                    'buffer': buffer,
                    'filename': f'generation-history-originals-{int(time.time())}.zip',
                    'success_count': success_count,
                    'updated_at': time.time(),
                })
    except Exception as exc:
        logger.warning('Failed to build async history zip: %s', exc)
        with ZIP_TASKS_LOCK:
            task = ZIP_TASKS.get(task_id)
            if task:
                task.update({'status': 'failed', 'error': '打包下载失败，请稍后重试', 'updated_at': time.time()})


def _extract_clean_history_download_urls(payload: dict | None) -> tuple[list[str], str | None]:
    urls = payload.get('urls') if isinstance(payload, dict) else []
    if not isinstance(urls, list):
        return [], '下载参数无效'
    clean_urls = []
    for url in urls:
        clean_url = str(url or '').strip()
        if _is_allowed_history_download_url(clean_url) and clean_url not in clean_urls:
            clean_urls.append(clean_url)
    if not clean_urls:
        return [], '请先选择可下载的本站图片'
    if len(clean_urls) > ZIP_DOWNLOAD_MAX_ITEMS:
        return [], f'单次最多打包下载 {ZIP_DOWNLOAD_MAX_ITEMS} 张图片'
    return clean_urls, None


@app.get('/api/generation-history/download-image')
def download_generation_history_image():
    session_data = g.get('supabase_session') or get_supabase_session()
    user_id = _get_supabase_user_id(session_data)
    if not user_id:
        return jsonify({'success': False, 'error': '请先登录'}), 401
    image_url = str(request.args.get('url') or '').strip()
    if not _is_allowed_history_download_url(image_url):
        return jsonify({'success': False, 'error': '下载地址不允许'}), 400
    try:
        content, normalized_url = _download_history_image(image_url)
    except requests.Timeout:
        return jsonify({'success': False, 'error': '图片下载超时，请稍后重试'}), 504
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'图片下载失败：{exc}'}), 502
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    filename = _build_history_download_filename(normalized_url, 0).removeprefix('001-')
    response = send_file(
        io.BytesIO(content),
        mimetype=_guess_history_image_mimetype(normalized_url),
        as_attachment=True,
        download_name=filename,
    )
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.post('/api/generation-history/download-zip')
def generation_history_download_zip():
    session_data = g.get('supabase_session') or get_supabase_session()
    user_id = _get_supabase_user_id(session_data)
    if not user_id:
        return jsonify({'success': False, 'error': '请先登录'}), 401
    clean_urls, error = _extract_clean_history_download_urls(request.get_json(silent=True) if request.is_json else {})
    if error:
        return jsonify({'success': False, 'error': error}), 400
    buffer, success_count = _build_history_zip_buffer(clean_urls)
    if success_count <= 0:
        return jsonify({'success': False, 'error': '选中的图片下载失败，请稍后重试'}), 502
    response = send_file(
        buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'generation-history-originals-{int(time.time())}.zip',
    )
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.post('/api/generation-history/zip-tasks')
def create_generation_history_zip_task():
    try:
        session_data = g.get('supabase_session') or get_supabase_session()
        user_id = _get_supabase_user_id(session_data)
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录'}), 401
        _cleanup_zip_tasks()
        clean_urls, error = _extract_clean_history_download_urls(request.get_json(silent=True) if request.is_json else {})
        if error:
            return jsonify({'success': False, 'error': error}), 400
        task_id = uuid.uuid4().hex
        with ZIP_TASKS_LOCK:
            active_for_user = any(task.get('user_id') == user_id and task.get('status') in {'queued', 'running'} for task in ZIP_TASKS.values())
            if active_for_user:
                return jsonify({'success': False, 'error': '已有打包任务正在处理中，请稍后再试'}), 429
            ZIP_TASKS[task_id] = {
                'task_id': task_id,
                'user_id': user_id,
                'status': 'queued',
                'total': len(clean_urls),
                'created_at': time.time(),
                'updated_at': time.time(),
            }
        def task_runner():
            with ZIP_TASKS_LOCK:
                task = ZIP_TASKS.get(task_id)
                if task:
                    task.update({'status': 'running', 'updated_at': time.time()})
            _run_zip_task(task_id, clean_urls)
        ZIP_TASK_EXECUTOR.submit(task_runner)
        return jsonify({'success': True, 'task_id': task_id, 'status': 'queued'})
    except Exception as exc:
        logger.warning('Failed to create async history zip task: %s', exc)
        return jsonify({'success': False, 'error': f'创建打包任务失败：{exc}'}), 500


@app.get('/api/generation-history/zip-tasks/<task_id>')
def get_generation_history_zip_task(task_id):
    session_data = g.get('supabase_session') or get_supabase_session()
    user_id = _get_supabase_user_id(session_data)
    if not user_id:
        return jsonify({'success': False, 'error': '请先登录'}), 401
    _cleanup_zip_tasks()
    with ZIP_TASKS_LOCK:
        task = ZIP_TASKS.get(str(task_id or '').strip())
        if not task or task.get('user_id') != user_id:
            return jsonify({'success': False, 'error': '打包任务不存在或已过期'}), 404
        status = task.get('status') or 'missing'
        return jsonify({
            'success': True,
            'task': {
                'task_id': task.get('task_id'),
                'status': status,
                'total': task.get('total') or 0,
                'success_count': task.get('success_count') or 0,
                'error': task.get('error') or '',
                'download_url': f'/api/generation-history/zip-tasks/{task.get("task_id")}/download' if status == 'succeeded' else '',
            },
        })


@app.get('/api/generation-history/zip-tasks/<task_id>/download')
def download_generation_history_zip_task(task_id):
    session_data = g.get('supabase_session') or get_supabase_session()
    user_id = _get_supabase_user_id(session_data)
    if not user_id:
        return jsonify({'success': False, 'error': '请先登录'}), 401
    with ZIP_TASKS_LOCK:
        task = ZIP_TASKS.get(str(task_id or '').strip())
        if not task or task.get('user_id') != user_id:
            return jsonify({'success': False, 'error': '打包任务不存在或已过期'}), 404
        if task.get('status') != 'succeeded' or not task.get('buffer'):
            return jsonify({'success': False, 'error': '打包任务尚未完成'}), 409
        buffer = task.get('buffer')
        filename = task.get('filename') or f'generation-history-originals-{int(time.time())}.zip'
        buffer.seek(0)
    response = send_file(buffer, mimetype='application/zip', as_attachment=True, download_name=filename)
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/api/generation-history')
def generation_history_list():
    session_data = g.get('supabase_session') or get_supabase_session()
    user_id = _get_supabase_user_id(session_data)
    if not user_id:
        return jsonify({'success': False, 'error': '请先登录'}), 401
    try:
        limit = max(1, min(int(request.args.get('limit', 50)), 50))
        offset = max(0, int(request.args.get('offset', 0)))
    except ValueError:
        return jsonify({'success': False, 'error': '分页参数无效'}), 400
    mode = request.args.get('mode') or None
    direct_items = fetch_user_generation_history_images(user_id, limit=limit + 1, offset=offset, mode=mode, _logger=logger)
    if direct_items:
        page_items = direct_items[:limit]
        next_offset = offset + len(page_items)
        return jsonify({
            'success': True,
            'items': page_items,
            'limit': limit,
            'offset': offset,
            'next_offset': next_offset,
            'has_more': len(direct_items) > limit,
            'source': 'history_images',
        })
    target_count = offset + limit + 1
    task_offset = 0
    task_batch_size = 50
    max_task_scan = 500
    items = []
    scanned = 0
    while len(items) < target_count and scanned < max_task_scan:
        tasks = fetch_user_generation_tasks(user_id, limit=task_batch_size, offset=task_offset, mode=mode, status='succeeded')
        if not tasks:
            break
        for task in tasks:
            items.extend(serialize_generation_history_items(task))
        scanned += len(tasks)
        task_offset += len(tasks)
        if len(tasks) < task_batch_size:
            break
    page_items = items[offset:offset + limit]
    next_offset = offset + len(page_items)
    return jsonify({
        'success': True,
        'items': page_items,
        'limit': limit,
        'offset': offset,
        'next_offset': next_offset,
        'has_more': len(items) > next_offset,
    })


@app.get('/api/generation-tasks/<task_id>')
@limiter.limit("30 per minute")
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
    task = maybe_fail_stale_generation_task(task)
    serialized_task = serialize_generation_task(task)
    return jsonify({'success': True, 'task': serialized_task})


@app.post('/api/generation-tasks/<task_id>/cancel')
def generation_task_cancel(task_id):
    session_data = g.get('supabase_session') or get_supabase_session()
    user_id = _get_supabase_user_id(session_data)
    if not user_id:
        return jsonify({'success': False, 'error': '请先登录'}), 401
    task = get_generation_task(task_id, prefer_cache=True)
    if not task:
        return jsonify({'success': False, 'error': '生成任务不存在或已过期'}), 404
    if str(task.get('user_id') or '') != str(user_id):
        return jsonify({'success': False, 'error': '无权访问该生成任务'}), 403
    if task.get('status') in {'succeeded', 'failed'}:
        return jsonify({'success': True, 'task': serialize_generation_task(task)})
    generation_started = bool(task.get('generation_started'))
    skip_refund = generation_started
    cancel_event = GENERATION_TASK_CANCEL_EVENTS.get(task_id)
    if cancel_event:
        cancel_event.set()
    fail_generation_task_with_refund(task_id, '生成已取消', skip_refund=skip_refund)
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
        run_async = str(request.form.get('async_task', '') or '').strip().lower() in {'1', 'true', 'yes'}

        if not selling_text and not image_payloads and not reference_payloads:
            return jsonify({'success': False, 'error': '请至少提供核心卖点文案或上传 1 张图片'}), 400

        def build_aplus_result(task_id: str):
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
            resolved_product_json = product_json
            if resolved_product_json is None and planning_payloads:
                logger.warning('A+ generation extracting product_json from uploaded reference images: product_count=%s reference_count=%s total_generation_count=%s', len(image_payloads), len(reference_payloads), len(planning_payloads))
                resolved_product_json = extract_product_json_from_image_payloads(selling_text, planning_payloads)
            logger.warning(
                'A+ generation upload payloads: product_count=%s reference_count=%s total_generation_count=%s product_json_ready=%s',
                len(image_payloads),
                len(reference_payloads),
                len(planning_payloads),
                bool(resolved_product_json),
            )
            plan = build_aplus_plan(platform, selling_text, selected_modules, planning_payloads, country, text_type, image_size_ratio, selected_style, resolved_product_json)
            images = generate_aplus_images(plan, planning_payloads, task_id, image_size_ratio, text_type, country, resolved_product_json)
            return {
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

        if run_async:
            session_data = g.get('supabase_session') or get_supabase_session()
            user_id = _get_supabase_user_id(session_data)
            if not user_id:
                return jsonify({'success': False, 'error': '请先登录'}), 401
            spend_record = None
            spend_payload = request.form.get('spend_record')
            if spend_payload:
                try:
                    parsed_spend_record = json.loads(spend_payload)
                    if isinstance(parsed_spend_record, dict):
                        spend_record = parsed_spend_record
                except (TypeError, ValueError):
                    spend_record = None
            request_id = str(request.form.get('points_request_id') or (spend_record or {}).get('requestId') or '').strip()
            task = create_generation_task(user_id, 'aplus', request_id, spend_record)
            GENERATION_TASK_EXECUTOR.submit(
                run_background_generation_task,
                task['task_id'],
                lambda: build_aplus_result(task['task_id']),
                600,
                'A+ 生成超时（10分钟），请稍后重试',
            )
            return jsonify({'success': True, 'async_task': True, 'task': task, 'task_id': task['task_id']}), 202

        task_id = uuid.uuid4().hex
        return jsonify(build_aplus_result(task_id))
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


@socketio.on('connect')
def handle_connect():
    logger.info('WebSocket client connected: %s', request.sid)


@socketio.on('disconnect')
def handle_disconnect():
    logger.info('WebSocket client disconnected: %s', request.sid)


@socketio.on('subscribe_task')
def handle_subscribe_task(data):
    task_id = data.get('task_id')
    if task_id:
        join_room(f'task_{task_id}')
        logger.debug('Client %s subscribed to task %s', request.sid, task_id)
        emit('subscribed', {'task_id': task_id})


@socketio.on('unsubscribe_task')
def handle_unsubscribe_task(data):
    task_id = data.get('task_id')
    if task_id:
        leave_room(f'task_{task_id}')
        logger.debug('Client %s unsubscribed from task %s', request.sid, task_id)


def emit_task_update(task_id, task_data):
    socketio.emit('task_update', {
        'task_id': task_id,
        'task': task_data
    }, room=f'task_{task_id}')


if __name__ == '__main__':
    from batch_worker import start_background_processor
    start_background_processor(interval=5, _logger=logger)
    
    host = get_supabase_setting('HOST', get_optional_env('HOST', '0.0.0.0')) or '0.0.0.0'
    port = get_supabase_setting_int('PORT', get_optional_int_env('PORT', 5078))
    debug = get_supabase_setting_bool('FLASK_DEBUG', get_optional_bool_env('FLASK_DEBUG', False))
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)

