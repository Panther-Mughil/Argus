"""Local, on-disk storage for uploaded challenge artifacts.

Files are stored under ``ARGUS_ARTIFACTS_DIR`` (default
``backend/artifacts``), keyed by challenge id.  There is **no** database
table for files — they live purely on disk (and are gitignored).

Uploads are streamed to disk in chunks so that arbitrarily large files
never have to be buffered entirely in memory.
"""

import shutil
from pathlib import Path

from backend.config import settings


class OversizeError(Exception):
    """Raised when an upload exceeds the configured per-file size cap.

    Callers should map this to an HTTP ``413`` response.
    """


def artifacts_root() -> Path:
    """Return the absolute path to the artifacts root directory."""
    return Path(settings.resolved_artifacts_dir)


def challenge_dir(challenge_id: int) -> Path:
    """Return the directory that stores a challenge's uploaded files."""
    return artifacts_root() / str(challenge_id)


def sanitize_filename(filename: str) -> str:
    """Strip path components and reject dangerous/empty names.

    Returns the bare filename.  Raises ``ValueError`` if the result is
    empty or one of ``"."`` / ``".."``.
    """
    name = Path(filename).name
    if name in ("", ".", ".."):
        raise ValueError(f"Invalid filename: {filename!r}")
    return name


def save_upload(challenge_id: int, filename: str, stream) -> Path:
    """Write an upload stream to disk in chunks.

    Parameters
    ----------
    challenge_id:
        The owning challenge, used as the storage subdirectory.
    filename:
        Original (possibly path-containing) filename; sanitized here.
    stream:
        A binary file-like object supporting ``read(size)``.

    Returns
    -------
    Path to the stored file.

    Raises
    ------
    OversizeError
        If the running total exceeds ``ARGUS_MAX_UPLOAD_SIZE_MB``.  Any
        partial file is removed before raising.
    """
    dest_dir = challenge_dir(challenge_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(filename)
    dest = dest_dir / safe_name

    max_bytes = settings.max_upload_size_bytes
    total = 0
    try:
        # Open in wb mode so we can clean up a partial file via unlink.
        with dest.open("wb") as fh:
            while True:
                chunk = stream.read(1024 * 1024)  # 1 MiB chunks
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise OversizeError(
                        f"File exceeds {settings.ARGUS_MAX_UPLOAD_SIZE_MB} MB limit"
                    )
                fh.write(chunk)
    except BaseException:
        # Leave no partial file behind on error/oversize.
        dest.unlink(missing_ok=True)
        raise
    return dest


def list_files(challenge_id: int) -> list:
    """Return ``[(filename, size), ...]`` for a challenge's uploads."""
    directory = challenge_dir(challenge_id)
    if not directory.exists():
        return []
    result = []
    try:
        entries = sorted(directory.iterdir())
    except OSError:
        return []
    for path in entries:
        try:
            if path.is_file():
                result.append((path.name, path.stat().st_size))
        except OSError:
            # File may have been removed concurrently; skip it.
            continue
    return result


def delete_challenge_files(challenge_id: int) -> None:
    """Recursively remove a challenge's artifacts directory (if present)."""
    directory = challenge_dir(challenge_id)
    if directory.exists():
        try:
            shutil.rmtree(directory, ignore_errors=True)
        except OSError:
            # Best-effort cleanup; ignore failures.
            pass
