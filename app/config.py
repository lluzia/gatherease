from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "GatherEase"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── Local auth mode ──────────────────────────────────────────────────────
    # When True: backend issues its own JWTs — no AWS Cognito needed.
    # When False: backend validates JWTs against Cognito public keys (production).
    local_auth: bool = False

    # ── Database ────────────────────────────────────────────────────────────
    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # ── AWS Cognito (required only when local_auth=False) ────────────────────
    cognito_region: str = "eu-west-1"
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_client_secret: str = ""

    # ── AWS General ─────────────────────────────────────────────────────────
    aws_region: str = "eu-west-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # ── S3 / MinIO ──────────────────────────────────────────────────────────
    s3_bucket_name: str = "gatherease-assets-dev"
    s3_presigned_url_expiry: int = 3600
    # Set to http://localhost:9000 for local MinIO; empty = real AWS S3
    s3_endpoint_url: str = ""

    # ── SNS ─────────────────────────────────────────────────────────────────
    sns_topic_arn: str = ""

    # ── CORS ────────────────────────────────────────────────────────────────
    cors_origins: list[AnyHttpUrl] = []

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list) -> list:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    # ── Security ────────────────────────────────────────────────────────────
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    guest_token_expire_days: int = 7

    # ── Email (local Mailpit / production SES) ───────────────────────────────
    smtp_host: str = "localhost"
    smtp_port: int = 1025

    # ── Derived helpers ─────────────────────────────────────────────────────
    @property
    def cognito_jwks_url(self) -> str:
        return (
            f"https://cognito-idp.{self.cognito_region}.amazonaws.com"
            f"/{self.cognito_user_pool_id}/.well-known/jwks.json"
        )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def using_local_s3(self) -> bool:
        return bool(self.s3_endpoint_url)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance. Use as a FastAPI dependency."""
    return Settings()
