from __future__ import annotations

from dataclasses import replace
import unittest

from backend.app.controller.models import (
    CompactionState,
    ControllerCheckpoint,
    ControllerDecision,
    FailureSignal,
    ProtectedCore,
    QueueState,
)
from backend.app.controller.precedence import ControllerSignals, resolve_controller_action
from backend.app.controller.strategies import CompressionControllerAdapter


class FakeStrategy:
    def __init__(self) -> None:
        self.goal = None
        self.constraints = None
        self.compactions = []

    def initialize(self, original_goal: str, constraints: list[str]) -> None:
        self.goal = original_goal
        self.constraints = constraints

    def update_goal(self, new_goal: str, rationale: str = "") -> None:
        self.goal = new_goal

    def compress(self, context: list[dict[str, object]], trigger_point: int) -> str:
        self.compactions.append((context, trigger_point))
        return f"compressed:{trigger_point}:{len(context)}"

    def name(self) -> str:
        return "fake-instinct8"


def make_checkpoint() -> ControllerCheckpoint:
    return ControllerCheckpoint(
        checkpoint_id="cp-safe-1",
        protected_core=ProtectedCore(
            task_goal="Keep Memphis PoC behavior stable through compaction.",
            expected_output="Checkpointable controller scaffold.",
            current_step="Apply fail-soft precedence.",
            resume_point="Resume at repair-or-review branch.",
            hard_constraints=(
                "Do not replace the main runtime.",
                "Keep read and write behavior unchanged.",
            ),
            business_invariants=("Memphis-only scope",),
        ),
        compaction=CompactionState(
            strategy_name="Strategy B - Codex-Style Checkpoint",
            compaction_sequence=0,
            halo_summary="",
            recent_turn_ids=(),
        ),
        validated_artifacts=("contracts/tool-schema.yaml",),
        active_failure_signal=FailureSignal(
            kind="none",
            severity="none",
            source="controller",
            details=None,
        ),
        controller_last_decision=ControllerDecision(
            action="review",
            reason="insufficient_signal_default_review",
            source="controller",
        ),
    )


class ControllerScaffoldTests(unittest.TestCase):
    def test_review_approve_beats_safe_triage_abort(self) -> None:
        decision = resolve_controller_action(
            ControllerSignals(
                review_outcome="approve",
                triage_abort_requested=True,
            )
        )

        self.assertEqual(decision.action, "continue")
        self.assertEqual(decision.source, "review")

    def test_validator_pass_beats_safe_triage_abort_without_failure(self) -> None:
        decision = resolve_controller_action(
            ControllerSignals(
                validator_outcome="pass",
                triage_abort_requested=True,
            )
        )

        self.assertEqual(decision.action, "continue")
        self.assertEqual(decision.source, "validator")

    def test_unsafe_failure_forces_abort(self) -> None:
        decision = resolve_controller_action(
            ControllerSignals(
                review_outcome="approve",
                validator_outcome="pass",
                triage_abort_requested=True,
                failure_signal=FailureSignal(
                    kind="destructive_write_risk",
                    severity="unsafe",
                    source="triage",
                    details="write would cross office scope",
                ),
            )
        )

        self.assertEqual(decision.action, "abort")
        self.assertEqual(decision.reason, "unsafe_or_destructive_state")

    def test_recoverable_failure_routes_to_repair(self) -> None:
        decision = resolve_controller_action(
            ControllerSignals(
                review_outcome="approve",
                concrete_failure=True,
                failure_signal=FailureSignal(
                    kind="stale_checkpoint",
                    severity="recoverable",
                    source="controller",
                    details="resume marker missing recent turn",
                ),
            )
        )

        self.assertEqual(decision.action, "repair")
        self.assertEqual(decision.reason, "recoverable_failure_requires_repair")

    def test_adapter_preserves_protected_core_and_recent_turns(self) -> None:
        strategy = FakeStrategy()
        adapter = CompressionControllerAdapter(strategy)
        checkpoint = make_checkpoint()

        adapter.prime(checkpoint.protected_core)
        envelope = adapter.compact(
            checkpoint=checkpoint,
            halo_turns=[
                {"id": 1, "role": "user", "content": "Need checkpoint"},
                {"id": 2, "role": "assistant", "content": "Planning patch"},
            ],
            recent_turns=[{"id": 3, "role": "assistant", "content": "Continue from here"}],
            trigger_point=2,
        )

        self.assertEqual(strategy.goal, checkpoint.protected_core.task_goal)
        self.assertEqual(strategy.constraints, list(checkpoint.protected_core.hard_constraints))
        self.assertEqual(envelope.strategy_name, "fake-instinct8")
        self.assertEqual(envelope.protected_core["resume_point"], "Resume at repair-or-review branch.")
        self.assertEqual(envelope.recent_turns[0]["id"], 3)
        self.assertEqual(envelope.compressed_halo, "compressed:2:2")

    def test_checkpoint_round_trip_preserves_queue_snapshot_and_terminal_state(self) -> None:
        checkpoint = replace(
            make_checkpoint(),
            queue=QueueState(
                wave_name="Controlled Flag-On Validation",
                status="queued",
                run_policy="auto",
                eligible=True,
                requires_explicit_request=False,
                approval_authority="main",
            ),
            terminal_state=None,
        )

        restored = ControllerCheckpoint.from_dict(checkpoint.to_dict())

        self.assertIsNotNone(restored.queue)
        self.assertEqual(restored.queue.wave_name, "Controlled Flag-On Validation")
        self.assertEqual(restored.queue.run_policy, "auto")
        self.assertTrue(restored.queue.eligible)
        self.assertEqual(restored.queue.approval_authority, "main")
        self.assertIsNone(restored.terminal_state)


if __name__ == "__main__":
    unittest.main()
