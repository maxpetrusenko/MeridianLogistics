from __future__ import annotations

import os
import unittest
from unittest import mock

from backend.app.config import load_config
from backend.app.main import create_app
from backend.app.jobs.store import InMemoryJobStore
from backend.app.session.store import InMemorySessionStore
from backend.app.state.database import connect_state_database
from backend.app.storage.context import load_storage_context
from backend.app.storage.service import StorageService


class StorageConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_names = [
            "MERIDIAN_DATABASE_URL",
            "MERIDIAN_DIRECT_DATABASE_URL",
            "MERIDIAN_STATE_DATABASE_URL",
            "MERIDIAN_B2_PROVIDER",
            "MERIDIAN_B2_ENDPOINT",
            "MERIDIAN_B2_BUCKET_NAME",
            "MERIDIAN_B2_ACCESS_KEY_ID",
            "MERIDIAN_B2_SECRET_ACCESS_KEY",
            "MERIDIAN_B2_PREFIX",
        ]
        self._previous_env = {name: os.environ.get(name) for name in self._env_names}

    def tearDown(self) -> None:
        for name, value in self._previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_load_config_reads_direct_database_url_and_b2_settings(self) -> None:
        os.environ["MERIDIAN_DATABASE_URL"] = "postgresql+psycopg://app@db/meridian"
        os.environ["MERIDIAN_DIRECT_DATABASE_URL"] = "postgresql+psycopg://direct@db/meridian"
        os.environ["MERIDIAN_STATE_DATABASE_URL"] = "sqlite:////tmp/meridian-state.sqlite3"
        os.environ["MERIDIAN_B2_ENDPOINT"] = "https://s3.us-west-004.backblazeb2.com"
        os.environ["MERIDIAN_B2_BUCKET_NAME"] = "meridian-artifacts"
        os.environ["MERIDIAN_B2_ACCESS_KEY_ID"] = "key-id"
        os.environ["MERIDIAN_B2_SECRET_ACCESS_KEY"] = "secret-key"
        os.environ["MERIDIAN_B2_PREFIX"] = "dev"

        config = load_config()

        self.assertEqual(config.database_url, "postgresql+psycopg://app@db/meridian")
        self.assertEqual(config.direct_database_url, "postgresql+psycopg://direct@db/meridian")
        self.assertEqual(config.state_database_url, "sqlite:////tmp/meridian-state.sqlite3")
        self.assertEqual(config.b2_endpoint, "https://s3.us-west-004.backblazeb2.com")
        self.assertEqual(config.b2_bucket_name, "meridian-artifacts")
        self.assertEqual(config.b2_access_key_id, "key-id")
        self.assertEqual(config.b2_secret_access_key, "secret-key")
        self.assertEqual(config.b2_prefix, "dev")

    def test_storage_context_exposes_provider_bucket_and_prefix(self) -> None:
        os.environ["MERIDIAN_B2_ENDPOINT"] = "https://s3.us-west-004.backblazeb2.com"
        os.environ["MERIDIAN_B2_BUCKET_NAME"] = "meridian-artifacts"
        os.environ["MERIDIAN_B2_ACCESS_KEY_ID"] = "key-id"
        os.environ["MERIDIAN_B2_SECRET_ACCESS_KEY"] = "secret-key"
        os.environ["MERIDIAN_B2_PREFIX"] = "test-prefix"

        context = load_storage_context()

        self.assertEqual(context.provider, "backblaze_b2")
        self.assertEqual(context.bucket_name, "meridian-artifacts")
        self.assertEqual(context.endpoint, "https://s3.us-west-004.backblazeb2.com")
        self.assertEqual(context.prefix, "test-prefix")

    def test_storage_service_is_unconfigured_without_b2_values(self) -> None:
        for name in (
            "MERIDIAN_B2_ENDPOINT",
            "MERIDIAN_B2_BUCKET_NAME",
            "MERIDIAN_B2_ACCESS_KEY_ID",
            "MERIDIAN_B2_SECRET_ACCESS_KEY",
        ):
            os.environ.pop(name, None)

        service = StorageService(load_storage_context())

        self.assertFalse(service.is_configured)
        with self.assertRaisesRegex(RuntimeError, "storage is not configured"):
            service.require_configured()

    def test_app_state_exposes_storage_service(self) -> None:
        app = create_app()

        self.assertTrue(hasattr(app.state, "storage_service"))

    @mock.patch("backend.app.state.database.sqlite3.connect")
    @mock.patch("backend.app.state.database._connect_postgres")
    def test_state_stores_use_postgres_driver_for_postgres_urls(
        self,
        connect_postgres: mock.MagicMock,
        sqlite_connect: mock.MagicMock,
    ) -> None:
        fake_connection = mock.MagicMock()
        connect_postgres.return_value = fake_connection
        sqlite_connect.side_effect = AssertionError("sqlite should not be used for postgres urls")

        InMemorySessionStore(database_url="postgresql+psycopg://postgres:postgres@localhost:5432/meridian")
        InMemoryJobStore(database_url="postgresql+psycopg://postgres:postgres@localhost:5432/meridian")

        self.assertEqual(connect_postgres.call_count, 2)
        sqlite_connect.assert_not_called()

    @mock.patch("backend.app.state.database.sqlite3.connect")
    @mock.patch("backend.app.state.database._connect_postgres")
    def test_create_app_defaults_to_sqlite_state_database_without_override(
        self,
        connect_postgres: mock.MagicMock,
        sqlite_connect: mock.MagicMock,
    ) -> None:
        os.environ.pop("MERIDIAN_STATE_DATABASE_URL", None)
        fake_connection = mock.MagicMock()
        sqlite_connect.return_value = fake_connection

        app = create_app()

        self.assertTrue(app.state.config.state_database_url.startswith("sqlite:///"))
        self.assertEqual(sqlite_connect.call_count, 3)
        connect_postgres.assert_not_called()

    def test_postgres_state_connection_enables_autocommit(self) -> None:
        postgres_url = os.environ.get("MERIDIAN_POSTGRES_TEST_URL")
        if not postgres_url:
            self.skipTest("MERIDIAN_POSTGRES_TEST_URL not set")

        connection = connect_state_database(postgres_url)
        try:
            self.assertTrue(connection.autocommit)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
