from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Argus application settings.

    Reads from project-root .env if present; provides sensible defaults
    so the app runs without the file (local podman mode).
    """

    ARGUS_CONTAINER_HOST: str = "10.0.2.6"
    ARGUS_CONTAINER_PORT: int = 2222
    ARGUS_CONTAINER_USER: str = "root"
    ARGUS_CONTAINER_SSH_KEY: str = "/mnt/D/Shared/Mughil/Personal/HomeLab/SSH_Keys/argus"
    ARGUS_CONTAINER_CMD_TIMEOUT: int = 120

    @property
    def resolved_ssh_key_path(self) -> str:
        """Resolve the SSH key path relative to the project root."""
        project_root = Path(__file__).resolve().parent.parent
        key_path = Path(self.ARGUS_CONTAINER_SSH_KEY)
        if not key_path.is_absolute():
            key_path = project_root / key_path
        return str(key_path)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
