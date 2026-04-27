import hashlib
import json
import os
from urllib.parse import urlparse, parse_qs

import requests
from dotenv import dotenv_values

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ENV_PATH = os.path.join(PROJECT_ROOT, '.env')
ENV = dotenv_values(ENV_PATH)
BASE_URL = 'http://8.163.52.51:60009'
SUPABASE_URL = ENV.get('SUPABASE_URL', '')
SUPABASE_ANON_KEY = ENV.get('SUPABASE_ANON_KEY', '')
TEST_EMAIL = 'paytest20260427@example.com'
TEST_PASSWORD = 'PayTest#20260427'
ZPAY_KEY = ENV.get('ZPAY_KEY', '')


def build_sign(params: dict) -> str:
    parts = []
    for key in sorted(params.keys()):
        if key in {'sign', 'sign_type'}:
            continue
        value = params.get(key)
        if value is None:
            continue
        value_str = str(value).strip()
        if not value_str:
            continue
        parts.append(f'{key}={value_str}')
    return hashlib.md5(('&'.join(parts) + ZPAY_KEY).encode('utf-8')).hexdigest()


def login_session() -> dict:
    response = requests.post(
        f'{SUPABASE_URL}/auth/v1/token?grant_type=password',
        headers={
            'apikey': SUPABASE_ANON_KEY,
            'Content-Type': 'application/json',
        },
        json={'email': TEST_EMAIL, 'password': TEST_PASSWORD},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def sync_backend_session(http_session: requests.Session, session_payload: dict) -> None:
    response = http_session.post(
        f'{BASE_URL}/api/auth/session-sync',
        json={'session': session_payload},
        timeout=20,
    )
    response.raise_for_status()


def create_order(http_session: requests.Session, *, user_id: str, product_id: str, amount: str, pay_type: str) -> dict:
    response = http_session.post(
        f'{BASE_URL}/api/pay/create',
        json={
            'user_id': user_id,
            'product_id': product_id,
            'amount': amount,
            'pay_type': pay_type,
        },
        timeout=20,
    )
    return {
        'status_code': response.status_code,
        'json': response.json(),
    }


def build_notify_payload(order_data: dict, *, trade_no: str) -> dict:
    order = order_data['data']['order']
    payload = {
        'out_trade_no': order['out_trade_no'],
        'trade_no': trade_no,
        'money': order['amount'],
        'trade_status': 'TRADE_SUCCESS',
        'sign_type': 'MD5',
    }
    payload['sign'] = build_sign(payload)
    return payload


def notify_success(payload: dict) -> dict:
    response = requests.post(f'{BASE_URL}/api/pay/notify', data=payload, timeout=20)
    return {
        'status_code': response.status_code,
        'text': response.text,
    }


def parse_payment_url(order_data: dict) -> dict:
    payment_url = order_data['data']['payment_url']
    query = parse_qs(urlparse(payment_url).query)
    simplified = {key: values[0] for key, values in query.items()}
    return {
        'payment_url': payment_url,
        'query': simplified,
    }


def main() -> None:
    supabase_session = login_session()
    user_id = supabase_session['user']['id']

    browser_session = requests.Session()
    sync_backend_session(browser_session, supabase_session)

    one_time = create_order(browser_session, user_id=user_id, product_id='plan_1', amount='1.00', pay_type='one_time')
    subscribe = create_order(browser_session, user_id=user_id, product_id='plan_2', amount='9.90', pay_type='subscribe')

    one_time_notify = None
    subscribe_notify = None
    if one_time['status_code'] == 200 and one_time['json'].get('success'):
        one_time_order_no = one_time['json']['data']['order']['out_trade_no']
        one_time_notify = notify_success(build_notify_payload(one_time['json'], trade_no=f'TRADE-ONE-TIME-{one_time_order_no}'))
    if subscribe['status_code'] == 200 and subscribe['json'].get('success'):
        subscribe_order_no = subscribe['json']['data']['order']['out_trade_no']
        subscribe_notify = notify_success(build_notify_payload(subscribe['json'], trade_no=f'TRADE-SUBSCRIBE-{subscribe_order_no}'))

    result = {
        'user_id': user_id,
        'one_time': {
            'create': one_time,
            'payment': parse_payment_url(one_time['json']) if one_time['status_code'] == 200 and one_time['json'].get('success') else None,
            'notify': one_time_notify,
        },
        'subscribe': {
            'create': subscribe,
            'payment': parse_payment_url(subscribe['json']) if subscribe['status_code'] == 200 and subscribe['json'].get('success') else None,
            'notify': subscribe_notify,
        },
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
