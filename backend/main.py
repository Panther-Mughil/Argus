from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
# pi-lens-ignore: python-hallucinated-import — sqlalchemy exposes `text` and `delete`; rule is a false positive.
from sqlalchemy import text, delete
from contextlib import asynccontextmanager

from .db.database import engine, Base, get_db
from .db.models import Challenge, ChallengeStatus

# Adds FLAG_PROPOSED to the native Postgres enum if the DB was created before
# that value existed. Idempotent on Postgres 12+ (compose uses postgres:15).
_ENUM_MIGRATION_SQL = text(
    """
    DO $$
    DECLARE
      enum_name text;
    BEGIN
      SELECT pg_type.typname INTO enum_name
      FROM pg_attribute
      JOIN pg_type ON pg_type.oid = pg_attribute.atttypid
      WHERE pg_attribute.attrelid = 'challenges'::regclass
        AND pg_attribute.attname = 'status';
      IF enum_name IS NOT NULL THEN
        EXECUTE format('ALTER TYPE %I ADD VALUE IF NOT EXISTS ''FLAG_PROPOSED''', enum_name);
      END IF;
    END $$;
    """
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # Create tables (In production, use Alembic for migrations)
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with engine.connect() as conn:
            # pi-lens-ignore: python-sql-injection — enum_name is read from the
            # Postgres system catalog (pg_type.typname), not user input, and is
            # quoted with the %I identifier specifier. ALTER TYPE ... ADD VALUE
            # cannot take a bound type name, so %I quoting is the safe form.
            await conn.execute(_ENUM_MIGRATION_SQL)
            # Static DDL (no user input): add the proposed_flag column if absent.
            await conn.exec_driver_sql(
                "ALTER TABLE challenges ADD COLUMN IF NOT EXISTS proposed_flag VARCHAR"
            )
            await conn.commit()
    except Exception as exc:
        # Non-fatal: only matters for DBs created before FLAG_PROPOSED existed.
        print(f"Enum migration skipped: {exc}")
    yield


app = FastAPI(title="Argus", lifespan=lifespan)

# Allow CORS for local frontend development (same-origin serving is the norm).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import HTMLResponse
from pathlib import Path
import os
import json
import asyncio
from fastapi import WebSocket, WebSocketDisconnect, UploadFile, File
from typing import Dict, List
from pydantic import BaseModel

from .agent.loop import AgentLoop
from .agent.llm import model_list, default_model, known_model_ids
from backend.storage import (
    list_files,
    save_upload,
    sanitize_filename,
    delete_challenge_files,
    OversizeError,
)

CHALLENGE_CATEGORIES = {"Web", "Pwn", "Reverse Engineering", "Cryptography", "Forensics", "OSINT", "Misc", "Steganography", "Programming", "Hardware", "Cloud", "Blockchain", "Mobile", "Network", "AI/ML"}

# Event type -> tailwind text color, used when replaying persisted events.
_EVENT_COLORS = {
    "PLAN": "text-lavender",
    "ACTION": "text-sand",
    "OBSERVATION": "text-cream",
    "HYPOTHESIS": "text-iris",
    "SYSTEM": "text-mint",
}

class ConnectionManager:
    def __init__(self):
        # Maps challenge_id to a list of connected WebSockets
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, challenge_id: int):
        await websocket.accept()
        if challenge_id not in self.active_connections:
            self.active_connections[challenge_id] = []
        self.active_connections[challenge_id].append(websocket)

    def disconnect(self, websocket: WebSocket, challenge_id: int):
        if challenge_id in self.active_connections:
            self.active_connections[challenge_id].remove(websocket)

    async def broadcast_to_challenge(self, challenge_id: int, message: dict):
        if challenge_id in self.active_connections:
            for connection in self.active_connections[challenge_id]:
                await connection.send_text(json.dumps(message))

manager = ConnectionManager()
active_agents: Dict[int, AgentLoop] = {}

# Static frontend files served by the backend (same-origin)
FRONTEND_DIR = Path(os.path.dirname(os.path.dirname(__file__))) / "frontend"

@app.get("/")
async def serve_frontend():
    try:
        return HTMLResponse(content=(FRONTEND_DIR / "index.html").read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="index.html not found") from e

@app.get("/favicon.svg")
async def serve_favicon():
    try:
        return HTMLResponse(
            content=(FRONTEND_DIR / "favicon.svg").read_text(encoding="utf-8"),
            media_type="image/svg+xml",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="favicon.svg not found") from e

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Argus Backend is running."}

@app.get("/api/challenges")
async def get_challenges(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Challenge))
    challenges = result.scalars().all()
    return challenges

@app.get("/api/models")
async def get_models():
    """List available models from the registry (drives the UI dropdown)."""
    return {"models": model_list(), "default_model": default_model()}


class _ModelChoice(BaseModel):
    model: str


@app.post("/api/challenges/{challenge_id}/model")
async def set_challenge_model(challenge_id: int, choice: _ModelChoice, db: AsyncSession = Depends(get_db)):
    """Set the model used for a challenge's next agent run."""
    challenge = await db.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    if choice.model not in known_model_ids():
        raise HTTPException(status_code=400, detail=f"Unknown model '{choice.model}'")
    challenge.assigned_model = choice.model
    await db.commit()
    return {"status": "ok", "assigned_model": challenge.assigned_model}


@app.post("/api/challenges")
async def create_challenge(title: str, description: str, category: str, assigned_model: str = "", db: AsyncSession = Depends(get_db)):
    if category not in CHALLENGE_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {', '.join(sorted(CHALLENGE_CATEGORIES))}")
    if assigned_model and assigned_model not in known_model_ids():
        raise HTTPException(status_code=400, detail=f"Unknown model '{assigned_model}'")
    new_challenge = Challenge(
        title=title,
        description=description,
        category=category,
        status=ChallengeStatus.QUEUED,
        assigned_model=assigned_model or None,
    )
    db.add(new_challenge)
    await db.commit()
    await db.refresh(new_challenge)
    return new_challenge

@app.post("/api/challenges/{challenge_id}/start")
async def start_agent(challenge_id: int, db: AsyncSession = Depends(get_db)):
    challenge = await db.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    challenge.status = ChallengeStatus.IN_PROGRESS
    await db.commit()
    
    # Start the real agent in the background
    agent = AgentLoop(
        challenge_id,
        manager,
        challenge.title,
        challenge.description or "",
        challenge.category or "",
        challenge.assigned_model or "",
    )
    active_agents[challenge_id] = agent
    asyncio.create_task(agent.run())
    
    return {"status": "Agent started"}

@app.post("/api/challenges/{challenge_id}/stop")
async def stop_agent(challenge_id: int, db: AsyncSession = Depends(get_db)):
    challenge = await db.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    if challenge_id in active_agents:
        active_agents[challenge_id].stop()
        del active_agents[challenge_id]
        
    challenge.status = ChallengeStatus.FAILED
    await db.commit()
    
    return {"status": "Agent stopped"}


@app.post("/api/challenges/{challenge_id}/restart")
async def restart_agent(challenge_id: int, db: AsyncSession = Depends(get_db)):
    """Re-run a challenge's agent completely fresh, without deleting the challenge
    or re-uploading its files.

    Stops any running agent, clears the event log so the UI terminal starts blank,
    resets status to IN_PROGRESS, and spawns a new AgentLoop (which re-stages
    originals/ + work/ from the host on start, giving a clean environment).
    """
    challenge = await db.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Detach + stop any running agent. The guard in AgentLoop.finally ("is self")
    # prevents a stale run from removing the fresh agent from active_agents.
    old = active_agents.pop(challenge_id, None)
    if old is not None:
        old.stop()

    # Clear the event log so the terminal starts blank for the fresh run.
    try:
        from .db.database import AsyncSessionLocal
        from .db.models import EventLog
        async with AsyncSessionLocal() as session:
            await session.execute(delete(EventLog).where(EventLog.challenge_id == challenge_id))
            await session.commit()
    except Exception as exc:
        print(f"Restart: failed to clear event log for {challenge_id}: {exc}")

    challenge.status = ChallengeStatus.IN_PROGRESS
    await db.commit()

    agent = AgentLoop(
        challenge_id,
        manager,
        challenge.title,
        challenge.description or "",
        challenge.category or "",
        challenge.assigned_model or "",
    )
    active_agents[challenge_id] = agent
    asyncio.create_task(agent.run())

    return {"status": "Agent restarted"}

@app.post("/api/challenges/{challenge_id}/solved")
async def mark_solved(challenge_id: int, db: AsyncSession = Depends(get_db)):
    """Mark a challenge solved after a human confirms the proposed flag."""
    challenge = await db.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    challenge.status = ChallengeStatus.SOLVED
    await db.commit()

    if challenge_id in active_agents:
        active_agents[challenge_id].stop()
        del active_agents[challenge_id]

    return {"status": "Marked solved"}

@app.post("/api/challenges/{challenge_id}/files", status_code=201)
async def upload_challenge_file(
    challenge_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file attached to a challenge.

    Stored locally under ``backend/artifacts/{challenge_id}/``.  The upload
    is streamed to disk in chunks; if it exceeds ``ARGUS_MAX_UPLOAD_SIZE_MB``
    a ``413`` is returned and no partial file is left behind.
    """
    challenge = await db.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    filename = file.filename or ""
    try:
        safe_name = sanitize_filename(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")

    try:
        # Files are large (up to the configured cap); read in a worker
        # thread so we don't block the event loop.
        path = await asyncio.to_thread(save_upload, challenge_id, safe_name, file.file)
    except OversizeError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to store file: {exc}")

    return {"filename": path.name, "size": path.stat().st_size}

@app.get("/api/challenges/{challenge_id}/files")
async def list_challenge_files(challenge_id: int, db: AsyncSession = Depends(get_db)):
    """List the uploaded files for a challenge."""
    challenge = await db.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    files = list_files(challenge_id)
    return {"files": [{"filename": name, "size": size} for name, size in files]}

def _cleanup_remote_workspace(challenge_id: int) -> None:
    """Best-effort removal of the container workspace dir for a challenge."""
    from worker.sandbox import SandboxManager
    SandboxManager().remove_remote_dir(f"/workspace/{challenge_id}")


@app.delete("/api/challenges/{challenge_id}")
async def delete_challenge(challenge_id: int, db: AsyncSession = Depends(get_db)):
    challenge = await db.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    # If agent is running, stop it first
    if challenge_id in active_agents:
        active_agents[challenge_id].stop()
        del active_agents[challenge_id]
        
    await db.delete(challenge)
    await db.commit()

    # Clean up uploaded files: remove the local artifacts dir and
    # best-effort remove the container workspace dir.
    delete_challenge_files(challenge_id)
    try:
        # SSH remove is blocking; run it off the event loop.
        await asyncio.to_thread(_cleanup_remote_workspace, challenge_id)
    except Exception as exc:
        # Non-fatal: cleanup inside the container is best-effort.
        print(f"Failed to clean up container workspace for challenge {challenge_id}: {exc}")
    
    return {"status": "Challenge deleted"}

async def _replay_events(websocket: WebSocket, challenge_id: int):
    """Send recent persisted events to a freshly-connected client."""
    from .db.database import AsyncSessionLocal
    from .db.models import EventLog

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(EventLog)
                .where(EventLog.challenge_id == challenge_id)
                .order_by(EventLog.created_at.asc())
                .limit(200)
            )
            events = result.scalars().all()
    except Exception as exc:
        print(f"Event replay failed: {exc}")
        return

    for event in events:
        etype = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
        ts = event.created_at.strftime("%H:%M:%S") if event.created_at else ""
        await websocket.send_text(json.dumps({
            "type": etype,
            "content": event.content,
            "timestamp": ts,
            "color": _EVENT_COLORS.get(etype, "text-cream"),
        }))

@app.websocket("/api/ws/challenges/{challenge_id}")
async def websocket_endpoint(websocket: WebSocket, challenge_id: int):
    await manager.connect(websocket, challenge_id)
    await _replay_events(websocket, challenge_id)
    try:
        while True:
            # Wait for any messages from the client (e.g. human intervention)
            data = await websocket.receive_text()
            
            # Broadcast to UI
            msg = {
                "type": "USER_INTERVENTION",
                "content": data,
                "timestamp": "now",
                "color": "text-lavender"
            }
            await manager.broadcast_to_challenge(challenge_id, msg)
            
            # Inject into active agent context
            if challenge_id in active_agents:
                agent = active_agents[challenge_id]
                if agent.paused:
                    # The agent proposed a flag and is awaiting verification;
                    # this message is the human's verdict — resume the loop.
                    agent.inject_intervention(data)
                    await agent.reject_flag()
                else:
                    agent.inject_intervention(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket, challenge_id)
