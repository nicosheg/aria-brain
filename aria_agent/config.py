from __future__ import annotations

from dataclasses import dataclass, field
import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("ARIA_APP_NAME", "ARIA")
    app_version: str = os.getenv("ARIA_APP_VERSION", "4.0.0")
    database_url: str = os.getenv("SUPABASE_DB_URL", "")
    autonomy_level: str = os.getenv("ARIA_AUTONOMY_LEVEL", "supervised").lower()
    max_steps_per_run: int = _int("ARIA_MAX_STEPS", 12)
    max_tool_output_chars: int = _int("ARIA_MAX_TOOL_OUTPUT_CHARS", 12000)
    approval_ttl_seconds: int = _int("ARIA_APPROVAL_TTL_SECONDS", 1800)
    llm_timeout_seconds: int = _int("ARIA_LLM_TIMEOUT_SECONDS", 25)
    search_timeout_seconds: int = _int("ARIA_SEARCH_TIMEOUT_SECONDS", 12)
    allow_browser: bool = os.getenv("ARIA_BROWSER_ENABLED", "false").lower() == "true"
    connector_encryption_key: str = os.getenv("ARIA_CONNECTOR_ENCRYPTION_KEY", "")
    public_base_url: str = os.getenv("ARIA_PUBLIC_BASE_URL", "")
    default_model: str = os.getenv("ARIA_MODEL", "llama-3.3-70b-versatile")
    groq_model: str = os.getenv("GROQ_MODEL", os.getenv("ARIA_MODEL", "llama-3.3-70b-versatile"))
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    search_provider: str = os.getenv("ARIA_SEARCH_PROVIDER", "auto").lower()
    allowed_external_domains: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            d.strip().lower() for d in os.getenv("ARIA_ALLOWED_DOMAINS", "").split(",") if d.strip()
        )
    )


def get_settings() -> Settings:
    return Settings()
