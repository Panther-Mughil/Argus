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


def _config() -> dict:
    """Return a fresh copy of the registry (re-read the file each call).

    Re-reading lets admin edits to models.json take effect immediately and
    avoids the fragile ``next(...)`` import-time lookup when Onyx is removed.
    """
    return _load_models_config()


def _as_int(value, default: int) -> int:
    """Safely coerce a value to int; returns ``default`` on bad input."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _default_concurrency() -> int:
    cfg = _config()
    for provider in cfg.get("providers", []):
        if provider.get("name") == "Onyx":
            return _as_int(provider.get("concurrency"), 1)
    for provider in cfg.get("providers", []):
        return _as_int(provider.get("concurrency"), 1)
    return 1


def _concurrency_for(model: str) -> int:
    """Return the configured concurrency limit for a model, else the provider default."""
    for provider in _config().get("providers", []):
        for m in provider.get("models", []):
            if m.get("id") == model:
                return _as_int(provider.get("concurrency"), _default_concurrency())
    return _default_concurrency()


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
