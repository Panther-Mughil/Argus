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


async def _safe_send(websocket, text: str) -> None:
    """Send text without raising if the client has already disconnected."""
    try:
        await websocket.send_text(text)
    except Exception as exc:
        logger.debug("ws send failed (client gone): %s", exc)


async def handle_shell(websocket, host_name: str) -> None:
    """Accept a WebSocket and run an interactive shell on the named host."""
    try:
        await websocket.accept()
    except Exception:
        return

    host = _find_host(host_name)
    if not host:
        await _safe_send(websocket, f"[ARGUS] Unknown host: {host_name}\r\n")
        try:
            await websocket.close()
        except Exception as exc:
            logger.debug("ws close failed (unknown host): %s", exc)
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
        await _safe_send(websocket, f"[ARGUS] SSH connection failed: {exc}\r\n")
        try:
            await websocket.close()
        except Exception as exc:
            logger.debug("ws close failed (ssh error): %s", exc)
        return

    try:
        channel = client.invoke_shell(width=120, height=32)
    except Exception as exc:
        await _safe_send(websocket, f"[ARGUS] Failed to open shell: {exc}\r\n")
        try:
            await websocket.close()
        except Exception as exc:
            logger.debug("ws close failed (shell error): %s", exc)
        client.close()
        return
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
