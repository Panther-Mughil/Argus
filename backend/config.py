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
    
    # Container-host registry (mirrors models.json; supports multi-host load balancing).
    ARGUS_HOSTS_PATH: str = "backend/hosts.json"
    
    # Uploaded challenge artifacts (stored locally, gitignored).
    ARGUS_ARTIFACTS_DIR: str = "backend/artifacts"
    # Per-file upload cap, in MB.
    ARGUS_MAX_UPLOAD_SIZE_MB: int = 500
    
    # Model / LLM client.
    ARGUS_MODEL: str = ""  # empty -> first model in models.json
    ARGUS_LLM_TIMEOUT: int = 120
    ARGUS_LLM_MAX_TOKENS: int = 4096
    
    # API Keys for free providers.
    ARGUS_OPENROUTER_API_KEY: str = ""
    ARGUS_GROQ_API_KEY: str = ""
    
    # Agent loop guardrails.
    ARGUS_MAX_ITERATIONS: int = 30
    ARGUS_MAX_RUN_SECONDS: int = 1800
    # Consecutive identical failing commands before the loop nudges the model to switch strategy.
    ARGUS_STALE_ATTEMPT_THRESHOLD: int = 3
    # Consecutive tool calls without new info before the loop nudges the model to switch strategy.
    ARGUS_STAGNATION_TURNS: int = 6
    # Cap on a single tool result fed back into the model context (chars).
    ARGUS_MAX_TOOL_OUTPUT_CHARS: int = 6000
    
    # Sandbox root directory prefix (per-challenge workspace root).
    ARGUS_SANDBOX_ROOT: str = "/workspace"
    # Subdirectory names inside each challenge workspace.
    ARGUS_ORIGINALS_DIR: str = "originals"
    ARGUS_WORK_DIR: str = "work"
    
    # Database.
    ARGUS_DATABASE_URL: str = "postgresql+asyncpg://argus:argus_password@localhost:5432/argus_db"
    
    # JWT Configuration
    ARGUS_JWT_SECRET: str = "dev-secret-key"
    ARGUS_JWT_EXPIRES_MINUTES: int = 1440
    
    # Admin User Configuration
    ARGUS_ADMIN_USERNAME: str = "admin"
    ARGUS_ADMIN_EMAIL: str = "admin@argus.local"
    ARGUS_ADMIN_PASSWORD: str = "admin"
    
    @property
    def resolved_ssh_key_path(self) -> str:
        """Resolve the SSH key path relative to the project root."""
        project_root = Path(__file__).resolve().parent.parent
        key_path = Path(self.ARGUS_CONTAINER_SSH_KEY)
        if not key_path.is_absolute():
            key_path = project_root / key_path
        return str(key_path)
    
    @property
    def resolved_artifacts_dir(self) -> str:
        """Resolve the artifacts dir relative to the project root."""
        project_root = Path(__file__).resolve().parent.parent
        artifacts_path = Path(self.ARGUS_ARTIFACTS_DIR)
        if not artifacts_path.is_absolute():
            artifacts_path = project_root / artifacts_path
        return str(artifacts_path)
    
    @property
    def max_upload_size_bytes(self) -> int:
        """Per-file upload cap expressed in bytes."""
        return self.ARGUS_MAX_UPLOAD_SIZE_MB * 1024 * 1024
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()