from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

    @classmethod
    def from_string(cls, value: str) -> "JobStatus":
        for status in cls:
            if status.value == value:
                return status
        if value == "queued":
            return cls.PENDING
        raise ValueError(f"Invalid JobStatus: {value}")


JobStatusLiteral = Literal["pending", "running", "succeeded", "failed", "cancelled", "expired"]


_TERMINAL_STATUSES = frozenset({JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.EXPIRED})
_TRANSIENT_STATUSES = frozenset({JobStatus.PENDING, JobStatus.RUNNING})

_VALID_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.PENDING: frozenset({JobStatus.RUNNING, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.EXPIRED}),
    JobStatus.RUNNING: frozenset({JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.EXPIRED}),
    JobStatus.SUCCEEDED: frozenset(),
    JobStatus.FAILED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
    JobStatus.EXPIRED: frozenset(),
}


class InvalidJobTransitionError(Exception):
    def __init__(self, current: JobStatus, attempted: JobStatus) -> None:
        self.current = current
        self.attempted = attempted
        super().__init__(f"Invalid job transition: {current.value} -> {attempted.value}")


def validate_job_transition(current: JobStatus | str, next_status: JobStatus | str) -> None:
    current_status = JobStatus.from_string(current) if isinstance(current, str) else current
    next_status_val = JobStatus.from_string(next_status) if isinstance(next_status, str) else next_status

    allowed = _VALID_TRANSITIONS.get(current_status, frozenset())
    if next_status_val not in allowed:
        raise InvalidJobTransitionError(current_status, next_status_val)


def is_terminal_status(status: JobStatus | str) -> bool:
    status_val = JobStatus.from_string(status) if isinstance(status, str) else status
    return status_val in _TERMINAL_STATUSES


def is_transient_status(status: JobStatus | str) -> bool:
    status_val = JobStatus.from_string(status) if isinstance(status, str) else status
    return status_val in _TRANSIENT_STATUSES


@dataclass(frozen=True)
class JobState:
    job_id: str
    session_id: str
    broker_id: str
    office_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    progress_message: str
    retry_allowed: bool
    pending_response_id: str | None = None
    completed_response_id: str | None = None
    result: dict[str, object] | None = None
    job_poll_token: str | None = None
    completion_refreshes_remaining: int | None = None
    completion_ready_at: float | None = None
    error_message: str | None = None
    failed_at: str | None = None
    autonomy_metadata: dict[str, object] | None = None

    @property
    def status_literal(self) -> str:
        return self.status.value

    def is_terminal(self) -> bool:
        return is_terminal_status(self.status)

    def is_transient(self) -> bool:
        return is_transient_status(self.status)

    def can_transition_to(self, next_status: JobStatus | str) -> bool:
        try:
            validate_job_transition(self.status, next_status)
            return True
        except InvalidJobTransitionError:
            return False

    def to_dict(self) -> dict[str, object]:
        base = {
            "job_id": self.job_id,
            "session_id": self.session_id,
            "status": self.status_literal,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "progress_message": self.progress_message,
            "retry_allowed": self.retry_allowed,
        }
        if self.completed_response_id:
            base["completed_response_id"] = self.completed_response_id
        if self.result:
            base["result"] = self.result
        if self.error_message:
            base["error_message"] = self.error_message
        if self.failed_at:
            base["failed_at"] = self.failed_at
        if self.autonomy_metadata:
            base["autonomy_metadata"] = self.autonomy_metadata
        return base

    def to_api_dict(self) -> dict[str, object]:
        base = self.to_dict()
        base["job_poll_token"] = self.job_poll_token
        # Exclude internal autonomy metadata from public API
        if "autonomy_metadata" in base:
            del base["autonomy_metadata"]
        return base

    def with_status(
        self,
        new_status: JobStatus,
        *,
        progress_message: str | None = None,
        result: dict[str, object] | None = None,
        error_message: str | None = None,
        failed_at: str | None = None,
        updated_at: str | None = None,
        autonomy_metadata: dict[str, object] | None = None,
    ) -> "JobState":
        validate_job_transition(self.status, new_status)

        return JobState(
            job_id=self.job_id,
            session_id=self.session_id,
            broker_id=self.broker_id,
            office_id=self.office_id,
            status=new_status,
            created_at=self.created_at,
            updated_at=updated_at or self.updated_at,
            progress_message=progress_message or self.progress_message,
            retry_allowed=self.retry_allowed,
            pending_response_id=self.pending_response_id,
            completed_response_id=self.completed_response_id,
            result=result or self.result,
            job_poll_token=self.job_poll_token,
            completion_refreshes_remaining=self.completion_refreshes_remaining,
            completion_ready_at=self.completion_ready_at,
            error_message=error_message or self.error_message,
            failed_at=failed_at or self.failed_at,
            autonomy_metadata=autonomy_metadata or self.autonomy_metadata,
        )
