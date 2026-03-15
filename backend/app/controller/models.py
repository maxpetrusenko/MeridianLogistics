from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


ControllerAction = Literal[
    "continue",
    "review",
    "repair",
    "abort",
    "done",
    "blocked",
    "waiting_user_approval",
    "aborted",
]
DecisionSource = Literal["controller", "review", "triage", "validator"]
DriftStatus = Literal["stable", "watch", "drift_detected"]
FailureSeverity = Literal["none", "recoverable", "unsafe"]
QueueStatus = Literal["queued", "active", "done", "blocked"]
RunPolicy = Literal["auto", "explicit_request", "blocked_until_input"]
ApprovalAuthority = Literal["main", "user"]
ControllerTerminalState = Literal[
    "DONE",
    "BLOCKED",
    "WAITING_USER_APPROVAL",
    "ABORTED",
] | None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ProtectedCore:
    task_goal: str
    expected_output: str
    current_step: str
    resume_point: str
    hard_constraints: tuple[str, ...]
    business_invariants: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "task_goal": self.task_goal,
            "expected_output": self.expected_output,
            "current_step": self.current_step,
            "resume_point": self.resume_point,
            "hard_constraints": list(self.hard_constraints),
            "business_invariants": list(self.business_invariants),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ProtectedCore":
        return cls(
            task_goal=str(payload["task_goal"]),
            expected_output=str(payload["expected_output"]),
            current_step=str(payload["current_step"]),
            resume_point=str(payload["resume_point"]),
            hard_constraints=tuple(str(item) for item in payload["hard_constraints"]),
            business_invariants=tuple(str(item) for item in payload["business_invariants"]),
        )


@dataclass(frozen=True)
class FailureSignal:
    kind: str
    severity: FailureSeverity
    source: str
    details: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "source": self.source,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "FailureSignal":
        return cls(
            kind=str(payload["kind"]),
            severity=str(payload["severity"]),
            source=str(payload["source"]),
            details=None if payload.get("details") is None else str(payload["details"]),
        )


@dataclass(frozen=True)
class ControllerDecision:
    action: ControllerAction
    reason: str
    source: DecisionSource

    def to_dict(self) -> dict[str, str]:
        return {
            "action": self.action,
            "reason": self.reason,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ControllerDecision":
        return cls(
            action=str(payload["action"]),
            reason=str(payload["reason"]),
            source=str(payload["source"]),
        )


@dataclass(frozen=True)
class CompactionState:
    strategy_name: str
    compaction_sequence: int
    halo_summary: str
    recent_turn_ids: tuple[int, ...]
    drift_status: DriftStatus = "stable"

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_name": self.strategy_name,
            "compaction_sequence": self.compaction_sequence,
            "halo_summary": self.halo_summary,
            "recent_turn_ids": list(self.recent_turn_ids),
            "drift_status": self.drift_status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "CompactionState":
        return cls(
            strategy_name=str(payload["strategy_name"]),
            compaction_sequence=int(payload["compaction_sequence"]),
            halo_summary=str(payload["halo_summary"]),
            recent_turn_ids=tuple(int(item) for item in payload["recent_turn_ids"]),
            drift_status=str(payload["drift_status"]),
        )


@dataclass(frozen=True)
class QueueState:
    wave_name: str
    status: QueueStatus
    run_policy: RunPolicy
    eligible: bool
    requires_explicit_request: bool = False
    approval_authority: ApprovalAuthority = "user"

    def to_dict(self) -> dict[str, object]:
        return {
            "wave_name": self.wave_name,
            "status": self.status,
            "run_policy": self.run_policy,
            "eligible": self.eligible,
            "requires_explicit_request": self.requires_explicit_request,
            "approval_authority": self.approval_authority,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "QueueState":
        return cls(
            wave_name=str(payload["wave_name"]),
            status=str(payload["status"]),
            run_policy=str(payload["run_policy"]),
            eligible=bool(payload["eligible"]),
            requires_explicit_request=bool(payload.get("requires_explicit_request", False)),
            approval_authority=str(payload.get("approval_authority", "user")),
        )


@dataclass(frozen=True)
class ControllerCheckpoint:
    checkpoint_id: str
    protected_core: ProtectedCore
    compaction: CompactionState
    validated_artifacts: tuple[str, ...]
    active_failure_signal: FailureSignal
    controller_last_decision: ControllerDecision
    queue: QueueState | None = None
    terminal_state: ControllerTerminalState = None
    created_at: str = field(default_factory=_utc_now)
    checkpoint_version: str = "0.1.0"

    def to_dict(self) -> dict[str, object]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "checkpoint_version": self.checkpoint_version,
            "created_at": self.created_at,
            "protected_core": self.protected_core.to_dict(),
            "compaction": self.compaction.to_dict(),
            "validated_artifacts": list(self.validated_artifacts),
            "active_failure_signal": self.active_failure_signal.to_dict(),
            "controller_last_decision": self.controller_last_decision.to_dict(),
            "queue": None if self.queue is None else self.queue.to_dict(),
            "terminal_state": self.terminal_state,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ControllerCheckpoint":
        return cls(
            checkpoint_id=str(payload["checkpoint_id"]),
            checkpoint_version=str(payload["checkpoint_version"]),
            created_at=str(payload["created_at"]),
            protected_core=ProtectedCore.from_dict(payload["protected_core"]),
            compaction=CompactionState.from_dict(payload["compaction"]),
            validated_artifacts=tuple(str(item) for item in payload["validated_artifacts"]),
            active_failure_signal=FailureSignal.from_dict(payload["active_failure_signal"]),
            controller_last_decision=ControllerDecision.from_dict(payload["controller_last_decision"]),
            queue=None
            if payload.get("queue") is None
            else QueueState.from_dict(payload["queue"]),
            terminal_state=None
            if payload.get("terminal_state") is None
            else str(payload["terminal_state"]),
        )
