from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


ROOT_DIR = Path(__file__).resolve().parents[2]


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/meridian_logistics"
    redis_url: str = "redis://localhost:6379/0"
    contracts_dir: Path = ROOT_DIR / "contracts"
    memphis_office_id: str = "memphis"
    controller_checkpoints_enabled: bool = False
    controller_precedence_enabled: bool = False
    controller_checkpoint_dir: Path = ROOT_DIR / ".controller-checkpoints"


def load_config() -> AppConfig:
    return AppConfig(
        app_env=os.getenv("MERIDIAN_APP_ENV", "development"),
        database_url=os.getenv(
            "MERIDIAN_DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/meridian_logistics",
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
    )
