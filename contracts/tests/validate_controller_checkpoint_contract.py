#!/usr/bin/env python3

from jsonschema import Draft202012Validator

from backend.app.controller.models import (
    CompactionState,
    ControllerCheckpoint,
    ControllerDecision,
    FailureSignal,
    ProtectedCore,
    QueueState,
)
from backend.app.contracts import load_json_contract


validator = Draft202012Validator(load_json_contract("controller_checkpoint"))

valid_checkpoint = ControllerCheckpoint(
    checkpoint_id="cp-001",
    protected_core=ProtectedCore(
        task_goal="Return a Memphis-safe booking answer without replacing the runtime.",
        expected_output="Implementation plan and isolated control-plane patch.",
        current_step="Resolve controller precedence and checkpoint schema.",
        resume_point="Re-enter at control-plane scaffold review.",
        hard_constraints=(
            "Do not replace the main runtime.",
            "Preserve Memphis PoC business behavior.",
            "Abort only on unsafe or destructive states.",
        ),
        business_invariants=(
            "Memphis-only PoC scope remains frozen.",
            "Read and write contracts stay unchanged.",
        ),
    ),
    compaction=CompactionState(
        strategy_name="Strategy F - Protected Core",
        compaction_sequence=1,
        halo_summary="Checkpoint scaffold drafted; business paths untouched.",
        recent_turn_ids=(7, 8, 9),
    ),
    validated_artifacts=(
        "contracts/tool-schema.yaml",
        "contracts/agent-response-schema.json",
    ),
    active_failure_signal=FailureSignal(
        kind="none",
        severity="none",
        source="controller",
        details=None,
    ),
    controller_last_decision=ControllerDecision(
        action="continue",
        reason="review_approved_safe_to_continue",
        source="review",
    ),
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

errors = sorted(validator.iter_errors(valid_checkpoint.to_dict()), key=str)
if errors:
    raise AssertionError([error.message for error in errors])

invalid_checkpoint = valid_checkpoint.to_dict()
invalid_checkpoint["controller_last_decision"] = {
    "action": "abort",
    "reason": "triage requested stop",
    "source": "unknown",
}

invalid_errors = list(validator.iter_errors(invalid_checkpoint))
if not invalid_errors:
    raise AssertionError("controller checkpoint contract: expected invalid source to fail")

invalid_terminal = valid_checkpoint.to_dict()
invalid_terminal["terminal_state"] = "PAUSED"

invalid_terminal_errors = list(validator.iter_errors(invalid_terminal))
if not invalid_terminal_errors:
    raise AssertionError("controller checkpoint contract: expected invalid terminal state to fail")

print("controller checkpoint contract validation tests passed")
