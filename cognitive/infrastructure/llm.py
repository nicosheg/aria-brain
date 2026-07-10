# cognitive/infrastructure/llm.py

from typing import Optional
import requests
import os

# Use environment keys for Groq
KEYS = {
    'groq': [os.environ.get(f"GROQ_KEY_{i}", "") for i in range(1, 21)],
    'gemini': [os.environ.get(f"GEMINI_KEY_{i}", "") for i in range(1, 21)],
    'deepseek': [os.environ.get(f"DEEPSEEK_KEY_{i}", "") for i in range(1, 6)]
}

def try_all_apis_parallel(prompt: str, system_prompt: str, timeout: int = 20) -> Optional[str]:
    """Call Groq APIs sequentially until one works."""
    for k in KEYS.get('groq', []):
        if not k:
            continue
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={
                    "model": "llama-3.3-70b-versatile",
                    "temperature": 0.7,
                    "max_tokens": 300,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                },
                headers={"Authorization": f"Bearer {k}"},
                timeout=timeout
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
        except Exception:
            continue
    return None

def call_llm(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call LLM with system and user prompts."""
    return try_all_apis_parallel(user_prompt, system_prompt)
