from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


ROOT_DIR = Path(__file__).resolve().parents[2]


def _default_state_database_url() -> str:
    return f"sqlite:///{ROOT_DIR / '.runtime' / 'meridian_state.sqlite3'}"


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/meridian_logistics"
    direct_database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/meridian_logistics"
    state_database_url: str = _default_state_database_url()
    redis_url: str = "redis://localhost:6379/0"
    contracts_dir: Path = ROOT_DIR / "contracts"
    memphis_office_id: str = "memphis"
    controller_checkpoints_enabled: bool = False
    controller_precedence_enabled: bool = False
    controller_checkpoint_dir: Path = ROOT_DIR / ".controller-checkpoints"
    object_storage_provider: str = "backblaze_b2"
    object_storage_prefix: str = "artifacts/dev"
    b2_prefix: str = "artifacts/dev"
    b2_endpoint: str | None = None
    b2_bucket_name: str | None = None
    b2_access_key_id: str | None = None
    b2_secret_access_key: str | None = None
    running_autonomy_enabled: bool = False
    running_autonomy_max_steps: int = 3
    running_autonomy_poll_step_timeout_seconds: int = 5


def load_config() -> AppConfig:
    database_url = os.getenv(
        "MERIDIAN_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/meridian_logistics",
    )
    return AppConfig(
        app_env=os.getenv("MERIDIAN_APP_ENV", "development"),
        database_url=database_url,
        direct_database_url=os.getenv("MERIDIAN_DIRECT_DATABASE_URL", database_url),
        state_database_url=os.getenv(
            "MERIDIAN_STATE_DATABASE_URL",
            _default_state_database_url(),
        ),
        redis_url=os.getenv("MERIDIAN_REDIS_URL", "redis://localhost:6379/0"),
        contracts_dir=ROOT_DIR / os.getenv("MERIDIAN_CONTRACTS_DIR", "contracts"),
        memphis_office_id=os.getenv("MERIDIAN_MEMPHIS_OFFICE_ID", "memphis"),
        controller_checkpoints_enabled=_env_flag(
            "MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED",
            default=False,
        ),
        controller_precedence_enabled=_env_flag(
            "MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED",
            default=False,
        ),
        controller_checkpoint_dir=ROOT_DIR / os.getenv(
            "MERIDIAN_CONTROLLER_CHECKPOINT_DIR",
            ".controller-checkpoints",
        ),
        object_storage_provider=os.getenv(
            "MERIDIAN_OBJECT_STORAGE_PROVIDER",
            os.getenv("MERIDIAN_B2_PROVIDER", "backblaze_b2"),
        ),
        object_storage_prefix=os.getenv(
            "MERIDIAN_OBJECT_STORAGE_PREFIX",
            os.getenv("MERIDIAN_B2_PREFIX", "artifacts/dev"),
        ),
        b2_prefix=os.getenv(
            "MERIDIAN_B2_PREFIX",
            os.getenv("MERIDIAN_OBJECT_STORAGE_PREFIX", "artifacts/dev"),
        ),
        b2_endpoint=os.getenv("MERIDIAN_B2_ENDPOINT"),
        b2_bucket_name=os.getenv("MERIDIAN_B2_BUCKET_NAME"),
        b2_access_key_id=os.getenv("MERIDIAN_B2_ACCESS_KEY_ID"),
        b2_secret_access_key=os.getenv("MERIDIAN_B2_SECRET_ACCESS_KEY"),
        running_autonomy_enabled=_env_flag(
            "MERIDIAN_RUNNING_AUTONOMY_ENABLED",
            default=False,
        ),
        running_autonomy_max_steps=int(os.getenv("MERIDIAN_RUNNING_AUTONOMY_MAX_STEPS", "3")),
        # PHASE 2: Per-step wall-clock timeout enforcement
        # Phase 1 completes immediately; timeout will be enforced when
        # actual step execution is implemented (resume_one_step does work)
        running_autonomy_poll_step_timeout_seconds=int(os.getenv("MERIDIAN_RUNNING_AUTONOMY_POLL_STEP_TIMEOUT_SECONDS", "5")),
    )
