import asyncio
import json
from datetime import datetime

from .llm import generate_chat_completion
from .scheduler import qwen_scheduler
from backend.storage import list_files, challenge_dir
from worker.sandbox import SandboxManager

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a bash command in the isolated CTF sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to run (e.g. 'ls -la', 'cat flag.txt')"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_flag",
            "description": "Submit the flag when you have found it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flag": {
                        "type": "string",
                        "description": "The exact flag string"
                    }
                },
                "required": ["flag"]
            }
        }
    }
]

class AgentLoop:
    def __init__(self, challenge_id: int, websocket_manager, challenge_title: str, challenge_desc: str):
        self.challenge_id = challenge_id
        self.websocket_manager = websocket_manager
        self.running = False
        self.messages = [
            {"role": "system", "content": f"You are a cybersecurity expert solving a CTF challenge.\nChallenge: {challenge_title}\nDescription: {challenge_desc}\nUse your tools to investigate the sandbox."}
        ]
        self.sandbox = SandboxManager()
        self.model = "gpt-oss-20B"

    async def _emit(self, event_type: str, content: str, color: str = "text-cream"):
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        message = {
            "type": event_type,
            "content": content,
            "timestamp": timestamp,
            "color": color
        }
        await self.websocket_manager.broadcast_to_challenge(self.challenge_id, message)

    async def _push_challenge_files(self) -> None:
        """Upload the challenge's stored files into the container.

        Called after ``ensure_connected()``.  Adds the remote paths to the
        system prompt so the agent can ``cat``/``strings``/``binwalk`` them.

        Fails soft: on any SSH/upload error, emits a SYSTEM event and
        returns with an empty file list (the agent simply has no files).
        """
        files = list_files(self.challenge_id)
        if not files:
            return

        remote_dir = f"/workspace/{self.challenge_id}"
        remote_paths = []
        try:
            for name, _size in files:
                local_path = str(challenge_dir(self.challenge_id) / name)
                remote_path = await asyncio.to_thread(
                    self.sandbox.upload_file, local_path, remote_dir
                )
                remote_paths.append(remote_path)
        except Exception as exc:
            await self._emit(
                "SYSTEM",
                f"Warning: could not push challenge files into sandbox: {exc}",
                "text-danger",
            )
            print(f"Failed to upload challenge files: {exc}")
            return

        file_list = ", ".join(remote_paths)
        self.messages[0]["content"] += (
            f"\nChallenge files (already placed in the sandbox): {file_list}"
        )
        await self._emit(
            "SYSTEM", f"Loaded {len(remote_paths)} challenge file(s) into sandbox.", "text-mint"
        )

    async def run(self):
        self.running = True
        await self._emit("SYSTEM", "Agent initializing sandbox...", "text-mint")

        try:
            # Connect to the shared kali-forensics container via SSH
            self.sandbox.ensure_connected()
            await self._emit("SYSTEM", "Connected to kali-forensics sandbox.", "text-mint")

            # Push any uploaded challenge files into the container and
            # expose their paths to the agent in the system prompt.
            await self._push_challenge_files()

            while self.running:
                await self._emit("SYSTEM", f"Waiting for model queue lock (concurrency)...", "text-stone")
                await qwen_scheduler.acquire()
                try:
                    await self._emit("PLAN", "Thinking...", "text-lavender")
                    response = await generate_chat_completion(self.model, self.messages, TOOLS)
                finally:
                    qwen_scheduler.release()

                if not self.running: break

                if not response or "choices" not in response:
                    await self._emit("SYSTEM", "Error: No response from LLM.", "text-danger")
                    break

                choice = response["choices"][0]
                message = choice["message"]

                # Append assistant message
                self.messages.append(message)

                # Handle reasoning (Qwen A3B deep think)
                if message.get("reasoning_content"):
                    await self._emit("HYPOTHESIS", message["reasoning_content"].strip(), "text-iris")

                if message.get("content"):
                    await self._emit("OBSERVATION", message["content"].strip(), "text-cream")

                if choice["finish_reason"] == "tool_calls":
                    for tool_call in message["tool_calls"]:
                        fn_name = tool_call["function"]["name"]
                        fn_args = json.loads(tool_call["function"]["arguments"])

                        if fn_name == "execute_command":
                            cmd = fn_args["command"]
                            await self._emit("ACTION", f"$ {cmd}", "text-sand")

                            # Run in sandbox (SSH into kali-forensics)
                            result = await asyncio.to_thread(self.sandbox.execute_command, "kali-forensics", cmd)

                            # Truncate output to prevent context exhaustion
                            out = result["output"]
                            if len(out) > 3000:
                                out = out[:1500] + "\n...[TRUNCATED]...\n" + out[-1500:]

                            await self._emit("OBSERVATION", out if out.strip() else "[No output]", "text-stone")

                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "content": out
                            })

                        elif fn_name == "submit_flag":
                            flag = fn_args["flag"]
                            await self._emit("SYSTEM", f"Agent submitted flag: {flag}", "text-mint")
                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "content": "Flag submitted."
                            })
                            self.running = False
                            break
                else:
                    # No tool calls -> the model produced a final answer.
                    # Stop the agent instead of looping indefinitely.
                    await self._emit("SYSTEM", "Agent reached a conclusion.", "text-mint")
                    break

        except Exception as e:
            await self._emit("SYSTEM", f"Agent Error: {str(e)}", "text-danger")
            print(f"Agent Loop Error: {e}")

        finally:
            # Close SSH connection (never stop the shared container)
            await self._emit("SYSTEM", "Cleaning up sandbox connection...", "text-stone")
            await asyncio.to_thread(self.sandbox.disconnect)

            await self._emit("SYSTEM", "Agent finished execution.", "text-mint")
            self.running = False

            # Update DB
            from ..db.database import AsyncSessionLocal
            from ..db.models import Challenge, ChallengeStatus
            async with AsyncSessionLocal() as session:
                challenge = await session.get(Challenge, self.challenge_id)
                if challenge and challenge.status == ChallengeStatus.IN_PROGRESS:
                    challenge.status = ChallengeStatus.SOLVED
                    await session.commit()

            import backend.main as main
            if self.challenge_id in main.active_agents:
                del main.active_agents[self.challenge_id]

    def stop(self):
        self.running = False

    async def inject_intervention(self, text: str):
        self.messages.append({
            "role": "user",
            "content": f"[USER INTERVENTION]: {text}"
        })
