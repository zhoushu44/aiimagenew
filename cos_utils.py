import os
import logging
from datetime import datetime

from qcloud_cos import CosConfig, CosS3Client

logger = logging.getLogger(__name__)

COS_SECRET_ID = (os.getenv('COS_SECRET_ID') or '').strip()
COS_SECRET_KEY = (os.getenv('COS_SECRET_KEY') or '').strip()
COS_REGION = (os.getenv('COS_REGION') or 'ap-guangzhou').strip()
COS_BUCKET = (os.getenv('COS_BUCKET') or '').strip()
COS_CDN_DOMAIN = (os.getenv('COS_CDN_DOMAIN') or '').strip()
COS_URL_PREFIX = f"https://{COS_CDN_DOMAIN}" if COS_CDN_DOMAIN else (f"https://{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com" if COS_BUCKET else '')
COS_ENABLED = bool(COS_SECRET_ID and COS_SECRET_KEY and COS_BUCKET)

try:
    if COS_ENABLED:
        _cos_config = CosConfig(Region=COS_REGION, SecretId=COS_SECRET_ID, SecretKey=COS_SECRET_KEY)
        cos_client = CosS3Client(_cos_config)
        logger.info("COS client initialized: bucket=%s region=%s", COS_BUCKET, COS_REGION)
    else:
        cos_client = None
        logger.warning("COS is disabled: missing COS_SECRET_ID, COS_SECRET_KEY or COS_BUCKET")
except Exception as e:
    cos_client = None
    logger.error("COS client init failed: %s", e)


def upload_to_cos(file_data: bytes, file_key: str, content_type: str = 'image/jpeg') -> str:
    if not cos_client:
        raise RuntimeError("COS client not initialized")
    try:
        cos_client.put_object(
            Bucket=COS_BUCKET,
            Body=file_data,
            Key=file_key,
            EnableMD5=False,
            ContentType=content_type,
            ACL='public-read',
        )
        url = f"{COS_URL_PREFIX}/{file_key}"
        logger.info("COS upload OK: %s", url)
        return url
    except Exception as e:
        logger.error("COS upload failed: %s", e)
        raise


def delete_from_cos(file_key: str):
    if not cos_client:
        raise RuntimeError("COS client not initialized")
    try:
        cos_client.delete_object(Bucket=COS_BUCKET, Key=file_key)
        logger.info("COS delete OK: %s", file_key)
    except Exception as e:
        logger.error("COS delete failed: %s", e)
        raise


def generate_cos_key(task_id: str, filename: str) -> str:
    date_str = datetime.now().strftime('%Y%m')
    return f"generated/{date_str}/{task_id}/{filename}"


def is_cos_enabled() -> bool:
    return cos_client is not None
