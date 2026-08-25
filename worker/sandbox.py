from pathlib import Path
from typing import Optional

import logging

import paramiko

from backend.config import settings

logger = logging.getLogger(__name__)


class SandboxManager:
    """Connects to the shared Kali forensics container via direct SSH.

    Replaces the previous podman-based sandbox manager.  The Kali container
    (*kali-forensics*) is always running; the manager opens and closes SSH
    connections into it on demand.
    """

    def __init__(self) -> None:
        self._client: Optional[paramiko.SSHClient] = None

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open a persistent SSH connection to the container.

        Raises ``ConnectionError`` with a human-readable message if the
        container cannot be reached.
        """
        if self._client is not None:
            # Already connected – just verify the transport is alive.
            if not self._client.get_transport():
                self._client.close()
                self._client = None

        if self._client is None:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            key_path = settings.resolved_ssh_key_path
            try:
                client.connect(
                    hostname=settings.ARGUS_CONTAINER_HOST,
                    port=settings.ARGUS_CONTAINER_PORT,
                    username=settings.ARGUS_CONTAINER_USER,
                    key_filename=key_path,
                    timeout=10,
                )
            except Exception as exc:
                raise ConnectionError(
                    f"Sandbox unreachable: is kali-forensics running and "
                    f"reachable at {settings.ARGUS_CONTAINER_HOST}:{settings.ARGUS_CONTAINER_PORT}? "
                    f"({exc})"
                ) from exc
            self._client = client

    def ping(self) -> bool:
        """Quick connectivity check."""
        try:
            self.connect()
            if self._client is None:
                return False
            _, stdout, _ = self._client.exec_command("echo ok", timeout=5)
            return stdout.read().decode().strip() == "ok"
        except Exception:
            return False

    def ensure_connected(self) -> None:
        """Alias for ``connect()`` (used by the agent loop)."""
        self.connect()

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def execute_command(self, container_id: str, cmd: str) -> dict:
        """Execute *cmd* inside the container and return exit_code + output.

        Parameters
        ----------
        container_id:
            Ignored for direct-SSH mode (there is only one container), but
            kept for API compatibility.
        cmd:
            Shell command to run.

        Returns
        -------
        dict with keys ``exit_code`` (int), ``output`` (str, stdout), and
        ``stderr`` (str).
        """
        self.connect()
        if self._client is None:
            raise RuntimeError("SSH client is not connected")
        timeout = settings.ARGUS_CONTAINER_CMD_TIMEOUT
        stdin, stdout, stderr = self._client.exec_command(cmd, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8", errors="replace")
        error_output = stderr.read().decode("utf-8", errors="replace")
        return {
            "exit_code": exit_code,
            "output": output,
            "stderr": error_output,
        }

    # ------------------------------------------------------------------
    # File transfer (SFTP)
    # ------------------------------------------------------------------

    def upload_file(self, local_path: str, remote_dir: str) -> str:
        """Upload a local file into the container via SFTP.

        Creates *remote_dir* if it does not already exist, then uploads the
        file, preserving its basename.

        Returns the full remote path of the uploaded file.
        """
        self.connect()
        if self._client is None:
            raise RuntimeError("SSH client is not connected")

        local_path = str(local_path)
        remote_dir = remote_dir.rstrip("/")
        remote_path = f"{remote_dir}/{Path(local_path).name}"

        # Ensure the destination directory exists (use exec_command, as
        # paramiko's SFTP client has no trivial recursive makedirs).
        stdin, stdout, stderr = self._client.exec_command(f"mkdir -p {remote_dir}")
        stdout.channel.recv_exit_status()

        sftp = self._client.open_sftp()
        try:
            sftp.put(local_path, remote_path)
        finally:
            sftp.close()
        return remote_path

    def remove_remote_dir(self, remote_dir: str) -> None:
        """Best-effort recursive removal of a remote directory.

        Failures are logged, never raised (cleanup should not crash the
        caller).
        """
        try:
            self.connect()
            if self._client is None:
                return
            stdin, stdout, stderr = self._client.exec_command(f"rm -rf {remote_dir}")
            stdout.channel.recv_exit_status()
        except Exception as exc:
            logger.warning("Failed to remove remote dir %s: %s", remote_dir, exc)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop_sandbox(self, container_id: str) -> None:
        """Close the SSH connection.

        *Never* stops or removes the container — it is a shared,
        always-on forensics environment.
        """
        self.disconnect()

    def disconnect(self) -> None:
        """Explicitly close the SSH connection."""
        client, self._client = self._client, None
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                # Connection may already be gone — nothing to recover.
                logger.debug("Ignoring error while closing SSH transport: %s", exc)
