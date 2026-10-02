from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    model: str = os.getenv("ARIA_MODEL", "gpt-6-luna")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    max_turns: int = int(os.getenv("ARIA_MAX_TURNS", "18"))
    max_message_chars: int = int(os.getenv("ARIA_MAX_MESSAGE_CHARS", "12000"))
    max_provider_attempts: int = int(os.getenv("ARIA_MAX_PROVIDER_ATTEMPTS", "10"))

    browser_enabled: bool = os.getenv("ARIA_BROWSER_ENABLED", "false").lower() == "true"
    allow_email_identity: bool = os.getenv("ARIA_ALLOW_EMAIL_IDENTITY", "false").lower() == "true"

    data_dir: Path = Path(os.getenv("ARIA_DATA_DIR", "/data/aria"))

    database_url: str = os.getenv("SUPABASE_DB_URL", "")
    encryption_key: str = os.getenv("ARIA_ENCRYPTION_KEY", "")
    app_secret: str = os.getenv("ARIA_APP_SECRET", "")


settings = Settings()
