import json
from pathlib import Path
from typing import Optional

import httpx

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

async def generate_chat_completion(model: str, messages: list, tools: Optional[list] = None):
    """
    Calls the local OpenAI-compatible endpoint.
    """
    url = f"{BASE_URL}/chat/completions"
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
    }
    
    if tools:
        payload["tools"] = tools
        
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"LLM API Error: {e}")
            return None
