"""BYOK provider access. Credentials come from environment/.env and are
never printed, logged, or returned by this layer.

Supported providers (configurable through environment):

    OPENAI_API_KEY, OPENAI_BASE_URL (default api.openai.com/v1), OPENAI_MODEL
    ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL (default api.anthropic.com), ANTHROPIC_MODEL

Multiple providers are attempted sequentially by default; callers may also
drive them concurrently across files.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

DEFAULT_OPENAI_BASE = "https://api.openai.com/v1"
DEFAULT_ANTHROPIC_BASE = "https://api.anthropic.com"


def load_dotenv(path: str | Path = ".env") -> dict[str, str]:
    """Parse a minimal .env file (KEY=VALUE, # comments, no interpolation)."""
    env: dict[str, str] = {}
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return env
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            env[key] = value
    return env


def env_with_dotenv(path: str | Path = ".env") -> dict[str, str]:
    """Merged os.environ plus .env values (os.environ wins)."""
    merged = dict(load_dotenv(path))
    merged.update(os.environ)
    return merged


def _mask(value: str) -> str:
    return f"{value[:3]}***{value[-2:]}" if len(value) > 6 else "***"


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 60) -> str:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


class Provider:
    def __init__(self, name: str, env: dict[str, str]):
        self.name = name
        self.env = env
        self.key = env.get(self.key_env(), "")
        self.model = env.get(self.model_env(), self.default_model())

    def key_env(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    def model_env(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    def default_model(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    def configured(self) -> bool:
        return bool(self.key)

    def describe(self) -> str:
        return f"{self.name} model={self.model or 'hmmm'} key={_mask(self.key) if self.key else 'absent'}"

    def chat(self, system: str, user: str) -> str:  # pragma: no cover - overridden
        raise NotImplementedError


class OpenAIProvider(Provider):
    def __init__(self, env: dict[str, str]):
        super().__init__("openai", env)
        base = env.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE).rstrip("/")
        self.url = f"{base}/chat/completions"

    def key_env(self) -> str:
        return "OPENAI_API_KEY"

    def model_env(self) -> str:
        return "OPENAI_MODEL"

    def default_model(self) -> str:
        return "gpt-4o-mini"

    def chat(self, system: str, user: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.key}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
        }
        data = json.loads(_post_json(self.url, payload, headers))
        return data["choices"][0]["message"]["content"]


class AnthropicProvider(Provider):
    def __init__(self, env: dict[str, str]):
        super().__init__("anthropic", env)
        base = env.get("ANTHROPIC_BASE_URL", DEFAULT_ANTHROPIC_BASE).rstrip("/")
        self.url = f"{base}/v1/messages"

    def key_env(self) -> str:
        return "ANTHROPIC_API_KEY"

    def model_env(self) -> str:
        return "ANTHROPIC_MODEL"

    def default_model(self) -> str:
        return "claude-3-5-haiku-latest"

    def chat(self, system: str, user: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        data = json.loads(_post_json(self.url, payload, headers))
        return "".join(block.get("text", "") for block in data.get("content", []))


def configured_providers(env: dict[str, str]) -> list[Provider]:
    """Return providers with credentials, in stable order."""
    providers = [OpenAIProvider(env), AnthropicProvider(env)]
    return [p for p in providers if p.configured()]


def chat_with_fallback(providers: list[Provider], system: str, user: str) -> tuple[str, str]:
    """Try providers sequentially. Returns (text, provider_name) or raises."""
    errors: list[str] = []
    for provider in providers:
        try:
            return provider.chat(system, user), provider.name
        except Exception as exc:  # noqa: BLE001 - boundary to hmmm, never to crash
            errors.append(f"{provider.name}: {type(exc).__name__}")
    raise RuntimeError("; ".join(errors) or "no providers configured")
