import base64
import logging
import sys
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from celery_app import celery_app

logger = logging.getLogger(__name__)

_RETRY_KWARGS = {
    'max_retries': 2,
    'countdown': 10,
    'retry_backoff': True,
    'retry_backoff_max': 60,
    'retry_jitter': True,
}

_TRANSIENT_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)

_IMAGE_PAYLOAD_MARKER = '__aiimagenew_image_payload__'


def _try_upload_to_cos(payload):
    if not hasattr(payload, 'bytes') or not payload.bytes:
        return None
    try:
        from cos_utils import upload_to_cos, generate_cos_key, is_cos_enabled
        if not is_cos_enabled():
            return None
        filename = getattr(payload, 'filename', 'image.png')
        mime_type = getattr(payload, 'mime_type', 'image/png')
        task_id = getattr(payload, '_task_id', '') or uuid.uuid4().hex[:12]
        cos_key = generate_cos_key(task_id, filename, storage_group='celery_input')
        cos_url = upload_to_cos(payload.bytes, cos_key, content_type=mime_type)
        return cos_url
    except Exception as exc:
        logger.warning('COS upload failed for celery payload, falling back to base64: %s', exc)
        return None


def _serialize_image_payload(payload, task_id: str = ''):
    if hasattr(payload, 'bytes') and hasattr(payload, 'filename') and hasattr(payload, 'mime_type'):
        cos_url = _try_upload_to_cos(payload)
        if cos_url:
            return {
                _IMAGE_PAYLOAD_MARKER: True,
                'filename': payload.filename,
                'mime_type': payload.mime_type,
                'source_url': cos_url,
                'content_base64': '',
            }
        return {
            _IMAGE_PAYLOAD_MARKER: True,
            'filename': payload.filename,
            'mime_type': payload.mime_type,
            'content_base64': base64.b64encode(payload.bytes).decode('utf-8'),
            'source_url': getattr(payload, 'source_url', None),
        }
    if isinstance(payload, dict):
        return {key: _serialize_image_payload(value, task_id) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_serialize_image_payload(item, task_id) for item in payload]
    return payload


def serialize_payloads_for_celery(payloads, task_id: str = ''):
    return _serialize_image_payload(payloads, task_id)


def _restore_image_payload(payload):
    if isinstance(payload, dict) and payload.get(_IMAGE_PAYLOAD_MARKER):
        from image_utils import LazyImagePayload

        content_base64 = payload.get('content_base64') or ''
        source_url = payload.get('source_url')

        if not content_base64 and source_url:
            restored = LazyImagePayload(
                filename=str(payload.get('filename') or 'image'),
                mime_type=str(payload.get('mime_type') or 'image/png'),
                content=b'',
            )
            restored.source_url = str(source_url)
            return restored

        content = base64.b64decode(content_base64) if content_base64 else b''
        restored = LazyImagePayload(
            filename=str(payload.get('filename') or 'image'),
            mime_type=str(payload.get('mime_type') or 'image/png'),
            content=content,
        )
        if source_url:
            restored.source_url = str(source_url)
        return restored
    if isinstance(payload, dict):
        return {key: _restore_image_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_restore_image_payload(item) for item in payload]
    return payload


def restore_payloads_from_celery(payloads):
    return _restore_image_payload(payloads)


@celery_app.task(name='generation.run_generation_task', autoretry_for=_TRANSIENT_EXCEPTIONS, **_RETRY_KWARGS)
def run_generation_task_celery(task_id: str, form_payload: dict, file_payloads: dict):
    from app import run_generation_task

    return run_generation_task(task_id, form_payload, restore_payloads_from_celery(file_payloads))


@celery_app.task(name='generation.run_replicate_generation_task', autoretry_for=_TRANSIENT_EXCEPTIONS, **_RETRY_KWARGS)
def run_replicate_generation_task_celery(task_id: str, form_payload: dict, file_payloads: dict):
    from app import run_replicate_generation_task

    return run_replicate_generation_task(task_id, form_payload, restore_payloads_from_celery(file_payloads))


@celery_app.task(name='generation.run_fashion_model_task', autoretry_for=_TRANSIENT_EXCEPTIONS, **_RETRY_KWARGS)
def run_fashion_model_task_celery(task_id: str, form_payload: dict):
    from app import run_fashion_model_task

    return run_fashion_model_task(task_id, form_payload)


@celery_app.task(name='generation.run_mode_image_task', autoretry_for=_TRANSIENT_EXCEPTIONS, **_RETRY_KWARGS)
def run_mode_image_task_celery(task_id: str, mode_name: str, form_payload: dict, file_payloads: dict):
    from app import run_mode_image_task

    return run_mode_image_task(task_id, mode_name, form_payload, restore_payloads_from_celery(file_payloads))


@celery_app.task(name='generation.run_aplus_task', autoretry_for=_TRANSIENT_EXCEPTIONS, **_RETRY_KWARGS)
def run_aplus_task_celery(task_id: str, form_payload: dict, file_payloads: dict):
    from app import run_aplus_task

    return run_aplus_task(task_id, form_payload, restore_payloads_from_celery(file_payloads))


@celery_app.task(name='generation.run_zip_task', autoretry_for=_TRANSIENT_EXCEPTIONS, **_RETRY_KWARGS)
def run_zip_task_celery(task_id: str, image_paths: list[str]):
    from app import run_zip_task

    return run_zip_task(task_id, image_paths)


@celery_app.task(name='generation.run_ai_write_task', autoretry_for=_TRANSIENT_EXCEPTIONS, **_RETRY_KWARGS)
def run_ai_write_task_celery(task_id: str, form_payload: dict, file_payloads: dict):
    from app import run_ai_write_task

    return run_ai_write_task(task_id, form_payload, restore_payloads_from_celery(file_payloads))


@celery_app.task(name='generation.run_style_analysis_task', autoretry_for=_TRANSIENT_EXCEPTIONS, **_RETRY_KWARGS)
def run_style_analysis_task_celery(task_id: str, form_payload: dict, file_payloads: dict):
    from app import run_style_analysis_task

    return run_style_analysis_task(task_id, form_payload, restore_payloads_from_celery(file_payloads))
