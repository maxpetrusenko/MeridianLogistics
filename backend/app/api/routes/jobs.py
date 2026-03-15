from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
import logging

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.schemas.chat import (
    AsyncJobEnvelope,
    AsyncJobListEnvelope,
    ChatResponseEnvelope,
    JobStatus,
)
from backend.app.autonomy.models import AutonomyJobMetadata
from backend.app.jobs.models import JobStatus as JobStatusEnum


logger = logging.getLogger(__name__)


router = APIRouter(tags=["jobs"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    session_access_token: str = Field(min_length=1)
    progress_message: str = Field(min_length=1, max_length=500)
    retry_allowed: bool = Field(default=True)
    job_kind: Literal["analytics_refresh", "data_export", "report_generation"] = Field(
        default="analytics_refresh"
    )


class JobListEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jobs: list[AsyncJobListEnvelope]
    total: int
    filtered: int
    offset: int
    limit: int


class JobLifecycleEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    session_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    completed_at: str | None = None
    progress_message: str
    retry_allowed: bool
    pending_response_id: str | None = None
    completed_response_id: str | None = None
    result: ChatResponseEnvelope | None = None
    lifecycle_state: Literal[
        "pending",
        "active",
        "completing",
        "completed",
        "failed",
        "cancelled",
        "expired",
    ]


@router.post("/jobs", response_model=AsyncJobEnvelope)
def create_job(request_payload: JobCreateRequest, request: Request) -> AsyncJobEnvelope:
    session = request.app.state.session_store.get_session_by_access_token(
        request_payload.session_id,
        request_payload.session_access_token,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")

    job = request.app.state.job_store.create_job(
        session_id=session.session_id,
        broker_id=session.broker_id,
        office_id=session.office_id,
        progress_message=request_payload.progress_message,
        retry_allowed=request_payload.retry_allowed,
    )
    return AsyncJobEnvelope.model_validate(job.to_api_dict())


@router.get("/jobs", response_model=JobListEnvelope)
def list_jobs(
    request: Request,
    session_id: str,
    session_access_token: str,
    status: JobStatus | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> JobListEnvelope:
    session_store = request.app.state.session_store
    job_store = request.app.state.job_store

    session = session_store.get_session_by_access_token(session_id, session_access_token)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")

    # Convert status from Literal string to JobStatus enum for the store
    status_enum = JobStatusEnum.from_string(status) if status else None

    # Get all jobs for this session (max limit for counting)
    all_jobs = job_store.list_jobs(
        session_id=session_id,
        status=status_enum,
        offset=0,
        limit=10000,
    )

    # Get unfiltered total for this session
    total_jobs = job_store.list_jobs(
        session_id=session_id,
        status=None,
        offset=0,
        limit=10000,
    )

    total = len(total_jobs)
    filtered = len(all_jobs)

    # Apply pagination in-memory
    paginated_jobs = all_jobs[offset:offset + limit]

    # Build response without job_poll_token
    job_items = []
    for job in paginated_jobs:
        job_dict = job.to_dict()
        job_items.append(AsyncJobListEnvelope.model_validate(job_dict))

    return JobListEnvelope(
        jobs=job_items,
        total=total,
        filtered=filtered,
        offset=offset,
        limit=limit,
    )


@router.get("/jobs/{job_id}", response_model=AsyncJobEnvelope)
def get_job(
    job_id: str,
    request: Request,
    job_poll_token: str = Query(min_length=1),
) -> AsyncJobEnvelope:
    job_store = request.app.state.job_store
    autonomy_service = request.app.state.autonomy_service

    job = job_store.get_job_by_poll_token(job_id, job_poll_token)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")

    # Handle bounded autonomy for transient jobs
    autonomy_completed = False
    if job.is_transient() and job.autonomy_metadata is not None and autonomy_service.is_enabled():
        try:
            metadata = AutonomyJobMetadata.from_dict(job.autonomy_metadata)
            new_metadata, outcome = autonomy_service.advance_step(
                job_id=job_id,
                current_metadata=metadata,
            )

            # If step completed the job, mark for completion
            if outcome.is_terminal and not outcome.error_message:
                autonomy_completed = True
                logger.info(
                    "autonomy_complete %s",
                    {"job_id": job_id, "steps": new_metadata.step_index},
                )

            # Update job with new autonomy metadata
            # If autonomy completed, trigger immediate completion
            job_store.update_autonomy_metadata(
                job_id,
                new_metadata.to_dict(),
                trigger_completion=autonomy_completed,
            )

            # Fail the job if autonomy failed
            if outcome.is_terminal and outcome.error_message:
                job_store.fail_job(
                    job_id,
                    error_message=outcome.error_message,
                    progress_message="Bounded autonomy failed.",
                )
                logger.info(
                    "autonomy_failed %s",
                    {"job_id": job_id, "reason": outcome.error_message},
                )

            # Reload job to get updated state
            job = job_store.get_job(job_id) or job

        except Exception as exc:
            logger.error("autonomy_step_error %s: %s", job_id, exc)
            # Continue with existing job state on error

    # Existing refresh logic - works for both autonomy and non-autonomy jobs
    job = job_store.refresh_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")

    # For autonomy jobs that completed, the refresh logic handles materialization
    # via the prepared_result_payload mechanism
    if job.completed_response_id is not None and job.pending_response_id is not None:
        request.app.state.session_store.promote_job_completion(
            session_id=job.session_id,
            expected_last_response_id=job.pending_response_id,
            completed_response_id=job.completed_response_id,
            job_id=job.job_id,
        )
    return AsyncJobEnvelope.model_validate(job.to_api_dict())


@router.get("/jobs/{job_id}/lifecycle", response_model=JobLifecycleEnvelope)
def get_job_lifecycle(
    job_id: str,
    request: Request,
    job_poll_token: str = Query(min_length=1),
) -> JobLifecycleEnvelope:
    store = request.app.state.job_store
    job = store.get_job_by_poll_token(job_id, job_poll_token)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")

    job = store.refresh_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")

    lifecycle_state = _map_lifecycle_state(job.status)

    completed_at = None
    if job.status.value in ("succeeded", "failed", "cancelled", "expired"):
        completed_at = job.failed_at if job.status.value == "failed" else job.updated_at

    return JobLifecycleEnvelope(
        job_id=job.job_id,
        session_id=job.session_id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=completed_at,
        progress_message=job.progress_message,
        retry_allowed=job.retry_allowed,
        pending_response_id=job.pending_response_id,
        completed_response_id=job.completed_response_id,
        result=(
            ChatResponseEnvelope.model_validate(job.result)
            if job.result
            else None
        ),
        lifecycle_state=lifecycle_state,
    )


@router.post("/jobs/{job_id}/cancel", response_model=AsyncJobEnvelope)
def cancel_job(
    job_id: str,
    request: Request,
    job_poll_token: str = Query(min_length=1),
) -> AsyncJobEnvelope:
    store = request.app.state.job_store
    job = store.get_job_by_poll_token(job_id, job_poll_token)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")

    if job.status.value not in ("pending", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"cannot cancel job with status: {job.status.value}",
        )

    cancelled_job = store.cancel_job(job_id)
    if cancelled_job is None:
        raise HTTPException(status_code=404, detail="unknown job")

    return AsyncJobEnvelope.model_validate(cancelled_job.to_api_dict())


def _map_lifecycle_state(
    status: JobStatus,
) -> Literal[
    "pending",
    "active",
    "completing",
    "completed",
    "failed",
    "cancelled",
    "expired",
]:
    match status:
        case "queued":
            return "pending"
        case "running":
            return "active"
        case "succeeded":
            return "completed"
        case "failed":
            return "failed"
        case "cancelled":
            return "cancelled"
        case "expired":
            return "expired"
        case _:
            return "pending"
