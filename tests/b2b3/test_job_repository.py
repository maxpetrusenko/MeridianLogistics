"""
Tests for job persistence layer.

Tests:
- JobRepository CRUD operations
- IdempotentJobStore idempotency guarantees
- Job-result linkage via artifacts
"""
from __future__ import annotations

import json
import os

import pytest

from backend.app.jobs.repository import JobRepository
from backend.app.jobs.idempotent_store import (
    IdempotentJobStore,
    IdempotentJobResult,
)


@pytest.fixture
def job_repository() -> JobRepository:
    """Create a job repository using test database."""
    database_url = os.getenv(
        "MERIDIAN_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/meridian_logistics",
    )
    repo = JobRepository(database_url=database_url)
    repo._ensure_schema()
    return repo


@pytest.fixture
def idempotent_store(job_repository: JobRepository) -> IdempotentJobStore:
    """Create an idempotent job store."""
    return IdempotentJobStore(repository=job_repository)


def test_repository_create_job(job_repository: JobRepository) -> None:
    """Test creating a job in the repository."""
    job = job_repository.create(
        session_id="test-session-123",
        office_id="memphis",
        broker_id="broker-1",
        job_kind="analytics_refresh",
        progress_message="Test job",
    )

    assert job["job_id"].startswith("job_")
    assert job["session_id"] == "test-session-123"
    assert job["status"] == "queued"
    assert job["office_id"] == "memphis"
    assert job["broker_id"] == "broker-1"
    assert job["retry_allowed"] is False
    assert job["job_poll_token"] is not None


def test_repository_get_job(job_repository: JobRepository) -> None:
    """Test retrieving a job by ID."""
    created = job_repository.create(
        session_id="test-session-456",
        office_id="memphis",
        broker_id="broker-2",
    )

    retrieved = job_repository.get(created["job_id"])

    assert retrieved is not None
    assert retrieved["job_id"] == created["job_id"]
    assert retrieved["session_id"] == "test-session-456"


def test_repository_get_by_poll_token(job_repository: JobRepository) -> None:
    """Test retrieving a job by poll token."""
    created = job_repository.create(
        session_id="test-session-789",
        office_id="memphis",
        broker_id="broker-3",
    )

    retrieved = job_repository.get_by_poll_token(
        created["job_id"],
        created["job_poll_token"],
    )

    assert retrieved is not None
    assert retrieved["job_id"] == created["job_id"]


def test_repository_update_status(job_repository: JobRepository) -> None:
    """Test updating job status."""
    job = job_repository.create(
        session_id="test-session-status",
        office_id="memphis",
        broker_id="broker-status",
    )

    updated = job_repository.update_status(
        job["job_id"],
        "running",
        progress_message="Processing",
    )

    assert updated is not None
    assert updated["status"] == "running"
    assert updated["progress_message"] == "Processing"


def test_repository_start_job(job_repository: JobRepository) -> None:
    """Test starting a job."""
    job = job_repository.create(
        session_id="test-session-start",
        office_id="memphis",
        broker_id="broker-start",
    )

    started = job_repository.start(job["job_id"])

    assert started is not None
    assert started["status"] == "running"
    assert started["completion_refreshes_remaining"] == 2


def test_repository_complete_job(job_repository: JobRepository) -> None:
    """Test completing a job with result."""
    job = job_repository.create(
        session_id="test-session-complete",
        office_id="memphis",
        broker_id="broker-complete",
    )

    result = {
        "response_id": "resp-123",
        "summary": "Job completed successfully",
        "data": {"count": 42},
    }

    completed = job_repository.complete(
        job["job_id"],
        result=result,
        progress_message="Done",
    )

    assert completed is not None
    assert completed["status"] == "succeeded"
    assert completed["result"] == result
    assert completed["completed_response_id"] == "resp-123"
    assert completed["completed_at"] is not None


def test_repository_prepare_and_refresh(job_repository: JobRepository) -> None:
    """Test preparing result and refresh-based completion."""
    job = job_repository.create(
        session_id="test-session-refresh",
        office_id="memphis",
        broker_id="broker-refresh",
    )

    job_repository.start(job["job_id"])

    prepared_result = {
        "response_id": "resp-refresh",
        "summary": "Refreshed result",
    }

    job_repository.prepare_result(job["job_id"], prepared_result)

    # First refresh - should decrement count
    after_first = job_repository.refresh(job["job_id"])
    assert after_first["status"] == "running"
    assert after_first["completion_refreshes_remaining"] == 1

    # Second refresh - should decrement to zero
    after_second = job_repository.refresh(job["job_id"])
    assert after_second["status"] == "running"
    assert after_second["completion_refreshes_remaining"] == 0

    # Third refresh - should complete with prepared result
    final = job_repository.refresh(job["job_id"])
    assert final["status"] == "succeeded"
    assert final["result"] == prepared_result


def test_repository_link_artifact(job_repository: JobRepository) -> None:
    """Test linking an artifact to a job."""
    job = job_repository.create(
        session_id="test-session-artifact",
        office_id="memphis",
        broker_id="broker-artifact",
    )

    result = {"response_id": "resp-artifact"}
    job_repository.complete(
        job["job_id"],
        result=result,
    )

    linked = job_repository.link_artifact(
        job["job_id"],
        artifact_key="artifacts/test/report.pdf",
        mime_type="application/pdf",
        size_bytes=12345,
    )

    assert linked is not None
    assert linked["artifact_key"] == "artifacts/test/report.pdf"
    assert linked["artifact_mime_type"] == "application/pdf"
    assert linked["artifact_size_bytes"] == 12345


def test_idempotent_store_create(idempotent_store: IdempotentJobStore) -> None:
    """Test idempotent job creation."""
    # First call - should create
    result1 = idempotent_store.create_job(
        session_id="test-idep-session",
        office_id="memphis",
        broker_id="broker-idep",
        job_kind="analytics_refresh",
    )

    assert result1.outcome == "created"
    assert result1.job is not None

    # Duplicate call with same params - should replay
    result2 = idempotent_store.create_job(
        session_id="test-idep-session",
        office_id="memphis",
        broker_id="broker-idep",
        job_kind="analytics_refresh",
    )

    assert result2.outcome == "replayed"
    assert result2.job is not None
    assert result2.job["job_id"] == result1.job["job_id"]


def test_idempotent_store_complete(idempotent_store: IdempotentJobStore) -> None:
    """Test idempotent job completion."""
    # Create a job
    created = idempotent_store.create_job(
        session_id="test-idep-complete",
        office_id="memphis",
        broker_id="broker-idep-complete",
    )
    job_id = created.job["job_id"]

    result = {"response_id": "resp-idep", "data": "test"}

    # First completion
    complete1 = idempotent_store.complete_job(
        job_id,
        result=result,
    )

    assert complete1.outcome == "created"
    assert complete1.job["status"] == "succeeded"

    # Duplicate completion with same result - should replay
    complete2 = idempotent_store.complete_job(
        job_id,
        result=result,
    )

    assert complete2.outcome == "replayed"


def test_repository_get_session_jobs(job_repository: JobRepository) -> None:
    """Test getting all jobs for a session."""
    session_id = "test-session-list"

    job_repository.create(
        session_id=session_id,
        office_id="memphis",
        broker_id="broker-list-1",
    )
    job_repository.create(
        session_id=session_id,
        office_id="memphis",
        broker_id="broker-list-2",
    )

    jobs = job_repository.get_by_session(session_id)

    assert len(jobs) == 2
    assert all(j["session_id"] == session_id for j in jobs)


def test_repository_bind_pending_response(job_repository: JobRepository) -> None:
    """Test binding a pending response to a job."""
    job = job_repository.create(
        session_id="test-session-pending",
        office_id="memphis",
        broker_id="broker-pending",
    )

    bound = job_repository.bind_pending_response(
        job["job_id"],
        "pending-response-123",
    )

    assert bound is not None
    assert bound["pending_response_id"] == "pending-response-123"
