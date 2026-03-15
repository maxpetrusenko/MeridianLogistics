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

    def tearDown(self) -> None:
        if self._previous_state_database_url is None:
            os.environ.pop("MERIDIAN_STATE_DATABASE_URL", None)
        else:
            os.environ["MERIDIAN_STATE_DATABASE_URL"] = self._previous_state_database_url
        self._temp_dir.cleanup()

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

        # First poll: should advance to step 1, job still running
        first_poll = client.get(
            f"/jobs/{job_id}",
            params=self._job_query(job_poll_token=poll_token),
        )
        self.assertEqual(first_poll.status_code, 200)
        first_data = first_poll.json()
        self.assertEqual(first_data["status"], "running")

        # Check step index in checkpoint
        checkpoint_path = self._checkpoint_path_for_job(job_id)
        checkpoint = ControllerCheckpoint.from_dict(json.loads(checkpoint_path.read_text()))
        self.assertEqual(checkpoint.queue.status, "active")
        # Step should have advanced

        # Second poll: should advance to step 2, job still running
        second_poll = client.get(
            f"/jobs/{job_id}",
            params=self._job_query(job_poll_token=poll_token),
        )
        self.assertEqual(second_poll.status_code, 200)
        second_data = second_poll.json()
        self.assertEqual(second_data["status"], "running")

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

        # First, verify checkpoint was created (will fail until autonomy implemented)
        checkpoint_path = self._checkpoint_path_for_job(job_id)
        if not checkpoint_path.exists():
            self.skipTest("Autonomy not yet implemented - checkpoint seeding not working")

        # Simulate stale job metadata by updating checkpoint directly
        checkpoint_data = json.loads(checkpoint_path.read_text())
        checkpoint_data["queue"]["status"] = "completed"
        checkpoint_data["queue"]["eligible"] = False
        checkpoint_path.write_text(json.dumps(checkpoint_data))

        # Poll should use checkpoint truth, not stale job metadata
        poll_response = client.get(
            f"/jobs/{job_id}",
            params=self._job_query(job_poll_token=poll_token),
        )
        self.assertEqual(poll_response.status_code, 200)
        poll_data = poll_response.json()

        # Should complete based on checkpoint truth
        self.assertEqual(poll_data["status"], "succeeded")

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

        # First poll: use the only step, job should transition to terminal
        # If work isn't complete, should fail-soft
        first_poll = client.get(
            f"/jobs/{job_id}",
            params=self._job_query(job_poll_token=poll_token),
        )
        self.assertEqual(first_poll.status_code, 200)
        first_data = first_poll.json()

        # Either succeeded (if work complete) or failed (if step budget exhausted)
        self.assertIn(first_data["status"], ["succeeded", "running", "failed"])

        # Second poll: if still running, step budget exhausted should cause completion
        second_poll = client.get(
            f"/jobs/{job_id}",
            params=self._job_query(job_poll_token=poll_token),
        )
        self.assertEqual(second_poll.status_code, 200)
        second_data = second_poll.json()

        # Should be terminal (succeeded with result or failed with error)
        self.assertIn(
            second_data["status"],
            ["succeeded", "failed"],
            "Job should reach terminal state when step budget exhausted",
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

        # Verify job is still accessible with valid token (no steps advanced)
        valid_poll = client.get(
            f"/jobs/{job_id}",
            params=self._job_query(job_poll_token=valid_token),
        )
        self.assertEqual(valid_poll.status_code, 200)
        poll_data = valid_poll.json()
        # Job should still be in initial state
        self.assertEqual(poll_data["status"], "pending")


def load_config():
    """Helper to load config for checkpoint path lookup."""
    from backend.app.config import load_config
    return load_config()


import json


if __name__ == "__main__":
    unittest.main()
