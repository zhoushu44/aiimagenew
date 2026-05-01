import json
import logging
from datetime import datetime, timezone

import requests

from config import (
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_POINTS_TABLE,
    SUPABASE_PAYMENTS_TABLE,
    SUPABASE_USER_PROFILES_TABLE,
    SUPABASE_GENERATION_TASKS_TABLE,
    VIP_PLAN_CONFIG_TABLE,
    build_supabase_request_url,
    _build_supabase_service_headers,
    _get_supabase_user_id,
)
from utils import (
    parse_iso_datetime,
    normalize_vip_plan_key,
    _extract_single_supabase_row,
    _safe_json_payload,
)

logger = logging.getLogger(__name__)


def build_supabase_auth_headers() -> dict:
    return {
        'apikey': SUPABASE_ANON_KEY,
        'Content-Type': 'application/json',
    }


def _fetch_user_points_row(user_id: str, _logger: logging.Logger | None = None) -> dict | None:
    log = _logger or logger
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


def get_user_points_balance(user_id: str, _logger: logging.Logger | None = None) -> dict | None:
    log = _logger or logger
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id:
        return None
    try:
        return _fetch_user_points_row(normalized_user_id, _logger=log)
    except requests.RequestException as exc:
        log.warning('Failed to fetch user points balance for %s: %s', normalized_user_id, exc)
        return None


def _create_legacy_points_balance_row(user_id: str, _logger: logging.Logger | None = None) -> dict | None:
    log = _logger or logger
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


def _ensure_points_balance_row_direct(user_id: str, _logger: logging.Logger | None = None) -> dict | None:
    log = _logger or logger
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id:
        return None
    points_row = get_user_points_balance(normalized_user_id, _logger=log)
    if points_row:
        return _normalize_points_row(points_row, normalized_user_id)
    try:
        return _create_legacy_points_balance_row(normalized_user_id, _logger=log)
    except requests.RequestException as exc:
        log.warning('Failed to create legacy points balance row for %s: %s', normalized_user_id, exc)
        return _normalize_points_row(_build_legacy_points_balance_row(normalized_user_id), normalized_user_id)


def _claim_daily_free_points_direct(user_id: str, amount: int, _logger: logging.Logger | None = None) -> dict | None:
    log = _logger or logger
    normalized_user_id = str(user_id or '').strip()
    normalized_amount = max(int(amount or 0), 0)
    if not normalized_user_id:
        return None
    points_row = _ensure_points_balance_row_direct(normalized_user_id, _logger=log)
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


def _spend_user_points_direct(user_id: str, amount: int, transaction_type: str = 'consume', reason: str = '', metadata: dict | None = None, _logger: logging.Logger | None = None) -> dict | None:
    log = _logger or logger
    normalized_user_id = str(user_id or '').strip()
    normalized_amount = int(amount)
    if not normalized_user_id or normalized_amount <= 0:
        return None
    points_row = _ensure_points_balance_row_direct(normalized_user_id, _logger=log)
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
        balance_row = get_user_points_balance(normalized_user_id, _logger=log) or points_row
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
        log.warning('Failed to insert direct spend transaction for %s: %s', normalized_user_id, exc)
    return {
        'success': True,
        'spent': True,
        'balance_row': balance_row,
        'transaction_row': transaction_row,
    }


def add_user_points_direct(user_id: str, amount: int, transaction_type: str = 'refund', reason: str = '', metadata: dict | None = None, related_transaction_id=None, _logger: logging.Logger | None = None) -> dict | None:
    log = _logger or logger
    normalized_user_id = str(user_id or '').strip()
    normalized_amount = max(int(amount), 0)
    if not normalized_user_id or normalized_amount <= 0:
        return None
    points_row = _ensure_points_balance_row_direct(normalized_user_id, _logger=log)
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
        return get_user_points_balance(normalized_user_id, _logger=log) or points_row
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
        log.warning('Failed to insert direct add transaction for %s: %s', normalized_user_id, exc)
    return {
        'success': True,
        'added': True,
        'balance_row': balance_row,
        'transaction_row': transaction_row,
    }


def fetch_vip_plan_config(_logger: logging.Logger | None = None) -> dict:
    log = _logger or logger
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError('Supabase 服务配置缺失')
    response = requests.get(
        build_supabase_request_url(f'/rest/v1/{VIP_PLAN_CONFIG_TABLE}'),
        headers=_build_supabase_service_headers(),
        params={
            'select': '*',
            'config_key': 'eq.default',
            'limit': '1',
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    row = _extract_single_supabase_row(payload)
    if not isinstance(row, dict) or not row:
        raise RuntimeError('未找到 Supabase vip_plan_config 套餐配置')
    return row


def grant_payment_points_once(order_row: dict, _logger: logging.Logger | None = None) -> dict | None:
    log = _logger or logger
    user_id = str((order_row or {}).get('user_id') or '').strip()
    order_no = str((order_row or {}).get('order_no') or (order_row or {}).get('out_trade_no') or '').strip()
    package_id = str((order_row or {}).get('package_id') or (order_row or {}).get('product_id') or '').strip()

    from points_rules import get_payment_points_amount
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
            'metadata': f"cs.{json.dumps({'order_no': order_no}, separators=(',', ':'), ensure_ascii=False)}",
            'limit': '1',
        },
        timeout=20,
    )
    existing_response.raise_for_status()
    existing_payload = existing_response.json()
    if isinstance(existing_payload, list) and existing_payload:
        return get_user_points_balance(user_id, _logger=log)

    from points_rules import add_user_points
    return add_user_points(
        user_id,
        points_amount,
        'purchase',
        '购买积分套餐入账',
        {
            'order_no': order_no,
            'package_id': package_id,
            'amount': str((order_row or {}).get('amount') or ''),
            'zpay_trade_no': str((order_row or {}).get('zpay_trade_no') or (order_row or {}).get('trade_no') or ''),
        },
    )


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


def persist_generation_task(task: dict, _logger: logging.Logger | None = None) -> None:
    log = _logger or logger
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
            log.warning('Failed to persist generation task %s: status=%s body=%s', db_payload.get('id'), response.status_code, response.text)
            response.raise_for_status()
    except Exception as exc:
        log.warning('Failed to persist generation task %s: %s', db_payload.get('id'), exc)


def fetch_generation_task_row(task_id: str, _logger: logging.Logger | None = None) -> dict | None:
    log = _logger or logger
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
            log.warning('Failed to fetch generation task %s: status=%s body=%s', normalized_task_id, response.status_code, response.text)
            return None
        return _extract_single_supabase_row(response.json())
    except Exception as exc:
        log.warning('Failed to fetch generation task %s: %s', normalized_task_id, exc)
        return None


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
    }


def fetch_latest_active_subscription(user_id: str, product_id: str, _logger: logging.Logger | None = None) -> dict | None:
    log = _logger or logger
    normalized_user_id = str(user_id or '').strip()
    normalized_product_id = normalize_vip_plan_key(product_id)
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
            'status': 'in.(paid,success)',
            'order': 'subscribe_expire.desc',
            'limit': '1',
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return _extract_single_supabase_row(payload)


def create_payment_order_record(order_payload: dict, _logger: logging.Logger | None = None) -> dict:
    log = _logger or logger
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError('Supabase 服务配置缺失')

    def _build_legacy_payment_order_payload(p: dict) -> dict:
        return {
            'out_trade_no': p.get('order_no'),
            'user_id': p.get('user_id'),
            'amount': p.get('amount'),
            'status': p.get('status'),
            'type': p.get('pay_type'),
            'product_id': p.get('package_id'),
            'trade_no': p.get('zpay_trade_no'),
            'subscribe_start': p.get('subscribe_start_at'),
            'subscribe_expire': p.get('subscribe_expire_at'),
        }

    db_payload = _build_legacy_payment_order_payload(order_payload)
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


def fetch_payment_order_by_out_trade_no(out_trade_no: str, _logger: logging.Logger | None = None) -> dict | None:
    log = _logger or logger
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


def update_payment_order(out_trade_no: str, patch_payload: dict, _logger: logging.Logger | None = None) -> dict:
    log = _logger or logger
    normalized_order_no = str(out_trade_no or '').strip()
    if not normalized_order_no:
        raise ValueError('缺少 out_trade_no')

    def _build_legacy_payment_patch_payload(p: dict) -> dict:
        legacy_payload = {}
        if 'status' in p:
            legacy_payload['status'] = p.get('status')
        if 'zpay_trade_no' in p:
            legacy_payload['trade_no'] = p.get('zpay_trade_no')
        if 'subscribe_start_at' in p:
            legacy_payload['subscribe_start'] = p.get('subscribe_start_at')
        if 'subscribe_expire_at' in p:
            legacy_payload['subscribe_expire'] = p.get('subscribe_expire_at')
        return legacy_payload

    db_payload = _build_legacy_payment_patch_payload(patch_payload)
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
        log.warning('Failed to patch payment order %s: status=%s body=%s', normalized_order_no, response.status_code, response.text)
        response.raise_for_status()
    row = fetch_payment_order_by_out_trade_no(normalized_order_no, _logger=log)
    if not row:
        raise RuntimeError('更新支付订单失败')
    return row


def fetch_user_profile_by_user_id(user_id: str, _logger: logging.Logger | None = None) -> dict | None:
    log = _logger or logger
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


def upsert_user_subscription_profile(user_id: str, subscribe_expire: str | None, _logger: logging.Logger | None = None) -> dict:
    log = _logger or logger
    normalized_user_id = str(user_id or '').strip()
    normalized_expire = str(subscribe_expire or '').strip()
    if not normalized_user_id:
        raise ValueError('缺少 user_id')
    existing_row = fetch_user_profile_by_user_id(normalized_user_id, _logger=log)
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
            log.warning('Failed to patch user subscription profile for %s: %s', normalized_user_id, response.text)
            response.raise_for_status()
        refreshed_row = fetch_user_profile_by_user_id(normalized_user_id, _logger=log)
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
        log.warning('Failed to create user subscription profile for %s: %s', normalized_user_id, response.text)
        response.raise_for_status()
    payload = response.json()
    row = _extract_single_supabase_row(payload, allow_empty=True)
    return row or {}


def _fetch_supabase_user_admin_flag(user_id: str, _logger: logging.Logger | None = None) -> bool:
    log = _logger or logger
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
        log.warning('Failed to fetch admin flag for %s: %s', normalized_user_id, exc)
        return False

    if not isinstance(payload, list) or not payload:
        return False

    row = payload[0]
    if not isinstance(row, dict):
        return False

    def _is_truthy_flag(value) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

    return _is_truthy_flag(row.get('is_admin'))


def find_refundable_spend_transaction(user_id: str, request_id: str, amount: int | None = None, transaction_type: str = '', _logger: logging.Logger | None = None) -> dict | None:
    log = _logger or logger
    normalized_user_id = str(user_id or '').strip()
    normalized_request_id = str(request_id or '').strip()
    normalized_transaction_type = str(transaction_type or '').strip()
    if not normalized_user_id or not normalized_request_id:
        return None
    params = {
        'select': '*',
        'user_id': f'eq.{normalized_user_id}',
        'metadata': f"cs.{json.dumps({'request_id': normalized_request_id}, separators=(',', ':'), ensure_ascii=False)}",
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


def find_refund_transaction_for_request(user_id: str, request_id: str, _logger: logging.Logger | None = None) -> dict | None:
    log = _logger or logger
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
            'metadata': f"cs.{json.dumps({'request_id': normalized_request_id}, separators=(',', ':'), ensure_ascii=False)}",
            'limit': '1',
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return _extract_single_supabase_row(payload)


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


def supabase_logout_session(session_data: dict, _logger: logging.Logger | None = None) -> bool:
    log = _logger or logger
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
        log.warning('Failed to revoke Supabase session: %s', exc)
        return False

    if response.status_code not in {200, 204}:
        log.warning('Supabase logout returned %s: %s', response.status_code, response.text[:200])
        return False

    return True


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
