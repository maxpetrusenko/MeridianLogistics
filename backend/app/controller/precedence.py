from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from backend.app.controller.models import ControllerDecision, FailureSignal


ReviewOutcome = Literal["none", "approve", "changes_requested", "blocked"]
ValidatorOutcome = Literal["unknown", "pass", "fail"]


@dataclass(frozen=True)
class ControllerSignals:
    review_outcome: ReviewOutcome = "none"
    validator_outcome: ValidatorOutcome = "unknown"
    triage_abort_requested: bool = False
    concrete_failure: bool = False
    failure_signal: FailureSignal = field(
        default_factory=lambda: FailureSignal(
            kind="none",
            severity="none",
            source="controller",
            details=None,
        )
    )


def resolve_controller_action(signals: ControllerSignals) -> ControllerDecision:
    if signals.failure_signal.severity == "unsafe":
        return ControllerDecision(
            action="abort",
            reason="unsafe_or_destructive_state",
            source="triage",
        )

    if signals.review_outcome == "approve" and not signals.concrete_failure:
        return ControllerDecision(
            action="continue",
            reason="review_approved_safe_to_continue",
            source="review",
        )

    if signals.validator_outcome == "pass" and not signals.concrete_failure:
        return ControllerDecision(
            action="continue",
            reason="validator_passed_no_concrete_failure",
            source="validator",
        )

    if signals.review_outcome == "changes_requested":
        return ControllerDecision(
            action="repair",
            reason="review_requested_changes",
            source="review",
        )

    if signals.validator_outcome == "fail" or signals.concrete_failure:
        return ControllerDecision(
            action="repair",
            reason="recoverable_failure_requires_repair",
            source="controller",
        )

    if signals.triage_abort_requested:
        return ControllerDecision(
            action="review",
            reason="triage_abort_demoted_until_safety_proven",
            source="triage",
        )

    return ControllerDecision(
        action="review",
        reason="insufficient_signal_default_review",
        source="controller",
    )
