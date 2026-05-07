import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from qcloud_cos import CosConfig, CosS3Client

load_dotenv(Path(__file__).resolve().parent / '.env')

logger = logging.getLogger(__name__)

cos_client = None
_cos_signature = None
COS_URL_PREFIX = ''


def _read_cos_env(name: str, default: str = '') -> str:
    value = (os.getenv(name) or '').strip()
    if value:
        return value
    try:
        from config import LOCAL_CONFIG
        value = str(LOCAL_CONFIG.get(name, '')).strip()
        if value:
            return value
    except Exception:
        pass
    return default


def _get_cos_config() -> dict:
    secret_id = _read_cos_env('COS_SECRET_ID')
    secret_key = _read_cos_env('COS_SECRET_KEY')
    region = _read_cos_env('COS_REGION', 'ap-guangzhou') or 'ap-guangzhou'
    bucket = _read_cos_env('COS_BUCKET')
    cdn_domain = _read_cos_env('COS_CDN_DOMAIN')
    url_prefix = f"https://{cdn_domain}" if cdn_domain else (f"https://{bucket}.cos.{region}.myqcloud.com" if bucket else '')
    enabled = bool(secret_id and secret_key and bucket)
    return {
        'secret_id': secret_id,
        'secret_key': secret_key,
        'region': region,
        'bucket': bucket,
        'cdn_domain': cdn_domain,
        'url_prefix': url_prefix.rstrip('/'),
        'enabled': enabled,
    }


def _get_cos_client():
    global cos_client, _cos_signature, COS_URL_PREFIX
    config = _get_cos_config()
    signature = (config['secret_id'], config['secret_key'], config['region'], config['bucket'], config['cdn_domain'])
    COS_URL_PREFIX = config['url_prefix']
    if not config['enabled']:
        if cos_client is not None:
            logger.warning("COS is disabled: missing COS_SECRET_ID, COS_SECRET_KEY or COS_BUCKET")
        cos_client = None
        _cos_signature = signature
        return None, config
    if cos_client is not None and _cos_signature == signature:
        return cos_client, config
    try:
        cos_client = CosS3Client(CosConfig(Region=config['region'], SecretId=config['secret_id'], SecretKey=config['secret_key']))
        _cos_signature = signature
        logger.info("COS client initialized: bucket=%s region=%s", config['bucket'], config['region'])
        return cos_client, config
    except Exception as e:
        cos_client = None
        _cos_signature = signature
        logger.error("COS client init failed: %s", e)
        return None, config


def get_cos_url_prefix() -> str:
    _client, config = _get_cos_client()
    return config['url_prefix']


def upload_to_cos(file_data: bytes, file_key: str, content_type: str = 'image/jpeg') -> str:
    client, config = _get_cos_client()
    if not client:
        raise RuntimeError("COS client not initialized")
    try:
        client.put_object(
            Bucket=config['bucket'],
            Body=file_data,
            Key=file_key,
            EnableMD5=False,
            ContentType=content_type,
            ACL='public-read',
        )
        url = f"{config['url_prefix']}/{file_key}"
        logger.info("COS upload OK: %s", url)
        return url
    except Exception as e:
        logger.error("COS upload failed: %s", e)
        raise


def delete_from_cos(file_key: str):
    client, config = _get_cos_client()
    if not client:
        raise RuntimeError("COS client not initialized")
    try:
        client.delete_object(Bucket=config['bucket'], Key=file_key)
        logger.info("COS delete OK: %s", file_key)
    except Exception as e:
        logger.error("COS delete failed: %s", e)
        raise


def generate_cos_key(task_id: str, filename: str, storage_group: str = 'generated') -> str:
    date_str = datetime.now().strftime('%Y%m')
    safe_group = str(storage_group or 'generated').strip().strip('/').replace('..', '') or 'generated'
    safe_filename = str(filename or '').lstrip('/').replace('..', '')
    return f"{safe_group}/{date_str}/{task_id}/{safe_filename}"


def is_cos_enabled() -> bool:
    client, _config = _get_cos_client()
    return client is not None
