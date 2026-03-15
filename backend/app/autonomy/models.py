"""Internal autonomy models for bounded execution in the running app.

These are internal backend models only. Do not widen public request or
response schemas with these in phase 1.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class AutonomyMode(str, Enum):
    """Execution mode for autonomy jobs."""
    POLL_DRIVEN = "poll_driven"


class TaskKind(str, Enum):
    """Types of work that can run under bounded autonomy."""
    ASYNC_READ_REFRESH = "async_read_refresh"


class StepKind(str, Enum):
    """Allowed step kinds for phase 1 bounded autonomy."""
    SEED_CONTEXT = "seed_context"
    EXECUTE_ALLOWLISTED_READ = "execute_allowlisted_read"
    BUILD_RESPONSE = "build_response"
    COMPLETE_JOB = "complete_job"
    FAIL_JOB = "fail_job"


@dataclass(frozen=True)
class AutonomyJobMetadata:
    """Derivative job metadata persisted with the job row.

    This is a cache; the controller checkpoint is authoritative.
    """
    mode: AutonomyMode
    task_kind: TaskKind
    checkpoint_id: str
    step_index: int
    step_budget: int
    last_controller_action: str

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "task_kind": self.task_kind.value,
            "checkpoint_id": self.checkpoint_id,
            "step_index": self.step_index,
            "step_budget": self.step_budget,
            "last_controller_action": self.last_controller_action,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> AutonomyJobMetadata:
        return cls(
            mode=AutonomyMode(data["mode"]),
            task_kind=TaskKind(data["task_kind"]),
            checkpoint_id=str(data["checkpoint_id"]),
            step_index=int(data["step_index"]),
            step_budget=int(data["step_budget"]),
            last_controller_action=str(data["last_controller_action"]),
        )


@dataclass(frozen=True)
class StepOutcome:
    """Result of executing a single autonomy step."""
    step_kind: StepKind
    next_step_kind: StepKind | None
    is_terminal: bool
    error_message: str | None = None
    result_payload: dict[str, object] | None = None


ALLOWED_STEP_KINDS = frozenset({
    StepKind.SEED_CONTEXT,
    StepKind.EXECUTE_ALLOWLISTED_READ,
    StepKind.BUILD_RESPONSE,
    StepKind.COMPLETE_JOB,
    StepKind.FAIL_JOB,
})
