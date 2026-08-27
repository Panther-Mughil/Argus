import logging
import shlex
from pathlib import Path

import paramiko

from backend.config import settings

from .host_registry import acquire_host, release_host, select_host

logger = logging.getLogger(__name__)


class SandboxManager:
    """Connects to the shared Kali forensics container via direct SSH.

    Replaces the previous podman-based sandbox manager.  The Kali container
    (*kali-forensics*) is always running; the manager opens and closes SSH
    connections into it on demand.
    """

    def __init__(self) -> None:
        self._client: paramiko.SSHClient | None = None
        self._host: dict | None = None
        self._acquired: bool = False

    def _resolve_host(self) -> dict:
        host = self._host
        if host is None:
            host = select_host()
            self._host = host
        return host

    def _host_key_path(self, host: dict) -> str:
        key = str(host.get("ssh_key", "")).strip()
        if key:
            key_path = Path(key)
            if not key_path.is_absolute():
                return str(Path(__file__).resolve().parent.parent / key_path)
            return str(key_path)
        return settings.resolved_ssh_key_path

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open a persistent SSH connection to a selected container host.

        Raises ``ConnectionError`` with a human-readable message if the
        selected host cannot be reached.
        """
        if self._client is not None:
            # Already connected – just verify the transport is alive.
            if self._client.get_transport():
                return
            self._client.close()
            self._client = None

        host = self._resolve_host()
        if host is None:
            raise ConnectionError("No container host configured")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key_path = self._host_key_path(host)
        try:
            client.connect(
                hostname=host["host"],
                port=host.get("port", 2222),
                username=host.get("user", "root"),
                key_filename=key_path,
                timeout=10,
            )
        except Exception as exc:
            raise ConnectionError(
                f"Sandbox unreachable: is {host.get('name', 'sandbox')} running and "
                f"reachable at {host['host']}:{host.get('port', 2222)}? "
                f"({exc})"
            ) from exc
        self._client = client
        if not self._acquired:
            acquire_host(host["name"])
            self._acquired = True

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
    # Evidence protection helpers (REQ-003)
    # ------------------------------------------------------------------

    def ensure_dir(self, remote_dir: str) -> None:
        """Ensure a remote directory exists on the container filesystem.

        Parameters
        ----------
        remote_dir:
            Absolute path inside the container.
        """
        self.connect()
        if self._client is None:
            raise RuntimeError("SSH client is not connected")
        stdin, stdout, stderr = self._client.exec_command(f"mkdir -p {remote_dir}")
        stdout.channel.recv_exit_status()

    def copy_originals_to_work(
        self, challenge_id: int, sandbox_root: str = "/workspace"
    ) -> None:
        """Stage a clean copy of the originals into the work directory.

        Removes any stale contents in *work/* first, then copies files
        from *originals/* using ``cp -n`` (skip if work copy already exists).
        Handles the case where ``originals/`` is empty (no-op).

        Parameters
        ----------
        challenge_id:
            Integer challenge id.
        sandbox_root:
            The common root prefix (default ``/workspace``).
        """
        self.connect()
        if self._client is None:
            raise RuntimeError("SSH client is not connected")

        challenge_root = f"{sandbox_root}/{challenge_id}"
        originals_dir = f"{challenge_root}/originals"
        work_dir = f"{challenge_root}/work"

        # Ensure both directories exist.
        self.ensure_dir(originals_dir)
        self.ensure_dir(work_dir)

        # Remove stale junk from work/, then copy originals in.
        cmd = (
            f"cd {shlex.quote(challenge_root)} && "
            f"rm -rf work/* work/.* 2>/dev/null; "
            f"cp -n originals/* work/ 2>/dev/null || true"
        )
        stdin, stdout, stderr = self._client.exec_command(cmd)
        stdout.channel.recv_exit_status()

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
        """Explicitly close the SSH connection and release the host slot."""
        client, self._client = self._client, None
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                # Connection may already be gone — nothing to recover.
                logger.debug("Ignoring error while closing SSH transport: %s", exc)
        if self._host is not None and self._acquired:
            release_host(self._host["name"])
            self._acquired = False
