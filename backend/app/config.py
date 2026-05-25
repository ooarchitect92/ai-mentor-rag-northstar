from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_api_url: str = "https://api.anthropic.com/v1/messages"
    anthropic_version: str = "2023-06-01"
    anthropic_max_tokens: int = 1800

    embedding_provider: Literal["hash", "openai"] = "hash"
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "mentor_knowledge"

    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 86400

    admin_token: str = "change-me"

    whatsapp_verify_token: str = "change-me-whatsapp"
    whatsapp_access_token: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""
    meta_app_secret: str = ""
    meta_app_id: str = ""
    facebook_app_id: str = ""
    whatsapp_graph_api_version: str = "v25.0"
    whatsapp_graph_base: str = ""
    whatsapp_business_account_id: str = ""
    whatsapp_default_course: str = "GENERAL"
    whatsapp_default_mode: str = "doubt_solving"
    whatsapp_default_level: str = "beginner"
    whatsapp_max_reply_chars: int = 3900
    whatsapp_session_ttl_seconds: int = 2592000
    whatsapp_start_template_name: str = "hello_world"
    whatsapp_start_template_language: str = "en_US"
    whatsapp_use_mock: bool = False

    app_host: str = "0.0.0.0"
    app_port: int = 8000

    top_k: int = 5
    max_context_chars: int = 9000
    request_timeout_seconds: int = 45

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
