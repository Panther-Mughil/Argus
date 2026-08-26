"""OpenAI-compatible chat completion client with a provider registry.

The registry lives in ``backend/models.json``: a list of providers, each with an
``api_type`` (only ``openai-completions`` for now), ``base_url``, optional
``api_key``, ``concurrency``, and a list of ``models``. The client resolves the
owning provider for any model id so Argus can talk to more than one endpoint
(and, later, free web gateways) without hardcoding a single provider.
"""

import json
import os
from pathlib import Path
from typing import Optional

import httpx

from backend.config import settings


# Load the model registry once at import time.
MODELS_CONFIG_PATH = Path(__file__).resolve().parent.parent / "models.json"


def _load_models_config() -> dict:
    try:
        return json.loads(MODELS_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"Failed to load models config from {MODELS_CONFIG_PATH}: {e}"
        ) from e


MODELS_CONFIG = _load_models_config()


def _provider_for_model(model: str) -> dict | None:
    """Return the provider dict that owns ``model``, or None if unknown."""
    for provider in MODELS_CONFIG["providers"]:
        for m in provider.get("models") or []:
            if m.get("id") == model:
                return provider
    return None


def default_model() -> str:
    """Return the first configured model id (used when no override is set)."""
    for provider in MODELS_CONFIG["providers"]:
        for model in provider.get("models") or []:
            return model["id"]
    return "Qwen3.6-35B-A3B"


def model_list() -> list[dict]:
    """Flatten the registry into rows the UI/API can render."""
    rows = []
    for provider in MODELS_CONFIG["providers"]:
        for model in provider.get("models") or []:
            rows.append(
                {
                    "id": model.get("id"),
                    "display_name": model.get("display_name", model.get("id")),
                    "provider": provider.get("name"),
                    "api_type": provider.get("api_type", "openai-completions"),
                    "base_url": provider.get("base_url"),
                    "ctx": model.get("ctx"),
                    "free": bool(model.get("free", False)),
                    "concurrency": provider.get("concurrency", 1),
                }
            )
    return rows


def known_model_ids() -> set[str]:
    return {row["id"] for row in model_list()}


def _sanitize_messages(messages: list) -> list:
    """Strip non-standard fields before sending messages back to the API.

    Some endpoints reject unknown assistant-message fields (e.g. Qwen's
    ``reasoning_content``) when they appear in the request. We keep only the
    OpenAI-compatible shape.
    """
    cleaned = []
    for m in messages:
        role = m.get("role")
        if role == "assistant":
            entry = {"role": "assistant", "content": m.get("content")}
            if m.get("tool_calls"):
                entry["tool_calls"] = m["tool_calls"]
            cleaned.append(entry)
        elif role == "tool":
            cleaned.append(
                {
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id"),
                    "content": m.get("content", ""),
                }
            )
        else:
            cleaned.append({"role": role, "content": m.get("content", "")})
    return cleaned


def _get_api_key(provider: dict) -> Optional[str]:
    """Get the API key from the provider dict, falling back to env if needed."""
    if provider.get("api_key"):
        return provider["api_key"]
    if provider.get("api_key_env"):
        return os.environ.get(provider["api_key_env"])
    return None


async def generate_chat_completion(
    model: str,
    messages: list,
    tools: Optional[list] = None,
    max_tokens: Optional[int] = None,
):
    """Call the OpenAI-compatible endpoint that owns ``model``.

    Raises on transport/HTTP error.
    """
    provider = _provider_for_model(model)
    if provider is None:
        raise ValueError(f"No provider configured for model '{model}'")

    base_url = provider.get("base_url", "").rstrip("/")
    url = f"{base_url}/chat/completions"

    headers = {}
    api_key = _get_api_key(provider)
    if api_key:
        # pi-lens-ignore: no-secret-in-env-var-name — api_key is resolved from the
        # provider registry / environment at runtime, not hardcoded here.
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": _sanitize_messages(messages),
        "temperature": 0.1,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=settings.ARGUS_LLM_TIMEOUT) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code == 429:
            raise RateLimitError(f"Provider rate-limited: {provider.get('name')}")
        if response.status_code == 402:
            raise QuotaExceededError(f"Provider quota exceeded: {provider.get('name')}")
        response.raise_for_status()
        return response.json()


class RateLimitError(Exception):
    pass


class QuotaExceededError(Exception):
    pass
