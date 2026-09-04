import json
import os
import threading
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_environment: Literal["development", "test", "production"] = "development"

    mentor_provider: Literal["nvidia", "gemini", "anthropic"] = "nvidia"
    mentor_fallback_provider: Literal["nvidia", "anthropic", "gemini", "none"] = "gemini"
    mentor_policy_provider: Literal["gemini", "primary"] = "gemini"

    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    nvidia_temperature: float = 1.0
    nvidia_top_p: float = 0.95
    nvidia_max_tokens: int = 2048
    nvidia_enable_thinking: bool = False
    nvidia_reasoning_budget: int = 2048
    nvidia_policy_max_tokens: int = 32

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_api_url: str = "https://generativelanguage.googleapis.com/v1beta/models"
    gemini_max_output_tokens: int = 1800

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
    question_answer_file: str = "/app/data/question_answers.txt"
    question_repeat_ttl_seconds: int = 31536000

    admin_token: str = ""
    admin_database_file: str = "data/admin.sqlite3"
    admin_upload_max_bytes: int = 20 * 1024 * 1024
    admin_upload_max_files: int = 10
    training_lease_timeout_seconds: int = 900
    training_recovery_interval_seconds: int = 60
    runtime_config_file: str = "data/runtime-config.json"
    mentor_system_prompt_file: str = "data/mentor-system-prompt.txt"

    whatsapp_verify_token: str = ""
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
    whatsapp_webhook_callback_url: str = ""
    # Stable public origin Meta can reach for direct webhook delivery. A
    # trycloudflare quick-tunnel URL is intentionally not inferred because it
    # changes after a restart and silently breaks inbound routing.
    northstar_public_base_url: str = ""
    whatsapp_messaging_enabled: bool = True
    # When enabled, every WhatsApp sender receives CMA access without being
    # written to the enrollment store. Explicit enrollments can still grant
    # additional courses.
    whatsapp_open_cma_access: bool = False
    whatsapp_default_course: Literal["CMA", "CPA", "CFA", "ACCA", "CS", "EA"] = "CMA"
    whatsapp_default_mode: Literal["teach", "quiz", "revise", "job_hunt", "doubt_solving"] = "teach"
    whatsapp_default_level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    whatsapp_max_reply_chars: int = 3900
    whatsapp_max_media_bytes: int = 5 * 1024 * 1024
    whatsapp_session_ttl_seconds: int = 2592000
    whatsapp_feedback_number: str = ""
    whatsapp_feedback_prefill: str = "FEEDBACK\nPlease describe the change or error. You can also attach a screenshot."
    whatsapp_feedback_session_ttl_seconds: int = 900
    whatsapp_webhook_lease_timeout_seconds: int = 360
    whatsapp_webhook_recovery_interval_seconds: int = 15
    whatsapp_webhook_max_attempts: int = 6
    whatsapp_inbound_processing_ttl_seconds: int = 300
    whatsapp_message_retention_days: int = 90
    # Legacy development/test compatibility secret. Relay endpoints are always
    # disabled in production and this value is never exposed through public config.
    whatsapp_relay_token: str = ""
    feedback_media_directory: str = "data/feedback-media"
    feedback_max_per_sender_per_day: int = 10
    feedback_max_storage_bytes: int = 1024 * 1024 * 1024
    feedback_retention_days: int = 365
    whatsapp_start_template_name: str = "hello_world"
    whatsapp_start_template_language: str = "en_US"
    whatsapp_use_mock: bool = False
    whatsapp_enrollments: str = ""
    whatsapp_enrollments_file: str = ""
    whatsapp_enrollments_google_sheet_id: str = ""
    whatsapp_enrollments_google_sheet_range: str = "Enrollments!A:E"
    whatsapp_enrollments_google_refresh_seconds: int = 60
    google_service_account_file: str = ""

    app_host: str = "0.0.0.0"
    app_port: int = 8000

    top_k: int = 5
    max_context_chars: int = 9000
    strict_grounding: bool = True
    minimum_retrieval_score: float = 0.35
    course_retrieval_enabled: bool = True
    request_timeout_seconds: int = 120

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


RUNTIME_EDITABLE_FIELDS = frozenset(
    {
        "mentor_provider",
        "mentor_fallback_provider",
        "mentor_policy_provider",
        "nvidia_model",
        "nvidia_temperature",
        "nvidia_top_p",
        "nvidia_max_tokens",
        "nvidia_enable_thinking",
        "nvidia_reasoning_budget",
        "gemini_model",
        "gemini_max_output_tokens",
        "anthropic_model",
        "anthropic_max_tokens",
        "cache_ttl_seconds",
        "top_k",
        "max_context_chars",
        "strict_grounding",
        "minimum_retrieval_score",
        "course_retrieval_enabled",
        "whatsapp_default_course",
        "whatsapp_messaging_enabled",
        "whatsapp_open_cma_access",
        "whatsapp_default_mode",
        "whatsapp_default_level",
        "whatsapp_max_reply_chars",
        "whatsapp_feedback_number",
        "whatsapp_feedback_prefill",
    }
)

RUNTIME_SYSTEM_PROMPT_KEY = "_system_prompt"
RUNTIME_VERSION_KEY = "_version"


class RuntimeConfigurationConflictError(RuntimeError):
    """Raised when an administrator saves an out-of-date configuration form."""


_runtime_write_lock = threading.RLock()


def _read_runtime_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _read_runtime_overrides(path: Path) -> dict[str, Any]:
    payload = _read_runtime_payload(path)
    return {key: value for key, value in payload.items() if key in RUNTIME_EDITABLE_FIELDS}


def _runtime_version(payload: dict[str, Any]) -> int:
    try:
        return max(0, int(payload.get(RUNTIME_VERSION_KEY, 0)))
    except (TypeError, ValueError):
        return 0


def runtime_configuration_version(settings: Settings | None = None) -> int:
    current = settings or get_settings()
    return _runtime_version(_read_runtime_payload(Path(current.runtime_config_file)))


def _normalize_system_prompt(prompt: str) -> str:
    normalized = prompt.strip()
    if not 100 <= len(normalized) <= 20_000:
        raise ValueError("System prompt must contain between 100 and 20,000 characters")
    return normalized


def _write_runtime_payload(target: Path, payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@lru_cache
def get_settings() -> Settings:
    base = Settings()
    overrides = _read_runtime_overrides(Path(base.runtime_config_file))
    if not overrides:
        return base
    return Settings(**{**base.model_dump(), **overrides})


def public_runtime_settings(settings: Settings | None = None) -> dict[str, Any]:
    current = settings or get_settings()
    values = current.model_dump()
    return {key: values[key] for key in sorted(RUNTIME_EDITABLE_FIELDS)}


def update_runtime_configuration(
    updates: dict[str, Any],
    *,
    system_prompt: str | None,
    expected_version: int,
    default_prompt: str = "",
) -> tuple[Settings, str, int]:
    unknown = set(updates) - RUNTIME_EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Settings are not dashboard-editable: {', '.join(sorted(unknown))}")
    normalized_prompt = _normalize_system_prompt(system_prompt) if system_prompt is not None else None

    with _runtime_write_lock:
        # Reload after acquiring the write lock so a previous request in this
        # process cannot be hidden behind the settings cache.
        get_settings.cache_clear()
        current = get_settings()
        target = Path(current.runtime_config_file)
        existing_payload = _read_runtime_payload(target)
        current_version = _runtime_version(existing_payload)
        if int(expected_version) != current_version:
            raise RuntimeConfigurationConflictError(
                "Configuration changed after this page was opened. Reload and review the latest values."
            )
        candidate_data = {**current.model_dump(), **updates}
        candidate = Settings(**candidate_data)
        persisted = public_runtime_settings(candidate)
        if normalized_prompt is not None:
            persisted[RUNTIME_SYSTEM_PROMPT_KEY] = normalized_prompt
        elif isinstance(existing_payload.get(RUNTIME_SYSTEM_PROMPT_KEY), str):
            persisted[RUNTIME_SYSTEM_PROMPT_KEY] = existing_payload[RUNTIME_SYSTEM_PROMPT_KEY]
        else:
            legacy_prompt = read_system_prompt(default_prompt)
            if legacy_prompt:
                persisted[RUNTIME_SYSTEM_PROMPT_KEY] = legacy_prompt
        new_version = current_version + 1
        persisted[RUNTIME_VERSION_KEY] = new_version
        _write_runtime_payload(target, persisted)
        get_settings.cache_clear()
        settings = get_settings()
        return settings, read_system_prompt(default_prompt), new_version


def update_runtime_settings(updates: dict[str, Any]) -> Settings:
    version = runtime_configuration_version()
    settings, _, _ = update_runtime_configuration(
        updates,
        system_prompt=None,
        expected_version=version,
    )
    return settings


def validate_runtime_setting_values(values: dict[str, Any]) -> dict[str, Any]:
    """Validate partial settings while preserving pydantic's useful field errors."""
    unknown = set(values) - RUNTIME_EDITABLE_FIELDS
    if unknown:
        raise ValueError(f"Settings are not dashboard-editable: {', '.join(sorted(unknown))}")
    current = get_settings()
    candidate = Settings(**{**current.model_dump(), **values})
    return {key: getattr(candidate, key) for key in values}


def write_system_prompt(prompt: str) -> None:
    update_runtime_configuration(
        {},
        system_prompt=prompt,
        expected_version=runtime_configuration_version(),
    )


def read_system_prompt(default: str) -> str:
    settings = get_settings()
    payload = _read_runtime_payload(Path(settings.runtime_config_file))
    stored = payload.get(RUNTIME_SYSTEM_PROMPT_KEY)
    if isinstance(stored, str) and stored.strip():
        return stored.strip()
    try:
        prompt = Path(settings.mentor_system_prompt_file).read_text(encoding="utf-8").strip()
    except OSError:
        return default
    return prompt or default
