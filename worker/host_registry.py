"""Multi-host container registry + load balancer for Argus sandboxes.

The registry lives in ``backend/hosts.json`` (configurable via
``ARGUS_HOSTS_PATH``).  Each host declares connection details, a
per-host concurrency cap, and a max-challenge capacity.  ``select_host``
picks a healthy, under-capacity host using round-robin among the
eligible set, falling back to the first healthy host if everything is
full.
"""

import json
import socket
from pathlib import Path
from threading import Lock

from backend.config import settings


_HOSTS_CONFIG_PATH = Path(settings.ARGUS_HOSTS_PATH)
if not _HOSTS_CONFIG_PATH.is_absolute():
    _HOSTS_CONFIG_PATH = Path(__file__).resolve().parent.parent / _HOSTS_CONFIG_PATH


def _load_hosts_config() -> dict:
    try:
        return json.loads(_HOSTS_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"hosts": []}


HOSTS_CONFIG = _load_hosts_config()

# Module-level tracking of currently-acquired hosts (SandoxManager connect/disconnect).
_active_counts: dict[str, int] = {}
_active_lock = Lock()

# Round-robin cursor for spreading load across eligible hosts.
_round_robin_index = 0


def _tcp_health_check(host: str, port: int, timeout: float = 2.0) -> bool:
    """Lightweight TCP connectivity probe."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# Tests can monkeypatch this to avoid real network calls.
_health_check_func = _tcp_health_check


def list_hosts() -> list[dict]:
    """Return the configured container hosts."""
    return HOSTS_CONFIG.get("hosts", [])


def reload() -> None:
    """Re-read hosts.json into the in-memory config (after an admin edit)."""
    global HOSTS_CONFIG
    HOSTS_CONFIG = _load_hosts_config()


def acquire_host(name: str) -> None:
    """Increment the active-use counter for *name*."""
    with _active_lock:
        _active_counts[name] = _active_counts.get(name, 0) + 1


def release_host(name: str) -> None:
    """Decrement the active-use counter for *name*."""
    with _active_lock:
        if name in _active_counts:
            _active_counts[name] = max(0, _active_counts[name] - 1)
            if _active_counts[name] == 0:
                del _active_counts[name]


def active_count(name: str) -> int:
    """Return the current active-use counter for *name*."""
    with _active_lock:
        return _active_counts.get(name, 0)


def select_host(active: dict[str, int] | None = None) -> dict:
    """Pick a container host to run a challenge on.

    Parameters
    ----------
    active:
        Optional mapping of host-name -> current active count.  When
        omitted the internal ``acquire_host`` counters are used.  Tests
        can supply this to avoid relying on global state.

    Returns
    -------
    The selected host dict.

    Raises
    ------
    RuntimeError if no hosts are configured.
    """
    hosts = list_hosts()
    if not hosts:
        raise RuntimeError("No container hosts configured in backend/hosts.json")

    with _active_lock:
        counts = dict(_active_counts)
    if active is not None:
        counts.update(active)

    eligible: list[dict] = []
    for host in hosts:
        if not host.get("healthy", True):
            continue
        host_addr: str = host.get("host") or ""
        port: int = host.get("port", 2222)
        name: str = host.get("name") or ""
        if not host_addr or not _health_check_func(host_addr, port):
            continue
        current = counts.get(name, 0)
        max_challenges = host.get("max_challenges") or 0
        if max_challenges > 0 and current >= max_challenges:
            continue
        eligible.append(host)

    if eligible:
        global _round_robin_index
        with _active_lock:
            idx = _round_robin_index % len(eligible)
            _round_robin_index += 1
        return eligible[idx]

    # Fallback: first host marked healthy, ignoring capacity and reachability.
    for host in hosts:
        if host.get("healthy", True):
            return host

    # Last resort if every host is marked unhealthy.
    return hosts[0]
