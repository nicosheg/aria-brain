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
    groq_model: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    reasoning_effort: str = os.getenv("ARIA_REASONING_EFFORT", "default").strip().lower()
    # Legacy field compatibility keeps an older Render instance bootable during a rolling deploy.
    # The live provider path is still Groq Qwen3.8 only.
    model: str = os.getenv("ARIA_MODEL", "qwen/qwen3.8-27b")
    qwen_model: str = os.getenv("QWEN_MODEL", "qwen/qwen3.8-27b")
    qwencloud_model: str = os.getenv("QWENCLOUD_MODEL", "qwen3.8-flash")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    openrouter_site_url: str = os.getenv("OPENROUTER_SITE_URL", "")
    openrouter_site_name: str = os.getenv("OPENROUTER_SITE_NAME", "ARIA")
    max_turns: int = int(os.getenv("ARIA_MAX_TURNS", "32"))
    max_message_chars: int = int(os.getenv("ARIA_MAX_MESSAGE_CHARS", "12000"))
    memory_results: int = int(os.getenv("ARIA_MEMORY_RESULTS", "12"))
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
        if os.getenv("GROQ_API_KEY", "").strip():
            return True
        return any(os.getenv(f"GROQ_KEY_{i}", "").strip() for i in range(1, 21))


settings = Settings()
if not settings.data_dir.exists():
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
