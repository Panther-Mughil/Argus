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
1.  **Central Web Application (FastAPI):** Orchestrates sessions, manages the PostgreSQL database, serves the Web UI, handles WebSocket real-time updates, and streams files.
2.  **Web UI:** A real-time collaborative frontend dashboard.
3.  **Database (PostgreSQL):** Stores sessions, challenges, agent state, tool execution logs, and artifacts. Runs entirely locally via Podman/Docker compose.
4.  **Model Scheduler:** Manages access to local inference endpoints (like `10.0.2.2:12057`), ensuring concurrency limits are respected.
5.  **Worker Daemon:** A lightweight Python agent running on sandbox hosts (e.g., `10.0.2.6`). It receives tasks via HTTP/WebSockets from the central app, pulls files locally, and manages the Podman lifecycle for the challenge container.

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
