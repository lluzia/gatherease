"""
Amazon S3 service helpers.

Provides:
- get_s3_client()          – cached Boto3 S3 client
- generate_presigned_url() – for client-side avatar uploads
- delete_object()          – for removing old avatars
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import boto3
import structlog
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import get_settings
from app.core.exceptions import AppException

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def get_s3_client() -> Any:
    settings = get_settings()
    kwargs: dict = {
        "region_name": settings.aws_region,
        "config": Config(
            retries={"max_attempts": 3, "mode": "standard"},
            signature_version="s3v4",
        ),
    }
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    # Local MinIO support — set S3_ENDPOINT_URL=http://localhost:9000
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client("s3", **kwargs)


def generate_presigned_upload_url(
    key: str,
    content_type: str = "image/jpeg",
    expiry: int | None = None,
) -> dict[str, str]:
    """Generate a presigned POST URL for direct client → S3 uploads.

    Returns a dict with 'url' and 'fields' for the multipart POST.
    """
    settings = get_settings()
    client = get_s3_client()
    expiry = expiry or settings.s3_presigned_url_expiry

    try:
        presigned = client.generate_presigned_post(
            Bucket=settings.s3_bucket_name,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, 5 * 1024 * 1024],  # 5 MB max
            ],
            ExpiresIn=expiry,
        )
    except ClientError as exc:
        logger.error("s3_presigned_url_error", key=key, error=str(exc))
        raise AppException("Failed to generate upload URL.") from exc

    return presigned


async def delete_object(key: str) -> None:
    """Delete an object from the GatherEase S3 bucket."""
    settings = get_settings()
    client = get_s3_client()
    try:
        client.delete_object(Bucket=settings.s3_bucket_name, Key=key)
    except ClientError as exc:
        logger.warning("s3_delete_error", key=key, error=str(exc))
        # Non-fatal — log and continue
