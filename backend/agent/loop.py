"""The Argus agent loop: drives a single challenge's LLM + tool execution.

Design goals (see the investigation plan):
- Feed the model *rich, truthful* tool results (exit code + stdout + stderr).
- Bound the loop (max iterations / time) and recover from bad responses.
- Only announce the model-queue lock when it is actually contended.
- Pause on ``submit_flag`` for human verification, and resume on rejection.
"""

import asyncio
import base64
import json
import re
import shlex
import time
from datetime import datetime

from .llm import generate_chat_completion, default_model
from .scheduler import model_scheduler
from backend.storage import list_files, challenge_dir
from backend.config import settings
from worker.sandbox import SandboxManager


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": (
                "Run a shell command inside the isolated Kali Linux CTF sandbox. "
                "Use this for any filesystem, network, or tooling operation. "
                "The result includes the exit code, stdout, and stderr — use them "
                "to detect failures. Prefer non-interactive commands and pipe large "
                "output through head/tail/grep."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command to run."}
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a bounded slice of a file in the sandbox by byte offset. "
                "Use this to page through a large file instead of dumping it all."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path in the sandbox."},
                    "offset": {"type": "integer", "description": "Byte offset to start at (default 0)."},
                    "limit": {"type": "integer", "description": "Max bytes to read (default 6000)."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write content to a file in the sandbox (e.g. a small analysis/decoding "
                "script). Parent directories are created automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path in the sandbox."},
                    "content": {"type": "string", "description": "Text to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Recursively search files under a directory for a regular expression "
                "(uses ripgrep). Defaults to a flag-like pattern. Use this to hunt for "
                "flags across extracted artifacts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search."},
                    "pattern": {"type": "string", "description": "Regex; defaults to a flag-like pattern."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_flag",
            "description": (
                "Propose the flag you believe is correct. The run then pauses for a human "
                "to verify it. If the human rejects it, you will be asked to keep looking."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "flag": {"type": "string", "description": "The exact flag string."}
                },
                "required": ["flag"],
            },
        },
    },
]


CORE_PROMPT = """You are an autonomous CTF-solving agent operating inside an isolated Kali Linux sandbox. This is an authorized educational CTF environment only.

Work in a disciplined loop: PLAN -> ACT -> OBSERVE. After each tool result, decide the next concrete step. Never repeat an identical failed command; if a command fails, read the exit code and stderr and adjust. If you are stuck after a few attempts, change approach or clearly state the blocker instead of spinning.

Tool results include an exit code, stdout, and stderr. A non-zero exit code means failure — use stderr to diagnose. Large output is truncated; use read_file/search_files/grep to narrow it down.

When you find a flag, call submit_flag with the exact string. Do not keep exploring after proposing a flag.
"""

CATEGORY_PROMPTS = {
    "Forensics": """\nThis is a FORENSICS challenge. IMPORTANT: this sandbox is an unprivileged container — loop mounts (`mount -o loop`, `losetup`) are NOT permitted and will always fail. Do NOT waste time on mount; extract and parse the image instead.

Recommended workflow:
1. Identify every artifact first: `file <path>`, `xxd <path> | head`.
2. Decompress/extract: `gunzip`, `tar xf`, `unzip`, `7z x`.
3. Disk/USB images (common case) — extract filesystem contents WITHOUT mounting:
   - `7z l <img>` / `7z x <img>`, or
   - sleuthkit: `mmls <img>` → `fls -o <offset> <img>` and `icat -o <offset> <img> <inode>`, or `tsk_recover -o <offset> <img> <dir>`, or
   - `binwalk -e <img>` (carve embedded files), or
   - parse it with Python (write a small script).
4. PCAPs: `tshark -r <file>`, `tcpflow`, follow streams, extract objects.
5. Metadata is often the answer: `exiftool <file>`, `strings -a <file>`, `stat`.
6. Look for embedded documents/images (PNG/JPEG/PDF/DOCX signatures) in `strings` output — a carved PNG/JPEG often holds the answer in its XMP metadata.
7. SEARCH FOR WHAT THE CHALLENGE ASKS, not the literal word "flag". If the description says the flag is a firstname_lastname (a person's name), search for name patterns and metadata: `strings -a <img> | grep -iE '[A-Za-z]+_[A-Za-z]+'`, `exiftool <carved.png>`, and list extracted files for user/account names.""",
    "Cryptography": """\nThis is a CRYPTOGRAPHY challenge. Identify the cipher/primitive first (look at the challenge text and any provided code/files), then implement a solution script with write_file + execute_command. Try common attacks: frequency analysis, known-plaintext, weak/modulus factoring, padding oracles, nonce reuse. Validate candidate plaintexts against the expected flag format.""",
    "Pwn": """\nThis is a BINARY EXPLOITATION (pwn) challenge. Inspect the binary with `file`, `checksec`, `readelf`, `objdump`, and a disassembler. Identify the vulnerability (overflow, format string, use-after-free) and write an exploit. The target runs locally in the sandbox unless stated otherwise.""",
    "Reverse Engineering": """\nThis is a REVERSE ENGINEERING challenge. Analyze the binary/script with `file`, `strings`, `readelf`, `objdump`, and disassemblers/decompilers. Trace the flag-check logic and reconstruct the input that produces the flag.""",
    "Web": """\nThis is a WEB challenge. Enumerate the target with curl, inspect source/headers/cookies, and look for common issues (SQLi, XSS, SSRF, IDOR, path traversal, deserialization). Use curl to interact with the provided URL(s).""",
    "OSINT": """\nThis is an OSINT challenge. Use the provided artifacts and metadata to trace the target. Correlate clues, timestamps, and identifiers; document your reasoning as you narrow down the answer.""",
    "Steganography": """\nThis is a STEGANOGRAPHY challenge. Inspect files with `file`, `exiftool`, `strings`, `binwalk`, and `zsteg`/`steghide` where relevant. Check for hidden data in images, audio, or LSB planes; then decode/decrypt the payload.""",
    "Misc": """\nThis is a MISC challenge. Identify the underlying puzzle (encoding, scripting, logic, or a mix) and solve it step by step with small scripts and careful observation.""",
}


def build_system_prompt(title: str, desc: str, category: str, goal: str | None = None) -> str:
    parts = [
        CORE_PROMPT,
        f"Challenge: {title or 'Untitled'}",
        f"Category: {category or 'Unknown'}",
        f"Description: {desc or '(none provided)'}",
    ]
    if goal:
        parts.append(
            "PROMPT GOAL / expected answer shape: " + goal + "\n"
            "The flag is expected to look like '" + goal + "'. Search for something matching this shape "
            "(for example a person's name), NOT for the literal word 'flag' or 'ctf'. "
            "Inspect metadata (exiftool), embedded documents/images, filenames, and account/user records."
        )
    category_prompt = CATEGORY_PROMPTS.get(category)
    if category_prompt:
        parts.append(category_prompt)
    return "\n".join(parts)


# Regex to pull the flag format out of a challenge description (e.g. "flag format is: firstname_lastname").
_GOAL_RE = re.compile(r"(?:flag\s+)?format\s+is:?\s*([A-Za-z0-9_]{2,})", re.IGNORECASE)


def extract_goal(desc: str | None) -> str | None:
    """Return the expected flag shape if the description declares one, else None."""
    if not desc:
        return None
    m = _GOAL_RE.search(desc)
    return m.group(1) if m else None


# Commands that cannot work in this unprivileged container — used to nudge the model off a dead end.
DEAD_END_GUIDANCE = {
    "mount": "Loop mounts are NOT permitted in this unprivileged container. Do not use mount. Extract disk-image contents with `7z x`, `binwalk -e`, or sleuthkit (`mmls` + `fls`/`icat`/`tsk_recover`).",
    "losetup": "Loop devices are not available here (losetup fails). Do not use mount/losetup. Extract the image with `7z x`, `binwalk -e`, or sleuthkit.",
    "sudo": "You are already running as root; `sudo` is not installed. Drop `sudo` from all commands.",
    "mknod": "Creating device nodes is not permitted. Do not try to recover loop devices; use `7z x`/`binwalk -e`/sleuthkit extraction instead.",
}


# Quick probe of which forensic tools actually exist in the sandbox (injected into the prompt).
TOOLCHECK = (
    "for t in 7z binwalk exiftool fls icat mmls tsk_recover foremost testdisk xxd file strings dd tar gzip unzip python3 rg grep; "
    "do command -v \"$t\" >/dev/null 2>&1 && echo \"YES $t\" || echo \"NO  $t\"; done"
)


def _missing_bin(text: str) -> str | None:
    m = re.search(r"([A-Za-z0-9_/.\-]{1,64}): command not found", text)
    return m.group(1) if m else None


def truncate(text: str, limit: int) -> str:
    """Truncate long output to head+tail, noting how much was omitted."""
    if not text or len(text) <= limit:
        return text
    head = limit // 2
    tail = limit - head
    return f"{text[:head]}\n...[TRUNCATED {len(text) - limit} chars omitted]...\n{text[-tail:]}"


def _to_int(value, default: int) -> int:
    """Coerce a tool argument to int, falling back to ``default`` on garbage."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class AgentLoop:
    def __init__(self, challenge_id: int, websocket_manager, challenge_title: str, challenge_desc: str, category: str = ""):
        self.challenge_id = challenge_id
        self.websocket_manager = websocket_manager
        self.running = False
        self.paused = False
        # Starts *cleared* so the loop blocks when paused; reject_flag()/stop() set it.
        self._resume_event = asyncio.Event()
        self._proposed_flag: str | None = None
        self.model = settings.ARGUS_MODEL or default_model()
        self._goal = extract_goal(challenge_desc)
        self.messages = [
            {"role": "system", "content": build_system_prompt(challenge_title, challenge_desc, category, self._goal)}
        ]
        self.sandbox = SandboxManager()
        self.iteration = 0
        self.started_at: float | None = None
        # Anti-loop state: detect repeated failing commands / dead-end approaches.
        self._last_cmd: str | None = None
        self._repeat_failures = 0
        self._last_goal_nudge = 0

    # ------------------------------------------------------------------
    # Event emission + persistence
    # ------------------------------------------------------------------

    async def _emit(self, event_type: str, content: str, color: str = "text-cream", tool_name: str | None = None):
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        message = {
            "type": event_type,
            "content": content,
            "timestamp": timestamp,
            "color": color,
        }
        await self.websocket_manager.broadcast_to_challenge(self.challenge_id, message)
        await self._persist_event(event_type, content, tool_name)

    async def _persist_event(self, event_type: str, content: str, tool_name: str | None = None):
        """Best-effort write to EventLog (never breaks the loop on DB errors)."""
        try:
            from ..db.database import AsyncSessionLocal
            from ..db.models import EventLog, EventType

            mapped = event_type if event_type in {e.value for e in EventType} else "SYSTEM"
            async with AsyncSessionLocal() as session:
                session.add(
                    EventLog(
                        challenge_id=self.challenge_id,
                        event_type=EventType(mapped),
                        content=content,
                        tool_name=tool_name,
                    )
                )
                await session.commit()
        except Exception as exc:
            print(f"Event persistence failed: {exc}")

    # ------------------------------------------------------------------
    # Challenge file staging + metadata
    # ------------------------------------------------------------------

    async def _file_type(self, remote_path: str) -> str | None:
        try:
            result = await asyncio.to_thread(
                self.sandbox.execute_command, "kali-forensics", f"file -b {shlex.quote(remote_path)}"
            )
            out = (result.get("output") or "").strip()
            return out or None
        except Exception:
            return None

    async def _archive_listing(self, remote_path: str, ftype: str) -> str | None:
        low = ftype.lower()
        cmd = None
        if "gzip" in low:
            cmd = f"tar tzf {shlex.quote(remote_path)} 2>/dev/null | head -20"
        elif "tar" in low:
            cmd = f"tar tf {shlex.quote(remote_path)} 2>/dev/null | head -20"
        elif "zip" in low:
            cmd = f"unzip -l {shlex.quote(remote_path)} 2>/dev/null | head -30"
        if not cmd:
            return None
        try:
            result = await asyncio.to_thread(self.sandbox.execute_command, "kali-forensics", cmd)
            out = (result.get("output") or "").strip()
            return truncate(out, 1000) if out else None
        except Exception:
            return None

    async def _push_challenge_files(self) -> None:
        """Upload the challenge's stored files into the container and expose
        their paths *plus* type/archive metadata to the agent in the prompt."""
        files = list_files(self.challenge_id)
        if not files:
            return

        remote_dir = f"/workspace/{self.challenge_id}"
        uploaded: list[tuple[str, int]] = []
        try:
            for name, size in files:
                local_path = str(challenge_dir(self.challenge_id) / name)
                remote_path = await asyncio.to_thread(
                    self.sandbox.upload_file, local_path, remote_dir
                )
                uploaded.append((remote_path, size))
        except Exception as exc:
            await self._emit(
                "SYSTEM",
                f"Warning: could not push challenge files into sandbox: {exc}",
                "text-danger",
            )
            print(f"Failed to upload challenge files: {exc}")
            return

        descriptions = []
        for remote_path, size in uploaded:
            desc = f"{remote_path} ({size} bytes)"
            ftype = await self._file_type(remote_path)
            if ftype:
                desc += f" — type: {ftype}"
                listing = await self._archive_listing(remote_path, ftype)
                if listing:
                    desc += f" — archive contents:\n{listing}"
            descriptions.append(desc)

        file_list = "\n".join(descriptions)
        self.messages[0]["content"] += (
            f"\nChallenge files (already placed in the sandbox):\n{file_list}"
        )
        await self._emit(
            "SYSTEM", f"Loaded {len(uploaded)} challenge file(s) into sandbox.", "text-mint"
        )

    async def _inject_tool_inventory(self) -> None:
        """Probe which forensic tools exist and tell the agent so it only uses real ones."""
        try:
            result = await asyncio.to_thread(self.sandbox.execute_command, "kali-forensics", TOOLCHECK)
            lines = [l.strip() for l in (result.get("output") or "").splitlines() if l.strip()]
            if not lines:
                return
            present = [l.split(maxsplit=1)[1] for l in lines if l.startswith("YES")]
            absent = [l.split(maxsplit=1)[1] for l in lines if l.startswith("NO")]
            self.messages[0]["content"] += (
                "\nTools available in this sandbox (verified present): " + ", ".join(present) + "\n"
                "Tools NOT installed (do not recommend or try to use): " + ", ".join(absent)
            )
        except Exception as exc:
            print(f"Tool inventory probe failed: {exc}")

    def _assess_and_nudge(self, cmd: str, result: dict) -> str | None:
        """Return targeted guidance when the model is on a clear dead-end path."""
        exit_code = result.get("exit_code")
        combined = (result.get("output") or "") + "\n" + (result.get("stderr") or "")
        failed = exit_code not in (None, 0)

        # A tool the model tried is simply absent → redirect + surface as observability.
        missing = _missing_bin(combined)
        if missing:
            return (
                f"Tool '{missing}' is NOT installed in this sandbox — do not use it. Use tools that exist "
                "(file, strings, dd, tar, gzip, rg, xxd, python3). For disk images, extract contents with "
                "`7z x`, `binwalk -e`, or sleuthkit (`mmls`/`fls`/`icat`/`tsk_recover`) instead."
            )

        # A known dead-end command family (mount/losetup/sudo/mknod) failed → nudge immediately.
        first = (cmd.split() or [""])[0]
        if first in DEAD_END_GUIDANCE and failed:
            return DEAD_END_GUIDANCE[first]

        # Same command failed repeatedly → nudge to change strategy.
        if cmd == self._last_cmd and failed:
            self._repeat_failures += 1
            if self._repeat_failures >= settings.ARGUS_STALE_ATTEMPT_THRESHOLD:
                self._repeat_failures = 0
                return (
                    f"You have run '{cmd}' repeatedly and it keeps failing. STOP repeating this command. "
                    "Change strategy: inspect the artifact differently (extract with `7z x`/`tar xf`/`binwalk -e`, "
                    "read metadata with `exiftool`/`strings`/`xxd`, or parse it with Python)."
                )
        else:
            self._last_cmd = cmd
            self._repeat_failures = 1 if failed else 0
        return None

    # ------------------------------------------------------------------
    # Tool result formatting
    # ------------------------------------------------------------------

    def _format_command_result(self, result: dict) -> str:
        exit_code = result.get("exit_code")
        out = result.get("output") or ""
        err = result.get("stderr") or ""
        limit = settings.ARGUS_MAX_TOOL_OUTPUT_CHARS

        parts = []
        if exit_code not in (None, 0):
            parts.append(f"[exit code {exit_code}]")
        if out.strip():
            parts.append(truncate(out, limit))
        if err.strip():
            parts.append(f"[stderr]\n{truncate(err, limit)}")
        if not parts:
            return "[No output]"
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def _run_sandbox(self, cmd: str) -> dict:
        return await asyncio.to_thread(self.sandbox.execute_command, "kali-forensics", cmd)

    async def _handle_tool_call(self, tool_call_id: str, fn_name: str, fn_args: dict) -> str | None:
        if fn_name == "execute_command":
            cmd = fn_args.get("command", "")
            await self._emit("ACTION", f"$ {cmd}", "text-sand", tool_name="execute_command")
            result = await self._run_sandbox(cmd)
            content = self._format_command_result(result)
            await self._emit("OBSERVATION", content if content.strip() else "[No output]", "text-stone", tool_name="execute_command")
            self.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})
            return self._assess_and_nudge(cmd, result)

        elif fn_name == "read_file":
            path = fn_args.get("path", "")
            offset = _to_int(fn_args.get("offset"), 0)
            limit = _to_int(fn_args.get("limit"), settings.ARGUS_MAX_TOOL_OUTPUT_CHARS)
            cmd = f"dd if={shlex.quote(path)} bs=1 skip={offset} count={limit} 2>/dev/null"
            await self._emit("ACTION", f"read_file {path} [{offset}:{offset + limit}]", "text-sand", tool_name="read_file")
            result = await self._run_sandbox(cmd)
            content = self._format_command_result(result)
            await self._emit("OBSERVATION", content if content.strip() else "[No output]", "text-stone", tool_name="read_file")
            self.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})

        elif fn_name == "write_file":
            path = fn_args.get("path", "")
            raw = fn_args.get("content", "")
            b64 = base64.b64encode(raw.encode("utf-8")).decode("ascii")
            cmd = (
                f"mkdir -p \"$(dirname {shlex.quote(path)})\" && "
                f"printf '%s' '{b64}' | base64 -d > {shlex.quote(path)}"
            )
            await self._emit("ACTION", f"write_file {path}", "text-sand", tool_name="write_file")
            result = await self._run_sandbox(cmd)
            content = self._format_command_result(result)
            await self._emit("OBSERVATION", content if content.strip() else "[written]", "text-stone", tool_name="write_file")
            self.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": content or "File written."})

        elif fn_name == "search_files":
            path = fn_args.get("path", "/workspace")
            pattern = fn_args.get("pattern") or r"flag|ctf|FLAG|CTF|\{[A-Za-z0-9_\-]{4,}\}|[A-Za-z]+_[A-Za-z]+"
            pat = shlex.quote(pattern)
            p = shlex.quote(path)
            cmd = (
                f"{{ if command -v rg >/dev/null 2>&1; then "
                f"rg -na --no-heading -e {pat} {p} 2>/dev/null; "
                f"else grep -rnaE -e {pat} {p}; fi; }} | head -100"
            )
            await self._emit("ACTION", f"search_files '{pattern}' in {path}", "text-sand", tool_name="search_files")
            result = await self._run_sandbox(cmd)
            content = self._format_command_result(result)
            await self._emit("OBSERVATION", content if content.strip() else "[No matches]", "text-stone", tool_name="search_files")
            self.messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": content or "[No matches]"})

        elif fn_name == "submit_flag":
            flag = fn_args.get("flag", "")
            self._proposed_flag = flag
            self.paused = True
            await self._emit("FLAG", flag, "text-mint", tool_name="submit_flag")
            await self._update_status("FLAG_PROPOSED", proposed_flag=flag)
            self.messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": f"Flag proposed: {flag}. The run is paused awaiting human verification.",
            })

        else:
            self.messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": f"Unknown tool: {fn_name}",
            })
        return None

    # ------------------------------------------------------------------
    # Status updates
    # ------------------------------------------------------------------

    async def _update_status(self, status: str, proposed_flag: str | None = None, clear_proposed: bool = False) -> None:
        try:
            from ..db.database import AsyncSessionLocal
            from ..db.models import Challenge, ChallengeStatus

            async with AsyncSessionLocal() as session:
                challenge = await session.get(Challenge, self.challenge_id)
                if challenge:
                    challenge.status = ChallengeStatus(status)
                    if clear_proposed:
                        challenge.proposed_flag = None
                    elif proposed_flag is not None:
                        challenge.proposed_flag = proposed_flag
                    await session.commit()
        except Exception as exc:
            print(f"Failed to update challenge status: {exc}")

    # ------------------------------------------------------------------
    # LLM call with retry
    # ------------------------------------------------------------------

    async def _call_llm_with_retry(self):
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                return await generate_chat_completion(
                    self.model,
                    self.messages,
                    TOOLS,
                    max_tokens=settings.ARGUS_LLM_MAX_TOKENS,
                )
            except Exception as exc:
                last_exc = exc
                print(f"LLM call failed (attempt {attempt + 1}/3): {exc}")
                await asyncio.sleep(1.0 * (attempt + 1))
        await self._emit("SYSTEM", f"LLM error after retries: {last_exc}", "text-danger")
        return None

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        self.running = True
        self.started_at = time.monotonic()
        await self._emit("SYSTEM", "Agent initializing sandbox...", "text-mint")

        try:
            self.sandbox.ensure_connected()
            await self._emit("SYSTEM", "Connected to kali-forensics sandbox.", "text-mint")
            await self._push_challenge_files()
            await self._inject_tool_inventory()

            while self.running:
                if self.paused:
                    await self._emit(
                        "SYSTEM",
                        "Paused — awaiting human verification of the proposed flag.",
                        "text-lavender",
                    )
                    await self._resume_event.wait()
                    self._resume_event.clear()
                    if not self.running:
                        break

                if self.iteration >= settings.ARGUS_MAX_ITERATIONS:
                    await self._emit(
                        "ERROR",
                        f"Stopping: reached max iterations ({settings.ARGUS_MAX_ITERATIONS}).",
                        "text-danger",
                    )
                    await self._update_status("FAILED")
                    break

                if time.monotonic() - self.started_at > settings.ARGUS_MAX_RUN_SECONDS:
                    await self._emit("ERROR", "Stopping: max run time exceeded.", "text-danger")
                    await self._update_status("FAILED")
                    break

                # Periodic goal reminder so the model doesn't lose the target / drift.
                if self._goal and not self._proposed_flag and self.iteration > 0 and self.iteration - self._last_goal_nudge >= 8:
                    self._last_goal_nudge = self.iteration
                    reminder = (
                        f"[GOAL REMINDER]: You are still looking for {self._goal}. Search for name patterns and "
                        "metadata (exiftool/strings), extract embedded files, and check filenames — do not grep for the "
                        "word 'flag'. If one tool fails, switch tools instead of repeating it."
                    )
                    await self._emit("SYSTEM", reminder, "text-lavender")
                    self.messages.append({"role": "user", "content": reminder})

                # Only announce the queue when we will actually block on it.
                if model_scheduler.locked(self.model):
                    await self._emit("SYSTEM", "Waiting for model queue lock (concurrency)...", "text-stone")
                await model_scheduler.acquire(self.model)
                try:
                    await self._emit("PLAN", "Thinking...", "text-lavender")
                    response = await self._call_llm_with_retry()
                finally:
                    model_scheduler.release(self.model)

                if not self.running:
                    break

                if response is None:
                    await self._emit("ERROR", "Error: no response from LLM after retries.", "text-danger")
                    await self._update_status("FAILED")
                    break

                if "choices" not in response or not response["choices"]:
                    await self._emit("ERROR", "Error: unexpected LLM response shape.", "text-danger")
                    await self._update_status("FAILED")
                    break

                choice = response["choices"][0]
                message = choice.get("message") or {}

                # Keep only the OpenAI-compatible assistant fields in context.
                reasoning = (message.get("reasoning_content") or "").strip()
                assistant = {"role": "assistant", "content": message.get("content")}
                if message.get("tool_calls"):
                    assistant["tool_calls"] = message["tool_calls"]
                self.messages.append(assistant)

                if reasoning:
                    await self._emit("HYPOTHESIS", reasoning, "text-iris")
                if message.get("content"):
                    await self._emit("OBSERVATION", message["content"].strip(), "text-cream")

                finish = choice.get("finish_reason")
                if finish == "length":
                    # Generation was cut off mid-response — keep going.
                    self.messages.append({
                        "role": "user",
                        "content": "Your previous response was cut off. Continue exactly where you left off.",
                    })
                    self.iteration += 1
                    continue

                if finish == "tool_calls" and message.get("tool_calls"):
                    nudges: list[str] = []
                    for tool_call in message["tool_calls"]:
                        if not self.running or self.paused:
                            break
                        fn_name = tool_call["function"]["name"]
                        try:
                            fn_args = json.loads(tool_call["function"].get("arguments") or "{}")
                        except json.JSONDecodeError as exc:
                            await self._emit("SYSTEM", f"Malformed tool arguments: {exc}", "text-danger")
                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "content": f"Error: could not parse arguments ({exc}). Please provide valid JSON.",
                            })
                            continue
                        nudge = await self._handle_tool_call(tool_call["id"], fn_name, fn_args)
                        if nudge:
                            nudges.append(nudge)
                    if nudges:
                        guidance = "\n".join(nudges)
                        await self._emit("SYSTEM", guidance, "text-lavender")
                        self.messages.append({"role": "user", "content": f"[SYSTEM GUIDANCE]: {guidance}"})
                    self.iteration += 1
                else:
                    await self._emit(
                        "SYSTEM",
                        "Agent reached a conclusion without proposing a flag.",
                        "text-stone",
                    )
                    await self._update_status("BLOCKED")
                    break

        except Exception as e:
            await self._emit("ERROR", f"Agent Error: {str(e)}", "text-danger")
            print(f"Agent Loop Error: {e}")
            await self._update_status("FAILED")

        finally:
            await self._emit("SYSTEM", "Cleaning up sandbox connection...", "text-stone")
            await asyncio.to_thread(self.sandbox.disconnect)
            await self._emit("SYSTEM", "Agent finished execution.", "text-mint")
            self.running = False
            self.paused = False
            self._resume_event.set()

            import backend.main as main
            if self.challenge_id in main.active_agents:
                del main.active_agents[self.challenge_id]

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def stop(self):
        self.running = False
        self.paused = False
        self._resume_event.set()

    async def reject_flag(self):
        """Resume the loop after the human rejected the proposed flag."""
        self.paused = False
        self._proposed_flag = None
        self._resume_event.set()
        await self._update_status("IN_PROGRESS", clear_proposed=True)

    def inject_intervention(self, text: str):
        self.messages.append({
            "role": "user",
            "content": f"[USER INTERVENTION]: {text}",
        })
