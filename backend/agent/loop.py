import asyncio
import json
from datetime import datetime

from .llm import generate_chat_completion
from .scheduler import qwen_scheduler
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
        self.container_id = None
        self.model = "Qwen3.6-35B-A3B"

    async def _emit(self, event_type: str, content: str, color: str = "text-gray-300"):
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        message = {
            "type": event_type,
            "content": content,
            "timestamp": timestamp,
            "color": color
        }
        await self.websocket_manager.broadcast_to_challenge(self.challenge_id, message)

    async def run(self):
        self.running = True
        await self._emit("SYSTEM", "Agent initializing sandbox...", "text-green-500")
        
        try:
            self.container_id = self.sandbox.create_sandbox(str(self.challenge_id))
            await self._emit("SYSTEM", f"Sandbox created ({self.container_id[:8]}). Starting investigation.", "text-green-500")
            
            while self.running:
                await self._emit("SYSTEM", f"Waiting for model queue lock (concurrency)...", "text-gray-500")
                await qwen_scheduler.acquire()
                try:
                    await self._emit("PLAN", "Thinking...", "text-blue-400")
                    response = await generate_chat_completion(self.model, self.messages, TOOLS)
                finally:
                    qwen_scheduler.release()
                
                if not self.running: break
                
                if not response or "choices" not in response:
                    await self._emit("SYSTEM", "Error: No response from LLM.", "text-red-500")
                    break
                    
                choice = response["choices"][0]
                message = choice["message"]
                
                # Append assistant message
                self.messages.append(message)
                
                # Handle reasoning (Qwen A3B deep think)
                if message.get("reasoning_content"):
                    await self._emit("HYPOTHESIS", message["reasoning_content"].strip(), "text-purple-400")
                
                if message.get("content"):
                    await self._emit("OBSERVATION", message["content"].strip(), "text-gray-300")
                
                if choice["finish_reason"] == "tool_calls":
                    for tool_call in message["tool_calls"]:
                        fn_name = tool_call["function"]["name"]
                        fn_args = json.loads(tool_call["function"]["arguments"])
                        
                        if fn_name == "execute_command":
                            cmd = fn_args["command"]
                            await self._emit("ACTION", f"$ {cmd}", "text-yellow-400")
                            
                            # Run in sandbox
                            # Offload blocking sandbox call to a thread so we don't block asyncio event loop
                            result = await asyncio.to_thread(self.sandbox.execute_command, self.container_id, cmd)
                            
                            # Truncate output to prevent context exhaustion
                            out = result["output"]
                            if len(out) > 3000:
                                out = out[:1500] + "\n...[TRUNCATED]...\n" + out[-1500:]
                                
                            await self._emit("OBSERVATION", out if out.strip() else "[No output]", "text-gray-400")
                            
                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "content": out
                            })
                            
                        elif fn_name == "submit_flag":
                            flag = fn_args["flag"]
                            await self._emit("SYSTEM", f"Agent submitted flag: {flag}", "text-green-500")
                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "content": "Flag submitted."
                            })
                            self.running = False
                            break

        except Exception as e:
            await self._emit("SYSTEM", f"Agent Error: {str(e)}", "text-red-500")
            print(f"Agent Loop Error: {e}")
            
        finally:
            if self.container_id:
                await self._emit("SYSTEM", "Cleaning up sandbox...", "text-gray-500")
                await asyncio.to_thread(self.sandbox.stop_sandbox, self.container_id)
            
            await self._emit("SYSTEM", "Agent finished execution.", "text-green-500")
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
