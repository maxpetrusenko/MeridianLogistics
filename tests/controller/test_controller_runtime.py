from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.app.config import AppConfig
from backend.app.controller.models import ProtectedCore
from backend.app.orchestrator import graph


class FakeStrategy:
    def initialize(self, original_goal: str, constraints: list[str]) -> None:
        self.goal = original_goal
        self.constraints = constraints

    def update_goal(self, new_goal: str, rationale: str = "") -> None:
        self.goal = new_goal

    def compress(self, context: list[dict[str, object]], trigger_point: int) -> str:
        return f"compressed:{trigger_point}:{len(context)}"

    def name(self) -> str:
        return "fake-instinct8"


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


class ControllerRuntimeTests(unittest.TestCase):
    def test_flag_off_keeps_graph_and_routing_on_legacy_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(
                root,
                checkpoints_enabled=False,
                precedence_enabled=False,
            )

            orchestration_graph = graph.build_orchestrator_graph(config=config)
            self.assertNotIn("controller", orchestration_graph)

            routed = graph.controller_route_decision(
                session_id="sess-legacy",
                stage_name="triage",
                legacy_action="abort",
                review_outcome="approve",
                validator_outcome="pass",
                triage_abort_requested=True,
                config=config,
            )

            self.assertEqual(routed.authoritative.action, "abort")
            self.assertIsNone(routed.new_decision)
            self.assertFalse(config.controller_checkpoint_dir.exists())

    def test_flag_on_logs_shadow_decisions_and_can_supersede_weak_triage_abort(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(
                root,
                checkpoints_enabled=True,
                precedence_enabled=True,
            )

            with self.assertLogs("backend.app.controller.runtime", level="INFO") as logs:
                routed = graph.controller_route_decision(
                    session_id="sess-shadow",
                    stage_name="triage",
                    legacy_action="abort",
                    review_outcome="approve",
                    validator_outcome="pass",
                    triage_abort_requested=True,
                    config=config,
                )

            self.assertEqual(routed.authoritative.action, "continue")
            self.assertEqual(routed.legacy_decision.action, "abort")
            self.assertEqual(routed.new_decision.action, "continue")
            self.assertTrue(routed.decisions_differ)
            self.assertIn("decision_differs", "\n".join(logs.output))

    def test_resume_uses_checkpoint_not_loose_doc_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(
                root,
                checkpoints_enabled=True,
                precedence_enabled=True,
            )
            checkpoint_core = make_protected_core("checkpoint goal")
            loose_doc_core = make_protected_core("loose doc goal")

            graph.controller_stage_transition(
                session_id="sess-resume",
                stage_name="review",
                protected_core=checkpoint_core,
                legacy_action="review",
                config=config,
            )
            handoff = graph.controller_prepare_compaction(
                session_id="sess-resume",
                fallback_protected_core=loose_doc_core,
                strategy=FakeStrategy(),
                halo_turns=[{"id": 1, "role": "user", "content": "Need handoff"}],
                recent_turns=[{"id": 2, "role": "assistant", "content": "Continue"}],
                trigger_point=1,
                config=config,
            )

            resumed = graph.controller_resume(
                session_id="sess-resume",
                fallback_protected_core=loose_doc_core,
                config=config,
            )

            self.assertEqual(handoff.envelope.protected_core, checkpoint_core.to_dict())
            self.assertEqual(resumed.protected_core.to_dict(), checkpoint_core.to_dict())
            self.assertNotEqual(resumed.protected_core.task_goal, loose_doc_core.task_goal)

    def test_missing_packet_fields_fail_soft_not_abort(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(
                root,
                checkpoints_enabled=True,
                precedence_enabled=True,
            )
            config.controller_checkpoint_dir.mkdir(parents=True, exist_ok=True)
            invalid_path = config.controller_checkpoint_dir / "sess-invalid.json"
            invalid_path.write_text(
                json.dumps(
                    {
                        "checkpoint_id": "broken",
                        "checkpoint_version": "0.1.0",
                        "created_at": "2026-03-14T12:00:00Z",
                    }
                )
            )

            fallback_core = make_protected_core("fallback goal")
            resumed = graph.controller_resume(
                session_id="sess-invalid",
                fallback_protected_core=fallback_core,
                config=config,
            )

            self.assertEqual(resumed.protected_core.to_dict(), fallback_core.to_dict())
            self.assertEqual(resumed.decision.action, "review")
            self.assertNotEqual(resumed.decision.action, "abort")

    def test_queue_auto_wave_continues_immediately(self) -> None:
        decision = graph.controller_finalize_queue_state(
            current_wave="Main Lane",
            queue_items=[
                {
                    "wave_name": "Review Lane",
                    "status": "queued",
                    "run_policy": "explicit_request",
                    "eligible": False,
                },
                {
                    "wave_name": "Repair Lane",
                    "status": "queued",
                    "run_policy": "auto",
                    "eligible": True,
                },
            ],
            blocker_packet_present=False,
        )

        self.assertEqual(decision["action"], "continue")
        self.assertEqual(decision["next_wave_name"], "Repair Lane")
        self.assertIsNone(decision["terminal_state"])

    def test_waiting_approval_only_for_explicit_request_waves(self) -> None:
        decision = graph.controller_next_terminal_or_runnable_state(
            queue_items=[
                {
                    "wave_name": "Human Write Authorization",
                    "status": "queued",
                    "run_policy": "explicit_request",
                    "eligible": False,
                    "approval_authority": "user",
                }
            ],
            blocker_packet_present=False,
        )

        self.assertEqual(decision["action"], "waiting_user_approval")
        self.assertEqual(decision["terminal_state"], "WAITING_USER_APPROVAL")

    def test_main_self_approves_controlled_flag_on_validation(self) -> None:
        decision = graph.controller_next_terminal_or_runnable_state(
            queue_items=[
                {
                    "wave_name": "Controlled Flag-On Validation",
                    "status": "queued",
                    "run_policy": "explicit_request",
                    "eligible": False,
                    "requires_explicit_request": True,
                    "approval_authority": "main",
                }
            ],
            blocker_packet_present=False,
        )

        self.assertEqual(decision["action"], "continue")
        self.assertEqual(decision["next_wave_name"], "Controlled Flag-On Validation")
        self.assertIsNone(decision["terminal_state"])
        self.assertEqual(decision["instantiated_wave"]["run_policy"], "explicit_request")
        self.assertTrue(decision["instantiated_wave"]["eligible"])
        self.assertEqual(decision["instantiated_wave"]["approval_authority"], "main")

    def test_safe_next_stage_auto_instantiates_when_no_auto_wave_exists(self) -> None:
        decision = graph.controller_next_terminal_or_runnable_state(
            queue_items=[
                {
                    "wave_name": "Human Write Authorization",
                    "status": "queued",
                    "run_policy": "explicit_request",
                    "eligible": False,
                    "approval_authority": "user",
                }
            ],
            blocker_packet_present=False,
            next_stage_candidate={
                "wave_name": "Lean Policy Runtime Verification",
                "owner": "Main",
                "objective": "Verify runtime hooks and queue semantics stay aligned.",
                "artifacts_in_scope": [
                    "backend/app/controller/runtime.py",
                    "backend/app/orchestrator/graph.py",
                    "tests/controller/test_controller_runtime.py",
                ],
                "success_check": "Runtime queue helpers instantiate the next safe wave deterministically.",
                "why_next": "Runtime verification is the next safe auto wave after queue finalization.",
                "run_policy": "auto",
                "within_approved_scope": True,
                "non_destructive": True,
                "requires_explicit_approval": False,
                "repo_grounded": True,
            },
        )

        self.assertEqual(decision["action"], "continue")
        self.assertEqual(decision["next_wave_name"], "Lean Policy Runtime Verification")
        self.assertIsNone(decision["terminal_state"])
        self.assertIsNotNone(decision["instantiated_wave"])
        self.assertEqual(decision["instantiated_wave"]["run_policy"], "auto")
        self.assertEqual(decision["instantiated_wave"]["owner"], "Main")
        self.assertEqual(
            decision["instantiated_wave"]["artifacts_in_scope"],
            [
                "backend/app/controller/runtime.py",
                "backend/app/orchestrator/graph.py",
                "tests/controller/test_controller_runtime.py",
            ],
        )

    def test_finalize_queue_auto_derives_safe_next_stage_from_current_wave(self) -> None:
        decision = graph.controller_finalize_queue_state(
            current_wave="Decision Tightening",
            queue_items=[
                {
                    "wave_name": "Human Write Authorization",
                    "status": "queued",
                    "run_policy": "explicit_request",
                    "eligible": False,
                    "approval_authority": "user",
                }
            ],
            blocker_packet_present=False,
        )

        self.assertEqual(decision["action"], "continue")
        self.assertEqual(decision["next_wave_name"], "Controller Docs Sync")
        self.assertIsNone(decision["terminal_state"])
        self.assertIsNotNone(decision["instantiated_wave"])
        self.assertEqual(decision["instantiated_wave"]["run_policy"], "auto")
        self.assertEqual(decision["instantiated_wave"]["owner"], "Main")

    def test_misaligned_control_truth_auto_instantiates_sync_wave(self) -> None:
        decision = graph.controller_finalize_queue_state(
            current_wave="Run Policy Tightening",
            queue_items=[
                {
                    "wave_name": "Human Write Authorization",
                    "status": "queued",
                    "run_policy": "explicit_request",
                    "eligible": False,
                    "approval_authority": "user",
                }
            ],
            blocker_packet_present=False,
            control_plane_truth={
                "queue_terminal_state": "WAITING_USER_APPROVAL",
                "checkpoint_terminal_state": "DONE",
                "report_terminal_state": "WAITING_USER_APPROVAL",
                "dispatch_terminal_state": "WAITING_USER_APPROVAL",
                "queue_next_wave_name": "Human Write Authorization",
                "checkpoint_next_wave_name": None,
                "report_next_wave_name": "Human Write Authorization",
                "dispatch_next_wave_name": "Human Write Authorization",
            },
        )

        self.assertEqual(decision["action"], "continue")
        self.assertEqual(decision["next_wave_name"], "Control Plane Truth Sync")
        self.assertEqual(decision["instantiated_wave"]["run_policy"], "auto")

    def test_abort_terminal_state_flows_through_graph(self) -> None:
        decision = graph.controller_next_terminal_or_runnable_state(
            queue_items=[],
            blocker_packet_present=False,
            abort_requested=True,
        )

        self.assertEqual(decision["action"], "aborted")
        self.assertEqual(decision["terminal_state"], "ABORTED")

    def test_finalize_queue_persists_self_approved_wave_checkpoint_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = make_config(
                root,
                checkpoints_enabled=True,
                precedence_enabled=True,
            )
            protected_core = make_protected_core("queue truth")

            graph.controller_stage_transition(
                session_id="sess-queue-truth",
                stage_name="review",
                protected_core=protected_core,
                legacy_action="review",
                config=config,
            )
            decision = graph.controller_finalize_queue_state(
                session_id="sess-queue-truth",
                current_wave="Decision Tightening",
                queue_items=[
                    {
                        "wave_name": "Controlled Flag-On Validation",
                        "status": "queued",
                        "run_policy": "explicit_request",
                        "eligible": False,
                        "requires_explicit_request": True,
                        "approval_authority": "main",
                    }
                ],
                blocker_packet_present=False,
                config=config,
            )
            resumed = graph.controller_resume(
                session_id="sess-queue-truth",
                fallback_protected_core=protected_core,
                config=config,
            )

            self.assertIsNone(decision["terminal_state"])
            self.assertIsNotNone(resumed.checkpoint)
            self.assertIsNotNone(resumed.checkpoint.queue)
            self.assertEqual(resumed.checkpoint.queue.wave_name, "Controlled Flag-On Validation")
            self.assertEqual(resumed.checkpoint.queue.run_policy, "explicit_request")
            self.assertTrue(resumed.checkpoint.queue.eligible)
            self.assertEqual(resumed.checkpoint.queue.status, "active")
            self.assertEqual(resumed.checkpoint.queue.approval_authority, "main")
            self.assertIsNone(resumed.checkpoint.terminal_state)

    def test_repair_gate_requires_exact_blocker_packet(self) -> None:
        self.assertFalse(
            graph.controller_should_open_repair(
                failure_signal={
                    "kind": "runtime_error",
                    "severity": "recoverable",
                    "source": "controller",
                    "details": "RuntimeError: missing exact scope",
                },
                file_path=None,
                failing_check="python -m unittest tests/controller/test_controller_runtime.py",
                contradiction_text="missing exact scope",
                bounded_scope=True,
            )
        )

    def test_review_gate_is_selective(self) -> None:
        self.assertFalse(
            graph.controller_should_open_review(
                runtime_changed=False,
                files_changed=1,
                contract_changed=False,
                blocker_previously_stalled=False,
                confidence_low=False,
            )
        )

    def test_main_continues_while_drift_review_runs(self) -> None:
        self.assertTrue(
            graph.controller_should_open_drift_review(
                wave_runs_longer_than_major_step=True,
                plan_changed_after_new_evidence=False,
                touched_multiple_control_artifacts=False,
                about_to_close_or_promote_wave=False,
            )
        )

    def test_main_continues_while_parallel_research_runs(self) -> None:
        self.assertTrue(
            graph.controller_should_open_parallel_research(
                freshness_matters=True,
                framework_or_vendor_claim=False,
                current_product_claim=False,
                repo_contains_answer=False,
            )
        )

    def test_main_waits_when_parallel_repair_hits_current_reasoning_path(self) -> None:
        self.assertFalse(
            graph.controller_can_continue_while_repair_runs(
                blocker_affects_current_reasoning_path=True,
                isolated_scope=True,
                conflicts_with_active_artifact=False,
            )
        )

    def test_main_blocks_parallel_mutation_of_same_artifact(self) -> None:
        self.assertFalse(
            graph.controller_should_open_parallel_repair(
                failure_signal={
                    "kind": "runtime_error",
                    "severity": "recoverable",
                    "source": "controller",
                    "details": "RuntimeError: exact isolated failure",
                },
                file_path="backend/app/controller/policy.py",
                failing_check="python -m unittest tests/controller/test_controller_policy.py",
                contradiction_text="exact isolated failure",
                bounded_scope=True,
                isolated_scope=True,
                conflicts_with_active_artifact=True,
            )
        )

    def test_advisory_subagent_output_does_not_override_without_explicit_merge(self) -> None:
        self.assertFalse(
            graph.controller_should_merge_subagent_result(
                explicit_merge_requested=False,
                mutates_controller_truth=False,
                conflicts_with_active_artifact=False,
            )
        )
        self.assertTrue(
            graph.controller_should_open_review(
                runtime_changed=False,
                files_changed=2,
                contract_changed=False,
                blocker_previously_stalled=False,
                confidence_low=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
