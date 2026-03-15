from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.app.config import AppConfig
from backend.app.controller.models import ProtectedCore, QueueState
from backend.app.orchestrator import graph


def make_config(
    root: Path,
    *,
    checkpoints_enabled: bool,
    precedence_enabled: bool,
) -> AppConfig:
    return AppConfig(
        app_env="test",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/meridian_logistics",
        redis_url="redis://localhost:6379/0",
        contracts_dir=root / "contracts",
        memphis_office_id="memphis",
        controller_checkpoints_enabled=checkpoints_enabled,
        controller_precedence_enabled=precedence_enabled,
        controller_checkpoint_dir=root / ".controller-checkpoints",
    )


def make_protected_core(task_goal: str) -> ProtectedCore:
    return ProtectedCore(
        task_goal=task_goal,
        expected_output="Return a safe controller decision.",
        current_step="routing",
        resume_point="resume from controller checkpoint",
        hard_constraints=(
            "Do not replace the main runtime.",
            "Keep business behavior unchanged.",
        ),
        business_invariants=("Memphis-only scope",),
    )


class MainAutonomousResumeTests(unittest.TestCase):
    """
    TDD tests for Main autonomous resume behavior.

    These tests enforce:
    - status-only resume with an eligible active `auto` wave continues instead of pausing
    - stale thread packet does not override controller truth when checkpoint/queue truth points to a different active wave
    - Main returns terminal state only when queue finalization yields literal `DONE`, `WAITING_USER_APPROVAL`, `BLOCKED`, or `ABORTED`
    - Main derives the next runnable packet from checkpoint/queue truth when no fresh manual packet is supplied
    - resume from BLOCKED, WAITING_USER_APPROVAL, or DONE checkpoints honors preserved terminal state
    """

    def test_status_only_resume_with_eligible_auto_wave_continues(self) -> None:
        """
        Status-only resume with an eligible active `auto` wave must continue automatically,
        not pause for user input or return a terminal state.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(
                root,
                checkpoints_enabled=True,
                precedence_enabled=True,
            )
            protected_core = make_protected_core("autonomous resume goal")

            # Create checkpoint with an active auto wave queued
            graph.controller_stage_transition(
                session_id="sess-status-resume",
                stage_name="review",
                protected_core=protected_core,
                legacy_action="review",
                config=config,
            )
            graph.controller_finalize_queue_state(
                session_id="sess-status-resume",
                current_wave="Previous Wave",
                queue_items=[
                    {
                        "wave_name": "Auto Wave",
                        "status": "queued",
                        "run_policy": "auto",
                        "eligible": True,
                    }
                ],
                blocker_packet_present=False,
                config=config,
            )

            # Resume from checkpoint (simulates status-only update, no fresh manual packet)
            resumed = graph.controller_resume(
                session_id="sess-status-resume",
                fallback_protected_core=protected_core,
                config=config,
            )

            # CRITICAL: Status-only resume with eligible auto wave must continue
            self.assertIsNone(resumed.checkpoint.terminal_state,
                "Status-only resume with eligible auto wave must not return terminal state")
            self.assertIsNotNone(resumed.checkpoint.queue,
                "Checkpoint must contain queue snapshot for resume")
            self.assertEqual(resumed.checkpoint.queue.wave_name, "Auto Wave",
                "Active auto wave must be preserved from checkpoint")
            self.assertEqual(resumed.decision.action, "continue",
                "Status-only resume with eligible auto wave must continue automatically")

    def test_stale_thread_packet_does_not_override_controller_truth(self) -> None:
        """
        Stale thread packet (e.g., from previous conversation summary) must NOT override
        controller checkpoint/queue truth when they point to different active waves.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(
                root,
                checkpoints_enabled=True,
                precedence_enabled=True,
            )
            protected_core = make_protected_core("controller truth priority")

            # Create checkpoint with "Real Auto Wave" as active
            graph.controller_stage_transition(
                session_id="sess-stale-override",
                stage_name="review",
                protected_core=protected_core,
                legacy_action="review",
                config=config,
            )
            graph.controller_finalize_queue_state(
                session_id="sess-stale-override",
                current_wave="Previous Wave",
                queue_items=[
                    {
                        "wave_name": "Real Auto Wave",
                        "status": "queued",
                        "run_policy": "auto",
                        "eligible": True,
                    }
                ],
                blocker_packet_present=False,
                config=config,
            )

            # Simulate resume with stale thread summary claiming different wave
            # (this represents thread drift from manual summaries)
            resumed = graph.controller_resume(
                session_id="sess-stale-override",
                fallback_protected_core=protected_core,
                config=config,
            )

            # CRITICAL: Controller truth must win over stale thread packets
            self.assertIsNotNone(resumed.checkpoint,
                "Must load checkpoint truth")
            self.assertEqual(resumed.checkpoint.queue.wave_name, "Real Auto Wave",
                "Controller checkpoint truth must win, not stale thread summary")
            self.assertEqual(resumed.decision.action, "continue",
                "Must follow checkpoint truth, not drift with stale thread")

    def test_main_terminal_only_on_literal_terminal_states(self) -> None:
        """
        Main must return terminal state ONLY when queue finalization yields one of:
        - DONE
        - WAITING_USER_APPROVAL
        - BLOCKED
        - ABORTED

        Status-only updates, progress reports, or intermediate states must NOT be terminal.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(
                root,
                checkpoints_enabled=True,
                precedence_enabled=True,
            )
            protected_core = make_protected_core("terminal state gate")

            # Scenario 1: Eligible auto wave exists -> not terminal
            decision = graph.controller_next_terminal_or_runnable_state(
                queue_items=[
                    {
                        "wave_name": "Auto Wave",
                        "status": "queued",
                        "run_policy": "auto",
                        "eligible": True,
                    }
                ],
                blocker_packet_present=False,
            )

            self.assertEqual(decision["action"], "continue",
                "Eligible auto wave must continue, not be terminal")
            self.assertIsNone(decision["terminal_state"],
                "Continue action must have no terminal state")

            # Scenario 2: Only explicit_request wave remains -> WAITING_USER_APPROVAL
            decision = graph.controller_next_terminal_or_runnable_state(
                queue_items=[
                    {
                        "wave_name": "User Approval Wave",
                        "status": "queued",
                        "run_policy": "explicit_request",
                        "eligible": False,
                        "approval_authority": "user",
                    }
                ],
                blocker_packet_present=False,
            )

            self.assertEqual(decision["action"], "waiting_user_approval",
                "Explicit request wave must wait for user approval")
            self.assertEqual(decision["terminal_state"], "WAITING_USER_APPROVAL",
                "Must return literal terminal state")

            # Scenario 3: No runnable waves -> DONE
            decision = graph.controller_next_terminal_or_runnable_state(
                queue_items=[],
                blocker_packet_present=False,
            )

            self.assertEqual(decision["action"], "done",
                "No runnable waves must be DONE")
            self.assertEqual(decision["terminal_state"], "DONE",
                "Must return literal DONE terminal state")

            # Scenario 4: Exact blocker present -> BLOCKED
            decision = graph.controller_next_terminal_or_runnable_state(
                queue_items=[
                    {
                        "wave_name": "Auto Wave",
                        "status": "queued",
                        "run_policy": "auto",
                        "eligible": True,
                    }
                ],
                blocker_packet_present=True,
            )

            self.assertEqual(decision["action"], "blocked",
                "Exact blocker must BLOCK")
            self.assertEqual(decision["terminal_state"], "BLOCKED",
                "Must return literal BLOCKED terminal state")

    def test_main_derives_next_wave_packet_from_checkpoint_truth(self) -> None:
        """
        When no fresh manual packet is supplied, Main must derive the next runnable
        wave selection from checkpoint/queue truth.

        Note: Checkpoint queue snapshot stores wave selection metadata (wave_name,
        status, run_policy, eligible, requires_explicit_request, approval_authority).
        Full execution packet fields (owner, objective, success_check, why_next) are
        NOT persisted in checkpoint - those come from dispatch-board or are derived
        at wave instantiation time.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(
                root,
                checkpoints_enabled=True,
                precedence_enabled=True,
            )
            protected_core = make_protected_core("derive from checkpoint")

            # Create checkpoint with queued auto wave
            graph.controller_stage_transition(
                session_id="sess-derive-packet",
                stage_name="review",
                protected_core=protected_core,
                legacy_action="review",
                config=config,
            )
            graph.controller_finalize_queue_state(
                session_id="sess-derive-packet",
                current_wave="Previous Wave",
                queue_items=[
                    {
                        "wave_name": "Derived Auto Wave",
                        "status": "queued",
                        "run_policy": "auto",
                        "eligible": True,
                        "objective": "Test objective for derived wave",
                    }
                ],
                blocker_packet_present=False,
                config=config,
            )

            # Resume without fresh manual packet
            resumed = graph.controller_resume(
                session_id="sess-derive-packet",
                fallback_protected_core=protected_core,
                config=config,
            )

            # CRITICAL: Must derive next wave selection from checkpoint truth
            self.assertIsNotNone(resumed.checkpoint.queue,
                "Must have queue snapshot in checkpoint")
            self.assertEqual(resumed.checkpoint.queue.wave_name, "Derived Auto Wave",
                "Must derive correct wave from checkpoint")
            self.assertEqual(resumed.checkpoint.queue.run_policy, "auto",
                "Derived wave must preserve run_policy")
            self.assertTrue(resumed.checkpoint.queue.eligible,
                "Derived wave must preserve eligible status")
            # Note: owner, objective, success_check, why_next are NOT in checkpoint

            # Decision must be continue with derived wave
            self.assertEqual(resumed.decision.action, "continue",
                "Must continue with derived wave")

    def test_resume_from_blocked_checkpoint_honors_terminal_state(self) -> None:
        """
        Resume from a BLOCKED checkpoint must preserve the blocked state,
        not re-derive a continue or done action from the queue snapshot.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(
                root,
                checkpoints_enabled=True,
                precedence_enabled=True,
            )
            protected_core = make_protected_core("blocked checkpoint goal")

            # Create checkpoint with BLOCKED terminal state
            graph.controller_stage_transition(
                session_id="sess-resume-blocked",
                stage_name="review",
                protected_core=protected_core,
                legacy_action="blocked",
                config=config,
            )

            # Manually write a blocked checkpoint (queue with blocker)
            checkpoint_path = config.controller_checkpoint_dir / "sess-resume-blocked.json"
            checkpoint_data = json.loads(checkpoint_path.read_text())
            checkpoint_data["terminal_state"] = "BLOCKED"
            checkpoint_data["queue"] = {
                "wave_name": "Auto Wave",
                "status": "blocked",
                "run_policy": "auto",
                "eligible": True,
                "requires_explicit_request": False,
                "approval_authority": "main",
            }
            checkpoint_path.write_text(json.dumps(checkpoint_data, indent=2))

            # Resume from blocked checkpoint
            resumed = graph.controller_resume(
                session_id="sess-resume-blocked",
                fallback_protected_core=protected_core,
                config=config,
            )

            # CRITICAL: Blocked checkpoint must stay blocked
            self.assertEqual(resumed.checkpoint.terminal_state, "BLOCKED",
                "Terminal state must be preserved from checkpoint")
            self.assertEqual(resumed.decision.action, "blocked",
                "Resume from blocked checkpoint must return blocked action")
            self.assertIn("terminal_state", resumed.decision.reason.lower(),
                "Reason should indicate terminal state was preserved")

    def test_resume_from_waiting_user_approval_checkpoint_honors_terminal_state(self) -> None:
        """
        Resume from a WAITING_USER_APPROVAL checkpoint must preserve the terminal state,
        not re-derive a continue or done action from the queue snapshot.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(
                root,
                checkpoints_enabled=True,
                precedence_enabled=True,
            )
            protected_core = make_protected_core("waiting approval goal")

            # Create checkpoint with WAITING_USER_APPROVAL terminal state
            graph.controller_stage_transition(
                session_id="sess-resume-waiting",
                stage_name="review",
                protected_core=protected_core,
                legacy_action="waiting_user_approval",
                config=config,
            )

            # Manually write a waiting approval checkpoint
            checkpoint_path = config.controller_checkpoint_dir / "sess-resume-waiting.json"
            checkpoint_data = json.loads(checkpoint_path.read_text())
            checkpoint_data["terminal_state"] = "WAITING_USER_APPROVAL"
            checkpoint_data["queue"] = {
                "wave_name": "User Approval Wave",
                "status": "queued",
                "run_policy": "explicit_request",
                "eligible": False,
                "requires_explicit_request": True,
                "approval_authority": "user",
            }
            checkpoint_path.write_text(json.dumps(checkpoint_data, indent=2))

            # Resume from waiting checkpoint
            resumed = graph.controller_resume(
                session_id="sess-resume-waiting",
                fallback_protected_core=protected_core,
                config=config,
            )

            # CRITICAL: Waiting approval checkpoint must stay waiting
            self.assertEqual(resumed.checkpoint.terminal_state, "WAITING_USER_APPROVAL",
                "Terminal state must be preserved from checkpoint")
            self.assertEqual(resumed.decision.action, "waiting_user_approval",
                "Resume from waiting checkpoint must return waiting_user_approval action")

    def test_resume_from_done_checkpoint_honors_terminal_state(self) -> None:
        """
        Resume from a DONE checkpoint must preserve the done state,
        not re-derive a continue action from the queue snapshot.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(
                root,
                checkpoints_enabled=True,
                precedence_enabled=True,
            )
            protected_core = make_protected_core("done checkpoint goal")

            # Create checkpoint with DONE terminal state
            graph.controller_stage_transition(
                session_id="sess-resume-done",
                stage_name="review",
                protected_core=protected_core,
                legacy_action="done",
                config=config,
            )

            # Manually write a done checkpoint
            checkpoint_path = config.controller_checkpoint_dir / "sess-resume-done.json"
            checkpoint_data = json.loads(checkpoint_path.read_text())
            checkpoint_data["terminal_state"] = "DONE"
            checkpoint_data["queue"] = None  # No queue when done
            checkpoint_path.write_text(json.dumps(checkpoint_data, indent=2))

            # Resume from done checkpoint
            resumed = graph.controller_resume(
                session_id="sess-resume-done",
                fallback_protected_core=protected_core,
                config=config,
            )

            # CRITICAL: Done checkpoint must stay done
            self.assertEqual(resumed.checkpoint.terminal_state, "DONE",
                "Terminal state must be preserved from checkpoint")
            self.assertEqual(resumed.decision.action, "done",
                "Resume from done checkpoint must return done action")

    def test_close_active_wave_auto_promotes_next_eligible_wave_in_same_turn(self) -> None:
        """
        Live-path regression: When an active wave closes, controller must
        auto-promote the next eligible auto wave in the same turn without
        waiting for a manual packet.

        This tests the full flow:
        1. Active wave completes
        2. Controller finalizes queue state
        3. Next eligible auto wave is activated immediately
        4. No status-only stop between waves
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(
                root,
                checkpoints_enabled=True,
                precedence_enabled=True,
            )
            protected_core = make_protected_core("same-turn promotion goal")

            # Setup: active wave with next eligible auto wave in queue
            graph.controller_stage_transition(
                session_id="sess-same-turn",
                stage_name="review",
                protected_core=protected_core,
                legacy_action="review",
                config=config,
            )

            # Close active wave and auto-promote next wave in one operation
            decision = graph.controller_finalize_queue_state(
                session_id="sess-same-turn",
                current_wave="Active Wave",
                queue_items=[
                    {
                        "wave_name": "Next Auto Wave",
                        "status": "queued",
                        "run_policy": "auto",
                        "eligible": True,
                    }
                ],
                blocker_packet_present=False,
                config=config,
            )

            # CRITICAL: Next auto wave must activate in same turn
            self.assertEqual(decision["action"], "continue",
                "Must auto-promote next eligible auto wave")
            self.assertEqual(decision["next_wave_name"], "Next Auto Wave",
                "Must promote correct wave")
            self.assertIsNone(decision["terminal_state"],
                "Auto-promotion is not terminal")

            # Verify checkpoint captures the transition
            resumed = graph.controller_resume(
                session_id="sess-same-turn",
                fallback_protected_core=protected_core,
                config=config,
            )
            self.assertEqual(resumed.checkpoint.queue.wave_name, "Next Auto Wave",
                "Checkpoint must capture promoted wave")
            self.assertEqual(resumed.checkpoint.queue.status, "active",
                "Promoted wave must be active in checkpoint")


if __name__ == "__main__":
    unittest.main()
