from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.app.api.identity import TrustedIdentity
from backend.app.main import create_app


class ChatAuthSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._previous_state_database_url = os.environ.get("MERIDIAN_STATE_DATABASE_URL")
        self._previous_app_env = os.environ.get("MERIDIAN_APP_ENV")
        os.environ["MERIDIAN_STATE_DATABASE_URL"] = f"sqlite:///{self._temp_dir.name}/state.sqlite3"

    def tearDown(self) -> None:
        if self._previous_state_database_url is None:
            os.environ.pop("MERIDIAN_STATE_DATABASE_URL", None)
        else:
            os.environ["MERIDIAN_STATE_DATABASE_URL"] = self._previous_state_database_url
        if self._previous_app_env is None:
            os.environ.pop("MERIDIAN_APP_ENV", None)
        else:
            os.environ["MERIDIAN_APP_ENV"] = self._previous_app_env
        self._temp_dir.cleanup()

    def _request_payload(self) -> dict[str, object]:
        return {
            "prompt": "Show shipment 88219 details.",
            "broker_id": "broker-999",
            "office_id": "atlanta",
            "role": "broker",
            "current_module": "dispatch_board",
            "current_resource": {
                "resource_type": "shipment",
                "resource_id": "88219",
                "resource_fingerprint": "shipment:88219:v1",
            },
        }

    def _client(
        self,
        *,
        app_env: str,
        trusted_identity: TrustedIdentity | None = None,
    ) -> TestClient:
        os.environ["MERIDIAN_APP_ENV"] = app_env
        app = create_app()
        if trusted_identity is not None:
            @app.middleware("http")
            async def inject_trusted_identity(request, call_next):
                request.state.trusted_chat_identity = trusted_identity
                return await call_next(request)

        return TestClient(app)

    def _seeded_identity(self) -> TrustedIdentity:
        app = create_app()
        broker = app.state.read_repository.brokers_for_office("memphis", role="broker")[0]
        return TrustedIdentity(
            broker_id=str(broker["broker_id"]),
            office_id=str(broker["office_id"]),
            role=str(broker["role"]),
        )

    def test_chat_rejects_direct_identity_headers_without_trusted_middleware(self) -> None:
        client = self._client(app_env="development")

        response = client.post(
            "/chat",
            json=self._request_payload(),
            headers={
                "x-meridian-broker-id": "broker-999",
                "x-meridian-office-id": "atlanta",
                "x-meridian-role": "broker",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "untrusted auth context")

    def test_chat_fails_closed_without_server_identity_in_production(self) -> None:
        client = self._client(app_env="production")

        response = client.post("/chat", json=self._request_payload())

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "server auth context unavailable")

    def test_chat_uses_trusted_request_state_for_valid_identity(self) -> None:
        client = self._client(
            app_env="production",
            trusted_identity=self._seeded_identity(),
        )

        response = client.post("/chat", json=self._request_payload())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["audit"]["actor_role"], "broker")
        self.assertEqual(payload["audit"]["office_scope"], "memphis")

    def test_chat_rejects_trusted_identity_that_is_not_in_repository_scope(self) -> None:
        client = self._client(
            app_env="production",
            trusted_identity=TrustedIdentity(
                broker_id="broker-999",
                office_id="atlanta",
                role="broker",
            ),
        )

        response = client.post("/chat", json=self._request_payload())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "unknown auth context")


if __name__ == "__main__":
    unittest.main()
