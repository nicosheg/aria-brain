"""Regression tests for ARIA's optional Z.ai / GLM-5.3 provider."""
from aria_agent.config import settings
from aria_agent.runtime import AriaRuntime


PROVIDER_PRIMARY_KEYS = (
    "GROQ_API_KEY",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "OPENROUTER_API_KEY",
    "DASHSCOPE_API_KEY",
    "ZAI_API_KEY",
)
PROVIDER_KEY_PREFIXES = (
    "GROQ_KEY",
    "OPENAI_KEY",
    "DEEPSEEK_KEY",
    "GEMINI_KEY",
    "OPENROUTER_KEY",
    "DASHSCOPE_KEY",
    "ZAI_KEY",
)


def _runtime_without_rejected_keys() -> AriaRuntime:
    runtime = AriaRuntime.__new__(AriaRuntime)
    runtime._rejected_provider_keys = set()
    return runtime


def _clear_provider_keys(monkeypatch):
    for name in PROVIDER_PRIMARY_KEYS:
        monkeypatch.delenv(name, raising=False)
    for prefix in PROVIDER_KEY_PREFIXES:
        for index in range(1, 21):
            monkeypatch.delenv(f"{prefix}_{index}", raising=False)


def test_zai_provider_is_optional_and_uses_glm53_openai_compatible_endpoint(monkeypatch):
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("ZAI_API_KEY", "test-zai-key-not-a-real-secret")
    monkeypatch.setenv("ARIA_PROVIDER", "zai")
    monkeypatch.delenv("ZAI_BASE_URL", raising=False)

    configs = _runtime_without_rejected_keys()._provider_configs()
    assert configs
    assert configs[0]["provider"] == "zai"
    assert configs[0]["model"] == "glm-5.3"
    assert configs[0]["base_url"] == "https://api.z.ai/api/paas/v4"
    assert configs[0]["key"] == "test-zai-key-not-a-real-secret"
    assert configs[0]["fingerprint"] != configs[0]["key"]


def test_zai_endpoint_can_be_overridden_for_coding_plan_or_compatible_self_host(monkeypatch):
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("ZAI_API_KEY", "test-zai-key")
    monkeypatch.setenv("ARIA_PROVIDER", "zai")
    monkeypatch.setenv("ZAI_BASE_URL", "https://api.z.ai/api/coding/paas/v4/")

    configs = _runtime_without_rejected_keys()._provider_configs()
    assert configs[0]["provider"] == "zai"
    assert configs[0]["base_url"] == "https://api.z.ai/api/coding/paas/v4"


def test_zai_is_not_required_for_existing_provider_setup(monkeypatch):
    _clear_provider_keys(monkeypatch)
    monkeypatch.delenv("ARIA_PROVIDER", raising=False)
    monkeypatch.delenv("ZAI_BASE_URL", raising=False)

    assert all(
        config["provider"] != "zai"
        for config in _runtime_without_rejected_keys()._provider_configs()
    )
    assert settings.has_any_model is False


def test_zai_credentials_count_as_a_configured_model_provider(monkeypatch):
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("ZAI_API_KEY", "test-zai-key")
    assert settings.has_any_model is True


def test_glm53_reasoning_effort_is_restricted_to_supported_values(monkeypatch):
    runtime = _runtime_without_rejected_keys()
    assert runtime._zai_reasoning_effort() in {"low", "high", "max"}
