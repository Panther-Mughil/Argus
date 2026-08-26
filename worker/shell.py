"""Interactive SSH terminal over WebSocket for the in-UI shell.

Bridges a WebSocket to a paramiko PTY shell on a configured container host
(``backend/hosts.json``).  Used by Settings -> Podman Hosts -> terminal.
"""

import asyncio
import logging

import paramiko

from backend.config import settings
from worker.host_registry import list_hosts

logger = logging.getLogger(__name__)


def _find_host(name: str) -> dict | None:
    for h in list_hosts():
        if h.get("name") == name:
            return h
    return None


def _recv(channel) -> bytes | None:
    """Blocking read that returns None on timeout/error, b'' on EOF."""
    try:
        return channel.recv(4096)
    except Exception:
        return None


async def handle_shell(websocket, host_name: str) -> None:
    """Accept a WebSocket and run an interactive shell on the named host."""
    await websocket.accept()

    host = _find_host(host_name)
    if not host:
        await websocket.send_text(f"[ARGUS] Unknown host: {host_name}\r\n")
        await websocket.close()
        return

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        await asyncio.to_thread(
            client.connect,
            hostname=host.get("host") or "",
            port=int(host.get("port", 2222)),
            username=host.get("user") or "root",
            key_filename=host.get("ssh_key") or settings.resolved_ssh_key_path,
            timeout=10,
        )
    except Exception as exc:
        await websocket.send_text(f"[ARGUS] SSH connection failed: {exc}\r\n")
        await websocket.close()
        return

    channel = client.invoke_shell(width=120, height=32)
    channel.settimeout(0.5)

    async def pump_input_to_shell():
        try:
            while True:
                data = await websocket.receive_text()
                await asyncio.to_thread(channel.sendall, data.encode("utf-8"))
        except Exception as exc:
            logger.debug("shell input closed: %s", exc)
        finally:
            try:
                channel.close()
            except Exception as exc:
                logger.debug("channel close: %s", exc)

    async def pump_shell_to_websocket():
        try:
            while True:
                chunk = await asyncio.to_thread(_recv, channel)
                if chunk is None:
                    continue
                if chunk == b"":
                    break
                await websocket.send_text(chunk.decode("utf-8", "replace"))
        except Exception as exc:
            logger.debug("shell output closed: %s", exc)

    try:
        await asyncio.gather(pump_shell_to_websocket(), pump_input_to_shell())
    finally:
        try:
            channel.close()
        except Exception as exc:
            logger.debug("channel close final: %s", exc)
        client.close()
