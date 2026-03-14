from __future__ import annotations

from backend.app.config import AppConfig, load_config
from backend.app.controller.models import ProtectedCore
from backend.app.controller.precedence import ControllerSignals
from backend.app.controller.runtime import (
    ControllerCompactionResult,
    ControllerResumeResult,
    ControllerRouteResult,
    ControllerRuntime,
)
from backend.app.controller.strategies import Instinct8StrategyProtocol
from backend.app.contracts import load_json_contract, load_yaml_contract


def build_orchestrator_graph(config: AppConfig | None = None) -> dict[str, object]:
    active_config = config or load_config()
    tool_contract = load_yaml_contract("tool_schema")
    permission_contract = load_json_contract("permission_context")
    response_contract = load_json_contract("agent_response")

    graph = {
        "read_path": {
            "tool_families": ["read_tools"],
            "permission_policy": permission_contract["properties"]["safety_context"]["properties"][
                "read_path_policy"
            ]["enum"][0],
        },
        "write_path": {
            "confirmation_required": tool_contract["execution_model"]["write_tools"][
                "confirmation_required"
            ],
            "response_intents": [
                "write_confirmation_required",
                "write_submitted",
                "write_denied",
            ],
            "response_contract": response_contract["contract_name"],
        },
    }
    if not (
        active_config.controller_checkpoints_enabled or active_config.controller_precedence_enabled
    ):
        return graph

    graph["controller"] = {
        "feature_flags": {
            "MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED": active_config.controller_checkpoints_enabled,
            "MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED": active_config.controller_precedence_enabled,
        },
        "hook_points": [
            "controller_stage_transition",
            "controller_route_decision",
            "controller_prepare_compaction",
            "controller_resume",
            "controller_should_open_drift_review",
            "controller_should_open_parallel_research",
            "controller_should_open_parallel_repair",
            "controller_can_continue_while_repair_runs",
            "controller_should_merge_subagent_result",
            "controller_should_open_repair",
            "controller_should_open_review",
            "controller_next_terminal_or_runnable_state",
            "controller_finalize_queue_state",
        ],
    }
    return graph


def _runtime(config: AppConfig | None = None) -> ControllerRuntime:
    return ControllerRuntime(config or load_config())


def controller_route_decision(
    *,
    session_id: str,
    stage_name: str,
    legacy_action: str,
    review_outcome: str = "none",
    validator_outcome: str = "unknown",
    triage_abort_requested: bool = False,
    concrete_failure: bool = False,
    config: AppConfig | None = None,
) -> ControllerRouteResult:
    return _runtime(config).route_decision(
        session_id=session_id,
        stage_name=stage_name,
        legacy_action=legacy_action,
        signals=ControllerSignals(
            review_outcome=review_outcome,
            validator_outcome=validator_outcome,
            triage_abort_requested=triage_abort_requested,
            concrete_failure=concrete_failure,
        ),
    )


def controller_stage_transition(
    *,
    session_id: str,
    stage_name: str,
    protected_core: ProtectedCore,
    legacy_action: str,
    review_outcome: str = "none",
    validator_outcome: str = "unknown",
    triage_abort_requested: bool = False,
    concrete_failure: bool = False,
    validated_artifacts: tuple[str, ...] = (),
    config: AppConfig | None = None,
) -> object:
    route_result = controller_route_decision(
        session_id=session_id,
        stage_name=stage_name,
        legacy_action=legacy_action,
        review_outcome=review_outcome,
        validator_outcome=validator_outcome,
        triage_abort_requested=triage_abort_requested,
        concrete_failure=concrete_failure,
        config=config,
    )
    return _runtime(config).record_stage_transition(
        session_id=session_id,
        stage_name=stage_name,
        protected_core=protected_core,
        route_result=route_result,
        validated_artifacts=validated_artifacts,
    )


def controller_prepare_compaction(
    *,
    session_id: str,
    fallback_protected_core: ProtectedCore,
    strategy: Instinct8StrategyProtocol,
    halo_turns: list[dict[str, object]],
    recent_turns: list[dict[str, object]],
    trigger_point: int,
    config: AppConfig | None = None,
) -> ControllerCompactionResult | None:
    return _runtime(config).prepare_compaction(
        session_id=session_id,
        fallback_protected_core=fallback_protected_core,
        strategy=strategy,
        halo_turns=halo_turns,
        recent_turns=recent_turns,
        trigger_point=trigger_point,
    )


def controller_resume(
    *,
    session_id: str,
    fallback_protected_core: ProtectedCore,
    config: AppConfig | None = None,
) -> ControllerResumeResult:
    return _runtime(config).resume(
        session_id=session_id,
        fallback_protected_core=fallback_protected_core,
    )


def controller_should_open_repair(
    *,
    failure_signal: dict[str, object] | None,
    file_path: str | None,
    failing_check: str | None,
    contradiction_text: str | None,
    bounded_scope: bool,
    config: AppConfig | None = None,
) -> bool:
    return _runtime(config).repair_required(
        failure_signal=failure_signal,
        file_path=file_path,
        failing_check=failing_check,
        contradiction_text=contradiction_text,
        bounded_scope=bounded_scope,
    )


def controller_should_open_review(
    *,
    runtime_changed: bool,
    files_changed: int,
    contract_changed: bool,
    blocker_previously_stalled: bool,
    confidence_low: bool,
    config: AppConfig | None = None,
) -> bool:
    return _runtime(config).review_required(
        runtime_changed=runtime_changed,
        files_changed=files_changed,
        contract_changed=contract_changed,
        blocker_previously_stalled=blocker_previously_stalled,
        confidence_low=confidence_low,
    )


def controller_should_open_drift_review(
    *,
    wave_runs_longer_than_major_step: bool,
    plan_changed_after_new_evidence: bool,
    touched_multiple_control_artifacts: bool,
    about_to_close_or_promote_wave: bool,
    config: AppConfig | None = None,
) -> bool:
    return _runtime(config).drift_review_required(
        wave_runs_longer_than_major_step=wave_runs_longer_than_major_step,
        plan_changed_after_new_evidence=plan_changed_after_new_evidence,
        touched_multiple_control_artifacts=touched_multiple_control_artifacts,
        about_to_close_or_promote_wave=about_to_close_or_promote_wave,
    )


def controller_should_open_parallel_research(
    *,
    freshness_matters: bool,
    framework_or_vendor_claim: bool,
    current_product_claim: bool,
    repo_contains_answer: bool,
    config: AppConfig | None = None,
) -> bool:
    return _runtime(config).parallel_research_required(
        freshness_matters=freshness_matters,
        framework_or_vendor_claim=framework_or_vendor_claim,
        current_product_claim=current_product_claim,
        repo_contains_answer=repo_contains_answer,
    )


def controller_should_open_parallel_repair(
    *,
    failure_signal: dict[str, object] | None,
    file_path: str | None,
    failing_check: str | None,
    contradiction_text: str | None,
    bounded_scope: bool,
    isolated_scope: bool,
    conflicts_with_active_artifact: bool,
    config: AppConfig | None = None,
) -> bool:
    return _runtime(config).parallel_repair_required(
        failure_signal=failure_signal,
        file_path=file_path,
        failing_check=failing_check,
        contradiction_text=contradiction_text,
        bounded_scope=bounded_scope,
        isolated_scope=isolated_scope,
        conflicts_with_active_artifact=conflicts_with_active_artifact,
    )


def controller_can_continue_while_repair_runs(
    *,
    blocker_affects_current_reasoning_path: bool,
    isolated_scope: bool,
    conflicts_with_active_artifact: bool,
    config: AppConfig | None = None,
) -> bool:
    return _runtime(config).can_continue_with_parallel_repair(
        blocker_affects_current_reasoning_path=blocker_affects_current_reasoning_path,
        isolated_scope=isolated_scope,
        conflicts_with_active_artifact=conflicts_with_active_artifact,
    )


def controller_should_merge_subagent_result(
    *,
    explicit_merge_requested: bool,
    mutates_controller_truth: bool,
    conflicts_with_active_artifact: bool,
    config: AppConfig | None = None,
) -> bool:
    return _runtime(config).should_merge_parallel_result(
        explicit_merge_requested=explicit_merge_requested,
        mutates_controller_truth=mutates_controller_truth,
        conflicts_with_active_artifact=conflicts_with_active_artifact,
    )


def controller_next_terminal_or_runnable_state(
    *,
    queue_items: list[dict[str, object]],
    blocker_packet_present: bool,
    next_stage_candidate: dict[str, object] | None = None,
    abort_requested: bool = False,
    config: AppConfig | None = None,
) -> dict[str, object]:
    return _runtime(config).queue_terminal_or_runnable_state(
        queue_items=queue_items,
        blocker_packet_present=blocker_packet_present,
        next_stage_candidate=next_stage_candidate,
        abort_requested=abort_requested,
    ).to_dict()


def controller_finalize_queue_state(
    *,
    session_id: str | None = None,
    current_wave: str,
    queue_items: list[dict[str, object]],
    blocker_packet_present: bool,
    next_stage_candidate: dict[str, object] | None = None,
    control_plane_truth: dict[str, object] | None = None,
    abort_requested: bool = False,
    config: AppConfig | None = None,
) -> dict[str, object]:
    return _runtime(config).finalize_queue(
        session_id=session_id,
        current_wave=current_wave,
        queue_items=queue_items,
        blocker_packet_present=blocker_packet_present,
        next_stage_candidate=next_stage_candidate,
        control_plane_truth=control_plane_truth,
        abort_requested=abort_requested,
    ).to_dict()
