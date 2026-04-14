"""
Boto3 Cognito Identity Provider client — cached singleton.

Using a module-level singleton avoids creating a new client on every
request. Boto3 clients are thread-safe and can be shared across async
tasks safely when used with run_in_executor — but since all our Cognito
calls are quick and infrequent (auth actions only), we call them
directly. If latency becomes a concern, wrap with asyncio.to_thread().
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config

from app.config import get_settings


@lru_cache(maxsize=1)
def get_cognito_client() -> Any:
    """Return a cached boto3 Cognito IDP client."""
    settings = get_settings()

    kwargs: dict = {
        "region_name": settings.cognito_region,
        "config": Config(
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=10,
        ),
    }

    # In local development, explicit credentials may be set in .env.
    # In production (ECS Fargate), the IAM task role is used automatically.
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

    return boto3.client("cognito-idp", **kwargs)
