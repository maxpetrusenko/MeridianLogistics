from __future__ import annotations

import unittest

from backend.app.controller.models import FailureSignal
from backend.app.controller.policy import (
    Action,
    ControlPlaneTruth,
    MissingInfoAction,
    QueueItem,
    StageCandidate,
    control_plane_truth_aligned,
    can_continue_while_repair_runs,
    can_main_proceed,
    can_reopen_wave,
    derive_next_stage_candidate,
    finalize_queue_state,
    is_exact_blocker_packet,
    is_wave_complete,
    missing_info_action,
    next_terminal_or_runnable_state,
    requires_explicit_approval,
    should_merge_subagent_result,
    should_open_drift_review,
    should_open_parallel_repair,
    should_open_parallel_research,
    should_open_repair,
    should_open_research,
    should_open_review,
    should_delegate,
    should_use_web_search,
)


class ControllerPolicyTests(unittest.TestCase):
    def test_exact_blocker_packet_requires_full_evidence(self) -> None:
        blocker = FailureSignal(
            kind="failing_test",
            severity="recoverable",
            source="controller",
            details="AssertionError: expected continue got review",
        )

        self.assertTrue(
            is_exact_blocker_packet(
                blocker,
                file_path="tests/controller/test_controller_runtime.py",
                failing_check="python -m unittest tests/controller/test_controller_runtime.py",
                contradiction_text="expected continue got review",
                bounded_scope=True,
            )
        )
        self.assertFalse(
            is_exact_blocker_packet(
                blocker,
                file_path="",
                failing_check="python -m unittest tests/controller/test_controller_runtime.py",
                contradiction_text="expected continue got review",
                bounded_scope=True,
            )
        )

    def test_review_is_selective_not_default(self) -> None:
        self.assertFalse(
            should_open_review(
                runtime_changed=False,
                files_changed=1,
                contract_changed=False,
                blocker_previously_stalled=False,
                confidence_low=False,
            )
        )
        self.assertTrue(
            should_open_review(
                runtime_changed=True,
                files_changed=1,
                contract_changed=False,
                blocker_previously_stalled=False,
                confidence_low=False,
            )
        )

    def test_repair_requires_exact_blocker_packet(self) -> None:
        blocker = FailureSignal(
            kind="runtime_error",
            severity="recoverable",
            source="controller",
            details="RuntimeError: packet invalid",
        )

        self.assertFalse(
            should_open_repair(
                blocker,
                file_path=None,
                failing_check="pytest",
                contradiction_text="packet invalid",
                bounded_scope=True,
            )
        )
        self.assertTrue(
            should_open_repair(
                blocker,
                file_path="backend/app/controller/runtime.py",
                failing_check="pytest",
                contradiction_text="packet invalid",
                bounded_scope=True,
            )
        )

    def test_missing_info_defaults_to_infer_when_repo_grounded(self) -> None:
        self.assertEqual(
            missing_info_action(
                required_input_missing=False,
                repo_or_context_sufficient=True,
                freshness_required=False,
            ),
            MissingInfoAction.INFER,
        )

    def test_missing_info_uses_research_before_requesting_input(self) -> None:
        self.assertEqual(
            missing_info_action(
                required_input_missing=False,
                repo_or_context_sufficient=False,
                freshness_required=True,
            ),
            MissingInfoAction.RESEARCH,
        )

    def test_web_search_only_for_current_external_claims(self) -> None:
        self.assertTrue(
            should_use_web_search(
                freshness_matters=True,
                framework_or_vendor_claim=True,
                repo_contains_answer=False,
            )
        )
        self.assertFalse(
            should_use_web_search(
                freshness_matters=False,
                framework_or_vendor_claim=False,
                repo_contains_answer=True,
            )
        )

    def test_research_opens_without_user_interrupt_when_safe(self) -> None:
        self.assertTrue(
            should_open_research(
                freshness_matters=True,
                framework_or_vendor_claim=False,
                repo_contains_answer=False,
                architecture_comparison=False,
            )
        )
        self.assertFalse(
            should_open_research(
                freshness_matters=False,
                framework_or_vendor_claim=False,
                repo_contains_answer=True,
                architecture_comparison=False,
            )
        )

    def test_main_can_proceed_for_internal_hardening(self) -> None:
        self.assertTrue(
            can_main_proceed(
                internal_hardening=True,
                docs_sync=False,
                bounded_fix=False,
                local_validation=False,
                repo_grounded=False,
                safe_research=False,
                destructive_change=False,
                production_enablement=False,
                external_spend=False,
                irreversible_action=False,
                required_input_missing=False,
            )
        )

    def test_main_self_approves_internal_design_within_approved_scope(self) -> None:
        self.assertTrue(
            can_main_proceed(
                internal_hardening=False,
                docs_sync=False,
                bounded_fix=False,
                local_validation=False,
                repo_grounded=False,
                safe_research=False,
                internal_design=True,
                approved_scope=True,
                business_logic_unchanged=True,
                checkpoint_schema_widening=False,
                framework_migration=False,
                destructive_change=False,
                production_enablement=False,
                external_spend=False,
                irreversible_action=False,
                required_input_missing=False,
            )
        )
        self.assertFalse(
            requires_explicit_approval(
                destructive_change=False,
                production_enablement=False,
                external_spend=False,
                irreversible_action=False,
                required_input_missing=False,
                scope_expands=False,
                business_logic_changed=False,
                checkpoint_schema_widening=False,
                framework_migration=False,
                explicit_request_wave=False,
            )
        )
        self.assertFalse(
            should_delegate(
                exact_blocker=False,
                selective_review=False,
                needs_research=False,
            )
        )

    def test_wave_complete_requires_checks_and_no_live_blocker(self) -> None:
        self.assertFalse(
            is_wave_complete(
                intended_change_exists=True,
                required_checks_passed=False,
                blocker_packet_present=False,
            )
        )
        self.assertTrue(
            is_wave_complete(
                intended_change_exists=True,
                required_checks_passed=True,
                blocker_packet_present=False,
            )
        )

    def test_queue_finalization_promotes_next_auto_wave(self) -> None:
        decision = finalize_queue_state(
            current_wave="Main Lane",
            queue_items=[
                QueueItem(
                    wave_name="Review Lane",
                    status="queued",
                    run_policy="explicit_request",
                    eligible=True,
                ),
                QueueItem(
                    wave_name="Repair Lane",
                    status="queued",
                    run_policy="auto",
                    eligible=True,
                ),
            ],
            blocker_packet_present=False,
        )

        self.assertEqual(decision.action, Action.CONTINUE)
        self.assertEqual(decision.next_wave_name, "Repair Lane")
        self.assertIsNone(decision.terminal_state)

    def test_queue_waiting_approval_requires_explicit_request_wave(self) -> None:
        decision = next_terminal_or_runnable_state(
            [
                QueueItem(
                    wave_name="Human Write Authorization",
                    status="queued",
                    run_policy="explicit_request",
                    eligible=False,
                    approval_authority="user",
                )
            ],
            blocker_packet_present=False,
        )

        self.assertEqual(decision.action, Action.WAITING_USER_APPROVAL)
        self.assertEqual(decision.terminal_state, "WAITING_USER_APPROVAL")

    def test_main_self_approves_internal_explicit_request_wave(self) -> None:
        decision = next_terminal_or_runnable_state(
            [
                QueueItem(
                    wave_name="Controlled Flag-On Validation",
                    status="queued",
                    run_policy="explicit_request",
                    eligible=False,
                    requires_explicit_request=True,
                    approval_authority="main",
                )
            ],
            blocker_packet_present=False,
        )

        self.assertEqual(decision.action, Action.CONTINUE)
        self.assertEqual(decision.next_wave_name, "Controlled Flag-On Validation")
        self.assertIsNone(decision.terminal_state)
        self.assertIsNotNone(decision.instantiated_wave)
        self.assertEqual(decision.instantiated_wave["run_policy"], "explicit_request")
        self.assertTrue(decision.instantiated_wave["eligible"])
        self.assertEqual(decision.instantiated_wave["approval_authority"], "main")

    def test_safe_next_stage_auto_instantiates_before_waiting_approval(self) -> None:
        decision = next_terminal_or_runnable_state(
            [
                QueueItem(
                    wave_name="Controlled Flag-On Validation",
                    status="queued",
                    run_policy="explicit_request",
                    eligible=False,
                )
            ],
            blocker_packet_present=False,
            next_stage_candidate=StageCandidate(
                wave_name="Controller Docs Sync",
                owner="Main",
                objective="Keep controller docs aligned with enforced queue semantics.",
                artifacts_in_scope=("decisions.md", "runbook.md", "dispatch-board.md"),
                success_check="Docs and tests describe the same queue semantics.",
                why_next="Docs were the remaining safe internal follow-up after decision tightening.",
                run_policy="auto",
                within_approved_scope=True,
                non_destructive=True,
                requires_explicit_approval=False,
                repo_grounded=True,
            ),
        )

        self.assertEqual(decision.action, Action.CONTINUE)
        self.assertEqual(decision.next_wave_name, "Controller Docs Sync")
        self.assertIsNone(decision.terminal_state)
        self.assertIsNotNone(decision.instantiated_wave)
        self.assertEqual(decision.instantiated_wave["run_policy"], "auto")
        self.assertEqual(decision.instantiated_wave["owner"], "Main")
        self.assertEqual(
            decision.instantiated_wave["artifacts_in_scope"],
            ["decisions.md", "runbook.md", "dispatch-board.md"],
        )

    def test_finalize_queue_preserves_auto_instantiated_stage_reason(self) -> None:
        decision = finalize_queue_state(
            current_wave="Decision Tightening",
            queue_items=[
                QueueItem(
                    wave_name="Controlled Flag-On Validation",
                    status="queued",
                    run_policy="explicit_request",
                    eligible=False,
                )
            ],
            blocker_packet_present=False,
            next_stage_candidate=StageCandidate(
                wave_name="Controller Docs Sync",
                owner="Main",
                objective="Keep controller docs aligned with enforced queue semantics.",
                artifacts_in_scope=("decisions.md", "runbook.md", "dispatch-board.md"),
                success_check="Docs and tests describe the same queue semantics.",
                why_next="Docs were the remaining safe internal follow-up after decision tightening.",
                run_policy="auto",
                within_approved_scope=True,
                non_destructive=True,
                requires_explicit_approval=False,
                repo_grounded=True,
            ),
        )

        self.assertEqual(decision.action, Action.CONTINUE)
        self.assertEqual(decision.next_wave_name, "Controller Docs Sync")
        self.assertEqual(
            decision.reason,
            "Decision Tightening closed and auto_instantiate_safe_next_project_stage",
        )
        self.assertIsNotNone(decision.instantiated_wave)

    def test_next_stage_auto_instantiation_rejects_risky_future_work(self) -> None:
        decision = next_terminal_or_runnable_state(
            [],
            blocker_packet_present=False,
            next_stage_candidate=StageCandidate(
                wave_name="Framework Migration",
                owner="Main",
                objective="Migrate the controller to a new framework.",
                artifacts_in_scope=("backend/app/controller/runtime.py",),
                success_check="Controller works on a new framework.",
                why_next="Hypothetical risky follow-up.",
                run_policy="auto",
                within_approved_scope=True,
                non_destructive=True,
                requires_explicit_approval=False,
                repo_grounded=True,
                framework_migration=True,
            ),
        )

        self.assertEqual(decision.action, Action.DONE)
        self.assertEqual(decision.terminal_state, "DONE")
        self.assertIsNone(decision.instantiated_wave)

    def test_closed_wave_reopens_only_on_fresh_exact_blocker(self) -> None:
        blocker = FailureSignal(
            kind="failing_test",
            severity="recoverable",
            source="controller",
            details="AssertionError",
        )

        self.assertFalse(
            can_reopen_wave(
                fresh_blocker=False,
                explicit_controller_reopen=True,
                exact_blocker=is_exact_blocker_packet(
                    blocker,
                    file_path="tests/controller/test_controller_runtime.py",
                    failing_check="python -m unittest tests/controller/test_controller_runtime.py",
                    contradiction_text="AssertionError",
                    bounded_scope=True,
                ),
            )
        )

    def test_drift_review_opens_for_long_running_wave_closeout(self) -> None:
        self.assertTrue(
            should_open_drift_review(
                wave_runs_longer_than_major_step=True,
                plan_changed_after_new_evidence=False,
                touched_multiple_control_artifacts=False,
                about_to_close_or_promote_wave=True,
            )
        )

    def test_parallel_research_opens_without_blocking_main(self) -> None:
        self.assertTrue(
            should_open_parallel_research(
                freshness_matters=True,
                framework_or_vendor_claim=False,
                current_product_claim=False,
                repo_contains_answer=False,
            )
        )

    def test_parallel_repair_requires_isolated_non_conflicting_scope(self) -> None:
        blocker = FailureSignal(
            kind="runtime_error",
            severity="recoverable",
            source="controller",
            details="RuntimeError: exact isolated failure",
        )

        self.assertFalse(
            should_open_parallel_repair(
                failure_signal=blocker,
                file_path="backend/app/controller/policy.py",
                failing_check="python -m unittest tests/controller/test_controller_policy.py",
                contradiction_text="exact isolated failure",
                bounded_scope=True,
                isolated_scope=True,
                conflicts_with_active_artifact=True,
            )
        )

    def test_main_waits_when_parallel_repair_hits_current_reasoning_path(self) -> None:
        self.assertFalse(
            can_continue_while_repair_runs(
                blocker_affects_current_reasoning_path=True,
                isolated_scope=True,
                conflicts_with_active_artifact=False,
            )
        )

    def test_advisory_subagent_output_requires_explicit_merge(self) -> None:
        self.assertFalse(
            should_merge_subagent_result(
                explicit_merge_requested=False,
                mutates_controller_truth=False,
                conflicts_with_active_artifact=False,
            )
        )
        self.assertFalse(
            should_merge_subagent_result(
                explicit_merge_requested=True,
                mutates_controller_truth=True,
                conflicts_with_active_artifact=False,
            )
        )

    def test_control_plane_truth_requires_terminal_and_next_wave_alignment(self) -> None:
        self.assertFalse(
            control_plane_truth_aligned(
                ControlPlaneTruth(
                    queue_terminal_state="WAITING_USER_APPROVAL",
                    checkpoint_terminal_state="WAITING_USER_APPROVAL",
                    report_terminal_state="WAITING_USER_APPROVAL",
                    dispatch_terminal_state="DONE",
                    queue_next_wave_name="Human Write Authorization",
                    checkpoint_next_wave_name="Human Write Authorization",
                    report_next_wave_name="Human Write Authorization",
                    dispatch_next_wave_name=None,
                )
            )
        )

    def test_misaligned_control_plane_truth_derives_sync_wave(self) -> None:
        candidate = derive_next_stage_candidate(
            current_wave="Run Policy Tightening",
            queue_items=[
                QueueItem(
                    wave_name="Human Write Authorization",
                    status="queued",
                    run_policy="explicit_request",
                    eligible=False,
                    approval_authority="user",
                )
            ],
            control_plane_truth=ControlPlaneTruth(
                queue_terminal_state="WAITING_USER_APPROVAL",
                checkpoint_terminal_state="DONE",
                report_terminal_state="WAITING_USER_APPROVAL",
                dispatch_terminal_state="WAITING_USER_APPROVAL",
                queue_next_wave_name="Human Write Authorization",
                checkpoint_next_wave_name=None,
                report_next_wave_name="Human Write Authorization",
                dispatch_next_wave_name="Human Write Authorization",
            ),
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.wave_name, "Control Plane Truth Sync")
        self.assertEqual(candidate.owner, "Main")
        self.assertEqual(candidate.run_policy, "auto")
        self.assertIn("dispatch-board.md", candidate.artifacts_in_scope)

    def test_abort_terminal_state_is_available_for_hard_invariant_failure(self) -> None:
        decision = next_terminal_or_runnable_state(
            [],
            blocker_packet_present=False,
            abort_requested=True,
        )

        self.assertEqual(decision.action, Action.ABORTED)
        self.assertEqual(decision.terminal_state, "ABORTED")


if __name__ == "__main__":
    unittest.main()
