from __future__ import annotations

import unittest

from jsonschema import Draft202012Validator, ValidationError

from backend.app.contracts import load_json_contract
from backend.app.controller.models import (
    CompactionState,
    ControllerCheckpoint,
    ControllerDecision,
    FailureSignal,
    ProtectedCore,
    QueueState,
)

# Load current checkpoint schema for validation
_checkpoint_schema = load_json_contract("controller_checkpoint")
_validator = Draft202012Validator(_checkpoint_schema)


def _make_valid_checkpoint() -> dict:
    """Create a valid checkpoint dict for testing."""
    return ControllerCheckpoint(
        checkpoint_id="cp-compat-test-001",
        protected_core=ProtectedCore(
            task_goal="Test legacy state rejection.",
            expected_output="Validation errors for old states.",
            current_step="Test checkpoint compatibility.",
            resume_point="Resume after validation fix.",
            hard_constraints=(
                "Legacy checkpoints must fail validation",
                "New schema uses WAITING_USER_APPROVAL",
            ),
        ),
        compaction=CompactionState(
            strategy_name="test",
            compaction_sequence=0,
            halo_summary="test",
            recent_turn_ids=(),
        ),
        validated_artifacts=(),
        active_failure_signal=FailureSignal(
            kind="none",
            severity="none",
            source="controller",
        ),
        controller_last_decision=ControllerDecision(
            action="continue",
            reason="test",
            source="controller",
        ),
        queue=QueueState(
            wave_name="test",
            status="queued",
            run_policy="auto",
            eligible=True,
        ),
        terminal_state="WAITING_USER_APPROVAL",
    ).to_dict()


class CheckpointCompatibilityTests(unittest.TestCase):
    """Tests that legacy checkpoint states fail schema validation."""

    def test_legacy_waiting_approval_state_fails_validation(self) -> None:
        """Legacy WAITING_APPROVAL (without _USER) must fail schema validation."""
        checkpoint = _make_valid_checkpoint()
        checkpoint["terminal_state"] = "WAITING_APPROVAL"

        errors = list(_validator.iter_errors(checkpoint))
        self.assertTrue(
            errors,
            "Legacy WAITING_APPROVAL state should fail schema validation",
        )

        # Verify error is about terminal_state enum violation
        terminal_state_errors = [
            e for e in errors if "terminal_state" in e.path
        ]
        self.assertTrue(
            terminal_state_errors,
            "Expected validation error on terminal_state field",
        )
        error = terminal_state_errors[0]
        self.assertIn("enum", error.schema.keys())

    def test_valid_waiting_user_approval_state_passes(self) -> None:
        """Current WAITING_USER_APPROVAL state must pass validation."""
        checkpoint = _make_valid_checkpoint()
        checkpoint["terminal_state"] = "WAITING_USER_APPROVAL"

        errors = list(_validator.iter_errors(checkpoint))
        self.assertEqual(
            [],
            errors,
            "WAITING_USER_APPROVAL should pass schema validation",
        )

    def test_schema_catches_legacy_state_before_from_dict(self) -> None:
        """
        Schema validation must reject legacy states before they reach from_dict.

        Note: ControllerCheckpoint.from_dict is a thin dataclass constructor
        that doesn't do runtime enum validation. It relies on schema validation
        at the load boundary (ControllerRuntime.load_checkpoint) to catch
        invalid payloads before deserialization.
        """
        checkpoint = _make_valid_checkpoint()
        checkpoint["terminal_state"] = "WAITING_APPROVAL"

        errors = list(_validator.iter_errors(checkpoint))
        self.assertTrue(
            errors,
            "Schema must reject legacy WAITING_APPROVAL before from_dict sees it",
        )


if __name__ == "__main__":
    unittest.main()
