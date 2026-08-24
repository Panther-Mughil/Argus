from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from contextlib import asynccontextmanager

from .db.database import engine, Base, get_db
from .db.models import Challenge, ChallengeStatus

# Initialize database tables on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # Create tables (In production, use Alembic for migrations)
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Argus", lifespan=lifespan)

# Allow CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

from .agent.loop import AgentLoop
from backend.storage import (
    list_files,
    save_upload,
    sanitize_filename,
    delete_challenge_files,
    OversizeError,
)

CHALLENGE_CATEGORIES = {"Web", "Pwn", "Reverse Engineering", "Cryptography", "Forensics", "OSINT", "Misc", "Steganography", "Programming", "Hardware", "Cloud", "Blockchain", "Mobile", "Network", "AI/ML"}

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

@app.post("/api/challenges")
async def create_challenge(title: str, description: str, category: str, db: AsyncSession = Depends(get_db)):
    if category not in CHALLENGE_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {', '.join(sorted(CHALLENGE_CATEGORIES))}")
    new_challenge = Challenge(
        title=title,
        description=description,
        category=category,
        status=ChallengeStatus.QUEUED
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
    # Note: AgentLoop is imported instead of MockAgent now
    agent = AgentLoop(challenge_id, manager, challenge.title, challenge.description or "")
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
        
    challenge.status = ChallengeStatus.FAILED # Or some other status for manually stopped
    await db.commit()
    
    return {"status": "Agent stopped"}

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

@app.websocket("/api/ws/challenges/{challenge_id}")
async def websocket_endpoint(websocket: WebSocket, challenge_id: int):
    await manager.connect(websocket, challenge_id)
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
                await active_agents[challenge_id].inject_intervention(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket, challenge_id)
