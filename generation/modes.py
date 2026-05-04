import base64
import concurrent.futures
import io
import json
import logging
import re
import threading
import time
from pathlib import Path

import requests
from openai import OpenAI
from PIL import Image

from config import (
    get_supabase_setting,
    get_supabase_setting_int,
    get_supabase_setting_bool,
    get_optional_env,
    get_optional_int_env,
    get_optional_bool_env,
    get_app_mode,
)
from utils import IMAGE_SIZE_RATIO_MAP
from image_utils import (
    build_enriched_image_prompt,
)

logger = logging.getLogger(__name__)


def _normalize_generated_image_item(item):
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
    return _normalize_generated_image_item(data[0])


def collect_generated_images(response):
    data = getattr(response, 'data', None)
    if data is None and isinstance(response, dict):
        data = response.get('data')
    if not isinstance(data, list) or not data:
        raise ValueError('图像生成接口未返回图片数据')
    return [_normalize_generated_image_item(item) for item in data]


def _common_image_api_key(default: str = '') -> str:
    return get_supabase_setting('IMAGE_API_KEY', get_optional_env('IMAGE_API_KEY', default))


def _common_image_base_url(default: str = '') -> str:
    return get_supabase_setting('IMAGE_BASE_URL', get_optional_env('IMAGE_BASE_URL', default)).rstrip('/')


def _common_image_model(default: str = '') -> str:
    return get_supabase_setting('IMAGE_MODEL', get_optional_env('IMAGE_MODEL', default))


def get_mode1_api_key() -> str:
    api_key = get_supabase_setting('MODE1_IMAGE_API_KEY', get_optional_env('MODE1_IMAGE_API_KEY', ''))
    if not api_key:
        api_key = _common_image_api_key('')
    if not api_key:
        api_key = get_supabase_setting('ARK_API_KEY', get_optional_env('ARK_API_KEY', ''))
    if not api_key:
        api_key = get_supabase_setting('OPENAI_API_KEY', get_optional_env('OPENAI_API_KEY', ''))
    return api_key


def get_mode1_base_url() -> str:
    url = get_supabase_setting('MODE1_IMAGE_BASE_URL', get_optional_env('MODE1_IMAGE_BASE_URL', '')).rstrip('/')
    if not url:
        url = _common_image_base_url('')
    if not url:
        url = get_supabase_setting('ARK_BASE_URL', get_optional_env('ARK_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')).rstrip('/')
    return url


def get_mode1_client() -> OpenAI:
    return OpenAI(
        api_key=get_mode1_api_key(),
        base_url=get_mode1_base_url(),
    )


def get_mode2_api_key() -> str:
    api_key = get_supabase_setting('MODE2_IMAGE_API_KEY', get_optional_env('MODE2_IMAGE_API_KEY', ''))
    if not api_key:
        api_key = _common_image_api_key('any-value')
    return api_key


def get_mode2_base_url() -> str:
    url = get_supabase_setting('MODE2_IMAGE_BASE_URL', get_optional_env('MODE2_IMAGE_BASE_URL', '')).rstrip('/')
    if not url:
        url = _common_image_base_url('https://ark.cn-beijing.volces.com/api/v3')
    return url


def get_mode2_client() -> OpenAI:
    return OpenAI(
        api_key=get_mode2_api_key(),
        base_url=get_mode2_base_url(),
    )


def get_mode3_api_key() -> str:
    api_key = get_supabase_setting('MODE3_IMAGE_API_KEY', get_optional_env('MODE3_IMAGE_API_KEY', ''))
    if not api_key:
        api_key = _common_image_api_key('')
    if not api_key:
        api_key = get_supabase_setting('OPENAI_API_KEY', get_optional_env('OPENAI_API_KEY', ''))
    return api_key


def get_mode3_base_url() -> str:
    url = get_supabase_setting('MODE3_IMAGE_BASE_URL', get_optional_env('MODE3_IMAGE_BASE_URL', '')).rstrip('/')
    if not url:
        url = _common_image_base_url('https://code.ciyuanapi.xyz/v1')
    return url


def get_mode3_client() -> OpenAI:
    return OpenAI(
        api_key=get_mode3_api_key(),
        base_url=get_mode3_base_url(),
    )


def get_ark_client() -> OpenAI:
    api_key = get_supabase_setting('ARK_API_KEY', get_optional_env('ARK_API_KEY', ''))
    if not api_key:
        raise ValueError('缺少环境变量：ARK_API_KEY')
    return OpenAI(
        api_key=api_key,
        base_url=get_supabase_setting('ARK_BASE_URL', get_optional_env('ARK_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')).rstrip('/'),
    )


def _common_parallel_workers() -> int:
    return max(get_supabase_setting_int('PARALLEL_WORKERS', get_optional_int_env('PARALLEL_WORKERS', 3)), 1)


def _common_retry_attempts() -> int:
    return max(get_supabase_setting_int('RETRY_ATTEMPTS', get_optional_int_env('RETRY_ATTEMPTS', 2)), 0)


def _common_retry_delay_seconds() -> float:
    raw_value = get_supabase_setting('RETRY_DELAY_SECONDS', get_optional_env('RETRY_DELAY_SECONDS', '0.5'))
    try:
        return max(float(raw_value), 0.0)
    except ValueError:
        return 0.5


def _common_partial_retry_attempts() -> int:
    return max(get_supabase_setting_int('PARTIAL_RETRY_ATTEMPTS', get_optional_int_env('PARTIAL_RETRY_ATTEMPTS', 2)), 0)


def _common_timeout_seconds() -> int:
    return max(get_supabase_setting_int('TIMEOUT_SECONDS', get_optional_int_env('TIMEOUT_SECONDS', 180)), 30)


def _common_sequential_generation(target_count: int, image_payloads) -> bool:
    mode = str(get_supabase_setting('SEQUENTIAL_GENERATION', get_optional_env('SEQUENTIAL_GENERATION', 'auto')) or 'auto').strip().lower()
    if mode in {'on', 'true', '1', 'yes'}:
        return True
    if mode in {'off', 'false', '0', 'no'}:
        return False
    return int(target_count or 0) <= 1


def get_mode1_retry_attempts() -> int:
    return max(get_supabase_setting_int('MODE1_RETRY_ATTEMPTS', get_optional_int_env('MODE1_RETRY_ATTEMPTS', _common_retry_attempts())), 0)


def get_mode1_retry_delay_seconds() -> float:
    raw_value = get_supabase_setting('MODE1_RETRY_DELAY_SECONDS', get_optional_env('MODE1_RETRY_DELAY_SECONDS', str(_common_retry_delay_seconds())))
    try:
        return max(float(raw_value), 0.0)
    except ValueError:
        return _common_retry_delay_seconds()


def get_mode1_parallel_workers() -> int:
    return max(get_supabase_setting_int('MODE1_PARALLEL_WORKERS', get_optional_int_env('MODE1_PARALLEL_WORKERS', _common_parallel_workers())), 1)


def get_mode1_partial_retry_attempts() -> int:
    return max(get_supabase_setting_int('MODE1_PARTIAL_RETRY_ATTEMPTS', get_optional_int_env('MODE1_PARTIAL_RETRY_ATTEMPTS', _common_partial_retry_attempts())), 0)


def should_mode1_use_sequential_generation(target_count: int, image_payloads) -> bool:
    mode = str(get_supabase_setting('MODE1_SEQUENTIAL_GENERATION', get_optional_env('MODE1_SEQUENTIAL_GENERATION', 'auto')) or 'auto').strip().lower()
    if mode in {'on', 'true', '1', 'yes'}:
        return True
    if mode in {'off', 'false', '0', 'no'}:
        return False
    return _common_sequential_generation(target_count, image_payloads)


def get_mode2_retry_attempts() -> int:
    return max(get_supabase_setting_int('MODE2_RETRY_ATTEMPTS', get_optional_int_env('MODE2_RETRY_ATTEMPTS', _common_retry_attempts())), 0)


def get_mode2_retry_delay_seconds() -> float:
    raw_value = get_supabase_setting('MODE2_RETRY_DELAY_SECONDS', get_optional_env('MODE2_RETRY_DELAY_SECONDS', str(_common_retry_delay_seconds())))
    try:
        return max(float(raw_value), 0.0)
    except ValueError:
        return _common_retry_delay_seconds()


def get_mode2_parallel_workers() -> int:
    return max(get_supabase_setting_int('MODE2_PARALLEL_WORKERS', get_optional_int_env('MODE2_PARALLEL_WORKERS', _common_parallel_workers())), 1)


def get_mode2_partial_retry_attempts() -> int:
    return max(get_supabase_setting_int('MODE2_PARTIAL_RETRY_ATTEMPTS', get_optional_int_env('MODE2_PARTIAL_RETRY_ATTEMPTS', _common_partial_retry_attempts())), 0)


def should_mode2_use_sequential_generation(target_count: int, image_payloads) -> bool:
    mode = str(get_supabase_setting('MODE2_SEQUENTIAL_GENERATION', get_optional_env('MODE2_SEQUENTIAL_GENERATION', 'auto')) or 'auto').strip().lower()
    if mode in {'on', 'true', '1', 'yes'}:
        return True
    if mode in {'off', 'false', '0', 'no'}:
        return False
    return _common_sequential_generation(target_count, image_payloads)


def get_mode3_retry_attempts() -> int:
    return max(get_supabase_setting_int('MODE3_RETRY_ATTEMPTS', get_optional_int_env('MODE3_RETRY_ATTEMPTS', _common_retry_attempts())), 0)


def get_mode3_retry_delay_seconds() -> float:
    raw_value = get_supabase_setting('MODE3_RETRY_DELAY_SECONDS', get_optional_env('MODE3_RETRY_DELAY_SECONDS', str(_common_retry_delay_seconds())))
    try:
        return max(float(raw_value), 0.0)
    except ValueError:
        return _common_retry_delay_seconds()


def get_mode3_parallel_workers() -> int:
    return max(get_supabase_setting_int('MODE3_PARALLEL_WORKERS', get_optional_int_env('MODE3_PARALLEL_WORKERS', _common_parallel_workers())), 1)


def get_mode3_partial_retry_attempts() -> int:
    return max(get_supabase_setting_int('MODE3_PARTIAL_RETRY_ATTEMPTS', get_optional_int_env('MODE3_PARTIAL_RETRY_ATTEMPTS', _common_partial_retry_attempts())), 0)


def get_mode3_timeout_seconds() -> int:
    return max(get_supabase_setting_int('MODE3_TIMEOUT_SECONDS', get_optional_int_env('MODE3_TIMEOUT_SECONDS', _common_timeout_seconds())), 30)


def should_mode3_use_sequential_generation(target_count: int, image_payloads) -> bool:
    mode = str(get_supabase_setting('MODE3_SEQUENTIAL_GENERATION', get_optional_env('MODE3_SEQUENTIAL_GENERATION', 'auto')) or 'auto').strip().lower()
    if mode in {'on', 'true', '1', 'yes'}:
        return True
    if mode in {'off', 'false', '0', 'no'}:
        return False
    return _common_sequential_generation(target_count, image_payloads)


def get_mode2_sample_strength(sample_strength: str) -> float:
    raw_value = (sample_strength or '').strip() or get_supabase_setting('MODE2_DEFAULT_SAMPLE_STRENGTH', get_optional_env('MODE2_DEFAULT_SAMPLE_STRENGTH', '0.65'))
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError('sample_strength 必须为数字') from exc


def is_retryable_mode1_error(exc: Exception) -> bool:
    message = str(exc or '')
    retryable_fragments = (
        'openai_error',
        'bad_response_status_code',
        'Read timed out',
        'timed out',
        'Connection aborted',
        'Connection reset',
        'temporarily unavailable',
        'upstream',
        '524',
        'ssl',
        'sslerror',
        'decryption failed',
        'bad record mac',
        'max retries exceeded',
        'connectionpool',
        'protocolerror',
        'eof',
        'unexpected eof',
    )
    if any(fragment.lower() in message.lower() for fragment in retryable_fragments):
        return True
    status_code = getattr(exc, 'status_code', None)
    return status_code in {408, 409, 425, 429, 500, 502, 503, 504, 524}


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


def is_retryable_mode3_error(exc: Exception) -> bool:
    message = str(exc or '')
    retryable_fragments = (
        'openai_error',
        'bad_response_status_code',
        'Read timed out',
        'timed out',
        'Connection aborted',
        'Connection reset',
        'temporarily unavailable',
        'upstream',
        '524',
        'ssl',
        'sslerror',
        'decryption failed',
        'bad record mac',
        'max retries exceeded',
        'connectionpool',
        'protocolerror',
        'eof',
        'unexpected eof',
    )
    if any(fragment.lower() in message.lower() for fragment in retryable_fragments):
        return True
    status_code = getattr(exc, 'status_code', None)
    return status_code in {408, 409, 425, 429, 500, 502, 503, 504, 524}


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


def _resolve_image_size(image_size_ratio: str) -> str:
    ratio = (image_size_ratio or '').strip()
    if ratio in IMAGE_SIZE_RATIO_MAP:
        return IMAGE_SIZE_RATIO_MAP[ratio]
    return get_supabase_setting('ARK_IMAGE_SIZE', '2048x2048')


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


def get_mode3_image_edit_size(image_size_ratio: str = '') -> str:
    configured_size = get_supabase_setting('MODE3_IMAGE_EDIT_SIZE', get_optional_env('MODE3_IMAGE_EDIT_SIZE', '2048x2048')).strip()
    if configured_size:
        return configured_size
    return '2048x2048'


def get_mode3_image_generation_size(image_size_ratio: str = '') -> str:
    configured_size = get_supabase_setting('MODE3_IMAGE_GENERATION_SIZE', get_optional_env('MODE3_IMAGE_GENERATION_SIZE', '')).strip()
    if configured_size:
        return configured_size
    ratio = (image_size_ratio or '').strip()
    generation_size_map = {
        '1:1': '1024x1024',
        '3:4': '1024x1536',
        '4:3': '1536x1024',
        '9:16': '1024x1792',
        '16:9': '1792x1024',
    }
    return generation_size_map.get(ratio, '1024x1024')


_BLANK_CANVAS_DIR = Path(__file__).resolve().parent.parent / 'static' / 'blank'
_BLANK_CANVAS_CACHE: dict[str, 'LazyImagePayload'] = {}
_BLANK_CANVAS_CACHE_LOCK = threading.Lock()


def _get_or_create_blank_canvas(size_key: str, width: int, height: int):
    from image_utils import LazyImagePayload
    with _BLANK_CANVAS_CACHE_LOCK:
        cached = _BLANK_CANVAS_CACHE.get(size_key)
        if cached is not None:
            return cached
        file_path = _BLANK_CANVAS_DIR / f'blank-{size_key}.png'
        if file_path.exists():
            image_bytes = file_path.read_bytes()
        else:
            image = Image.new('RGB', (width, height), (255, 255, 255))
            buffer = io.BytesIO()
            image.save(buffer, format='PNG', optimize=True)
            image_bytes = buffer.getvalue()
            del image
            del buffer
        payload = LazyImagePayload(
            filename=f'blank-{size_key}.png',
            mime_type='image/png',
            content=image_bytes,
        )
        _BLANK_CANVAS_CACHE[size_key] = payload
        return payload


def _create_blank_canvas_payload(prefix: str, width: int, height: int):
    return _get_or_create_blank_canvas(f'{width}x{height}', width, height)


def create_mode1_blank_canvas_payload(image_size_ratio: str = ''):
    size = _resolve_image_size(image_size_ratio)
    width, height = 2048, 2048
    match = re.fullmatch(r'(\d+)x(\d+)', size)
    if match:
        width, height = int(match.group(1)), int(match.group(2))
    return _create_blank_canvas_payload('mode1', width, height)


def create_mode2_blank_canvas_payload(ratio: str = '', resolution: str = ''):
    size = resolve_mode2_image_size(ratio, resolution)
    width, height = 2048, 2048
    match = re.fullmatch(r'(\d+)x(\d+)', size)
    if match:
        width, height = int(match.group(1)), int(match.group(2))
    return _create_blank_canvas_payload('mode2', width, height)


def create_mode3_blank_canvas_payload(image_size_ratio: str = ''):
    size = get_mode3_image_edit_size(image_size_ratio)
    width, height = 2048, 2048
    match = re.fullmatch(r'(\d+)x(\d+)', size)
    if match:
        width, height = int(match.group(1)), int(match.group(2))
    return _create_blank_canvas_payload('mode3', width, height)


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


def call_mode1_image_edit(client: OpenAI, prompt: str, image_payloads, image_size_ratio: str = '', _logger: logging.Logger | None = None):
    log = _logger or logger
    model = get_supabase_setting('ARK_IMAGE_MODEL', get_optional_env('ARK_IMAGE_MODEL', 'doubao-seedream-5-0-260128'))
    size = _resolve_image_size(image_size_ratio)
    watermark = get_supabase_setting_bool('ARK_IMAGE_WATERMARK', get_optional_bool_env('ARK_IMAGE_WATERMARK', False))
    reference_instruction = build_mode1_reference_anchor_prompt(len(image_payloads or []))
    request_payload = {
        'model': model,
        'prompt': reference_instruction + prompt,
        'size': size,
        'response_format': 'url',
        'extra_body': {
            'image': [image_payload['data_url'] for image_payload in image_payloads],
            'watermark': watermark,
            'sequential_image_generation': 'disabled',
        },
    }
    log.warning('Mode1 image edit request model=%s size=%s reference_count=%s', model, size, len(image_payloads or []))
    response = client.images.generate(**request_payload)
    return pick_generated_image_item(response), model


def call_mode1_text2image(client: OpenAI, prompt: str):
    model = get_supabase_setting('ARK_IMAGE_MODEL', get_optional_env('ARK_IMAGE_MODEL', 'doubao-seedream-5-0-260128'))
    blank_payload = create_mode1_blank_canvas_payload()
    generated_item, _model = call_mode1_image_edit(client, prompt, [blank_payload], '1:1')
    return generated_item, model


def call_mode2_images_generate_with_retry(client: OpenAI, request_payload: dict, _logger: logging.Logger | None = None):
    log = _logger or logger
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
            log.warning('Mode2 image generation failed, retrying in %.2fs (%s/%s): %s', wait_seconds, attempt_index + 1, retry_attempts, exc)
            time.sleep(wait_seconds)
    raise last_exc


def call_mode2_image_edit(client: OpenAI, prompt: str, image_payloads, ratio: str, resolution: str, sample_strength: str, _logger: logging.Logger | None = None):
    log = _logger or logger
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
    log.warning('Mode2 image edit request extra_body image_count=%s ratio=%s resolution=%s', request_extra_body['image_count'], request_extra_body['ratio'], request_extra_body['resolution'])
    response = call_mode2_images_generate_with_retry(client, request_payload, _logger=log)
    return pick_generated_image_item(response), model


def call_mode2_text2image(client: OpenAI, prompt: str, ratio: str, resolution: str):
    model = get_supabase_setting('MODE2_TEXT2IMAGE_MODEL', get_optional_env('MODE2_TEXT2IMAGE_MODEL', 'doubao-seedream-5-0-260128'))
    blank_payload = create_mode2_blank_canvas_payload(ratio, resolution)
    generated_item, _model = call_mode2_image_edit(client, prompt, [blank_payload], ratio, resolution, '')
    return generated_item, model


def call_mode3_image_generation(client: OpenAI, prompt: str, image_size_ratio: str = '', _logger: logging.Logger | None = None):
    log = _logger or logger
    model = get_supabase_setting('MODE3_IMAGE_MODEL', get_optional_env('MODE3_IMAGE_MODEL', 'gpt-image-2'))
    size = get_mode3_image_generation_size(image_size_ratio)
    watermark = get_supabase_setting_bool('MODE3_IMAGE_WATERMARK', get_optional_bool_env('MODE3_IMAGE_WATERMARK', False))
    base_url = get_mode3_base_url()
    api_key = get_mode3_api_key()
    if not api_key:
        raise ValueError('mode3 文生图缺少 MODE3_OPENAI_API_KEY')
    request_url = f'{base_url}/images/generations'
    data = {
        'model': model,
        'prompt': prompt,
        'size': size,
        'response_format': 'url',
    }
    quality = get_supabase_setting('MODE3_IMAGE_QUALITY', get_optional_env('MODE3_IMAGE_QUALITY', '')).strip()
    if quality:
        data['quality'] = quality
    if watermark:
        data['watermark'] = 'true'
    log.warning('Mode3 image generation request model=%s size=%s base_url=%s', model, size, base_url)
    try:
        response = requests.post(
            request_url,
            headers={'Authorization': f'Bearer {api_key}'},
            json=data,
            timeout=get_mode3_timeout_seconds(),
        )
    except Exception as exc:
        log.exception('Mode3 image generation request failed before response: model=%s size=%s base_url=%s error=%s', model, size, base_url, exc)
        raise
    if response.status_code >= 400:
        log.warning(
            'Mode3 image generation response error: model=%s size=%s base_url=%s status=%s body=%s',
            model,
            size,
            base_url,
            response.status_code,
            response.text[:500],
        )
        raise ValueError(f'mode3 文生图接口错误 {response.status_code}：{response.text[:500]}')
    try:
        payload = response.json()
    except ValueError as exc:
        log.warning('Mode3 image generation response json parse failed: model=%s size=%s base_url=%s body=%s', model, size, base_url, response.text[:500])
        raise ValueError('mode3 文生图接口返回了无效 JSON') from exc
    return pick_generated_image_item(payload), model


def call_mode3_image_edit(client: OpenAI, prompt: str, image_payloads, image_size_ratio: str = '', _logger: logging.Logger | None = None):
    log = _logger or logger
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
    log.warning(
        'Mode3 image edit request via images/edits multipart model=%s size=%s reference_count=%s base_url=%s template=mode1_reference_anchor',
        model,
        size,
        len(files),
        base_url,
    )
    try:
        response = requests.post(
            request_url,
            headers={'Authorization': f'Bearer {api_key}'},
            data=data,
            files=files,
            timeout=get_mode3_timeout_seconds(),
        )
    except Exception as exc:
        log.exception('Mode3 image edit request failed before response: model=%s size=%s reference_count=%s base_url=%s error=%s', model, size, len(files), base_url, exc)
        raise
    if response.status_code >= 400:
        log.warning(
            'Mode3 image edit response error: model=%s size=%s reference_count=%s base_url=%s status=%s body=%s',
            model,
            size,
            len(files),
            base_url,
            response.status_code,
            response.text[:500],
        )
        raise ValueError(f'mode3 图生图接口错误 {response.status_code}：{response.text[:500]}')
    try:
        payload = response.json()
    except ValueError as exc:
        log.warning('Mode3 image edit response json parse failed: model=%s size=%s reference_count=%s base_url=%s body=%s', model, size, len(files), base_url, response.text[:500])
        raise ValueError('mode3 图生图接口返回了无效 JSON') from exc
    return pick_generated_image_item(payload), model


def call_mode3_text2image(client: OpenAI, prompt: str):
    generated_item, model = call_mode3_image_generation(client, prompt, '')
    return generated_item, model


def call_mode1_single_image(prompt: str, image_payloads, image_size_ratio: str = '', text_type: str = '', country: str = '', product_json=None, image_type: str = '', plan_item=None, all_plan_types=None):
    generated_item, _model = call_mode1_image_edit(get_mode1_client(), prompt, image_payloads or [create_mode1_blank_canvas_payload(image_size_ratio)], image_size_ratio)
    return generated_item


def call_mode1_single_image_with_retry(prompt: str, image_payloads, image_size_ratio: str = '', text_type: str = '', country: str = '', product_json=None, image_type: str = '', plan_item=None, all_plan_types=None, _logger: logging.Logger | None = None):
    log = _logger or logger
    retry_attempts = get_mode1_retry_attempts()
    retry_delay_seconds = get_mode1_retry_delay_seconds()
    last_exc = None
    for attempt in range(retry_attempts + 1):
        try:
            return call_mode1_single_image(prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types)
        except Exception as exc:
            last_exc = exc
            should_retry = attempt < retry_attempts and is_retryable_mode1_error(exc)
            if not should_retry:
                log.warning(
                    'Mode1 single image failed without retry: attempt=%s/%s image_type=%s reference_count=%s plan_type=%s error=%s',
                    attempt + 1,
                    retry_attempts + 1,
                    image_type or '',
                    len(image_payloads or []),
                    str((plan_item or {}).get('type') or ''),
                    exc,
                )
                raise
            wait_seconds = retry_delay_seconds * (attempt + 1)
            log.warning(
                'Mode1 single image failed, retrying in %.2fs (%s/%s): image_type=%s reference_count=%s plan_type=%s error=%s',
                wait_seconds,
                attempt + 1,
                retry_attempts,
                image_type or '',
                len(image_payloads or []),
                str((plan_item or {}).get('type') or ''),
                exc,
            )
            time.sleep(wait_seconds)
    log.exception(
        'Mode1 single image failed after retries: retry_attempts=%s image_type=%s reference_count=%s plan_type=%s',
        retry_attempts,
        image_type or '',
        len(image_payloads or []),
        str((plan_item or {}).get('type') or ''),
    )
    raise last_exc


def call_mode1_images_parallel_with_partial_retry(prompt: str, image_payloads, max_images: int, image_size_ratio: str = '', text_type: str = '', country: str = '', product_json=None, image_type: str = '', plan_item=None, all_plan_types=None, _logger: logging.Logger | None = None):
    log = _logger or logger
    target_count = max(1, int(max_images or 1))
    enriched_prompt = build_enriched_image_prompt(prompt, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types)
    if target_count == 1:
        return [call_mode1_single_image_with_retry(enriched_prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types, _logger=log)]

    if should_mode1_use_sequential_generation(target_count, image_payloads):
        generated_items = []
        for index in range(target_count):
            item = call_mode1_single_image_with_retry(enriched_prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types, _logger=log)
            generated_items.append(item)
        return generated_items[:target_count]

    workers = min(target_count, get_mode1_parallel_workers())
    partial_retry_attempts = get_mode1_partial_retry_attempts()
    retry_delay_seconds = get_mode1_retry_delay_seconds()
    generated_items = []
    failures = []

    def run_one(global_index: int):
        return call_mode1_single_image_with_retry(enriched_prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types, _logger=log)

    for attempt_index in range(partial_retry_attempts + 1):
        missing_count = target_count - len(generated_items)
        if missing_count <= 0:
            break
        failures = []
        batch_workers = min(missing_count, workers)
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_workers) as executor:
            future_map = {executor.submit(run_one, i): i for i in range(missing_count)}
            for future in concurrent.futures.as_completed(future_map):
                batch_index = future_map[future]
                try:
                    generated_items.append(future.result())
                except Exception as exc:
                    failures.append(f'第{batch_index+1}张：{exc}')
        if missing_count > 0 and len(generated_items) >= target_count:
            break
        if failures and attempt_index < partial_retry_attempts:
            log.warning('Mode1 parallel partial retry (%s/%s): %s', attempt_index + 1, partial_retry_attempts, '; '.join(failures[:3]))
            time.sleep(retry_delay_seconds * (attempt_index + 1))

    if len(generated_items) < target_count:
        error_text = '；'.join(failures[:3]) if failures else '未知错误'
        log.warning('Mode1 parallel generation failed: image_type=%s reference_count=%s plan_type=%s success=%s/%s failures=%s', image_type or '', len(image_payloads or []), str((plan_item or {}).get('type') or ''), len(generated_items), target_count, error_text)
        raise ValueError(f'mode1 部分图片生成失败，已成功 {len(generated_items)}/{target_count}：{error_text}')
    return generated_items[:target_count]


def call_mode2_single_image(prompt: str, image_payloads, image_size_ratio: str = '', text_type: str = '', country: str = '', product_json=None, image_type: str = '', plan_item=None, all_plan_types=None):
    ratio = image_size_ratio or '1:1'
    generated_item, _model = call_mode2_image_edit(get_mode2_client(), prompt, image_payloads or [create_mode2_blank_canvas_payload(ratio)], ratio, '', '')
    return generated_item


def call_mode2_single_image_with_retry(prompt: str, image_payloads, image_size_ratio: str = '', text_type: str = '', country: str = '', product_json=None, image_type: str = '', plan_item=None, all_plan_types=None, _logger: logging.Logger | None = None):
    log = _logger or logger
    retry_attempts = get_mode2_retry_attempts()
    retry_delay_seconds = get_mode2_retry_delay_seconds()
    last_exc = None
    for attempt in range(retry_attempts + 1):
        try:
            return call_mode2_single_image(prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types)
        except Exception as exc:
            last_exc = exc
            should_retry = attempt < retry_attempts and is_retryable_mode2_error(exc)
            if not should_retry:
                log.warning(
                    'Mode2 single image failed without retry: attempt=%s/%s image_type=%s reference_count=%s plan_type=%s error=%s',
                    attempt + 1,
                    retry_attempts + 1,
                    image_type or '',
                    len(image_payloads or []),
                    str((plan_item or {}).get('type') or ''),
                    exc,
                )
                raise
            wait_seconds = retry_delay_seconds * (attempt + 1)
            log.warning(
                'Mode2 single image failed, retrying in %.2fs (%s/%s): image_type=%s reference_count=%s plan_type=%s error=%s',
                wait_seconds,
                attempt + 1,
                retry_attempts,
                image_type or '',
                len(image_payloads or []),
                str((plan_item or {}).get('type') or ''),
                exc,
            )
            time.sleep(wait_seconds)
    log.exception(
        'Mode2 single image failed after retries: retry_attempts=%s image_type=%s reference_count=%s plan_type=%s',
        retry_attempts,
        image_type or '',
        len(image_payloads or []),
        str((plan_item or {}).get('type') or ''),
    )
    raise last_exc


def call_mode2_images_parallel_with_partial_retry(prompt: str, image_payloads, max_images: int, image_size_ratio: str = '', text_type: str = '', country: str = '', product_json=None, image_type: str = '', plan_item=None, all_plan_types=None, _logger: logging.Logger | None = None):
    log = _logger or logger
    target_count = max(1, int(max_images or 1))
    enriched_prompt = build_enriched_image_prompt(prompt, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types)
    if target_count == 1:
        return [call_mode2_single_image_with_retry(enriched_prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types, _logger=log)]

    if should_mode2_use_sequential_generation(target_count, image_payloads):
        generated_items = []
        for index in range(target_count):
            item = call_mode2_single_image_with_retry(enriched_prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types, _logger=log)
            generated_items.append(item)
        return generated_items[:target_count]

    workers = min(target_count, get_mode2_parallel_workers())
    partial_retry_attempts = get_mode2_partial_retry_attempts()
    retry_delay_seconds = get_mode2_retry_delay_seconds()
    generated_items = []
    failures = []

    def run_one(global_index: int):
        return call_mode2_single_image_with_retry(enriched_prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types, _logger=log)

    for attempt_index in range(partial_retry_attempts + 1):
        missing_count = target_count - len(generated_items)
        if missing_count <= 0:
            break
        failures = []
        batch_workers = min(missing_count, workers)
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_workers) as executor:
            future_map = {executor.submit(run_one, i): i for i in range(missing_count)}
            for future in concurrent.futures.as_completed(future_map):
                batch_index = future_map[future]
                try:
                    generated_items.append(future.result())
                except Exception as exc:
                    failures.append(f'第{batch_index+1}张：{exc}')
        if missing_count > 0 and len(generated_items) >= target_count:
            break
        if failures and attempt_index < partial_retry_attempts:
            log.warning('Mode2 parallel partial retry (%s/%s): %s', attempt_index + 1, partial_retry_attempts, '; '.join(failures[:3]))
            time.sleep(retry_delay_seconds * (attempt_index + 1))

    if len(generated_items) < target_count:
        error_text = '；'.join(failures[:3]) if failures else '未知错误'
        raise ValueError(f'mode2 部分图片生成失败，已成功 {len(generated_items)}/{target_count}：{error_text}')
    return generated_items[:target_count]


def call_mode3_single_image(prompt: str, image_payloads, image_size_ratio: str = '', text_type: str = '', country: str = '', product_json=None, image_type: str = '', plan_item=None, all_plan_types=None):
    if image_payloads:
        generated_item, _model = call_mode3_image_edit(get_mode3_client(), prompt, image_payloads, image_size_ratio)
    else:
        generated_item, _model = call_mode3_image_generation(get_mode3_client(), prompt, image_size_ratio)
    return generated_item


def call_mode3_single_image_with_retry(prompt: str, image_payloads, image_size_ratio: str = '', text_type: str = '', country: str = '', product_json=None, image_type: str = '', plan_item=None, all_plan_types=None, _logger: logging.Logger | None = None):
    log = _logger or logger
    retry_attempts = get_mode3_retry_attempts()
    retry_delay_seconds = get_mode3_retry_delay_seconds()
    last_exc = None
    for attempt in range(retry_attempts + 1):
        try:
            return call_mode3_single_image(prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types)
        except Exception as exc:
            last_exc = exc
            should_retry = attempt < retry_attempts and is_retryable_mode3_error(exc)
            if not should_retry:
                log.warning(
                    'Mode3 single image failed without retry: attempt=%s/%s image_type=%s reference_count=%s plan_type=%s error=%s',
                    attempt + 1,
                    retry_attempts + 1,
                    image_type or '',
                    len(image_payloads or []),
                    str((plan_item or {}).get('type') or ''),
                    exc,
                )
                raise
            wait_seconds = retry_delay_seconds * (attempt + 1)
            log.warning(
                'Mode3 single image failed, retrying in %.2fs (%s/%s): image_type=%s reference_count=%s plan_type=%s error=%s',
                wait_seconds,
                attempt + 1,
                retry_attempts,
                image_type or '',
                len(image_payloads or []),
                str((plan_item or {}).get('type') or ''),
                exc,
            )
            time.sleep(wait_seconds)
    log.exception(
        'Mode3 single image failed after retries: retry_attempts=%s image_type=%s reference_count=%s plan_type=%s',
        retry_attempts,
        image_type or '',
        len(image_payloads or []),
        str((plan_item or {}).get('type') or ''),
    )
    raise last_exc


def call_mode3_images_parallel_with_partial_retry(prompt: str, image_payloads, max_images: int, image_size_ratio: str = '', text_type: str = '', country: str = '', product_json=None, image_type: str = '', plan_item=None, all_plan_types=None, _logger: logging.Logger | None = None):
    log = _logger or logger
    target_count = max(1, int(max_images or 1))
    enriched_prompt = build_enriched_image_prompt(prompt, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types)
    if target_count == 1:
        return [call_mode3_single_image_with_retry(enriched_prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types, _logger=log)]

    if should_mode3_use_sequential_generation(target_count, image_payloads):
        generated_items = []
        for index in range(target_count):
            item = call_mode3_single_image_with_retry(enriched_prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types, _logger=log)
            generated_items.append(item)
        return generated_items[:target_count]

    workers = min(target_count, get_mode3_parallel_workers())
    partial_retry_attempts = get_mode3_partial_retry_attempts()
    retry_delay_seconds = get_mode3_retry_delay_seconds()
    generated_items = []
    failures = []

    def run_one(global_index: int):
        return call_mode3_single_image_with_retry(enriched_prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, plan_item, all_plan_types, _logger=log)

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
            log.warning('Mode3 partial generation missing %s/%s images, retrying failed parts in %.2fs (%s/%s): %s', missing_count, target_count, retry_delay_seconds * (attempt_index + 1), attempt_index + 1, partial_retry_attempts, '; '.join(str(exc) for exc in failures[:3]))
            time.sleep(retry_delay_seconds * (attempt_index + 1))

    if len(generated_items) < target_count:
        error_text = '; '.join(str(exc) for exc in failures[:3]) or '部分图片生成失败'
        raise ValueError(f'mode3 部分图片生成失败，已成功 {len(generated_items)}/{target_count}：{error_text}')
    return generated_items[:target_count]


def call_image_generation(client: OpenAI, prompt: str, image_payloads, image_size_ratio: str, text_type: str, country: str, product_json=None, image_type: str = '', plan_item=None, all_plan_types=None, max_images: int = 1, _logger: logging.Logger | None = None):
    log = _logger or logger
    model = get_supabase_setting('ARK_IMAGE_MODEL', get_optional_env('ARK_IMAGE_MODEL', 'doubao-seedream-5-0-260128'))
    size = _resolve_image_size(image_size_ratio)
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
    log.warning('ARK image request extra_body: %s', json.dumps(extra_body, ensure_ascii=False))

    response = client.images.generate(**request_payload)
    return collect_generated_images(response)


def call_app_mode_image_generation(client: OpenAI, prompt: str, image_payloads, image_size_ratio: str, text_type: str, country: str, product_json=None, image_type: str = '', plan_item=None, all_plan_types=None, max_images: int = 1, _logger: logging.Logger | None = None):
    log = _logger or logger
    app_mode = get_app_mode()
    if app_mode == 'mode1':
        return call_mode1_images_parallel_with_partial_retry(
            prompt, image_payloads, max_images, image_size_ratio, text_type, country,
            product_json, image_type, plan_item, all_plan_types, _logger=log,
        )
    if app_mode == 'mode2':
        return call_mode2_images_parallel_with_partial_retry(
            prompt, image_payloads, max_images, image_size_ratio, text_type, country,
            product_json, image_type, plan_item, all_plan_types, _logger=log,
        )
    if app_mode == 'mode3':
        return call_mode3_images_parallel_with_partial_retry(
            prompt, image_payloads, max_images, image_size_ratio, text_type, country,
            product_json, image_type, plan_item, all_plan_types, _logger=log,
        )
    return call_image_generation(
        client, prompt, image_payloads, image_size_ratio, text_type, country,
        product_json, image_type, plan_item, all_plan_types, max_images=max_images, _logger=log,
    )


def _get_parallel_config(app_mode: str, plan_item_count: int):
    if app_mode == 'mode1':
        return (
            min(plan_item_count, get_mode1_parallel_workers()),
            get_mode1_partial_retry_attempts(),
            get_mode1_retry_delay_seconds(),
        )
    if app_mode == 'mode2':
        return (
            min(plan_item_count, get_mode2_parallel_workers()),
            get_mode2_partial_retry_attempts(),
            get_mode2_retry_delay_seconds(),
        )
    if app_mode == 'mode3':
        return (
            min(plan_item_count, get_mode3_parallel_workers()),
            get_mode3_partial_retry_attempts(),
            get_mode3_retry_delay_seconds(),
        )
    return (min(plan_item_count, 3), 0, 1.5)
