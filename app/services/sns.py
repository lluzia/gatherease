"""
Amazon SNS notification service.

Sprint 1: stub only — structure is in place for Sprint 2 when
reminders and push notifications are built.

The pattern we'll follow:
    notify_budget_updated(gathering_id)  →  plain function call
    notify_rsvp_received(gathering_id)   →  plain function call

Each function publishes a JSON message to the SNS topic. SNS then
fans out to:
    - Firebase Cloud Messaging (mobile push) via an SNS → FCM subscription
    - Future: email digest, webhook, etc.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import boto3
import structlog
from botocore.config import Config

from app.config import get_settings

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def get_sns_client() -> Any:
    settings = get_settings()
    kwargs: dict = {
        "region_name": settings.aws_region,
        "config": Config(retries={"max_attempts": 3, "mode": "standard"}),
    }
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client("sns", **kwargs)


async def publish_event(event_type: str, payload: dict) -> None:
    """Publish a structured event to the GatherEase SNS topic.

    Args:
        event_type: e.g. "budget.updated", "rsvp.received"
        payload:    event-specific data dict
    """
    settings = get_settings()
    if not settings.sns_topic_arn:
        logger.debug("sns_skipped_no_topic_arn", event_type=event_type)
        return

    message = json.dumps({"event": event_type, "data": payload})
    try:
        client = get_sns_client()
        client.publish(
            TopicArn=settings.sns_topic_arn,
            Message=message,
            MessageAttributes={
                "event_type": {
                    "DataType": "String",
                    "StringValue": event_type,
                }
            },
        )
        logger.info("sns_event_published", event_type=event_type)
    except Exception as exc:
        # Notifications are non-critical — log but don't fail the request
        logger.error("sns_publish_error", event_type=event_type, error=str(exc))
