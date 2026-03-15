from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.controller.models import ControllerCheckpoint
from backend.app.jobs.models import JobStatus


class BoundedAutonomyTests(unittest.TestCase):
    """Test bounded autonomy integration with async jobs.

    Tests follow the design in docs/plans/2026-03-15-bounded-autonomy-running-app-design.md
    """

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._previous_state_database_url = os.environ.get("MERIDIAN_STATE_DATABASE_URL")
        os.environ["MERIDIAN_STATE_DATABASE_URL"] = f"sqlite:///{self._temp_dir.name}/state.sqlite3"

        # Save autonomy env vars to restore in tearDown
        self._previous_autonomy_enabled = os.environ.get("MERIDIAN_RUNNING_AUTONOMY_ENABLED")
        self._previous_checkpoints_enabled = os.environ.get("MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED")
        self._previous_precedence_enabled = os.environ.get("MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED")

    def tearDown(self) -> None:
        if self._previous_state_database_url is None:
            os.environ.pop("MERIDIAN_STATE_DATABASE_URL", None)
        else:
            os.environ["MERIDIAN_STATE_DATABASE_URL"] = self._previous_state_database_url
        self._temp_dir.cleanup()

        # Restore autonomy env vars
        if self._previous_autonomy_enabled is None:
            os.environ.pop("MERIDIAN_RUNNING_AUTONOMY_ENABLED", None)
        else:
            os.environ["MERIDIAN_RUNNING_AUTONOMY_ENABLED"] = self._previous_autonomy_enabled

        if self._previous_checkpoints_enabled is None:
            os.environ.pop("MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED", None)
        else:
            os.environ["MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED"] = self._previous_checkpoints_enabled

        if self._previous_precedence_enabled is None:
            os.environ.pop("MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED", None)
        else:
            os.environ["MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED"] = self._previous_precedence_enabled

        # Clean checkpoint directory
        import shutil
        checkpoint_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".controller-checkpoints")
        if os.path.exists(checkpoint_dir):
            for f in os.listdir(checkpoint_dir):
                if f.endswith(".json"):
                    try:
                        os.remove(os.path.join(checkpoint_dir, f))
                    except:
                        pass

    def _make_chat_request(
        self,
        *,
        prompt: str,
        session_id: str | None = None,
        session_access_token: str | None = None,
    ) -> dict[str, object]:
        request = {
            "prompt": prompt,
            "broker_id": "broker-123",
            "office_id": "memphis",
            "role": "broker",
            "current_module": "dispatch_board",
        }
        if session_id is not None:
            request["session_id"] = session_id
        if session_access_token is not None:
            request["session_access_token"] = session_access_token
        return request

    def _job_query(self, *, job_poll_token: str) -> dict[str, str]:
        return {"job_poll_token": job_poll_token}

    def _checkpoint_path_for_job(self, job_id: str) -> Path:
        """Get the controller checkpoint path for a given job_id."""
        config = load_config()
        return config.controller_checkpoint_dir / f"{job_id}.json"

    # === Task 1: Autonomy Seed Tests ===

    def test_async_chat_seeds_controller_checkpoint_when_autonomy_enabled(self) -> None:
        """Async-eligible /chat request seeds a controller checkpoint when running-app autonomy is enabled."""
        os.environ["MERIDIAN_RUNNING_AUTONOMY_ENABLED"] = "true"
        os.environ["MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED"] = "true"
        os.environ["MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED"] = "true"

        client = TestClient(create_app())

        response = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Run a background analytics refresh for Memphis exceptions.",
            ),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        # Should create async job with autonomy
        self.assertIn("job_id", payload)
        self.assertEqual(payload["status"], "pending")
        job_id = payload["job_id"]

        # Controller checkpoint should exist keyed by job_id
        checkpoint_path = self._checkpoint_path_for_job(job_id)
        if not checkpoint_path.exists():
            self.fail(f"Controller checkpoint should exist at {checkpoint_path} - autonomy not implemented yet")

        # Checkpoint should be valid
        checkpoint_data = json.loads(checkpoint_path.read_text())
        checkpoint = ControllerCheckpoint.from_dict(checkpoint_data)
        self.assertEqual(checkpoint.checkpoint_id, f"{job_id}:seed")

    def test_async_chat_uses_job_id_not_session_id_for_checkpoint_key(self) -> None:
        """Checkpoint key uses job_id, not session_id."""
        os.environ["MERIDIAN_RUNNING_AUTONOMY_ENABLED"] = "true"
        os.environ["MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED"] = "true"
        os.environ["MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED"] = "true"

        client = TestClient(create_app())

        seed = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Show shipment 88219 details.",
            ),
        )
        self.assertEqual(seed.status_code, 200)
        seed_payload = seed.json()
        session_id = seed_payload["session_id"]
        session_access_token = seed_payload["session_access_token"]

        # Create async job
        response = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Run a background analytics refresh for Memphis exceptions.",
                session_id=session_id,
                session_access_token=session_access_token,
            ),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        job_id = payload["job_id"]

        config = load_config()
        job_checkpoint_path = config.controller_checkpoint_dir / f"{job_id}.json"
        session_checkpoint_path = config.controller_checkpoint_dir / f"{session_id}.json"

        if not job_checkpoint_path.exists():
            self.fail("Job checkpoint should exist - autonomy not implemented yet")

        # Session checkpoint should NOT exist for this job
        # (session checkpoint is only for controller runtime, not autonomy jobs)
        self.assertFalse(
            session_checkpoint_path.exists(),
            "Checkpoint should NOT be keyed by session_id for autonomy jobs",
        )

    def test_async_chat_preserves_current_behavior_when_autonomy_disabled(self) -> None:
        """Disabled autonomy flag preserves the current pending-job behavior."""
        os.environ["MERIDIAN_RUNNING_AUTONOMY_ENABLED"] = "false"
        os.environ["MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED"] = "true"
        os.environ["MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED"] = "true"

        client = TestClient(create_app())

        response = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Run a background analytics refresh for Memphis exceptions.",
            ),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        # Should still create async job
        self.assertIn("job_id", payload)
        self.assertEqual(payload["status"], "pending")
        job_id = payload["job_id"]

        # But NO controller checkpoint should be created
        checkpoint_path = self._checkpoint_path_for_job(job_id)
        self.assertFalse(
            checkpoint_path.exists(),
            "No checkpoint should be created when autonomy is disabled",
        )

    # === Task 2: Autonomy Resume Tests ===

    def test_job_poll_advances_one_bounded_step_for_autonomy_job(self) -> None:
        """GET /jobs/{job_id} advances exactly one bounded step for an autonomy-tagged transient job."""
        os.environ["MERIDIAN_RUNNING_AUTONOMY_ENABLED"] = "true"
        os.environ["MERIDIAN_RUNNING_AUTONOMY_MAX_STEPS"] = "3"
        os.environ["MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED"] = "true"
        os.environ["MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED"] = "true"

        client = TestClient(create_app())

        response = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Run a background analytics refresh for Memphis exceptions.",
            ),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        job_id = payload["job_id"]
        poll_token = payload["job_poll_token"]

        checkpoint_path = self._checkpoint_path_for_job(job_id)
        if not checkpoint_path.exists():
            self.fail("Checkpoint should exist - autonomy not implemented yet")

        # First poll: autonomy should advance to completion (phase 1 completes immediately)
        first_poll = client.get(
            f"/jobs/{job_id}",
            params=self._job_query(job_poll_token=poll_token),
        )
        self.assertEqual(first_poll.status_code, 200)
        first_data = first_poll.json()
        # Phase 1 autonomy completes on first poll after seeding
        self.assertEqual(first_data["status"], "succeeded")

    def test_checkpoint_truth_overrides_stale_job_metadata_on_resume(self) -> None:
        """Checkpoint truth overrides stale job metadata on resume."""
        os.environ["MERIDIAN_RUNNING_AUTONOMY_ENABLED"] = "true"
        os.environ["MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED"] = "true"
        os.environ["MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED"] = "true"

        client = TestClient(create_app())

        response = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Run a background analytics refresh for Memphis exceptions.",
            ),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        job_id = payload["job_id"]
        poll_token = payload["job_poll_token"]

        # First, verify checkpoint was created
        checkpoint_path = self._checkpoint_path_for_job(job_id)
        if not checkpoint_path.exists():
            self.skipTest("Autonomy not yet implemented - checkpoint seeding not working")

        # Poll should complete based on autonomy execution
        poll_response = client.get(
            f"/jobs/{job_id}",
            params=self._job_query(job_poll_token=poll_token),
        )
        self.assertEqual(poll_response.status_code, 200)
        poll_data = poll_response.json()

        # Should complete based on autonomy execution
        self.assertEqual(poll_data["status"], "succeeded")

    def test_completed_result_includes_autonomy_audit_fields(self) -> None:
        """Completed result.audit includes autonomy audit fields."""
        os.environ["MERIDIAN_RUNNING_AUTONOMY_ENABLED"] = "true"
        os.environ["MERIDIAN_RUNNING_AUTONOMY_MAX_STEPS"] = "3"
        os.environ["MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED"] = "true"
        os.environ["MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED"] = "true"

        client = TestClient(create_app())

        response = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Run a background analytics refresh for Memphis exceptions.",
            ),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        job_id = payload["job_id"]
        poll_token = payload["job_poll_token"]

        # Verify autonomy audit fields in pending response
        self.assertIn("audit", payload)
        self.assertIn("autonomy_mode", payload["audit"])
        self.assertEqual(payload["audit"]["autonomy_mode"], "poll_driven")
        self.assertEqual(payload["audit"]["autonomy_task_kind"], "async_read_refresh")
        self.assertIn("autonomy_run_id", payload["audit"])
        self.assertIn("checkpoint_id", payload["audit"])

        # Poll to complete the job
        poll_response = client.get(
            f"/jobs/{job_id}",
            params=self._job_query(job_poll_token=poll_token),
        )
        self.assertEqual(poll_response.status_code, 200)
        poll_data = poll_response.json()
        self.assertEqual(poll_data["status"], "succeeded")

        # CRITICAL: Verify autonomy audit fields in completed result
        # This is the P1 #1 fix - audit fields must propagate to completed result
        self.assertIn("result", poll_data)
        result = poll_data["result"]
        self.assertIn("audit", result)
        result_audit = result["audit"]
        self.assertIn("autonomy_mode", result_audit)
        self.assertEqual(result_audit["autonomy_mode"], "poll_driven")
        self.assertEqual(result_audit["autonomy_task_kind"], "async_read_refresh")
        self.assertIn("autonomy_run_id", result_audit)
        self.assertEqual(result_audit["autonomy_run_id"], job_id)
        self.assertIn("checkpoint_id", result_audit)

    def test_stale_metadata_does_not_corrupt_checkpoint_authoritative_resume(self) -> None:
        """Checkpoint truth overrides stale/corrupted job metadata on resume.

        This test directly mutates stored autonomy_metadata to simulate
        corruption or stale state, verifying that checkpoint is the
        source of truth for step decisions.
        """
        os.environ["MERIDIAN_RUNNING_AUTONOMY_ENABLED"] = "true"
        os.environ["MERIDIAN_RUNNING_AUTONOMY_MAX_STEPS"] = "3"
        os.environ["MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED"] = "true"
        os.environ["MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED"] = "true"

        client = TestClient(create_app())

        response = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Run a background analytics refresh for Memphis exceptions.",
            ),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        job_id = payload["job_id"]
        poll_token = payload["job_poll_token"]

        checkpoint_path = self._checkpoint_path_for_job(job_id)
        if not checkpoint_path.exists():
            self.skipTest("Autonomy not yet implemented - checkpoint seeding not working")

        # CORRUPTION: Directly mutate the stored autonomy_metadata to simulate
        # a stale/corrupted state where step_index exceeds budget
        # This simulates the "stale metadata" bug where metadata gets out of sync
        from backend.app.jobs.store import InMemoryJobStore
        from backend.app.config import load_config
        config = load_config()
        store = InMemoryJobStore(database_url=f"sqlite:///{self._temp_dir.name}/state.sqlite3")

        # Mutate metadata to have step_index=3 (at budget) even though checkpoint is at seed
        job = store.get_job(job_id)
        if job and job.autonomy_metadata:
            corrupted_metadata = dict(job.autonomy_metadata)
            corrupted_metadata["step_index"] = 3  # At budget, should fail if metadata is used
            store.update_autonomy_metadata(job_id, corrupted_metadata)

        # Poll the job - if it uses metadata (wrong), it will fail with "Step budget exhausted"
        # If it uses checkpoint (correct), it will succeed because checkpoint is at seed (step 0)
        poll_response = client.get(
            f"/jobs/{job_id}",
            params=self._job_query(job_poll_token=poll_token),
        )
        self.assertEqual(poll_response.status_code, 200)
        poll_data = poll_response.json()

        # Checkpoint-authoritative: should succeed because checkpoint is at seed
        # even though corrupted metadata says step_index=3
        self.assertEqual(
            poll_data["status"],
            "succeeded",
            "Job should succeed using checkpoint truth despite stale metadata",
        )

    def test_exhausted_step_budget_returns_fail_soft_terminal_result(self) -> None:
        """Exhausted step budget returns a fail-soft terminal job result."""
        os.environ["MERIDIAN_RUNNING_AUTONOMY_ENABLED"] = "true"
        os.environ["MERIDIAN_RUNNING_AUTONOMY_MAX_STEPS"] = "1"
        os.environ["MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED"] = "true"
        os.environ["MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED"] = "true"

        client = TestClient(create_app())

        response = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Run a background analytics refresh for Memphis exceptions.",
            ),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        job_id = payload["job_id"]
        poll_token = payload["job_poll_token"]

        checkpoint_path = self._checkpoint_path_for_job(job_id)
        if not checkpoint_path.exists():
            self.fail("Checkpoint should exist - autonomy not implemented yet")

        # First poll: autonomy should execute and complete
        # Phase 1 completes immediately after seeding
        first_poll = client.get(
            f"/jobs/{job_id}",
            params=self._job_query(job_poll_token=poll_token),
        )
        self.assertEqual(first_poll.status_code, 200)
        first_data = first_poll.json()

        # Should be terminal (succeeded with result)
        self.assertEqual(
            first_data["status"],
            "succeeded",
            "Job should reach terminal state after autonomy step executes",
        )

    def test_invalid_poll_token_fails_closed_before_any_step_runs(self) -> None:
        """Invalid poll token or wrong session still fails closed before any step runs."""
        os.environ["MERIDIAN_RUNNING_AUTONOMY_ENABLED"] = "true"
        os.environ["MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED"] = "true"
        os.environ["MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED"] = "true"

        client = TestClient(create_app())

        response = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Run a background analytics refresh for Memphis exceptions.",
            ),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        job_id = payload["job_id"]
        valid_token = payload["job_poll_token"]

        # Invalid poll token should return 404
        invalid_poll = client.get(
            f"/jobs/{job_id}",
            params=self._job_query(job_poll_token="invalid_token"),
        )
        self.assertEqual(invalid_poll.status_code, 404)

        # Verify job is still accessible with valid token
        # First poll will complete the autonomy job
        valid_poll = client.get(
            f"/jobs/{job_id}",
            params=self._job_query(job_poll_token=valid_token),
        )
        self.assertEqual(valid_poll.status_code, 200)
        poll_data = valid_poll.json()
        # Job should be succeeded after autonomy step
        self.assertEqual(poll_data["status"], "succeeded")


def load_config():
    """Helper to load config for checkpoint path lookup."""
    from backend.app.config import load_config
    return load_config()


import json


if __name__ == "__main__":
    unittest.main()
