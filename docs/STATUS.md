# Argus — Project Status & Activity Log

> **Status as of:** 2026-08-24 16:45 IST
> **Owner:** Student project — AI-assisted CTF challenge-solving platform (authorized/lab scope only, per `AGENTS.md`).
> **Companion docs:** `docs/PRD.md` (product requirements), `docs/Design-Example.md` (Dashlane theme), `docs/plans/REQ-001-Overseer.md` (master gap analysis & roadmap).

---

## 1. What Argus Is

Argus is a **local-first**, team-oriented autonomous CTF investigation platform. A team creates a challenge (description + optional files + optional permitted URLs), assigns an AI agent, and the system provisions an isolated Linux environment where the agent runs structured tools (`execute_command`, `submit_flag`) while streaming its reasoning and actions to a shared real-time web UI. Teammates can intervene live.

Core philosophy (unchanged): **no cloud buckets**, all local; **one capable agent** over multi-agent debates; **custom async loop** over a heavyweight agent framework; disposable **rootless Podman** containers as the original sandbox model.

---

## 2. Current State at a Glance

| Area | Status | Detail |
| ------ | -------- | -------- |
| Backend API (FastAPI) | ✅ Working | `/`, `/favicon.svg`, `/health`, challenge CRUD, agent start/stop/delete, WebSocket streaming. CORS `*` (needs tightening). |
| Database (PostgreSQL) | ✅ Working | SQLAlchemy 2.0 async (`async_sessionmaker`). Tables auto-created on startup (`create_all`, no Alembic). Models: Team, User, CtfSession, Challenge, EventLog. |
| LLM client | ✅ Working | One local OpenAI-compatible provider (Onyx @ `10.0.2.2:12057/v1`), model `Qwen3.6-35B-A3B` (from `backend/models.json`). |
| Agent loop | ✅ Working | Real loop; tools `execute_command` + `submit_flag`; emits PLAN/ACTION/OBSERVATION/HYPOTHESIS/SYSTEM; model scheduler concurrency lock; human intervention injector. **Connects to the shared `kali-forensics` container via SSH.** |
| Sandbox transport | 🔁 **Changed to SSH** | `worker/sandbox.py` rewritten from the Podman client to **paramiko**. Never creates/stops containers; opens/closes SSH to the always-on `kali-forensics` container. |
| Worker Daemon | ⚠️ **Stub** | `worker/daemon.py` loops on `ping()` + sleep. Stale wording still says "Podman." No task polling from the central app. |
| Frontend (Vue 3 + Tailwind) | ✅ Working | Challenge list, create form, live terminal, human intervention input. Dashlane theme applied. Agent/model banner **hardcoded**. |
| File upload / streaming | ❌ Not built | No upload endpoint, no challenge artifact storage, no streaming to container. |
| Event persistence & replay | ❌ Not built | `EventLog` never written; events are WebSocket-only and lost on refresh. |
| Flag validation | ❌ Not built | `challenge.flag` exists but is never set/validated; `submit_flag` always "succeeds." |
| Model selection | ❌ Not built | `assigned_model` column unused; model hardcoded to `Qwen3.6-35B-A3B`. |

**Reading:** The app is functional end-to-end *for a single challenge with a single hardcoded model and no flag/files*, now running its agent inside the shared Kali container over SSH. Almost the entire roadmap in `REQ-001` is **not yet implemented** — the current uncommitted work is a prerequisite milestone (SSH connect), not the roadmap work itself.

---

## 3. What Has Happened — Activity Log

### 3.1 Committed history (`main`, oldest → newest)

| Commit | Type | Summary |
| -------- | ------ | --------- |
| `8f6c83c` | init | Initial commit. |
| `fcf2782` | feat | Real agent loop, WebSockets, and Mac-compatible setup. |
| `8c80953` | chore | Universal `.gitignore` / `.gitattributes` (LF endings, python linguist stats). |
| `2dc2cdf` | feat | Custom Argus cyber-eye SVG logo, wired into frontend header + favicon. |
| `725bf2b` | style | Tightly cropped favicon `viewBox` to increase apparent size. |
| `f4596a0` | feat(ui) | Adopted Dashlane-inspired theme across UI, favicon, agent colors. |
| `8413615` | fix(ui) | Aligned action-button radius with cards; ignore `docs/plans`. |

### 3.2 Uncommitted work — "Wire agent to the Kali-Forensics container (direct SSH)"

This is the **approved plan** (`kali-container-direct-ssh-connect`, dated 2026-08-23) — connecting the agent loop to *the one* always-on Kafka... (typo in draft — **Kali-forensics** container) via direct SSH, replacing the prior per-challenge Podman sandbox creation. It is in the working tree but **not committed**.

**Modified:**

| File | Change |
| ------ | -------- |
| `worker/sandbox.py` | Rewrote transport to **paramiko** direct SSH. `connect()` / `ping()` / `execute_command(container_id, cmd)` / `stop_sandbox()`→`disconnect()`. Never stops/creates the container. |
| `backend/agent/loop.py` | Replaced `create_sandbox`/`stop_sandbox` with `ensure_connected()`/`disconnect()`; runs commands via `sandbox.execute_command("kali-forensics", cmd)`. |
| `backend/agent/llm.py` | `pathlib` config load + `Optional` typings + explicit error handling. |
| `backend/db/database.py` | SQLAlchemy 2.0 async (`async_sessionmaker`); added module docstring. |
| `backend/db/models.py` | SQLAlchemy 2.0 typed annotations (`Mapped`/`mapped_column`, `Optional`/`List`); category comment. |
| `backend/main.py` | Pathlib-based static serving with `FileNotFoundError` → 404; `description or ""` guard. |
| `requirements.txt` | Added `paramiko==5.0.0`. |
| `.gitignore` | Added `keys/` (accidentally ×3) and `keys-ops/`. |
| `docs/Design-Example.md` | Markdown formatting/tidy only (no content change). |

**New (untracked):**

| File | Purpose |
| ------ | --------- |
| `backend/config.py` | `pydantic-settings` `Settings` reading project `.env` (defaults: host `10.0.2.6`, port `2222`, user `root`, key `keys/argus`, cmd timeout `120`). |
| `.env` | gitignored — `ARGUS_CONTAINER_HOST/PORT/USER/SSH_KEY`. |
| `keys/argus`, `keys/argus.pub` | gitignored — dedicated ed25519 keypair (app private key; public key installed in container). |
| `keys-ops/setup.sh` | gitignored — server-side ops: starts `kali-forensics`, configures sshd + injects pubkey. |
| `.gitleaks.toml` | Secret-scanning config (dev tooling). |
| `pyrightconfig.json` | Type-checker config (dev tooling). |
| `.pi/` | Agent/session working artifacts (gitignored). |

**Status of this milestone:** Implemented in code. **Not yet verified end-to-end** — the plan's acceptance criteria (direct `ssh -i keys/argus root@10.0.2.6 -p 2222` round-trip, container auto-restart, app-side "no podman exec", agent connects & runs commands) are recorded in the plan but not confirmed in this repo/session. The `WorkerDaemon` stub still *describes* Podman, which is now stale wording.

---

## 4. Implementation Status vs. Gap-Analysis Roadmap (`REQ-001`)

### Phase 1 — Solidify the MVP

| # | Gap | Status |
| --- | ----- | -------- |
| 1 | `POST /api/challenges` → JSON body + Pydantic; add `flag` + `assigned_model` to create/update | ❌ Not done (still query params; no flag/model) |
| 2 | Persist agent events to `EventLog`, replay to reconnecting UI | ❌ Not done |
| 3 | Validate `submit_flag` against `challenge.flag`; set terminal SOLVED/FAILED | ❌ Not done (always SOLVED on agent finish) |
| 4 | Per-challenge model selection wiring `assigned_model` | ❌ Not done (hardcoded) |
| 5 | `execute_command` timeout + `read_file`/`write_file` tools | ⚠️ Partial — timeout exists via `ARGUS_CONTAINER_CMD_TIMEOUT` (120s); no `read_file`/`write_file` tools |
| 6 | Challenge file upload + streaming to worker/container | ❌ Not done |

### Phase 2 — Worker Daemon & distribution

| # | Gap | Status |
|---|-----|--------|
| 1 | Worker Daemon task polling (HTTP/WS) | ❌ Not done |
| 2 | Move sandbox lifecycle to worker | ❌ Not done (agent runs in-process in backend) |
| 3 | Enforce network scope via `target_urls`; `--read-only` + `tmpfs` | ❌ Not done (irrelevant now — SSH into shared container) |

### Phase 3 — Teams / Sessions / Replay

All ❌ Not done (`CtfSession`, `Team`, `User` models exist but unused).

### Phase 4 — Hardening & Ops

| # | Gap | Status |
|---|-----|--------|
| 1 | Env-based config, tighten CORS, add tests | ⚠️ Partial — app config is now env-driven (`backend/config.py`), but DB URL is still **hardcoded** in `database.py`; CORS still `*`; no tests |

---

## 5. Known Issues / Tech Debt / Inconsistencies

- **`submit_flag` is a no-op:** always reports success; the loop marks the challenge `SOLVED` on *any* agent completion (even a manual stop or error finish). Flag never stored.
- **Events not persisted:** `EventLog` is written by nothing; history resets on reconnect. (Frontend directly calls `logs.value = []` on challenge switch.)
- **`worker/daemon.py` stale wording** — "connect to Podman socket" / "podman" references while `SandboxManager.ping()` is now SSH.
- **Missed normalization:** `loop.py` still hardcodes `self.model = "Qwen3.6-35B-A3B"`; `models.json` only has the single Onyx provider.
- **`.gitignore` duplicate:** `keys/` appears 3× (lines 63–65); harmless but sloppy.
- **DB URL hardcoded** (`postgresql+asyncpg://argus:argus_password@localhost:5432/argus_db`) — not moved to `.env`/settings (Phase 4).
- **CORS** `allow_origins=["*"]` with `allow_credentials=True` (should be scoped).
- **No tests** of any kind (unit/integration).
- **Frontend banner** "Primary Solver / Qwen-3.6-35B" is hardcoded; not driven by `assigned_model`.

---

## 6. Recommended Next Steps

The SSH-connect milestone is only a foundational prerequisite. The highest-value next slice is **Phase 1**, which unlocks real CTF solving:

1. **Flag lifecycle** — accept `flag` in challenge create; validate `submit_flag` vs stored flag; set proper terminal status (SOLVED / FAILED). *(Small, high impact.)*
2. **Pydantic request bodies** — refactor `POST /api/challenges` to a JSON body (`ChallengeCreate`) with `flag` + `assigned_model`.
3. **Per-challenge model selection** — wire `assigned_model` into the loop + a model dropdown in the UI.
4. **Event persistence + replay** — write `EventLog` on emit; replay recent events on WS connect; add history view.
5. **`read_file`/`write_file` tools** — add to `TOOLS` and the sandbox executor (SSH `cat`/heredoc).
6. **Worker Daemon distribution** (Phase 2) — move agent execution to the daemon over HTTP/WS.

Before building, **commit the current uncommitted SSH work** as a checkpoint so the new milestone starts from a clean, known baseline.

---

## 7. How Things Work Right Now (data flow)

1. Frontend creates a challenge via `POST /api/challenges` (query params) → stored in Postgres (`status=QUEUED`).
2. User clicks **Start Agent** → `POST /api/challenges/{id}/start` → status `IN_PROGRESS`, `AgentLoop.run()` spawned as an asyncio task.
3. Loop opens an SSH connection to `kali-forensics` (`SandboxManager.connect()` via paramiko, config from `.env`), acquires the model semaphore, calls the local Onyx LLM endpoint, and streams PLAN/ACTION/OBSERVATION/HYPOTHESIS/SYSTEM over WebSocket.
4. Tool calls (`execute_command`) are exec'd **inside the container over SSH**; output is truncated to ~3000 chars and fed back into the LLM context.
5. `submit_flag` or error/stop ends the run; loop closes the SSH connection (never the container) and marks the challenge (currently always `SOLVED` if it was `IN_PROGRESS`).
6. UI polls `/api/challenges` every 5s for status and reflects events on the live terminal.

---

## 8. Environment / Verification Notes

- **Config:** `.env` at project root (gitignored); `backend/config.py` supplies defaults. SSH key: `keys/argus`.
- **Container:** shared `kali-forensics` (Kali Rolling 2026.3), published to `10.0.2.6:2222` → container port 22, `--restart unless-stopped`. Server-side setup script: `keys-ops/setup.sh`.
- **LLM:** local OpenAI-compatible endpoint at `10.0.2.2:12057/v1`, model `Qwen3.6-35B-A3B`.
- **DB:** containerized Postgres `argus_db` (`argus:argus_password`).
- **Run:** `setup.sh` (init infra) → `start.sh` (start server/db/worker). `cleanup.sh` tears down. `docker-compose.yml` provides an alternative.

> ⚠️ The uncommitted code has **not** been run/verified this cycle. Before treating this as a stable baseline, run the app and confirm the SSH connect + agent loop path end-to-end.
