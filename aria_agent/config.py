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
    model: str = os.getenv("ARIA_MODEL", os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5"))
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    max_turns: int = int(os.getenv("ARIA_MAX_TURNS", "24"))
    max_message_chars: int = int(os.getenv("ARIA_MAX_MESSAGE_CHARS", "12000"))
    memory_results: int = int(os.getenv("ARIA_MEMORY_RESULTS", "12"))
    data_dir: Path = Path(os.getenv("ARIA_DATA_DIR", "/tmp/aria"))
    allow_email_identity: bool = _bool("ARIA_ALLOW_EMAIL_IDENTITY", False)
    browser_enabled: bool = _bool("ARIA_BROWSER_ENABLED", True)
    computer_enabled: bool = _bool("ARIA_COMPUTER_ENABLED", False)
    encryption_key: str = os.getenv("ARIA_ENCRYPTION_KEY", "")
    app_secret: str = os.getenv("ARIA_APP_SECRET", "")
    database_url: str = os.getenv("SUPABASE_DB_URL", os.getenv("DATABASE_URL", ""))

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
if not settings.data_dir.exists():
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
