from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

import requests

from .config import get_settings


def _keys(prefix: str, limit: int = 20) -> list[str]:
    return [os.getenv(f"{prefix}_{i}", "").strip() for i in range(1, limit + 1) if os.getenv(f"{prefix}_{i}", "").strip()]


class ModelGateway:
    """Model-agnostic gateway with provider failover."""

    def __init__(self):
        self.settings = get_settings()

    def text(self, system: str, user: str, max_tokens: int = 1200) -> Optional[str]:
        openai_keys = _keys("OPENAI_KEY", 5)
        if os.getenv("OPENAI_API_KEY", "").strip():
            openai_keys.insert(0, os.getenv("OPENAI_API_KEY", "").strip())
        providers = [
            ("groq", _keys("GROQ_KEY"), self.settings.groq_model),
            ("deepseek", _keys("DEEPSEEK_KEY", 5), self.settings.deepseek_model),
            ("gemini", _keys("GEMINI_KEY"), self.settings.gemini_model),
            ("openai", openai_keys, self.settings.openai_model),
        ]
        for provider, keys, model in providers:
            for key in keys:
                try:
                    result = self._call(provider, key, model, system, user, max_tokens)
                    if result:
                        return result
                except Exception as exc:
                    print(f"[ModelGateway] {provider} failed: {exc}")
        return None

    def image_to_text(
        self,
        prompt: str,
        image_base64: str,
        mime_type: str = "image/jpeg",
        max_tokens: int = 1800,
    ) -> Optional[str]:
        """Read an image using a provider with native vision support."""
        data_url = f"data:{mime_type};base64,{image_base64}"
        openai_keys = _keys("OPENAI_KEY", 5)
        if os.getenv("OPENAI_API_KEY", "").strip():
            openai_keys.insert(0, os.getenv("OPENAI_API_KEY", "").strip())
        for key in openai_keys:
            try:
                response = requests.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={
                        "model": self.settings.openai_model,
                        "instructions": "Read the supplied image carefully. Extract only information visible in the image. Never invent missing digits or text.",
                        "input": [{
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": prompt},
                                {"type": "input_image", "image_url": data_url},
                            ],
                        }],
                        "max_output_tokens": max_tokens,
                    },
                    timeout=self.settings.llm_timeout_seconds,
                )
                response.raise_for_status()
                output = response.json().get("output", [])
                texts = []
                for item in output:
                    for content in item.get("content", []):
                        if content.get("type") in {"output_text", "text"} and content.get("text"):
                            texts.append(content["text"])
                if texts:
                    return "\n".join(texts)
            except Exception as exc:
                print(f"[ModelGateway] OpenAI vision failed: {exc}")

        for key in _keys("GEMINI_KEY"):
            try:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_model}:generateContent"
                response = requests.post(
                    endpoint,
                    params={"key": key},
                    json={
                        "system_instruction": {"parts": [{"text": "Read only what is visibly present in the image. Do not guess."}]},
                        "contents": [{
                            "role": "user",
                            "parts": [
                                {"text": prompt},
                                {"inline_data": {"mime_type": mime_type, "data": image_base64}},
                            ],
                        }],
                        "generationConfig": {"temperature": 0.1, "maxOutputTokens": max_tokens},
                    },
                    timeout=self.settings.llm_timeout_seconds,
                )
                response.raise_for_status()
                parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
                text = "\n".join(p.get("text", "") for p in parts if p.get("text"))
                if text:
                    return text
            except Exception as exc:
                print(f"[ModelGateway] Gemini vision failed: {exc}")
        return None

    def json(self, system: str, user: str, max_tokens: int = 1600) -> Optional[dict[str, Any]]:
        raw = self.text(system, user + "\n\nReturn ONLY valid JSON. No markdown.", max_tokens=max_tokens)
        if not raw:
            return None
        cleaned = raw.strip()
        fence = chr(96) * 3
        if cleaned.startswith(fence):
            cleaned = re.sub(r"^" + fence + r"(?:json)?\s*", "", cleaned, flags=re.I)
            cleaned = re.sub(r"\s*" + fence + r"$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.S)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return None
        return None

    def _call(self, provider: str, key: str, model: str, system: str, user: str, max_tokens: int) -> Optional[str]:
        timeout = self.settings.llm_timeout_seconds
        if provider in {"groq", "deepseek"}:
            base = "https://api.groq.com/openai/v1" if provider == "groq" else "https://api.deepseek.com"
            response = requests.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "temperature": 0.2,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                },
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

        if provider == "openai":
            response = requests.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "instructions": system,
                    "input": user,
                    "temperature": 0.2,
                    "max_output_tokens": max_tokens,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            outputs = data.get("output", [])
            texts = []
            for item in outputs:
                for content in item.get("content", []):
                    if content.get("type") in {"output_text", "text"} and content.get("text"):
                        texts.append(content["text"])
            return "\n".join(texts) or None

        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        response = requests.post(
            endpoint,
            params={"key": key},
            json={
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
