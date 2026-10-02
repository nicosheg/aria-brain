import os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("ARIA_APP_NAME", "ARIA")
    model: str = os.getenv("ARIA_MODEL", os.getenv("OPENAI_DEFAULT_MODEL", "gpt-6-luna"))
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    max_turns: int = max(8, min(int(os.getenv("ARIA_MAX_TURNS", "32")), 64))
    max_message_chars: int = max(1000, min(int(os.getenv("ARIA_MAX_MESSAGE_CHARS", "12000")), 50000))
    memory_results: int = max(4, min(int(os.getenv("ARIA_MEMORY_RESULTS", "12")), 50))
    max_provider_attempts: int = max(1, min(int(os.getenv("ARIA_MAX_PROVIDER_ATTEMPTS", "10")), 32))

    data_dir: Path = Path(os.getenv("ARIA_DATA_DIR", "/tmp/aria"))
    allow_email_identity: bool = _bool("ARIA_ALLOW_EMAIL_IDENTITY", False)
    browser_enabled: bool = _bool("ARIA_BROWSER_ENABLED", True)
    computer_enabled: bool = _bool("ARIA_COMPUTER_ENABLED", False)

    encryption_key: str = os.getenv("ARIA_ENCRYPTION_KEY", "")
    app_secret: str = os.getenv("ARIA_APP_SECRET", "")
    database_url: str = os.getenv("SUPABASE_DB_URL", os.getenv("DATABASE_URL", ""))
    require_database: bool = _bool("ARIA_REQUIRE_DATABASE", False)

    worker_concurrency: int = max(1, min(int(os.getenv("ARIA_WORKER_CONCURRENCY", "2")), 16))
    job_max_attempts: int = max(1, min(int(os.getenv("ARIA_JOB_MAX_ATTEMPTS", "4")), 10))
    job_lease_seconds: int = max(30, min(int(os.getenv("ARIA_JOB_LEASE_SECONDS", "900")), 86400))

    @property
    def has_openai(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    @property
    def has_any_model(self) -> bool:
        prefixes = ("GROQ_KEY_", "DEEPSEEK_KEY_", "GEMINI_KEY_")
        return self.has_openai or any(
            any(k.startswith(prefix) and v for k, v in os.environ.items())
            for prefix in prefixes
        )


settings = Settings()
if settings.require_database and not settings.database_url:
    raise RuntimeError("ARIA_REQUIRE_DATABASE=true but no SUPABASE_DB_URL/DATABASE_URL is configured.")

try:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
except OSError:
    if settings.require_database:
        raise
