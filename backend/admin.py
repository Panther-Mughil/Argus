"""Admin data-management endpoints: container hosts + model registry.

These read/write the on-disk JSON registries (``hosts.json``, ``models.json``)
so the frontend Settings page can manage container hosts and the LLM model
registry directly.  Every route is admin-only.  The registries are re-read on
each request (see ``llm``/``scheduler``/``worker.host_registry``) so edits take
effect immediately without a restart.
"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.config import settings
from worker import host_registry

from .agent import llm
from .auth import admin_required
from .db.models import User

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


def _resolve(path_str: str) -> Path:
    """Resolve a possibly-relative path against the project root."""
    p = Path(path_str)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / p
    return p


_HOSTS_PATH = _resolve(settings.ARGUS_HOSTS_PATH)
_MODELS_PATH = llm.MODELS_CONFIG_PATH


def _read_json(path: Path, default) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ----------------------------------------------------------------------
# Container hosts
# ----------------------------------------------------------------------


class HostUpsert(BaseModel):
    name: str
    host: str = ""
    port: int = 2222
    user: str = "root"
    ssh_key: str = ""
    concurrency: int = 2
    max_challenges: int = 8
    healthy: bool = True
    notes: str = ""


@admin_router.get("/hosts")
async def list_hosts(_admin: User = Depends(admin_required)):
    return _read_json(_HOSTS_PATH, {"hosts": []})


@admin_router.post("/hosts")
async def add_host(
    body: HostUpsert,
    _admin: User = Depends(admin_required),
):
    data = _read_json(_HOSTS_PATH, {"hosts": []})
    hosts = data.setdefault("hosts", [])
    if any(h.get("name") == body.name for h in hosts):
        raise HTTPException(
            status_code=400, detail=f"Host '{body.name}' already exists"
        )
    hosts.append(body.model_dump())
    _write_json(_HOSTS_PATH, data)
    host_registry.reload()
    return {"status": "ok", "hosts": hosts}


@admin_router.put("/hosts/{name}")
async def update_host(
    name: str,
    body: HostUpsert,
    _admin: User = Depends(admin_required),
):
    data = _read_json(_HOSTS_PATH, {"hosts": []})
    hosts = data.setdefault("hosts", [])
    for i, h in enumerate(hosts):
        if h.get("name") == name:
            hosts[i] = body.model_dump()
            _write_json(_HOSTS_PATH, data)
            host_registry.reload()
            return {"status": "ok", "hosts": hosts}
    raise HTTPException(status_code=404, detail=f"Host '{name}' not found")


@admin_router.delete("/hosts/{name}")
async def delete_host(name: str, _admin: User = Depends(admin_required)):
    data = _read_json(_HOSTS_PATH, {"hosts": []})
    hosts = data.setdefault("hosts", [])
    new_hosts = [h for h in hosts if h.get("name") != name]
    if len(new_hosts) == len(hosts):
        raise HTTPException(status_code=404, detail=f"Host '{name}' not found")
    data["hosts"] = new_hosts
    _write_json(_HOSTS_PATH, data)
    host_registry.reload()
    return {"status": "ok", "hosts": new_hosts}


# ----------------------------------------------------------------------
# Model registry (providers + models)
# ----------------------------------------------------------------------


class ModelIn(BaseModel):
    id: str
    display_name: str | None = None
    ctx: int | None = None
    free: bool = False
    notes: str = ""


class ProviderIn(BaseModel):
    name: str
    api_type: str = "openai-completions"
    base_url: str = ""
    api_key: str | None = None
    api_key_env: str | None = None
    concurrency: int = 1
    models: list[ModelIn] = Field(default_factory=list)


@admin_router.get("/models")
async def get_models(_admin: User = Depends(admin_required)):
    return _read_json(_MODELS_PATH, {"providers": []})


@admin_router.post("/models/providers")
async def add_provider(
    body: ProviderIn,
    _admin: User = Depends(admin_required),
):
    data = _read_json(_MODELS_PATH, {"providers": []})
    providers = data.setdefault("providers", [])
    if any(p.get("name") == body.name for p in providers):
        raise HTTPException(
            status_code=400, detail=f"Provider '{body.name}' already exists"
        )
    providers.append(body.model_dump())
    _write_json(_MODELS_PATH, data)
    return {"status": "ok", "providers": providers}


@admin_router.put("/models/providers/{name}")
async def update_provider(
    name: str,
    body: ProviderIn,
    _admin: User = Depends(admin_required),
):
    data = _read_json(_MODELS_PATH, {"providers": []})
    providers = data.setdefault("providers", [])
    for i, p in enumerate(providers):
        if p.get("name") == name:
            new = body.model_dump()
            # Preserve existing models when the submitted body omits them
            # (the UI edit form does not send the models array).
            if not new.get("models"):
                new["models"] = p.get("models", [])
            providers[i] = new
            _write_json(_MODELS_PATH, data)
            return {"status": "ok", "providers": providers}
    raise HTTPException(status_code=404, detail=f"Provider '{name}' not found")


@admin_router.delete("/models/providers/{name}")
async def delete_provider(name: str, _admin: User = Depends(admin_required)):
    data = _read_json(_MODELS_PATH, {"providers": []})
    providers = data.setdefault("providers", [])
    new_providers = [p for p in providers if p.get("name") != name]
    if len(new_providers) == len(providers):
        raise HTTPException(status_code=404, detail=f"Provider '{name}' not found")
    data["providers"] = new_providers
    _write_json(_MODELS_PATH, data)
    return {"status": "ok", "providers": new_providers}


@admin_router.post("/models/providers/{name}/models")
async def add_model(
    name: str,
    body: ModelIn,
    _admin: User = Depends(admin_required),
):
    data = _read_json(_MODELS_PATH, {"providers": []})
    provider = next(
        (p for p in data.get("providers", []) if p.get("name") == name), None
    )
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{name}' not found")
    models = provider.setdefault("models", [])
    if any(m.get("id") == body.id for m in models):
        raise HTTPException(status_code=400, detail=f"Model '{body.id}' already exists")
    models.append(body.model_dump())
    _write_json(_MODELS_PATH, data)
    return {"status": "ok", "providers": data.get("providers", [])}


@admin_router.put("/models/providers/{name}/models/{model_id}")
async def update_model(
    name: str,
    model_id: str,
    body: ModelIn,
    _admin: User = Depends(admin_required),
):
    data = _read_json(_MODELS_PATH, {"providers": []})
    provider = next(
        (p for p in data.get("providers", []) if p.get("name") == name), None
    )
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{name}' not found")
    models = provider.setdefault("models", [])
    for i, m in enumerate(models):
        if m.get("id") == model_id:
            models[i] = body.model_dump()
            _write_json(_MODELS_PATH, data)
            return {"status": "ok", "providers": data.get("providers", [])}
    raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")


@admin_router.delete("/models/providers/{name}/models/{model_id}")
async def delete_model(
    name: str,
    model_id: str,
    _admin: User = Depends(admin_required),
):
    data = _read_json(_MODELS_PATH, {"providers": []})
    provider = next(
        (p for p in data.get("providers", []) if p.get("name") == name), None
    )
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{name}' not found")
    models = provider.setdefault("models", [])
    new_models = [m for m in models if m.get("id") != model_id]
    if len(new_models) == len(models):
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    provider["models"] = new_models
    _write_json(_MODELS_PATH, data)
    return {"status": "ok", "providers": data.get("providers", [])}
