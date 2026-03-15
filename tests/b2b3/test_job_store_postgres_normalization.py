from __future__ import annotations

from datetime import UTC, datetime
import unittest
from unittest.mock import patch

from backend.app.api.schemas.chat import AsyncJobEnvelope
from backend.app.jobs.store import InMemoryJobStore
from backend.app.state.database import execute_query as run_query


class _Cursor:
    def __init__(self, row: dict[str, object]) -> None:
        self._row = row

    def fetchone(self) -> dict[str, object]:
        return self._row


class JobStorePostgresNormalizationTests(unittest.TestCase):
    def _prepared_result(self, *, session_id: str, job_id: str) -> dict[str, object]:
        return {
            "contract_version": "0.1.0",
            "response_id": "resp_complete",
            "request_id": "req_complete",
            "trace_id": "trace_complete",
            "session_id": session_id,
            "conversation_scope": "analytics",
            "context_binding_state": "bound",
            "screen_sync_state": "not_applicable",
            "active_resource": None,
            "job_id": job_id,
            "job_poll_token": "jobpoll_token_123456",
            "intent_class": "read_result",
            "status": "success",
            "summary": "Background refresh completed.",
            "follow_up_prompt": None,
            "components": [],
            "actions": [],
            "policy": {
                "permission_context_applied": True,
                "sensitive_fields_redacted": True,
                "write_confirmation_required": False,
                "denial_reason_class": "none",
            },
            "audit": {
                "actor_role": "broker",
                "office_scope": "memphis",
                "tool_path": ["shipment_exception_lookup"],
                "response_generated_at": "2026-03-15T12:05:00Z",
            },
        }

    def test_row_to_job_accepts_postgres_native_json_and_timestamps(self) -> None:
        store = InMemoryJobStore()
        row = {
            "job_id": "job_20260315_abcdef123456",
            "session_id": "chat_s_20260315_0001",
            "broker_id": "broker-123",
            "office_id": "memphis",
            "job_status": "succeeded",
            "created_at": datetime(2026, 3, 15, 12, 0, tzinfo=UTC),
            "updated_at": datetime(2026, 3, 15, 12, 5, tzinfo=UTC),
            "progress_message": "Background refresh completed.",
            "retry_allowed": True,
            "pending_response_id": "resp_pending",
            "completed_response_id": "resp_complete",
            "result_payload": self._prepared_result(
                session_id="chat_s_20260315_0001",
                job_id="job_20260315_abcdef123456",
            ),
            "job_poll_token": "jobpoll_token_123456",
            "completion_refreshes_remaining": 0,
            "completion_ready_at": 0.0,
        }

        job = store._row_to_job(row)

        self.assertEqual(job.created_at, "2026-03-15T12:00:00Z")
        self.assertEqual(job.updated_at, "2026-03-15T12:05:00Z")
        self.assertEqual(job.result["response_id"], "resp_complete")
        envelope = AsyncJobEnvelope.model_validate(job.to_api_dict())
        self.assertEqual(envelope.completed_response_id, "resp_complete")

    def test_refresh_job_accepts_postgres_native_prepared_payload(self) -> None:
        store = InMemoryJobStore(completion_refresh_polls=0)
        job = store.create_job(
            session_id="chat_s_20260315_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh queued.",
            retry_allowed=True,
        )
        started = store.start_job(job.job_id, progress_message="Background refresh running.")
        self.assertIsNotNone(started)

        prepared_result = self._prepared_result(session_id=job.session_id, job_id=job.job_id)

        def patched_execute_query(connection, query, parameters=()):
            if "SELECT prepared_result_payload, completion_refreshes_remaining" in query:
                return _Cursor(
                    {
                        "prepared_result_payload": prepared_result,
                        "completion_refreshes_remaining": 0,
                    }
                )
            return run_query(connection, query, parameters)

        with patch("backend.app.jobs.store.execute_query", side_effect=patched_execute_query):
            completed = store.refresh_job(job.job_id)

        self.assertIsNotNone(completed)
        assert completed is not None
        self.assertEqual(completed.status, "succeeded")
        self.assertEqual(completed.result["response_id"], "resp_complete")


if __name__ == "__main__":
    unittest.main()
