from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from backend.app.controller.models import FailureSignal


TerminalState = Literal[
    "DONE",
    "BLOCKED",
    "WAITING_APPROVAL",
    "WAITING_USER_APPROVAL",
    "ABORTED",
] | None
RunPolicy = Literal["auto", "explicit_request", "blocked_until_input"]
WaveStatus = Literal["queued", "active", "done", "blocked"]
ApprovalAuthority = Literal["main", "user"]


class Action(str, Enum):
    CONTINUE = "continue"
    REPAIR = "repair"
    REVIEW = "review"
    RESEARCH = "research"
    WAITING_USER_APPROVAL = "waiting_user_approval"
    BLOCKED = "blocked"
    DONE = "done"
    ABORTED = "aborted"


class MissingInfoAction(str, Enum):
    INFER = "infer"
    RESEARCH = "research"
    REQUEST_INPUT = "request_input"
    BLOCK = "block"


@dataclass(frozen=True)
class QueueItem:
    wave_name: str
    status: WaveStatus
    run_policy: RunPolicy
    eligible: bool
    requires_explicit_request: bool = False
    approval_authority: ApprovalAuthority = "user"
    scope_expands: bool = False
    business_logic_changed: bool = False
    framework_migration: bool = False
    production_enablement: bool = False
    external_dependency: bool = False
    destructive_change: bool = False
    irreversible_action: bool = False
    external_spend: bool = False
    requires_human_authorization: bool = False


@dataclass(frozen=True)
class StageCandidate:
    wave_name: str
    owner: str
    objective: str
    artifacts_in_scope: tuple[str, ...]
    success_check: str
    why_next: str
    within_approved_scope: bool
    non_destructive: bool
    requires_explicit_approval: bool
    repo_grounded: bool
    run_policy: RunPolicy = "auto"
    external_dependency: bool = False
    framework_migration: bool = False
    risky_global_enablement: bool = False


SAFE_STAGE_SUCCESSORS: dict[str, StageCandidate] = {
    "decision tightening": StageCandidate(
        wave_name="Controller Docs Sync",
        owner="Main",
        objective="Keep controller control docs aligned with enforced queue semantics.",
        artifacts_in_scope=("decisions.md", "runbook.md", "dispatch-board.md", "reports/README.md"),
        success_check="Controller docs and tests describe the same queue and terminal-state rules.",
        why_next="Docs are the next safe internal follow-up after decision tightening closes.",
        run_policy="auto",
        within_approved_scope=True,
        non_destructive=True,
        requires_explicit_approval=False,
        repo_grounded=True,
    ),
}


@dataclass(frozen=True)
class ControlPlaneTruth:
    queue_terminal_state: TerminalState
    checkpoint_terminal_state: TerminalState
    report_terminal_state: TerminalState
    dispatch_terminal_state: TerminalState
    queue_next_wave_name: str | None = None
    checkpoint_next_wave_name: str | None = None
    report_next_wave_name: str | None = None
    dispatch_next_wave_name: str | None = None


@dataclass(frozen=True)
class QueueDecision:
    action: Action
    terminal_state: TerminalState
    next_wave_name: str | None
    reason: str
    instantiated_wave: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "terminal_state": self.terminal_state,
            "next_wave_name": self.next_wave_name,
            "reason": self.reason,
            "instantiated_wave": self.instantiated_wave,
        }


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())


def _normalize_failure_signal(
    failure_signal: FailureSignal | dict[str, object] | None,
) -> FailureSignal | None:
    if failure_signal is None:
        return None
    if isinstance(failure_signal, FailureSignal):
        return failure_signal
    return FailureSignal(
        kind=str(failure_signal.get("kind", "")),
        severity=str(failure_signal.get("severity", "none")),
        source=str(failure_signal.get("source", "controller")),
        details=None
        if failure_signal.get("details") is None
        else str(failure_signal.get("details")),
    )


def _queue_items(queue_items: list[QueueItem | dict[str, object]]) -> list[QueueItem]:
    normalized: list[QueueItem] = []
    for item in queue_items:
        if isinstance(item, QueueItem):
            normalized.append(item)
            continue
        normalized.append(
            QueueItem(
                wave_name=str(item["wave_name"]),
                status=str(item["status"]),
                run_policy=str(item["run_policy"]),
                eligible=bool(item["eligible"]),
                requires_explicit_request=bool(item.get("requires_explicit_request", False)),
                approval_authority=str(item.get("approval_authority", "user")),
                scope_expands=bool(item.get("scope_expands", False)),
                business_logic_changed=bool(item.get("business_logic_changed", False)),
                framework_migration=bool(item.get("framework_migration", False)),
                production_enablement=bool(item.get("production_enablement", False)),
                external_dependency=bool(item.get("external_dependency", False)),
                destructive_change=bool(item.get("destructive_change", False)),
                irreversible_action=bool(item.get("irreversible_action", False)),
                external_spend=bool(item.get("external_spend", False)),
                requires_human_authorization=bool(item.get("requires_human_authorization", False)),
            )
        )
    return normalized


def _stage_candidate(
    next_stage_candidate: StageCandidate | dict[str, object] | None,
) -> StageCandidate | None:
    if next_stage_candidate is None:
        return None
    if isinstance(next_stage_candidate, StageCandidate):
        return next_stage_candidate
    return StageCandidate(
        wave_name=str(next_stage_candidate["wave_name"]),
        owner=str(next_stage_candidate.get("owner", "Main")),
        objective=str(next_stage_candidate.get("objective", "")),
        artifacts_in_scope=tuple(
            str(item) for item in next_stage_candidate.get("artifacts_in_scope", ())
        ),
        success_check=str(next_stage_candidate.get("success_check", "")),
        why_next=str(next_stage_candidate.get("why_next", "")),
        run_policy=str(next_stage_candidate.get("run_policy", "auto")),
        within_approved_scope=bool(next_stage_candidate["within_approved_scope"]),
        non_destructive=bool(next_stage_candidate["non_destructive"]),
        requires_explicit_approval=bool(next_stage_candidate["requires_explicit_approval"]),
        repo_grounded=bool(next_stage_candidate["repo_grounded"]),
        external_dependency=bool(next_stage_candidate.get("external_dependency", False)),
        framework_migration=bool(next_stage_candidate.get("framework_migration", False)),
        risky_global_enablement=bool(next_stage_candidate.get("risky_global_enablement", False)),
    )


def _control_plane_truth(
    control_plane_truth: ControlPlaneTruth | dict[str, object] | None,
) -> ControlPlaneTruth | None:
    if control_plane_truth is None:
        return None
    if isinstance(control_plane_truth, ControlPlaneTruth):
        return control_plane_truth
    return ControlPlaneTruth(
        queue_terminal_state=control_plane_truth.get("queue_terminal_state"),
        checkpoint_terminal_state=control_plane_truth.get("checkpoint_terminal_state"),
        report_terminal_state=control_plane_truth.get("report_terminal_state"),
        dispatch_terminal_state=control_plane_truth.get("dispatch_terminal_state"),
        queue_next_wave_name=None
        if control_plane_truth.get("queue_next_wave_name") is None
        else str(control_plane_truth.get("queue_next_wave_name")),
        checkpoint_next_wave_name=None
        if control_plane_truth.get("checkpoint_next_wave_name") is None
        else str(control_plane_truth.get("checkpoint_next_wave_name")),
        report_next_wave_name=None
        if control_plane_truth.get("report_next_wave_name") is None
        else str(control_plane_truth.get("report_next_wave_name")),
        dispatch_next_wave_name=None
        if control_plane_truth.get("dispatch_next_wave_name") is None
        else str(control_plane_truth.get("dispatch_next_wave_name")),
    )


def control_plane_truth_aligned(
    control_plane_truth: ControlPlaneTruth | dict[str, object] | None,
) -> bool:
    truth = _control_plane_truth(control_plane_truth)
    if truth is None:
        return True
    terminal_states = {
        truth.queue_terminal_state,
        truth.checkpoint_terminal_state,
        truth.report_terminal_state,
        truth.dispatch_terminal_state,
    }
    next_wave_names = {
        truth.queue_next_wave_name,
        truth.checkpoint_next_wave_name,
        truth.report_next_wave_name,
        truth.dispatch_next_wave_name,
    }
    return len(terminal_states) == 1 and len(next_wave_names) == 1


def derive_next_stage_candidate(
    *,
    current_wave: str,
    queue_items: list[QueueItem | dict[str, object]],
    control_plane_truth: ControlPlaneTruth | dict[str, object] | None = None,
) -> StageCandidate | None:
    truth = _control_plane_truth(control_plane_truth)
    if truth is not None and not control_plane_truth_aligned(truth):
        candidate = StageCandidate(
            wave_name="Control Plane Truth Sync",
            owner="Main",
            objective="Align queue, checkpoint, report, and dispatch controller truth before any terminal stop.",
            artifacts_in_scope=(
                "dispatch-board.md",
                "reports/README.md",
                "decisions.md",
                "runbook.md",
            ),
            success_check="All controller truth surfaces agree on terminal state and next wave.",
            why_next="Misaligned controller truth must be repaired before a terminal state can be trusted.",
            run_policy="auto",
            within_approved_scope=True,
            non_destructive=True,
            requires_explicit_approval=False,
            repo_grounded=True,
        )
        if any(item.wave_name == candidate.wave_name for item in _queue_items(queue_items)):
            return None
        return candidate
    candidate = SAFE_STAGE_SUCCESSORS.get(current_wave.strip().casefold())
    if candidate is None:
        return None
    if any(item.wave_name == candidate.wave_name for item in _queue_items(queue_items)):
        return None
    return candidate


def is_exact_blocker_packet(
    failure_signal: FailureSignal | dict[str, object] | None,
    *,
    file_path: str | None,
    failing_check: str | None,
    contradiction_text: str | None,
    bounded_scope: bool,
) -> bool:
    signal = _normalize_failure_signal(failure_signal)
    if signal is None:
        return False
    if signal.severity == "none":
        return False
    return (
        _has_text(signal.kind)
        and _has_text(signal.details)
        and _has_text(file_path)
        and _has_text(failing_check)
        and _has_text(contradiction_text)
        and bounded_scope
    )


def is_fresh_blocker(*, exact_blocker: bool, stale: bool, superseded: bool) -> bool:
    return exact_blocker and not stale and not superseded


def can_reopen_wave(*, fresh_blocker: bool, explicit_controller_reopen: bool, exact_blocker: bool) -> bool:
    return fresh_blocker and explicit_controller_reopen and exact_blocker


def should_open_repair(
    failure_signal: FailureSignal | dict[str, object] | None,
    *,
    file_path: str | None,
    failing_check: str | None,
    contradiction_text: str | None,
    bounded_scope: bool,
) -> bool:
    return is_exact_blocker_packet(
        failure_signal,
        file_path=file_path,
        failing_check=failing_check,
        contradiction_text=contradiction_text,
        bounded_scope=bounded_scope,
    )


def should_open_review(
    *,
    runtime_changed: bool,
    files_changed: int,
    contract_changed: bool,
    blocker_previously_stalled: bool,
    confidence_low: bool,
) -> bool:
    return (
        runtime_changed
        or files_changed > 1
        or contract_changed
        or blocker_previously_stalled
        or confidence_low
    )


def is_review_required(
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


def should_open_research(
    *,
    freshness_matters: bool,
    framework_or_vendor_claim: bool,
    repo_contains_answer: bool,
    architecture_comparison: bool,
) -> bool:
    if repo_contains_answer:
        return False
    return freshness_matters or framework_or_vendor_claim or architecture_comparison


def should_use_web_search(
    *,
    freshness_matters: bool,
    framework_or_vendor_claim: bool,
    repo_contains_answer: bool,
) -> bool:
    if repo_contains_answer:
        return False
    return freshness_matters or framework_or_vendor_claim


def requires_explicit_approval(
    *,
    destructive_change: bool,
    production_enablement: bool,
    external_spend: bool,
    irreversible_action: bool,
    required_input_missing: bool,
    scope_expands: bool = False,
    business_logic_changed: bool = False,
    checkpoint_schema_widening: bool = False,
    framework_migration: bool = False,
    explicit_request_wave: bool = False,
) -> bool:
    return (
        destructive_change
        or production_enablement
        or external_spend
        or irreversible_action
        or required_input_missing
        or scope_expands
        or business_logic_changed
        or checkpoint_schema_widening
        or framework_migration
        or explicit_request_wave
    )


def requires_explicit_user_approval(
    *,
    destructive_change: bool,
    production_enablement: bool,
    external_spend: bool,
    irreversible_action: bool,
    required_input_missing: bool,
) -> bool:
    return requires_explicit_approval(
        destructive_change=destructive_change,
        production_enablement=production_enablement,
        external_spend=external_spend,
        irreversible_action=irreversible_action,
        required_input_missing=required_input_missing,
    )


def can_continue_without_user_input(
    *,
    internal_hardening: bool,
    docs_sync: bool,
    bounded_fix: bool,
    local_validation: bool,
    repo_grounded: bool,
    safe_research: bool,
    internal_design: bool = False,
    approved_scope: bool = True,
    business_logic_unchanged: bool = True,
    checkpoint_schema_widening: bool = False,
    framework_migration: bool = False,
    destructive_change: bool,
    production_enablement: bool,
    external_spend: bool,
    irreversible_action: bool,
    required_input_missing: bool,
) -> bool:
    if requires_explicit_approval(
        destructive_change=destructive_change,
        production_enablement=production_enablement,
        external_spend=external_spend,
        irreversible_action=irreversible_action,
        required_input_missing=required_input_missing,
        scope_expands=not approved_scope,
        business_logic_changed=not business_logic_unchanged,
        checkpoint_schema_widening=checkpoint_schema_widening,
        framework_migration=framework_migration,
    ):
        return False
    return (
        internal_hardening
        or docs_sync
        or bounded_fix
        or local_validation
        or repo_grounded
        or safe_research
        or (
            internal_design
            and approved_scope
            and business_logic_unchanged
            and not checkpoint_schema_widening
            and not framework_migration
        )
    )


def can_main_proceed(
    *,
    internal_hardening: bool,
    docs_sync: bool,
    bounded_fix: bool,
    local_validation: bool,
    repo_grounded: bool,
    safe_research: bool,
    internal_design: bool = False,
    approved_scope: bool = True,
    business_logic_unchanged: bool = True,
    checkpoint_schema_widening: bool = False,
    framework_migration: bool = False,
    destructive_change: bool,
    production_enablement: bool,
    external_spend: bool,
    irreversible_action: bool,
    required_input_missing: bool,
) -> bool:
    return can_continue_without_user_input(
        internal_hardening=internal_hardening,
        docs_sync=docs_sync,
        bounded_fix=bounded_fix,
        local_validation=local_validation,
        repo_grounded=repo_grounded,
        safe_research=safe_research,
        internal_design=internal_design,
        approved_scope=approved_scope,
        business_logic_unchanged=business_logic_unchanged,
        checkpoint_schema_widening=checkpoint_schema_widening,
        framework_migration=framework_migration,
        destructive_change=destructive_change,
        production_enablement=production_enablement,
        external_spend=external_spend,
        irreversible_action=irreversible_action,
        required_input_missing=required_input_missing,
    )


def should_delegate(*, exact_blocker: bool, selective_review: bool, needs_research: bool) -> bool:
    return exact_blocker or selective_review or needs_research


def can_main_handle_directly(
    *,
    exact_blocker: bool,
    selective_review: bool,
    needs_research: bool,
) -> bool:
    return not should_delegate(
        exact_blocker=exact_blocker,
        selective_review=selective_review,
        needs_research=needs_research,
    )


def should_open_drift_review(
    *,
    wave_runs_longer_than_major_step: bool,
    plan_changed_after_new_evidence: bool,
    touched_multiple_control_artifacts: bool,
    about_to_close_or_promote_wave: bool,
) -> bool:
    return (
        wave_runs_longer_than_major_step
        or plan_changed_after_new_evidence
        or touched_multiple_control_artifacts
        or about_to_close_or_promote_wave
    )


def should_open_parallel_research(
    *,
    freshness_matters: bool,
    framework_or_vendor_claim: bool,
    current_product_claim: bool,
    repo_contains_answer: bool,
) -> bool:
    if repo_contains_answer:
        return False
    return freshness_matters or framework_or_vendor_claim or current_product_claim


def should_open_parallel_repair(
    *,
    failure_signal: FailureSignal | dict[str, object] | None,
    file_path: str | None,
    failing_check: str | None,
    contradiction_text: str | None,
    bounded_scope: bool,
    isolated_scope: bool,
    conflicts_with_active_artifact: bool,
) -> bool:
    return (
        should_open_repair(
            failure_signal,
            file_path=file_path,
            failing_check=failing_check,
            contradiction_text=contradiction_text,
            bounded_scope=bounded_scope,
        )
        and isolated_scope
        and not conflicts_with_active_artifact
    )


def can_continue_while_repair_runs(
    *,
    blocker_affects_current_reasoning_path: bool,
    isolated_scope: bool,
    conflicts_with_active_artifact: bool,
) -> bool:
    return (
        not blocker_affects_current_reasoning_path
        and isolated_scope
        and not conflicts_with_active_artifact
    )


def should_merge_subagent_result(
    *,
    explicit_merge_requested: bool,
    mutates_controller_truth: bool,
    conflicts_with_active_artifact: bool,
) -> bool:
    return (
        explicit_merge_requested
        and not mutates_controller_truth
        and not conflicts_with_active_artifact
    )


def is_blocked_by_missing_required_input(
    *,
    required_input_missing: bool,
    repo_or_context_sufficient: bool,
) -> bool:
    return required_input_missing and not repo_or_context_sufficient


def can_infer_from_repo_or_context(
    *,
    repo_or_context_sufficient: bool,
    required_input_missing: bool,
) -> bool:
    return repo_or_context_sufficient and not required_input_missing


def missing_info_action(
    *,
    required_input_missing: bool,
    repo_or_context_sufficient: bool,
    freshness_required: bool,
) -> MissingInfoAction:
    if can_infer_from_repo_or_context(
        repo_or_context_sufficient=repo_or_context_sufficient,
        required_input_missing=required_input_missing,
    ):
        return MissingInfoAction.INFER
    if freshness_required:
        return MissingInfoAction.RESEARCH
    if required_input_missing:
        return MissingInfoAction.REQUEST_INPUT
    return MissingInfoAction.INFER


def is_safe_auto_wave(
    *,
    run_policy: RunPolicy,
    eligible: bool,
    destructive_change: bool,
    production_enablement: bool,
    external_spend: bool,
    irreversible_action: bool,
) -> bool:
    return (
        run_policy == "auto"
        and eligible
        and not requires_explicit_user_approval(
            destructive_change=destructive_change,
            production_enablement=production_enablement,
            external_spend=external_spend,
            irreversible_action=irreversible_action,
            required_input_missing=False,
        )
    )


def can_main_self_approve_wave(item: QueueItem) -> bool:
    return (
        item.approval_authority == "main"
        and not item.scope_expands
        and not item.business_logic_changed
        and not item.framework_migration
        and not item.production_enablement
        and not item.external_dependency
        and not item.destructive_change
        and not item.irreversible_action
        and not item.external_spend
        and not item.requires_human_authorization
    )


def self_approved_wave(item: QueueItem) -> dict[str, object]:
    return {
        "wave_name": item.wave_name,
        "status": "active",
        "run_policy": item.run_policy,
        "eligible": True,
        "requires_explicit_request": False,
        "approval_authority": item.approval_authority,
    }


def is_wave_complete(
    *,
    intended_change_exists: bool,
    required_checks_passed: bool,
    blocker_packet_present: bool,
) -> bool:
    return intended_change_exists and required_checks_passed and not blocker_packet_present


def can_promote_next_wave(
    queue_items: list[QueueItem | dict[str, object]],
    *,
    blocker_packet_present: bool,
) -> bool:
    if blocker_packet_present:
        return False
    return any(item.run_policy == "auto" and item.eligible for item in _queue_items(queue_items))


def can_auto_instantiate_next_stage(
    next_stage_candidate: StageCandidate | dict[str, object] | None,
) -> bool:
    candidate = _stage_candidate(next_stage_candidate)
    if candidate is None:
        return False
    return (
        candidate.within_approved_scope
        and candidate.non_destructive
        and not candidate.requires_explicit_approval
        and candidate.repo_grounded
        and not candidate.external_dependency
        and not candidate.framework_migration
        and not candidate.risky_global_enablement
    )


def auto_instantiate_next_stage(
    next_stage_candidate: StageCandidate | dict[str, object] | None,
) -> dict[str, object] | None:
    candidate = _stage_candidate(next_stage_candidate)
    if candidate is None or not can_auto_instantiate_next_stage(candidate):
        return None
    return {
        "wave_name": candidate.wave_name,
        "owner": candidate.owner,
        "objective": candidate.objective,
        "artifacts_in_scope": list(candidate.artifacts_in_scope),
        "success_check": candidate.success_check,
        "why_next": candidate.why_next,
        "status": "queued",
        "run_policy": candidate.run_policy,
        "eligible": True,
        "requires_explicit_request": False,
        "approval_authority": "main",
    }


def next_terminal_or_runnable_state(
    queue_items: list[QueueItem | dict[str, object]],
    *,
    blocker_packet_present: bool,
    next_stage_candidate: StageCandidate | dict[str, object] | None = None,
    abort_requested: bool = False,
) -> QueueDecision:
    items = _queue_items(queue_items)
    if abort_requested:
        return QueueDecision(
            action=Action.ABORTED,
            terminal_state="ABORTED",
            next_wave_name=None,
            reason="hard_invariant_requires_abort",
        )
    if blocker_packet_present:
        return QueueDecision(
            action=Action.BLOCKED,
            terminal_state="BLOCKED",
            next_wave_name=None,
            reason="exact_blocker_packet_present",
        )

    for item in items:
        if item.run_policy == "auto" and item.eligible:
            return QueueDecision(
                action=Action.CONTINUE,
                terminal_state=None,
                next_wave_name=item.wave_name,
                reason="activate_next_eligible_auto_wave",
            )

    for item in items:
        if item.run_policy == "explicit_request" and can_main_self_approve_wave(item):
            approved_wave = self_approved_wave(item)
            return QueueDecision(
                action=Action.CONTINUE,
                terminal_state=None,
                next_wave_name=item.wave_name,
                reason="main_self_approved_internal_wave",
                instantiated_wave=approved_wave,
            )

    instantiated_wave = auto_instantiate_next_stage(next_stage_candidate)
    if instantiated_wave is not None:
        return QueueDecision(
            action=Action.CONTINUE,
            terminal_state=None,
            next_wave_name=str(instantiated_wave["wave_name"]),
            reason="auto_instantiate_safe_next_project_stage",
            instantiated_wave=instantiated_wave,
        )

    for item in items:
        if item.run_policy == "explicit_request":
            return QueueDecision(
                action=Action.WAITING_USER_APPROVAL,
                terminal_state="WAITING_USER_APPROVAL",
                next_wave_name=item.wave_name,
                reason="explicit_request_wave_requires_user_approval",
            )

    return QueueDecision(
        action=Action.DONE,
        terminal_state="DONE",
        next_wave_name=None,
        reason="no_runnable_wave_remains",
    )


def finalize_queue_state(
    *,
    current_wave: str,
    queue_items: list[QueueItem | dict[str, object]],
    blocker_packet_present: bool,
    next_stage_candidate: StageCandidate | dict[str, object] | None = None,
    abort_requested: bool = False,
) -> QueueDecision:
    decision = next_terminal_or_runnable_state(
        queue_items,
        blocker_packet_present=blocker_packet_present,
        next_stage_candidate=next_stage_candidate,
        abort_requested=abort_requested,
    )
    if decision.action == Action.CONTINUE:
        if decision.instantiated_wave is not None:
            reason = f"{current_wave} closed and {decision.reason}"
        else:
            reason = f"{current_wave} closed and next eligible auto wave activated"
        return QueueDecision(
            action=decision.action,
            terminal_state=decision.terminal_state,
            next_wave_name=decision.next_wave_name,
            reason=reason,
            instantiated_wave=decision.instantiated_wave,
        )
    return QueueDecision(
        action=decision.action,
        terminal_state=decision.terminal_state,
        next_wave_name=decision.next_wave_name,
        reason=f"{current_wave} closed and {decision.reason}",
        instantiated_wave=decision.instantiated_wave,
    )
