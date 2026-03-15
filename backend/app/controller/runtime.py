from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from backend.app.config import AppConfig
from backend.app.controller.models import (
    CompactionState,
    ControllerCheckpoint,
    ControllerDecision,
    FailureSignal,
    ProtectedCore,
    QueueState,
)
from backend.app.controller.policy import (
    QueueDecision,
    can_continue_while_repair_runs,
    derive_next_stage_candidate,
    finalize_queue_state,
    next_terminal_or_runnable_state,
    should_merge_subagent_result,
    should_open_drift_review,
    should_open_parallel_repair,
    should_open_parallel_research,
    should_open_repair,
    should_open_review,
)
from backend.app.controller.precedence import ControllerSignals, resolve_controller_action
from backend.app.controller.strategies import (
    CompressionControllerAdapter,
    CompressionEnvelope,
    Instinct8StrategyProtocol,
)
from backend.app.contracts import load_json_contract


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ControllerRouteResult:
    authoritative: ControllerDecision
    legacy_decision: ControllerDecision
    new_decision: ControllerDecision | None
    decisions_differ: bool
    difference_reason: str


@dataclass(frozen=True)
class ControllerResumeResult:
    protected_core: ProtectedCore
    decision: ControllerDecision
    checkpoint: ControllerCheckpoint | None


@dataclass(frozen=True)
class ControllerCompactionResult:
    envelope: CompressionEnvelope
    checkpoint: ControllerCheckpoint
    decision: ControllerDecision


class ControllerRuntime:
    def __init__(self, config: AppConfig):
        self.config = config
        self._validator = Draft202012Validator(load_json_contract("controller_checkpoint"))

    def checkpoint_path(self, session_id: str) -> Path:
        return self.config.controller_checkpoint_dir / f"{session_id}.json"

    def route_decision(
        self,
        *,
        session_id: str,
        stage_name: str,
        legacy_action: str,
        signals: ControllerSignals,
    ) -> ControllerRouteResult:
        legacy_decision = ControllerDecision(
            action=legacy_action,
            reason=f"legacy_{stage_name}_route",
            source="controller",
        )
        if not self.config.controller_precedence_enabled:
            return ControllerRouteResult(
                authoritative=legacy_decision,
                legacy_decision=legacy_decision,
                new_decision=None,
                decisions_differ=False,
                difference_reason="precedence_flag_disabled",
            )

        new_decision = resolve_controller_action(signals)
        decisions_differ = legacy_decision.action != new_decision.action
        difference_reason = (
            "authoritative_action_changed_by_precedence"
            if decisions_differ
            else "legacy_and_new_actions_match"
        )
        logger.info(
            "controller_shadow_decision %s",
            json.dumps(
                {
                    "session_id": session_id,
                    "stage_name": stage_name,
                    "legacy_controller_decision": legacy_decision.to_dict(),
                    "new_controller_decision": new_decision.to_dict(),
                    "decision_differs": decisions_differ,
                    "difference_reason": difference_reason,
                },
                sort_keys=True,
            ),
        )
        return ControllerRouteResult(
            authoritative=new_decision,
            legacy_decision=legacy_decision,
            new_decision=new_decision,
            decisions_differ=decisions_differ,
            difference_reason=difference_reason,
        )

    def record_stage_transition(
        self,
        *,
        session_id: str,
        stage_name: str,
        protected_core: ProtectedCore,
        route_result: ControllerRouteResult,
        validated_artifacts: tuple[str, ...] = (),
        failure_signal: FailureSignal | None = None,
    ) -> ControllerCheckpoint | None:
        if not self.config.controller_checkpoints_enabled:
            return None

        current = self.load_checkpoint(session_id).checkpoint
        checkpoint = ControllerCheckpoint(
            checkpoint_id=f"{session_id}:{stage_name}",
            protected_core=protected_core,
            compaction=current.compaction
            if current is not None
            else CompactionState(
                strategy_name="none",
                compaction_sequence=0,
                halo_summary="",
                recent_turn_ids=(),
            ),
            validated_artifacts=validated_artifacts,
            active_failure_signal=failure_signal or self._default_failure_signal(),
            controller_last_decision=route_result.authoritative,
            queue=current.queue if current is not None else None,
            terminal_state=(
                "ABORTED"
                if route_result.authoritative.action == "abort"
                else None
            ),
        )
        self._write_checkpoint(session_id, checkpoint)
        return checkpoint

    def prepare_compaction(
        self,
        *,
        session_id: str,
        fallback_protected_core: ProtectedCore,
        strategy: Instinct8StrategyProtocol,
        halo_turns: list[dict[str, Any]],
        recent_turns: list[dict[str, Any]],
        trigger_point: int,
    ) -> ControllerCompactionResult | None:
        if not self.config.controller_checkpoints_enabled:
            return None

        loaded = self.load_checkpoint(session_id)
        checkpoint = loaded.checkpoint
        protected_core = checkpoint.protected_core if checkpoint is not None else fallback_protected_core
        decision = (
            checkpoint.controller_last_decision
            if checkpoint is not None
            else loaded.decision
        )
        base_checkpoint = checkpoint or ControllerCheckpoint(
            checkpoint_id=f"{session_id}:before_compaction",
            protected_core=protected_core,
            compaction=CompactionState(
                strategy_name=strategy.name(),
                compaction_sequence=0,
                halo_summary="",
                recent_turn_ids=(),
            ),
            validated_artifacts=(),
            active_failure_signal=self._default_failure_signal(),
            controller_last_decision=decision,
        )

        adapter = CompressionControllerAdapter(strategy)
        adapter.prime(protected_core)
        envelope = adapter.compact(
            checkpoint=base_checkpoint,
            halo_turns=halo_turns,
            recent_turns=recent_turns,
            trigger_point=trigger_point,
        )
        updated_checkpoint = ControllerCheckpoint(
            checkpoint_id=f"{session_id}:before_compaction",
            protected_core=protected_core,
            compaction=CompactionState(
                strategy_name=envelope.strategy_name,
                compaction_sequence=base_checkpoint.compaction.compaction_sequence + 1,
                halo_summary=envelope.compressed_halo,
                recent_turn_ids=tuple(
                    int(turn["id"])
                    for turn in recent_turns
                    if isinstance(turn.get("id"), int)
                ),
                drift_status=base_checkpoint.compaction.drift_status,
            ),
            validated_artifacts=base_checkpoint.validated_artifacts,
            active_failure_signal=base_checkpoint.active_failure_signal,
            controller_last_decision=decision,
            queue=base_checkpoint.queue,
            terminal_state=base_checkpoint.terminal_state,
        )
        self._write_checkpoint(session_id, updated_checkpoint)
        return ControllerCompactionResult(
            envelope=envelope,
            checkpoint=updated_checkpoint,
            decision=decision,
        )

    def load_checkpoint(self, session_id: str) -> ControllerResumeResult:
        if not self.config.controller_checkpoints_enabled:
            return ControllerResumeResult(
                protected_core=ProtectedCore(
                    task_goal="",
                    expected_output="",
                    current_step="",
                    resume_point="",
                    hard_constraints=(),
                    business_invariants=(),
                ),
                decision=ControllerDecision(
                    action="review",
                    reason="checkpoint_flag_disabled",
                    source="controller",
                ),
                checkpoint=None,
            )

        path = self.checkpoint_path(session_id)
        if not path.exists():
            return ControllerResumeResult(
                protected_core=ProtectedCore(
                    task_goal="",
                    expected_output="",
                    current_step="",
                    resume_point="",
                    hard_constraints=(),
                    business_invariants=(),
                ),
                decision=ControllerDecision(
                    action="review",
                    reason="checkpoint_missing_fail_soft",
                    source="controller",
                ),
                checkpoint=None,
            )

        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            return ControllerResumeResult(
                protected_core=ProtectedCore(
                    task_goal="",
                    expected_output="",
                    current_step="",
                    resume_point="",
                    hard_constraints=(),
                    business_invariants=(),
                ),
                decision=ControllerDecision(
                    action="review",
                    reason="checkpoint_unreadable_fail_soft",
                    source="controller",
                ),
                checkpoint=None,
            )

        errors = sorted(self._validator.iter_errors(payload), key=str)
        if errors:
            return ControllerResumeResult(
                protected_core=ProtectedCore(
                    task_goal="",
                    expected_output="",
                    current_step="",
                    resume_point="",
                    hard_constraints=(),
                    business_invariants=(),
                ),
                decision=ControllerDecision(
                    action="review",
                    reason="checkpoint_packet_invalid_fail_soft",
                    source="controller",
                ),
                checkpoint=None,
            )

        checkpoint = ControllerCheckpoint.from_dict(payload)
        return ControllerResumeResult(
            protected_core=checkpoint.protected_core,
            decision=checkpoint.controller_last_decision,
            checkpoint=checkpoint,
        )

    def resume(
        self,
        *,
        session_id: str,
        fallback_protected_core: ProtectedCore,
    ) -> ControllerResumeResult:
        if not self.config.controller_checkpoints_enabled:
            return ControllerResumeResult(
                protected_core=fallback_protected_core,
                decision=ControllerDecision(
                    action="review",
                    reason="checkpoint_flag_disabled",
                    source="controller",
                ),
                checkpoint=None,
            )

        loaded = self.load_checkpoint(session_id)
        if loaded.checkpoint is None:
            return ControllerResumeResult(
                protected_core=fallback_protected_core,
                decision=loaded.decision,
                checkpoint=None,
            )

        checkpoint = loaded.checkpoint

        # Precedence 1: If checkpoint has terminal_state, honor it directly
        # A blocked/done/waiting checkpoint must stay terminal on resume
        if checkpoint.terminal_state is not None:
            # Map terminal state literal to action
            terminal_to_action = {
                "DONE": "done",
                "BLOCKED": "blocked",
                "WAITING_USER_APPROVAL": "waiting_user_approval",
                "ABORTED": "aborted",
            }
            return ControllerResumeResult(
                protected_core=checkpoint.protected_core,
                decision=ControllerDecision(
                    action=terminal_to_action.get(
                        checkpoint.terminal_state,
                        checkpoint.terminal_state,
                    ),
                    reason=f"resume_from_preserved_terminal_state_{checkpoint.terminal_state}",
                    source="controller",
                ),
                checkpoint=checkpoint,
            )

        # Precedence 2: Re-evaluate queue state on resume for fresh decision
        # Only when checkpoint is non-terminal (terminal_state is None)
        if checkpoint.queue is not None:
            # Build queue items from checkpoint queue snapshot
            queue_items = [
                {
                    "wave_name": checkpoint.queue.wave_name,
                    "status": checkpoint.queue.status,
                    "run_policy": checkpoint.queue.run_policy,
                    "eligible": checkpoint.queue.eligible,
                    "requires_explicit_request": checkpoint.queue.requires_explicit_request,
                    "approval_authority": checkpoint.queue.approval_authority,
                }
            ]

            # Fresh decision based on checkpoint queue truth
            fresh_decision = self.queue_terminal_or_runnable_state(
                queue_items=queue_items,
                blocker_packet_present=False,
            )

            return ControllerResumeResult(
                protected_core=checkpoint.protected_core,
                decision=ControllerDecision(
                    action=fresh_decision.action.value,
                    reason="resume_from_checkpoint_queue_truth",
                    source="controller",
                ),
                checkpoint=checkpoint,
            )

        return loaded

    def review_required(
        self,
        *,
        runtime_changed: bool,
        files_changed: int,
        contract_changed: bool,
        blocker_previously_stalled: bool,
        confidence_low: bool,
    ) -> bool:
        return should_open_review(
            runtime_changed=runtime_changed,
            files_changed=files_changed,
            contract_changed=contract_changed,
            blocker_previously_stalled=blocker_previously_stalled,
            confidence_low=confidence_low,
        )

    def repair_required(
        self,
        *,
        failure_signal: FailureSignal | dict[str, object] | None,
        file_path: str | None,
        failing_check: str | None,
        contradiction_text: str | None,
        bounded_scope: bool,
    ) -> bool:
        return should_open_repair(
            failure_signal,
            file_path=file_path,
            failing_check=failing_check,
            contradiction_text=contradiction_text,
            bounded_scope=bounded_scope,
        )

    def drift_review_required(
        self,
        *,
        wave_runs_longer_than_major_step: bool,
        plan_changed_after_new_evidence: bool,
        touched_multiple_control_artifacts: bool,
        about_to_close_or_promote_wave: bool,
    ) -> bool:
        return should_open_drift_review(
            wave_runs_longer_than_major_step=wave_runs_longer_than_major_step,
            plan_changed_after_new_evidence=plan_changed_after_new_evidence,
            touched_multiple_control_artifacts=touched_multiple_control_artifacts,
            about_to_close_or_promote_wave=about_to_close_or_promote_wave,
        )

    def parallel_research_required(
        self,
        *,
        freshness_matters: bool,
        framework_or_vendor_claim: bool,
        current_product_claim: bool,
        repo_contains_answer: bool,
    ) -> bool:
        return should_open_parallel_research(
            freshness_matters=freshness_matters,
            framework_or_vendor_claim=framework_or_vendor_claim,
            current_product_claim=current_product_claim,
            repo_contains_answer=repo_contains_answer,
        )

    def parallel_repair_required(
        self,
        *,
        failure_signal: FailureSignal | dict[str, object] | None,
        file_path: str | None,
        failing_check: str | None,
        contradiction_text: str | None,
        bounded_scope: bool,
        isolated_scope: bool,
        conflicts_with_active_artifact: bool,
    ) -> bool:
        return should_open_parallel_repair(
            failure_signal=failure_signal,
            file_path=file_path,
            failing_check=failing_check,
            contradiction_text=contradiction_text,
            bounded_scope=bounded_scope,
            isolated_scope=isolated_scope,
            conflicts_with_active_artifact=conflicts_with_active_artifact,
        )

    def can_continue_with_parallel_repair(
        self,
        *,
        blocker_affects_current_reasoning_path: bool,
        isolated_scope: bool,
        conflicts_with_active_artifact: bool,
    ) -> bool:
        return can_continue_while_repair_runs(
            blocker_affects_current_reasoning_path=blocker_affects_current_reasoning_path,
            isolated_scope=isolated_scope,
            conflicts_with_active_artifact=conflicts_with_active_artifact,
        )

    def should_merge_parallel_result(
        self,
        *,
        explicit_merge_requested: bool,
        mutates_controller_truth: bool,
        conflicts_with_active_artifact: bool,
    ) -> bool:
        return should_merge_subagent_result(
            explicit_merge_requested=explicit_merge_requested,
            mutates_controller_truth=mutates_controller_truth,
            conflicts_with_active_artifact=conflicts_with_active_artifact,
        )

    def queue_terminal_or_runnable_state(
        self,
        *,
        queue_items: list[dict[str, object]],
        blocker_packet_present: bool,
        next_stage_candidate: dict[str, object] | None = None,
        abort_requested: bool = False,
    ) -> QueueDecision:
        return next_terminal_or_runnable_state(
            queue_items,
            blocker_packet_present=blocker_packet_present,
            next_stage_candidate=next_stage_candidate,
            abort_requested=abort_requested,
        )

    def finalize_queue(
        self,
        *,
        session_id: str | None = None,
        current_wave: str,
        queue_items: list[dict[str, object]],
        blocker_packet_present: bool,
        next_stage_candidate: dict[str, object] | None = None,
        control_plane_truth: dict[str, object] | None = None,
        abort_requested: bool = False,
    ) -> QueueDecision:
        candidate = next_stage_candidate
        should_derive_candidate = (
            candidate is None
            and (
                session_id is None
                or control_plane_truth is not None
            )
        )
        if should_derive_candidate:
            derived = derive_next_stage_candidate(
                current_wave=current_wave,
                queue_items=queue_items,
                control_plane_truth=control_plane_truth,
            )
            if derived is not None:
                candidate = {
                    "wave_name": derived.wave_name,
                    "owner": derived.owner,
                    "objective": derived.objective,
                    "artifacts_in_scope": list(derived.artifacts_in_scope),
                    "success_check": derived.success_check,
                    "why_next": derived.why_next,
                    "run_policy": derived.run_policy,
                    "within_approved_scope": derived.within_approved_scope,
                    "non_destructive": derived.non_destructive,
                    "requires_explicit_approval": derived.requires_explicit_approval,
                    "repo_grounded": derived.repo_grounded,
                    "external_dependency": derived.external_dependency,
                    "framework_migration": derived.framework_migration,
                    "risky_global_enablement": derived.risky_global_enablement,
                }
        decision = finalize_queue_state(
            current_wave=current_wave,
            queue_items=queue_items,
            blocker_packet_present=blocker_packet_present,
            next_stage_candidate=candidate,
            abort_requested=abort_requested,
        )
        if session_id is not None:
            self._persist_queue_truth(
                session_id=session_id,
                queue_items=queue_items,
                decision=decision,
            )
        return decision

    def _write_checkpoint(self, session_id: str, checkpoint: ControllerCheckpoint) -> None:
        self.config.controller_checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path(session_id).write_text(json.dumps(checkpoint.to_dict(), indent=2))

    def _default_failure_signal(self) -> FailureSignal:
        return FailureSignal(
            kind="none",
            severity="none",
            source="controller",
            details=None,
        )

    def _persist_queue_truth(
        self,
        *,
        session_id: str,
        queue_items: list[dict[str, object]],
        decision: QueueDecision,
    ) -> None:
        loaded = self.load_checkpoint(session_id)
        checkpoint = loaded.checkpoint
        if checkpoint is None:
            return
        queue_snapshot = self._queue_snapshot_for_decision(queue_items=queue_items, decision=decision)
        updated = ControllerCheckpoint(
            checkpoint_id=checkpoint.checkpoint_id,
            protected_core=checkpoint.protected_core,
            compaction=checkpoint.compaction,
            validated_artifacts=checkpoint.validated_artifacts,
            active_failure_signal=checkpoint.active_failure_signal,
            controller_last_decision=checkpoint.controller_last_decision,
            queue=queue_snapshot,
            terminal_state=decision.terminal_state,
            created_at=checkpoint.created_at,
            checkpoint_version=checkpoint.checkpoint_version,
        )
        self._write_checkpoint(session_id, updated)

    def _queue_snapshot_for_decision(
        self,
        *,
        queue_items: list[dict[str, object]],
        decision: QueueDecision,
    ) -> QueueState | None:
        if decision.instantiated_wave is not None:
            return QueueState(
                wave_name=str(decision.instantiated_wave["wave_name"]),
                status="active" if decision.action.value == "continue" else str(decision.instantiated_wave["status"]),
                run_policy=str(decision.instantiated_wave["run_policy"]),
                eligible=bool(decision.instantiated_wave["eligible"]),
                requires_explicit_request=bool(
                    decision.instantiated_wave.get("requires_explicit_request", False)
                ),
                approval_authority=str(decision.instantiated_wave.get("approval_authority", "user")),
            )
        if decision.next_wave_name is None:
            return None
        for item in queue_items:
            if str(item.get("wave_name")) != decision.next_wave_name:
                continue
            return QueueState(
                wave_name=str(item["wave_name"]),
                status="active" if decision.action.value == "continue" else str(item["status"]),
                run_policy=str(item["run_policy"]),
                eligible=bool(item["eligible"]),
                requires_explicit_request=bool(item.get("requires_explicit_request", False)),
                approval_authority=str(item.get("approval_authority", "user")),
            )
        return None
