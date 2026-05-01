import json
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from openai import APIError, APIStatusError

from config import get_supabase_setting

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IMAGE_SIZE_RATIO_MAP = {
    '1:1': '2048x2048',
    '3:4': '1728x2304',
    '9:16': '1440x2560',
    '16:9': '2560x1440',
}

HEX_COLOR_PATTERN = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


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


def parse_money_amount(value) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('金额格式不正确') from exc
    if amount <= Decimal('0.00'):
        raise ValueError('金额必须大于 0')
    return amount


def normalize_vip_plan_key(product_id: str | None) -> str:
    normalized_product_id = str(product_id or '').strip().lower()
    if not normalized_product_id:
        return ''
    if normalized_product_id not in {'plan_1', 'plan_2', 'plan_3'}:
        raise ValueError(f'无效的套餐标识: {normalized_product_id}')
    return normalized_product_id


def _resolve_configured_plan_key(value: str) -> str:
    normalized_value = str(value or '').strip().lower()
    return normalized_value if normalized_value in {'plan_1', 'plan_2', 'plan_3'} else ''


def parse_iso_datetime(value: str | None) -> datetime | None:
    raw_value = str(value or '').strip()
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value.replace('Z', '+00:00'))
    except ValueError:
        return None


def normalize_platform_label(platform: str) -> str:
    value = (platform or '').strip()
    if not value:
        return '亚马逊'
    if value == '速卖通速卖通':
        return '速卖通'
    return value


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


def resolve_image_size(image_size_ratio: str) -> str:
    ratio = (image_size_ratio or '').strip()
    if ratio in IMAGE_SIZE_RATIO_MAP:
        return IMAGE_SIZE_RATIO_MAP[ratio]
    return get_supabase_setting('ARK_IMAGE_SIZE', '2048x2048')


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

    logger.exception('ARK image generation failed: status=%s details=%s', status_code, details)

    return {
        'success': False,
        'error': '图像生成接口调用失败',
        'details': details,
    }, status_code


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
