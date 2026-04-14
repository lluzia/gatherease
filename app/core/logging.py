"""
Structured logging configuration using structlog.

In development:  pretty console output with colours.
In production:   JSON lines (compatible with AWS CloudWatch / Datadog).

Call configure_logging() once at startup in main.py.
"""

import logging
import sys

import structlog
from structlog.types import EventDict, WrappedLogger


def _add_app_info(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Inject service name + version into every log record."""
    # Imported lazily to avoid circular dependency at module load time
    from app.config import get_settings

    settings = get_settings()
    event_dict.setdefault("service", settings.app_name.lower())
    event_dict.setdefault("version", settings.app_version)
    event_dict.setdefault("env", settings.app_env)
    return event_dict


def configure_logging(debug: bool = False) -> None:
    """Configure structlog for the application.

    Args:
        debug: When True, use pretty console renderer; otherwise JSON.
    """
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_app_info,
        structlog.processors.StackInfoRenderer(),
    ]

    if debug:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Quiet noisy third-party loggers
    for noisy in ("uvicorn.access", "botocore", "boto3", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
