"""
Unit tests for job persistence layer using mocks.

Tests verify:
- JobRepository methods work correctly with mocked DB
- IdempotentJobStore provides idempotency guarantees
- Job-result linkage works
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch, call
from datetime import UTC, datetime

from backend.app.jobs.repository import (
    JobRepository,
    _utc_now,
    _generate_job_id,
    _decode_jsonb,
    _encode_jsonb,
)
from backend.app.jobs.idempotent_store import (
    IdempotentJobStore,
    IdempotentJobResult,
    _job_request_fingerprint,
)


class JobRepositoryUnitTests(unittest.TestCase):
    """Unit tests for JobRepository using mocks."""

    def setUp(self):
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

    def test_generate_job_id_format(self):
        """Job IDs follow expected format."""
        job_id = _generate_job_id()
        self.assertTrue(job_id.startswith("job_"))
        # Format: job_YYYYMMDD_12hex
        parts = job_id.split("_")
        self.assertEqual(len(parts), 3)
        self.assertEqual(len(parts[1]), 8)  # YYYYMMDD
        self.assertEqual(len(parts[2]), 12)  # 12 hex chars

    def test_utc_now_format(self):
        """Timestamp format is ISO."""
        ts = _utc_now()
        self.assertIn("T", ts)
        self.assertIn("Z", ts)

    def test_jsonb_encode_decode(self):
        """JSONB encoding/encoding works."""
        data = {"key": "value", "nested": {"count": 42}}
        encoded = _encode_jsonb(data)
        self.assertIsInstance(encoded, str)

        decoded = _decode_jsonb(encoded)
        self.assertEqual(decoded, data)

        self.assertIsNone(_decode_jsonb(None))
        self.assertIsNone(_encode_jsonb(None))

    def test_fingerprint_deterministic(self):
        """Request fingerprints are deterministic."""
        params = {
            "session_id": "session-1",
            "office_id": "memphis",
            "broker_id": "broker-1",
            "job_kind": "analytics",
            "request_context": {"filter": "active"},
        }

        fp1 = _job_request_fingerprint(**params)
        fp2 = _job_request_fingerprint(**params)

        self.assertEqual(fp1, fp2)
        self.assertEqual(len(fp1), 16)  # SHA256[:16]

    def test_fingerprint_different_params(self):
        """Different params produce different fingerprints."""
        base = {
            "session_id": "session-1",
            "office_id": "memphis",
            "broker_id": "broker-1",
            "job_kind": "analytics",
        }

        fp1 = _job_request_fingerprint(**base)
        fp2 = _job_request_fingerprint(**{**base, "job_kind": "refresh"})

        self.assertNotEqual(fp1, fp2)

    @patch("backend.app.jobs.repository._connect_postgres")
    def test_create_job_execution(self, mock_connect):
        """Create job executes correct SQL."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchone.return_value = {
            "job_id": "job_test",
            "session_id": "session-1",
            "office_id": "memphis",
            "broker_id": "broker-1",
            "job_kind": "analytics",
            "job_status": "queued",
            "progress_message": "Queued",
            "retry_allowed": False,
            "pending_response_id": None,
            "completed_response_id": None,
            "result_payload": None,
            "prepared_result_payload": None,
            "job_poll_token": "token123",
            "completion_refreshes_remaining": None,
            "completion_ready_at": None,
            "artifact_key": None,
            "artifact_mime_type": None,
            "artifact_size_bytes": None,
            "created_at": datetime(2026, 3, 15, 12, 0, tzinfo=UTC),
            "updated_at": datetime(2026, 3, 15, 12, 0, tzinfo=UTC),
            "completed_at": None,
        }

        repo = JobRepository(database_url="postgresql://test")
        repo._ensure_schema()  # Set up tables

        result = repo.create(
            session_id="session-1",
            office_id="memphis",
            broker_id="broker-1",
        )

        # Verify INSERT was called
        self.assertTrue(self.mock_cursor.execute.called)
        insert_call = [c for c in self.mock_cursor.execute.call_args_list
                      if "INSERT INTO generation_jobs" in str(c)]
        self.assertTrue(len(insert_call) > 0)

    @patch("backend.app.jobs.repository._connect_postgres")
    def test_row_to_dict_conversion(self, mock_connect):
        """Row conversion handles all fields."""
        mock_connect.return_value = self.mock_conn

        row = {
            "job_id": "job_1",
            "session_id": "sess-1",
            "office_id": "memphis",
            "broker_id": "broker-1",
            "job_kind": "analytics",
            "job_status": "running",
            "progress_message": "Running",
            "retry_allowed": True,
            "pending_response_id": "resp-1",
            "completed_response_id": None,
            "result_payload": '{"data": "test"}',
            "prepared_result_payload": None,
            "job_poll_token": "token",
            "completion_refreshes_remaining": 2,
            "completion_ready_at": 123.45,
            "artifact_key": "key",
            "artifact_mime_type": "text/plain",
            "artifact_size_bytes": 100,
            "created_at": datetime(2026, 3, 15, 12, 0, tzinfo=UTC),
            "updated_at": datetime(2026, 3, 15, 12, 1, tzinfo=UTC),
            "completed_at": None,
        }

        repo = JobRepository(database_url="postgresql://test")
        result = repo._row_to_dict(row)

        self.assertEqual(result["job_id"], "job_1")
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["result"], {"data": "test"})
        self.assertTrue(result["retry_allowed"])


class IdempotentJobStoreUnitTests(unittest.TestCase):
    """Unit tests for IdempotentJobStore."""

    def setUp(self):
        self.mock_repo = MagicMock(spec=JobRepository)
        self.store = IdempotentJobStore(repository=self.mock_repo)

    def test_idempotent_create_returns_created_first_time(self):
        """First create call returns 'created' outcome."""
        self.mock_repo.create.return_value = {
            "job_id": "job-1",
            "status": "queued",
        }

        result = self.store.create_job(
            session_id="sess-1",
            office_id="memphis",
            broker_id="broker-1",
        )

        self.assertEqual(result.outcome, "created")
        self.assertIsNotNone(result.job)
        self.mock_repo.create.assert_called_once()

    def test_idempotent_create_replays_same_request(self):
        """Duplicate request returns 'replayed' outcome."""
        self.mock_repo.create.return_value = {
            "job_id": "job-1",
            "status": "queued",
        }

        # First call
        result1 = self.store.create_job(
            session_id="sess-1",
            office_id="memphis",
            broker_id="broker-1",
        )
        self.assertEqual(result1.outcome, "created")

        # Second call with same params
        result2 = self.store.create_job(
            session_id="sess-1",
            office_id="memphis",
            broker_id="broker-1",
        )
        self.assertEqual(result2.outcome, "replayed")

        # Should only call repo once
        self.mock_repo.create.assert_called_once()

    def test_idempotent_complete_returns_created_first_time(self):
        """First complete call returns 'created' outcome."""
        self.mock_repo.get.return_value = {"status": "running"}
        self.mock_repo.complete.return_value = {
            "job_id": "job-1",
            "status": "succeeded",
            "result": {"response_id": "resp-1"},
        }

        result = self.store.complete_job(
            "job-1",
            result={"response_id": "resp-1"},
        )

        self.assertEqual(result.outcome, "created")
        self.mock_repo.complete.assert_called_once()

    def test_get_job_delegates_to_repo(self):
        """Get operations delegate to repository."""
        self.mock_repo.get.return_value = {"job_id": "job-1"}

        result = self.store.get_job("job-1")

        self.assertEqual(result["job_id"], "job-1")
        self.mock_repo.get.assert_called_once_with("job-1")

    def test_link_artifact_delegates_to_repo(self):
        """Artifact linking delegates to repository."""
        self.mock_repo.link_artifact.return_value = {
            "job_id": "job-1",
            "artifact_key": "artifacts/test.pdf",
        }

        result = self.store.link_artifact(
            "job-1",
            artifact_key="artifacts/test.pdf",
            mime_type="application/pdf",
            size_bytes=1000,
        )

        self.assertEqual(result["artifact_key"], "artifacts/test.pdf")
        self.mock_repo.link_artifact.assert_called_once_with(
            "job-1",
            "artifacts/test.pdf",
            "application/pdf",
            1000,
        )


if __name__ == "__main__":
    unittest.main()
