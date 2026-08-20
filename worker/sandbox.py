import os
from podman import PodmanClient

class SandboxManager:
    def __init__(self, uri="unix:///run/user/1000/podman/podman.sock"):
        # Connect to rootless podman socket
        # Note: the UID might be different, but 1000 is default for the first user
        try:
            self.uid = os.getuid()
        except AttributeError:
            self.uid = 1000
        
        # Override uri if default is requested but uid is different
        if uri.startswith("unix:///run/user/1000") and self.uid != 1000:
            uri = f"unix:///run/user/{self.uid}/podman/podman.sock"
            
        self.uri = uri

    def ping(self):
        with PodmanClient(base_url=self.uri) as client:
            return client.ping()

    def create_sandbox(self, challenge_id: str, allowed_urls: list = None):
        """
        Spawns a rootless Podman container for the agent to use.
        """
        with PodmanClient(base_url=self.uri) as client:
            # We use a lightweight kalilinux image, but for MVP let's use a basic python image or alpine
            # In real CTF scenarios we would build a custom kali image.
            image_name = "docker.io/library/alpine:latest"
            
            # Ensure image exists
            if not client.images.exists(image_name):
                client.images.pull(image_name)

            # Define container configurations for security
            container_name = f"argus-sandbox-{challenge_id}"
            
            # TODO: Configure strict networking based on allowed_urls
            # TODO: Mount tmpfs for /workspace
            
            container = client.containers.create(
                image_name,
                command=["sleep", "infinity"],
                name=container_name,
                remove=True, # Auto-remove when stopped
                # read_only=True, # Prevent modifying root fs
            )
            container.start()
            return container.id

    def execute_command(self, container_id: str, cmd: str):
        with PodmanClient(base_url=self.uri) as client:
            container = client.containers.get(container_id)
            # Execute command inside container
            exec_id = container.exec_run(cmd=cmd, tty=True)
            return {
                "exit_code": exec_id.exit_code,
                "output": exec_id.output.decode("utf-8", errors="replace") if exec_id.output else ""
            }
    
    def stop_sandbox(self, container_id: str):
        with PodmanClient(base_url=self.uri) as client:
            container = client.containers.get(container_id)
            container.stop()
