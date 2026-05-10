import base64
import ipaddress
import json
import logging
import mimetypes
import re
import shutil
import socket
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

from config import (
    GENERATED_SUITES_DIR,
    ALLOWED_IMAGE_MIME_TYPES,
    ALLOWED_IMAGE_EXTENSIONS,
    IMAGE_SIGNATURES,
    get_supabase_setting,
    get_supabase_setting_int,
    get_mode2_allowed_image_hosts,
)
from cos_utils import upload_to_cos, generate_cos_key, is_cos_enabled

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UPLOAD_MAX_FILE_BYTES = max(get_supabase_setting_int('UPLOAD_MAX_FILE_BYTES', 8 * 1024 * 1024), 1)
GENERATED_SUITE_RETENTION_DAYS = max(get_supabase_setting_int('GENERATED_SUITE_RETENTION_DAYS', 7), 0)
GENERATED_SUITE_RETENTION_COUNT = max(get_supabase_setting_int('GENERATED_SUITE_RETENTION_COUNT', 20), 0)

FASHION_MODEL_APPEARANCE_FALLBACK = '五官自然立体，肤质真实细腻，整体形象干净利落'

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

# ---------------------------------------------------------------------------
# Image file inspection utilities
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Generated suite cleanup
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Image payload construction
# ---------------------------------------------------------------------------


def file_to_data_url(file_storage) -> str:
    content = file_storage.read()
    if not content:
        raise ValueError(f'图片 {file_storage.filename or "未命名文件"} 内容为空')

    mime_type = file_storage.mimetype or mimetypes.guess_type(file_storage.filename or '')[0] or 'application/octet-stream'
    encoded = base64.b64encode(content).decode('utf-8')
    return f'data:{mime_type};base64,{encoded}'


class LazyImagePayload:
    __slots__ = ('filename', 'mime_type', '_bytes', '_base64', '_data_url', 'source_url')

    def __init__(self, filename: str, mime_type: str, content: bytes):
        self.filename = filename
        self.mime_type = mime_type
        self._bytes = content
        self._base64 = None
        self._data_url = None

    @property
    def bytes(self) -> bytes:
        return self._bytes

    @property
    def base64(self) -> str:
        if self._base64 is None:
            self._base64 = base64.b64encode(self._bytes).decode('utf-8')
        return self._base64

    @property
    def data_url(self) -> str:
        if self._data_url is None:
            self._data_url = f'data:{self.mime_type};base64,{self.base64}'
        return self._data_url

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)


def create_image_payload(file_storage):
    content = file_storage.read()
    mime_type = validate_image_file(file_storage, content)
    filename = file_storage.filename or 'image'
    return LazyImagePayload(filename=filename, mime_type=mime_type, content=content)


def build_multimodal_content(prompt_text: str, image_files):
    content = [{'type': 'text', 'text': prompt_text}]

    for image_file in image_files:
        source_url = getattr(image_file, 'source_url', None)
        if not source_url and isinstance(image_file, dict):
            source_url = image_file.get('source_url')
        if isinstance(source_url, str) and source_url.startswith(('http://', 'https://')):
            image_url = source_url
        elif hasattr(image_file, 'data_url'):
            image_url = image_file.data_url
        elif isinstance(image_file, dict):
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


# ---------------------------------------------------------------------------
# Remote image handling
# ---------------------------------------------------------------------------


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
    return _fetch_url_to_image_payload(normalized_url)


def _fetch_url_to_image_payload(image_url: str):
    response = requests.get(image_url, timeout=120, allow_redirects=False)
    if 300 <= response.status_code < 400:
        raise ValueError('参考图片链接不允许重定向')
    response.raise_for_status()
    content = response.content
    filename = Path(image_url.split('?', 1)[0]).name or 'reference-image'
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

    payload = LazyImagePayload(filename=filename, mime_type=mime_type, content=content)
    payload.source_url = image_url
    return payload


# ---------------------------------------------------------------------------
# Image decoding and saving
# ---------------------------------------------------------------------------


def _download_image_url_with_retry(url: str, max_attempts: int = 3, base_delay: float = 1.0):
    last_exc = None
    for attempt in range(max_attempts):
        try:
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            return response
        except Exception as exc:
            last_exc = exc
            if attempt >= max_attempts - 1:
                raise
            message = str(exc or '').lower()
            retryable = any(
                frag in message
                for frag in ('ssl', 'sslerror', 'eof', 'decryption failed', 'bad record mac',
                             'connection aborted', 'connection reset', 'timed out', 'max retries exceeded',
                             'connectionpool', 'protocolerror')
            )
            if not retryable:
                raise
            wait = base_delay * (attempt + 1)
            logger.warning('Image URL download failed, retrying in %.2fs (%s/%s): %s', wait, attempt + 1, max_attempts - 1, exc)
            time.sleep(wait)
    raise last_exc


def decode_generated_image(item: dict):
    if item.get('url'):
        response = _download_image_url_with_retry(item['url'])
        image_bytes = response.content
        header_mime_type = response.headers.get('Content-Type', 'image/png').split(';', 1)[0].strip()
        detected_mime_type = sniff_image_mime_type(image_bytes)
        return image_bytes, detected_mime_type or header_mime_type or 'image/png'

    if item.get('b64_json'):
        image_bytes = base64.b64decode(item['b64_json'])
        detected_mime_type = sniff_image_mime_type(image_bytes)
        return image_bytes, detected_mime_type or 'image/png'

    raise ValueError('图像生成接口未返回可用图片内容')


def _iso_utc_from_ts(timestamp: float | int | None) -> str:
    try:
        normalized = float(timestamp)
    except (TypeError, ValueError):
        normalized = time.time()
    return datetime.utcfromtimestamp(normalized).isoformat() + 'Z'


def _build_trace_event(stage: str, now_ts: float | int | None = None, extra: dict | None = None) -> dict:
    normalized_now = float(now_ts) if isinstance(now_ts, (int, float)) else time.time()
    event = {
        'stage': str(stage or '').strip() or 'unknown',
        'ts': normalized_now,
        'at': _iso_utc_from_ts(normalized_now),
    }
    if isinstance(extra, dict):
        for key, value in extra.items():
            if value is not None:
                event[key] = value
    return event


def _build_trace_payload(events) -> dict:
    trace_events = [item for item in (events or []) if isinstance(item, dict)]
    if not trace_events:
        return {}
    last_event = trace_events[-1]
    return {
        'events': trace_events[-40:],
        'last_stage': last_event.get('stage') or '',
        'last_at': last_event.get('at') or '',
        'last_ts': last_event.get('ts'),
    }


def save_generated_image(task_id: str, sort: int, image_type: str, image_bytes: bytes, mime_type: str, storage_group: str = 'generated'):
    extension = guess_extension(mime_type)
    filename = f'{sort:02d}-{sanitize_filename_part(image_type, "image")}{extension}'
    storage_started_at = time.time()
    storage_group_name = str(storage_group or 'generated').strip().strip('/') or 'generated'
    base_extra = {
        'sort': sort,
        'image_type': image_type,
        'storage_target': 'generated_image',
        'storage_group': storage_group_name,
        'bytes': len(image_bytes or b''),
        'mime_type': mime_type,
        'filename': filename,
    }
    trace_events = [_build_trace_event('image_storage_started', storage_started_at, base_extra)]

    if is_cos_enabled():
        try:
            cos_key = generate_cos_key(task_id, filename, storage_group=storage_group_name)
            cos_started_at = time.time()
            trace_events.append(_build_trace_event('image_cos_upload_started', cos_started_at, {**base_extra, 'file_key': cos_key}))
            image_url = upload_to_cos(image_bytes, cos_key, mime_type)
            cos_finished_at = time.time()
            trace_events.append(_build_trace_event('image_cos_upload_completed', cos_finished_at, {
                **base_extra,
                'file_key': cos_key,
                'image_url': image_url,
                'elapsed_ms': int(max((cos_finished_at - cos_started_at) * 1000, 0)),
            }))
            trace_events.append(_build_trace_event('image_storage_completed', cos_finished_at, {
                **base_extra,
                'storage_backend': 'cos',
                'file_key': cos_key,
                'image_url': image_url,
                'elapsed_ms': int(max((cos_finished_at - storage_started_at) * 1000, 0)),
            }))
            return filename, cos_key, image_url, _build_trace_payload(trace_events)
        except Exception as exc:
            failed_at = time.time()
            trace_events.append(_build_trace_event('image_cos_upload_failed', failed_at, {
                **base_extra,
                'error': str(exc),
                'elapsed_ms': int(max((failed_at - storage_started_at) * 1000, 0)),
            }))
            logger.warning('COS upload failed, falling back to local: %s', exc)

    output_dir = GENERATED_SUITES_DIR / storage_group_name / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    local_write_started_at = time.time()
    trace_events.append(_build_trace_event('image_local_write_started', local_write_started_at, {**base_extra, 'output_path': str(output_path)}))
    output_path.write_bytes(image_bytes)
    local_write_finished_at = time.time()
    relative_path = output_path.relative_to(GENERATED_SUITES_DIR).as_posix()
    image_url = f'/generated/{relative_path}'
    trace_events.append(_build_trace_event('image_local_write_completed', local_write_finished_at, {
        **base_extra,
        'output_path': str(output_path),
        'relative_path': relative_path,
        'image_url': image_url,
        'elapsed_ms': int(max((local_write_finished_at - local_write_started_at) * 1000, 0)),
    }))
    trace_events.append(_build_trace_event('image_storage_completed', local_write_finished_at, {
        **base_extra,
        'storage_backend': 'local',
        'relative_path': relative_path,
        'image_url': image_url,
        'elapsed_ms': int(max((local_write_finished_at - storage_started_at) * 1000, 0)),
    }))
    return filename, relative_path, image_url, _build_trace_payload(trace_events)


def save_reference_image(task_id: str, sort: int, filename: str, image_bytes: bytes, mime_type: str, storage_group: str = 'generated', storage_subdir: str = 'references'):
    extension = guess_extension(mime_type)
    source_stem = Path(filename or 'reference').stem
    safe_stem = sanitize_filename_part(source_stem, f'reference-{sort:02d}')
    output_name = f'{sort:02d}-{safe_stem}{extension}'
    storage_group_name = str(storage_group or 'generated').strip().strip('/') or 'generated'
    subdir = str(storage_subdir or 'references').strip().strip('/') or 'references'

    if is_cos_enabled():
        try:
            cos_key = generate_cos_key(task_id, f'{subdir}/{output_name}', storage_group=storage_group_name)
            image_url = upload_to_cos(image_bytes, cos_key, mime_type)
            return output_name, cos_key, image_url
        except Exception as exc:
            logger.warning('COS upload failed, falling back to local: %s', exc)

    output_dir = GENERATED_SUITES_DIR / storage_group_name / task_id / subdir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name
    output_path.write_bytes(image_bytes)
    relative_path = output_path.relative_to(GENERATED_SUITES_DIR).as_posix()
    return output_name, relative_path, f'/generated/{relative_path}'


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------


def build_reference_images(task_id: str, image_payloads, source: str = 'product', start_sort: int = 1):
    reference_images = []
    source_meta = {
        'product': {'type': '商品原图', 'type_tag': 'Prod', 'reference_source': 'product', 'storage_group': 'products', 'storage_subdir': 'references'},
        'reference': {'type': '参考图', 'type_tag': 'Ref', 'reference_source': 'reference', 'storage_group': 'temp', 'storage_subdir': 'references'},
        'fashion_reference': {'type': '穿搭参考图', 'type_tag': 'Look', 'reference_source': 'fashion_reference', 'storage_group': 'temp', 'storage_subdir': 'references'},
    }
    meta = source_meta.get(source, source_meta['product'])

    for offset, payload in enumerate(image_payloads):
        sort = start_sort + offset
        image_bytes = payload.get('bytes', b'') if hasattr(payload, 'get') else getattr(payload, 'bytes', b'')
        source_url = getattr(payload, 'source_url', None) if hasattr(payload, 'source_url') else payload.get('source_url') if hasattr(payload, 'get') else None
        if not image_bytes and source_url:
            try:
                logger.info('Downloading deferred image for task %s sort %d from %s', task_id, sort, source_url[:80])
                response = requests.get(source_url, timeout=60, allow_redirects=True)
                response.raise_for_status()
                image_bytes = response.content or b''
                logger.info('Downloaded %d bytes for task %s sort %d', len(image_bytes), task_id, sort)
                if image_bytes and hasattr(payload, '_bytes'):
                    payload._bytes = image_bytes
            except Exception as exc:
                logger.warning('Failed to download deferred image for task %s sort %d: %s', task_id, sort, exc)
        download_name, relative_path, image_url = save_reference_image(
            task_id,
            sort,
            payload.get('filename', '') if hasattr(payload, 'get') else getattr(payload, 'filename', ''),
            image_bytes,
            payload.get('mime_type', 'image/png') if hasattr(payload, 'get') else getattr(payload, 'mime_type', 'image/png'),
            storage_group=meta['storage_group'],
            storage_subdir=meta['storage_subdir'],
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


def build_mode2_success_response(task_id: str, mode: str, prompt: str, model: str, generated_item: dict):
    image_bytes, mime_type = decode_generated_image(generated_item)
    download_name, relative_path, image_url, storage_trace = save_generated_image(task_id, 1, mode, image_bytes, mime_type)
    return {
        'success': True,
        'task_id': task_id,
        'image_url': image_url,
        'image_path': relative_path,
        'download_name': download_name,
        'prompt': prompt,
        'model': model,
        'mode': mode,
        'trace': storage_trace,
    }


def build_generated_suite_image_item(task_id: str, plan_item: dict, generated_item: dict):
    image_bytes, mime_type = decode_generated_image(generated_item)
    download_name, relative_path, image_url, storage_trace = save_generated_image(task_id, plan_item['sort'], plan_item['type'], image_bytes, mime_type)
    return {
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
        'trace': storage_trace,
    }


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


# ---------------------------------------------------------------------------
# Product JSON normalization
# ---------------------------------------------------------------------------


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


def serialize_product_json(product_json) -> str:
    normalized = normalize_product_json(product_json or PRODUCT_JSON_FALLBACK)
    return json.dumps(normalized, ensure_ascii=False, indent=2)


def build_product_json_prompt_text(product_json) -> str:
    if not product_json:
        return '未提供不可变商品特征。'
    return PRODUCT_JSON_PROMPT_TEMPLATE.format(product_json_text=serialize_product_json(product_json))


# ---------------------------------------------------------------------------
# Prompt enrichment
# ---------------------------------------------------------------------------


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
    if image_type in {'标准爆款封面主图', '参考图风格封面主图', '核心卖点氛围封面主图', '高点击率封面主图', '高级质感封面主图', '极简干净封面主图', '场景氛围封面主图', '明亮清爽封面主图', '深色高级封面主图', '备用爆款封面主图'}:
        type_specific_rules = (
            '- 当前图类型：商品封面主图。只能生成适合作为商品第一张展示图的主图候选，不得生成详情页、尺寸图、材质图、人群图、对比图、细节放大图、功能说明图或参数说明图。\n'
            '- 核心卖点只能转化为背景氛围、光影、构图和视觉重点，不得变成文字标签、功能图标、参数标注或说明版式。\n'
            '- 本张图必须无新增文字、无水印、无促销标签、无乱码、无详情页排版；产品必须是画面绝对主体且清晰完整。\n'
            '- 参考图只用于构图、光影、背景氛围和风格，不得替换、改造或弱化商品图中的产品主体。\n'
        )
    elif image_type == '首屏主视觉图':
        type_specific_rules = (
            '- 当前图类型：首屏主视觉图。必须使用有场景的主视觉画面，并采用"大场景 + 单主体强聚焦"构图：场景需要真实存在且能承接商品气质，但商品主体仍必须是绝对视觉中心；禁止做成纯白底棚拍、纯色背景孤立陈列或空场静物图。\n'
            '- 优先保留完整环境信息、空间纵深或前后景层次，让用户一眼感知使用语境，但场景元素不得比商品更抢眼；禁止与核心卖点图、使用场景图复用同一站姿、同一手持关系、同一商品朝向、同一景别或同一构图骨架。\n'
        )
    elif image_type == '核心卖点图':
        type_specific_rules = (
            '- 当前图类型：核心卖点图。必须使用有场景的画面，并围绕一个核心卖点采用"场景内功能动作 / 局部卖点展示"结构重构视角；可采用场景中的局部放大、半身持握、俯拍陈列、剖面感或结构展示，但禁止继续沿用首屏主视觉图的同姿势、同朝向、同主体位置、同镜头距离。\n'
            '- 该图的场景必须直接服务卖点表达，例如收纳、清洁、使用前后、桌面操作、随身携带、厨房备餐等；优先出现操作关系、功能触发点、局部放大区域或利益点对应动作，禁止仅把首图换个背景后继续展示整件商品。即使保留人物，也必须让人物动作、身体朝向、持握关系、商品位置至少两项明显变化。\n'
        )
    elif image_type == '使用场景图':
        type_specific_rules = (
            '- 当前图类型：使用场景图。必须表现商品正在被真实使用，而不是静态拿着展示；优先采用操作中、接触中、桌面使用中、收纳取用中等动态关系。\n'
            '- 这张图禁止复用首屏主视觉图或核心卖点图的站位、朝向、裁切、商品位置与版式骨架，人物姿势、商品相对位置、镜头距离必须明显不同。\n'
        )
    elif image_type == 'fashion-look':
        type_specific_rules = (
            '- 当前图类型：服饰穿搭图。最终画面必须是"清晰可见的真人模特穿着商品"的完整穿搭成图；禁止只出衣服、禁止平铺挂拍、禁止无头模特、禁止裁切到看不出人物身份、禁止把商品单独陈列当成最终结果。\n'
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
            '- 严禁使用"底部居中粗白字+黑描边"的默认排版，不得整页堆砌单一粗黑大字；整体风格可以统一，但每张图的标题位置、信息骨架、标签组织和留白关系都必须根据模块职责变化。\n'
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
        f'- 若当前图类型不是 replicate，且提供了参考商品图，必须把参考图视为主体锚点，优先复用其主体外观、颜色关系、材质质感、结构比例、边缘轮廓、关键部件、logo/品牌位与稳定细节。\n'
        f'- 若当前图类型是 replicate，则第 1 张图片是预合成版式草图，第 2 张图片是唯一商品主体一致性锚点，最后 1 张图片是唯一文案与版式参考；产品图不参与文案提取，不得把产品图场景元素、水流、台面、墙面或道具带入结果，必须保留第 2 张产品外观并复刻最后 1 张参考图模板。\n'
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
