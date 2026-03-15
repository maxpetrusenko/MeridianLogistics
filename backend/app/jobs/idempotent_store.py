from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from backend.app.gateway.idempotency_store import (
    IdempotencyClaim,
    claim_record,
    complete_record,
    load_record,
)
from backend.app.jobs.repository import JobRepository


@dataclass(frozen=True)
class IdempotentJobResult:
    """Result of an idempotent job operation."""
    outcome: str  # "created", "replayed", "conflict", "error"
    job: dict[str, object] | None = None
    error: str | None = None


def _job_request_fingerprint(
    *,
    session_id: str,
    office_id: str,
    broker_id: str,
    job_kind: str,
    request_context: dict[str, object] | None = None,
) -> str:
    """Create deterministic fingerprint for job request."""
    payload = {
        "session_id": session_id,
        "office_id": office_id,
        "broker_id": broker_id,
        "job_kind": job_kind,
        "context": request_context or {},
    }
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


class IdempotentJobStore:
    """
    Job store with idempotency guarantees.
    Wraps JobRepository with idempotency_store patterns.
    """

    def __init__(
        self,
        repository: JobRepository | None = None,
        idempotency_store: MutableMapping[str, dict[str, object]] | None = None,
    ) -> None:
        self._repo = repository or JobRepository()
        self._idempotency_store = idempotency_store or {}

    def create_job(
        self,
        *,
        session_id: str,
        office_id: str,
        broker_id: str,
        job_kind: str = "analytics_refresh",
        progress_message: str = "Job queued",
        retry_allowed: bool = False,
        request_context: dict[str, object] | None = None,
    ) -> IdempotentJobResult:
        """
        Create a job idempotently.
        Same request fingerprint returns existing job.
        """
        fingerprint = _job_request_fingerprint(
            session_id=session_id,
            office_id=office_id,
            broker_id=broker_id,
            job_kind=job_kind,
            request_context=request_context,
        )
        idempotency_key = f"job:create:{fingerprint}"

        claim = claim_record(
            self._idempotency_store,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )

        if claim.outcome == "replay" and claim.record:
            # Return cached job
            result = claim.record.get("result", {})
            job = self._repo.get(result.get("job_id", "")) if result.get("job_id") else None
            if job:
                return IdempotentJobResult(outcome="replayed", job=job)

        if claim.outcome == "conflict":
            return IdempotentJobResult(
                outcome="conflict",
                error="Duplicate job request with different parameters",
            )

        # Create new job
        try:
            job = self._repo.create(
                session_id=session_id,
                office_id=office_id,
                broker_id=broker_id,
                job_kind=job_kind,
                progress_message=progress_message,
                retry_allowed=retry_allowed,
            )

            # Cache result for idempotency
            complete_record(
                self._idempotency_store,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                result={"job_id": job["job_id"], "job": job},
            )

            return IdempotentJobResult(outcome="created", job=job)

        except Exception as e:
            return IdempotentJobResult(
                outcome="error",
                error=str(e),
            )

    def complete_job(
        self,
        job_id: str,
        *,
        result: dict[str, object],
        progress_message: str = "Job completed",
        request_fingerprint: str | None = None,
    ) -> IdempotentJobResult:
        """
        Complete a job idempotently.
        Safe to call multiple times with same result.
        """
        idempotency_key = f"job:complete:{job_id}"
        fingerprint = request_fingerprint or hashlib.sha256(
            json.dumps(result, sort_keys=True).encode()
        ).hexdigest()[:16]

        # Check if already completed
        existing = self._repo.get(job_id)
        if existing and existing["status"] == "succeeded":
            existing_result = existing.get("result", {})
            if existing_result == result:
                return IdempotentJobResult(outcome="replayed", job=existing)
            return IdempotentJobResult(
                outcome="conflict",
                error="Job already completed with different result",
                job=existing,
            )

        claim = claim_record(
            self._idempotency_store,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )

        if claim.outcome == "replay" and claim.record:
            job = self._repo.get(job_id)
            if job:
                return IdempotentJobResult(outcome="replayed", job=job)

        if claim.outcome == "conflict":
            return IdempotentJobResult(
                outcome="conflict",
                error="Concurrent completion attempt",
            )

        try:
            job = self._repo.complete(
                job_id,
                result=result,
                progress_message=progress_message,
            )

            if not job:
                return IdempotentJobResult(
                    outcome="error",
                    error=f"Job {job_id} not found",
                )

            complete_record(
                self._idempotency_store,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                result={"job_id": job_id, "status": "succeeded"},
            )

            return IdempotentJobResult(outcome="created", job=job)

        except Exception as e:
            return IdempotentJobResult(
                outcome="error",
                error=str(e),
            )

    def prepare_result(self, job_id: str, result: dict[str, object]) -> None:
        """Prepare a result for later completion (not idempotent, internal)."""
        self._repo.prepare_result(job_id, result)

    def start_job(
        self,
        job_id: str,
        *,
        progress_message: str = "Job running",
    ) -> dict[str, object] | None:
        """Start a job (transition from queued to running)."""
        return self._repo.start(job_id, progress_message=progress_message)

    def refresh_job(self, job_id: str) -> dict[str, object] | None:
        """Refresh a running job; may complete if prepared result exists."""
        return self._repo.refresh(job_id)

    def get_job(self, job_id: str) -> dict[str, object] | None:
        """Get a job by ID (read-only, no idempotency needed)."""
        return self._repo.get(job_id)

    def get_job_by_poll_token(
        self,
        job_id: str,
        poll_token: str,
    ) -> dict[str, object] | None:
        """Get a job by ID and poll token."""
        return self._repo.get_by_poll_token(job_id, poll_token)

    def get_session_jobs(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        """Get all jobs for a session."""
        return self._repo.get_by_session(session_id, limit)

    def bind_pending_response(
        self,
        job_id: str,
        response_id: str,
    ) -> dict[str, object] | None:
        """Bind a pending response ID to a job."""
        return self._repo.bind_pending_response(job_id, response_id)

    def link_artifact(
        self,
        job_id: str,
        artifact_key: str,
        mime_type: str,
        size_bytes: int,
    ) -> dict[str, object] | None:
        """Link an artifact to a completed job."""
        return self._repo.link_artifact(job_id, artifact_key, mime_type, size_bytes)

    def fail_job(
        self,
        job_id: str,
        *,
        error_message: str,
    ) -> dict[str, object] | None:
        """Mark a job as failed."""
        return self._repo.fail(job_id, error_message=error_message)
