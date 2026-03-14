from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.app.config import ROOT_DIR, load_config


@dataclass(frozen=True)
class DatabaseContext:
    database_url: str
    schema_file: Path
    views_file: Path
    migrations_dir: Path
    seeds_dir: Path
    seed_bundle_file: Path


def load_database_context() -> DatabaseContext:
    config = load_config()
    return DatabaseContext(
        database_url=config.database_url,
        schema_file=ROOT_DIR / "db" / "schema.sql",
        views_file=ROOT_DIR / "db" / "views.sql",
        migrations_dir=ROOT_DIR / "db" / "migrations",
        seeds_dir=ROOT_DIR / "db" / "seeds",
        seed_bundle_file=ROOT_DIR / "db" / "seeds" / "memphis_seed_bundle.json",
    )
