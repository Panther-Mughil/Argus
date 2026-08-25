import json
from pathlib import Path
from typing import Optional

import httpx

from backend.config import settings

# Load models config
MODELS_CONFIG_PATH = Path(__file__).resolve().parent.parent / "models.json"


def _load_models_config() -> dict:
    try:
        return json.loads(MODELS_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Failed to load models config from {MODELS_CONFIG_PATH}: {e}") from e


MODELS_CONFIG = _load_models_config()

# Find the Onyx provider
onyx_provider = next(p for p in MODELS_CONFIG["providers"] if p["name"] == "Onyx")
BASE_URL = onyx_provider["base_url"]


def default_model() -> str:
    """Return the first configured model id (used when no override is set)."""
    for provider in MODELS_CONFIG["providers"]:
        models = provider.get("models") or []
        if models:
            return models[0]["id"]
    return "gpt-oss-20B"


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
            cleaned.append({
                "role": "tool",
                "tool_call_id": m.get("tool_call_id"),
                "content": m.get("content", ""),
            })
        else:
            cleaned.append({"role": role, "content": m.get("content", "")})
    return cleaned


async def generate_chat_completion(
    model: str,
    messages: list,
    tools: Optional[list] = None,
    max_tokens: Optional[int] = None,
):
    """Call the local OpenAI-compatible endpoint. Raises on transport/HTTP error."""
    url = f"{BASE_URL}/chat/completions"

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
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
