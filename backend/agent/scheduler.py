import asyncio
import json
import os

config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models.json")
with open(config_path, "r") as f:
    MODELS_CONFIG = json.load(f)
    
onyx_provider = next(p for p in MODELS_CONFIG["providers"] if p["name"] == "Onyx")
CONCURRENCY_LIMIT = onyx_provider.get("concurrency", 1)

class ModelScheduler:
    def __init__(self, limit: int):
        self.semaphore = asyncio.Semaphore(limit)

    async def acquire(self):
        await self.semaphore.acquire()
        
    def release(self):
        self.semaphore.release()

# Global scheduler instance for the Qwen model
qwen_scheduler = ModelScheduler(CONCURRENCY_LIMIT)
