import json
import httpx
import os

# Load models config
config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models.json")
with open(config_path, "r") as f:
    MODELS_CONFIG = json.load(f)

# Find the Onyx provider
onyx_provider = next(p for p in MODELS_CONFIG["providers"] if p["name"] == "Onyx")
BASE_URL = onyx_provider["base_url"]

async def generate_chat_completion(model: str, messages: list, tools: list = None):
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
