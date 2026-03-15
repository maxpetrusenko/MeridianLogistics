from __future__ import annotations

from dataclasses import dataclass

from backend.app.config import load_config


@dataclass(frozen=True)
class StorageContext:
    provider: str
    bucket_name: str | None
    endpoint: str | None
    prefix: str
    access_key_id: str | None
    secret_access_key: str | None

    @property
    def is_configured(self) -> bool:
        return all(
            (
                self.bucket_name,
                self.endpoint,
                self.access_key_id,
                self.secret_access_key,
            )
        )


def load_storage_context() -> StorageContext:
    config = load_config()
    return StorageContext(
        provider=config.object_storage_provider,
        bucket_name=config.b2_bucket_name,
        endpoint=config.b2_endpoint,
        prefix=config.b2_prefix.strip("/"),
        access_key_id=config.b2_access_key_id,
        secret_access_key=config.b2_secret_access_key,
    )
