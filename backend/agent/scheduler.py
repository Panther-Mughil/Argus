"""Per-model concurrency scheduling for local LLM endpoints.

The agent loop acquires a semaphore before each completion call so that a
provider with a small concurrency limit (e.g. 1) is not overwhelmed when
multiple challenges run at once. Semaphores are keyed by model id so that
different models do not contend with each other.
"""

import asyncio
import json
from pathlib import Path

MODELS_CONFIG_PATH = Path(__file__).resolve().parent.parent / "models.json"


def _load_models_config() -> dict:
    try:
        return json.loads(MODELS_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Failed to load models config from {MODELS_CONFIG_PATH}: {exc}"
        ) from exc


MODELS_CONFIG = _load_models_config()

onyx_provider = next(p for p in MODELS_CONFIG["providers"] if p["name"] == "Onyx")
DEFAULT_CONCURRENCY = onyx_provider.get("concurrency", 1)


def _concurrency_for(model: str) -> int:
    """Return the configured concurrency limit for a model, else the provider default."""
    for provider in MODELS_CONFIG["providers"]:
        for m in provider.get("models", []):
            if m.get("id") == model:
                return provider.get("concurrency", DEFAULT_CONCURRENCY)
    return DEFAULT_CONCURRENCY


class ModelScheduler:
    def __init__(self) -> None:
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def _get(self, model: str) -> asyncio.Semaphore:
        if model not in self._semaphores:
            self._semaphores[model] = asyncio.Semaphore(_concurrency_for(model))
        return self._semaphores[model]

    async def acquire(self, model: str) -> None:
        await self._get(model).acquire()

    def release(self, model: str) -> None:
        self._get(model).release()

    def locked(self, model: str) -> bool:
        """True if the model's semaphore cannot be acquired immediately."""
        return self._get(model).locked()


# Global scheduler instance shared by all agent loops.
model_scheduler = ModelScheduler()
