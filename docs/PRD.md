# PRD — ARGUS

## Autonomous Multi-Agent CTF Investigation Platform

**Status:** Architecture Definition
**Project codename:** Argus
**Primary interface:** Web UI (Real-time collaborative)
**Primary execution model:** Local-first distributed workers
**Core isolation:** Disposable rootless Podman containers
**Database:** Local PostgreSQL (Containerized)

---

# 1. Executive Summary

Argus is a team-oriented, local-first autonomous security investigation platform designed for authorized CTFs and intentionally vulnerable security labs.

A team provides a challenge consisting of:

- A natural-language description
- Files, archives, PCAPs, binaries, memory dumps
- Fully permissioned web URLs or targets

Argus allows team members to assign an AI agent to a challenge. The system provisions an isolated, ephemeral Linux environment (sandbox) on a designated worker host (Linux or Windows/WSL) and provides the agent with access to appropriate CTF tooling.

Argus ensures that agents use a structured tool interface to investigate, and streams their actions, hypotheses, and tool outputs in real time to the shared Web UI. Teammates can watch the agent's progress and intervene if the agent begins to hallucinate or gets sidetracked.

Argus strictly enforces a local-only infrastructure philosophy. No cloud buckets are used; all files, state, and coordination remain on the team's local network.

---

# 2. Product Vision

Build a platform that serves as a shared command center for human-AI CTF collaboration.
The team should be able to:

- See which challenges are currently being worked on by an agent to prevent duplicated effort.
- Observe real-time terminal outputs and agent reasoning.
- Pause or intervene in an agent's execution.
- Allocate shared local LLM resources (e.g., Qwen 35B) efficiently through a queuing system.
- Ensure that agents cannot break out of their sandbox or access unauthorized network resources outside the challenge scope.

---

# 3. Architecture

## 3.1 Components

1. **Central Web Application (FastAPI):** Orchestrates sessions, manages the PostgreSQL database, serves the Web UI, handles WebSocket real-time updates, and streams files.
2. **Web UI:** A real-time collaborative frontend dashboard.
3. **Database (PostgreSQL):** Stores sessions, challenges, agent state, tool execution logs, and artifacts. Runs entirely locally via Podman/Docker compose.
4. **Model Scheduler:** Manages access to local inference endpoints (like `10.0.2.2:12057`), ensuring concurrency limits are respected.
5. **Worker Daemon:** A lightweight Python agent running on sandbox hosts (e.g., `10.0.2.6`). It receives tasks via HTTP/WebSockets from the central app, pulls files locally, and manages the Podman lifecycle for the challenge container.

## 3.2 Agent Framework

Argus utilizes a **Custom Async Loop** rather than a bloated agent framework. This ensures:

- Strict control over the prompt format and tool schema.
- Native support for pausing, resuming, and human intervention.
- Granular event emission (Action, Observation, Hypothesis, Tool Start/End) required for the real-time UI.

## 3.3 File Distribution

To comply with the strict "no cloud bucket" rule, the central FastAPI server acts as the file repository. When a Worker Daemon starts a sandbox, it streams the required challenge files directly from the FastAPI server over HTTP and mounts them into the rootless container.

---

# 4. Agent Roles & Collaboration

**Primary Solver Agent:** A highly capable agent equipped with categorized tools (Forensics, Pwn, Web, Crypto, etc.). We favor one capable agent over complex multi-agent debate structures.

**Human Intervention:** Teammates can view the agent's live stream. If the agent hallucinates or goes down a rabbit hole, a user can hit "Intervene", supply a manual hint or correction, or manually execute a terminal command in the sandbox, and then return control to the agent.

---

# 5. Sandbox & Security Boundary

- **Runtimes:** Podman (Rootless). Support for native Linux and Windows/WSL hosts.
- **Networking:** Containers are isolated. By default, they do not have broad internet access. If a challenge provides explicit URLs, the container network is configured (or proxy-restricted) to allow access only to those specific URLs, ensuring the agent cannot autonomously attack arbitrary targets.
- **Environment:** Disposable Kali Linux (or similar CTF-tailored) base images, launched with `--read-only` root filesystems and `tmpfs` mounts for speed and security.

---

# 6. Tool Execution

Agents do not get raw interactive bash shells. They use structured tool APIs:

- `execute_command(command, timeout)`
- `read_file(path)`
- `write_file(path, content)`
- `inspect_network()`

Every tool execution is audited, timed, and saved to the PostgreSQL database for replay and reporting.

---

# 7. Deployment & Operations

To prevent host clutter, Argus includes three scripts:

- `setup.sh`: Builds necessary container images, initializes PostgreSQL and Redis (if needed) containers.
- `start.sh`: Starts the central web server, database, and local worker daemons.
- `cleanup.sh`: Tears down the infrastructure and removes ephemeral containers.

---

# 8. MVP Scope (Phase 1)

1. **Central Server & Local DB:** FastAPI + containerized PostgreSQL.
2. **Web UI:** Challenge list, agent assignment, and live event stream.
3. **Worker Daemon:** SSH-accessible or locally run Python daemon capable of spawning a Podman container.
4. **Basic Agent Loop:** Capable of tool execution, pausing, and human intervention.
5. **Local Model Support:** Integration with OpenAI-compatible local endpoints (e.g., Qwen 35B) with a simple concurrency lock.
6. **File Streaming:** Ability to upload a challenge file and stream it to the worker.
7. **Scripts:** `setup.sh`, `start.sh`, `cleanup.sh`.

---

# 9. Roadmap / Features to Add Next

This section is the forward-looking backlog, grounded in the current implementation status
(`docs/STATUS.md`) and gap analysis (`docs/plans/REQ-001-Overseer.md`). Items are prioritized
by value vs. risk. The headline new feature — **free web-based AI chatbot inference** — is an
explicit team request and is listed first.

## 9.0 Free Web-Based AI Chatbot Inference (FREE MODELS) — Top Priority

**Problem.** Argus currently talks to exactly one local OpenAI-compatible endpoint
(`backend/models.json`, provider `Onyx` at `10.0.2.2:12057/v1`, model `gpt-oss-20B`). This is
hardcoded in `backend/agent/llm.py` (`BASE_URL = onyx_provider["base_url"]`), the agent loop
(`self.model = settings.ARGUS_MODEL or default_model()`) and `backend/agent/scheduler.py`. A
student without a local GPU/server to host a Qwen-class model simply cannot run an agent.

**Goal.** Let a challenge's agent use **free web-based AI chatbot services** for inference —
OpenRouter free models, Google Gemini free tier, Groq free tier, Mistral free, etc. — in
addition to (or instead of) the local model, while preserving Argus' local-first, no-cloud
philosophy (free providers are **opt-in**; local inference stays the default).

**Requirements / work items:**

| Area | Change | Files |
| ------ | ------ | ------ |
| Provider registry | Generalize `models.json` to declare multiple providers: keep `api_type: openai-completions` for OpenAI-compatible free gateways (OpenRouter/Groq/…), and add adapters for non-OpenAI providers (e.g. `anthropic`, `google-gemini`) or route everything through an OpenAI-compatible gateway where possible. | `backend/models.json` |
| Remove hardcoded Onyx | Replace the `next(p for p in ... if p["name"] == "Onyx")` lookups in `llm.py` and `scheduler.py` with a config-driven registry keyed by model id (look up the provider that owns the model, its `api_type`, `base_url`, `api_key`, `concurrency`). | `backend/agent/llm.py`, `backend/agent/scheduler.py` |
| Model list endpoint | Add `GET /api/models` returning the available models with provider, free/paid tag, and concurrency, so the UI can render a dropdown instead of the hardcoded banner. | `backend/main.py` |
| Per-challenge model selection | Wire `challenge.assigned_model` (column already exists, currently unused) into `AgentLoop` on start; fall back to the first configured model when unset. | `backend/agent/loop.py`, `backend/main.py` |
| Frontend model dropdown | Replace the hardcoded `Primary Solver / GPT-OSS-20B` block with a model `<select>` bound to the selected challenge; show provider + free/paid tag. Offer a default model and a per-challenge override. | `frontend/index.html` |
| Secrets | Store provider API keys in `.env` (gitignored) via `backend/config.py`; never commit keys. Follow the existing `ARGUS_*` settings pattern; add `.env.example` for documentation. | `backend/config.py`, `.env.example` |
| Scheduler for web providers | Keep per-model concurrency semaphores for web providers too (free tiers are typically rate-limited / low concurrency). | `backend/agent/scheduler.py` |
| Graceful fallback | If a provider is unreachable, rate-limited, or returns an error, emit a clear `SYSTEM` event and (optionally) retry or fall back to another configured model instead of failing the run. | `backend/agent/loop.py`, `backend/agent/llm.py` |

**Out of scope / invariants:** No cloud buckets or remote state (PRD §1); no new heavyweight
dependencies unless justified; the custom async agent loop is preserved; the local model stays
the default. This feature is the enabler for per-challenge model choice and is the natural next
slice after the current single-provider MVP.

## 9.1 Pydantic Request Bodies + Model/Flag on Create

Refactor `POST /api/challenges` (currently `title`/`description`/`category` **query params**) to
accept a JSON body via a Pydantic schema (`ChallengeCreate`), and expose `flag` and
`assigned_model` on create/update. This is the plumbing that lets a teammate set the expected
flag and pick a model when creating a challenge, and it composes directly with §9.0.

**Files:** `backend/main.py`, `backend/schemas.py` (new or inline).

## 9.2 Worker Daemon Distribution (Phase 2)

Today the agent loop runs **in-process** in the FastAPI backend; `worker/daemon.py` is a stub
that only pings and sleeps, and its docstring still says "Podman". Move sandbox lifecycle and
agent execution to the worker daemon by having it pull tasks over HTTP/WebSocket from the
central app. Enforce network scope via `challenge.target_urls` and exercise `--read-only` +
`tmpfs` isolation on the sandbox container. (Unblocks true multi-host teams and removes the
interprocess coupling.)

**Files:** `worker/daemon.py`, `worker/sandbox.py`, `backend/agent/loop.py`, `backend/main.py`.

## 9.3 Teams / Sessions / Replay (Phase 3)

The `Team`, `User`, and `CtfSession` models exist but are unused. Add session + team APIs and a
UI switcher, and add an event-log inspection/replay view with search/filter. The `EventLog`
persistence and replay-on-connect are already in place, so this is primarily surfacing the data
and enabling team coordination.

**Files:** `backend/main.py`, `backend/db/models.py` (if schema changes), `frontend/index.html`.

## 9.4 Hardening & Ops (Phase 4)

- Verify the SSH-connect/agent loop path end-to-end (the current uncommitted SSH work has not
  been run this cycle).
- Add unit/integration tests for the API and the agent loop; add a CI-friendly smoke script.
- Tighten secrets handling (`.env` already gitignored; confirm no keys land in `models.json`).
- Remove the duplicate `keys/` entries in `.gitignore` (currently appears 3×) and reconcile
  `setup.sh`/`start.sh`/`cleanup.sh` with `docker-compose.yml`.

**Files:** `tests/`, `backend/db/database.py`, `.gitignore`, `setup.sh`, `start.sh`,
`cleanup.sh`.

**Definition of done (roadmap as a whole):** challenge create uses a JSON body with flag + model;
models are config-driven with a working `GET /api/models` and per-challenge selection; free web
AI providers can run agents; events persist and replay; worker distribution is in place; CORS,
secrets, and tests are hardened.
