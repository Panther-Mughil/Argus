import time
import asyncio
from .sandbox import SandboxManager

class WorkerDaemon:
    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url
        self.sandbox = SandboxManager()

    def run(self):
        print(f"Starting Argus Worker Daemon (API: {self.api_url})")
        
        # Test podman connection
        try:
            if self.sandbox.ping():
                print("Successfully connected to Podman socket.")
        except Exception as e:
            print(f"Failed to connect to Podman: {e}")
            print("Ensure the podman socket is running (systemctl --user enable --now podman.socket)")
            return

        print("Worker is ready and waiting for tasks...")
        # For now, just a dummy loop. Will implement WebSocket/HTTP polling soon.
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            print("Worker shutting down.")

if __name__ == "__main__":
    daemon = WorkerDaemon()
    daemon.run()
