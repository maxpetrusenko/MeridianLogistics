from __future__ import annotations

from datetime import UTC, datetime
import json
import secrets
import sqlite3
import threading
from uuid import uuid4

from backend.app.jobs.models import (
    InvalidJobTransitionError,
    is_terminal_status,
    JobState,
    JobStatus,
    validate_job_transition,
)
from backend.app.state.database import connect_state_database, execute_query


DEFAULT_COMPLETION_REFRESH_POLLS = 2
DEFAULT_JOB_TIMEOUT_SECONDS = 300


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_status(value: str | JobStatus) -> str:
    if isinstance(value, JobStatus):
        return value.value
    return value


def _status_from_string(value: str) -> JobStatus:
    try:
        return JobStatus.from_string(value)
    except ValueError:
        return JobStatus.from_string("queued" if value == "queued" else value)


def _normalize_timestamp(value: object) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return str(value)


def _decode_json_payload(value: object) -> dict[str, object] | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, (bytes, bytearray)):
        value = value.decode()
    if isinstance(value, str):
        return json.loads(value)
    return json.loads(str(value))


class InMemoryJobStore:
    def __init__(
        self,
        *,
        database_url: str = "sqlite:///:memory:",
        completion_refresh_polls: int = 2,
    ) -> None:
        self._connection = connect_state_database(database_url)
        self._lock = threading.RLock()
        self._completion_refresh_polls = completion_refresh_polls
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._lock:
            execute_query(
                self._connection,
                """
                CREATE TABLE IF NOT EXISTS generation_jobs (
                    job_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    office_id TEXT NOT NULL,
                    broker_id TEXT NOT NULL,
                    job_kind TEXT NOT NULL,
                    job_status TEXT NOT NULL,
                    progress_message TEXT NOT NULL,
                    retry_allowed INTEGER NOT NULL,
                    pending_response_id TEXT,
                    completed_response_id TEXT,
                    prepared_result_payload TEXT,
                    result_payload TEXT,
                    job_poll_token TEXT,
                    completion_refreshes_remaining INTEGER,
                    completion_ready_at REAL,
                    artifact_key TEXT,
                    artifact_mime_type TEXT,
                    artifact_size_bytes INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    error_message TEXT,
                    failed_at TEXT,
                    autonomy_metadata TEXT
                )
                """,
            )
            self._ensure_column("generation_jobs", "job_poll_token", "TEXT")
            self._ensure_column("generation_jobs", "completion_refreshes_remaining", "INTEGER")
            self._ensure_column("generation_jobs", "error_message", "TEXT")
            self._ensure_column("generation_jobs", "failed_at", "TEXT")
            self._ensure_column("generation_jobs", "autonomy_metadata", "TEXT")
            self._backfill_job_poll_tokens()
            self._connection.commit()

    def _ensure_column(self, table_name: str, column_name: str, column_definition: str) -> None:
        if isinstance(self._connection, sqlite3.Connection):
            existing_columns = {
                row["name"]
                for row in execute_query(
                    self._connection,
                    f"PRAGMA table_info({table_name})",
                ).fetchall()
            }
            if column_name in existing_columns:
                return
            execute_query(
                self._connection,
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}",
            )
            return
        execute_query(
            self._connection,
            f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_definition}",
        )

    def _new_job_poll_token(self) -> str:
        return secrets.token_urlsafe(24)

    def _backfill_job_poll_tokens(self) -> None:
        rows = execute_query(
            self._connection,
            """
            SELECT job_id
            FROM generation_jobs
            WHERE job_poll_token IS NULL OR job_poll_token = ''
            """,
        ).fetchall()
        for row in rows:
            execute_query(
                self._connection,
                """
                UPDATE generation_jobs
                SET job_poll_token = ?, updated_at = COALESCE(updated_at, ?)
                WHERE job_id = ?
                """,
                (self._new_job_poll_token(), _utc_now(), row["job_id"]),
            )

    def next_job_id(self) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d")
        return f"job_{stamp}_{uuid4().hex[:12]}"

    def _row_to_job(self, row: dict[str, object]) -> JobState:
        result = _decode_json_payload(row["result_payload"])
        completion_ready_at = row["completion_ready_at"]
        completion_refreshes_remaining = row["completion_refreshes_remaining"]
        status_raw = row["job_status"]
        status = _status_from_string(status_raw) if isinstance(status_raw, str) else JobStatus.PENDING

        row_dict = dict(row) if hasattr(row, "keys") else row

        autonomy_metadata = _decode_json_payload(row_dict.get("autonomy_metadata"))

        return JobState(
            job_id=row["job_id"],
            session_id=row["session_id"],
            broker_id=row["broker_id"],
            office_id=row["office_id"],
            status=status,
            created_at=_normalize_timestamp(row["created_at"]),
            updated_at=_normalize_timestamp(row["updated_at"]),
            progress_message=row["progress_message"],
            retry_allowed=bool(row["retry_allowed"]),
            pending_response_id=row["pending_response_id"],
            completed_response_id=row["completed_response_id"],
            result=result,
            job_poll_token=row["job_poll_token"],
            completion_refreshes_remaining=(
                int(completion_refreshes_remaining) if completion_refreshes_remaining is not None else None
            ),
            completion_ready_at=float(completion_ready_at) if completion_ready_at is not None else None,
            error_message=row_dict.get("error_message"),
            failed_at=row_dict.get("failed_at"),
            autonomy_metadata=autonomy_metadata,
        )

    def get_job(self, job_id: str) -> JobState | None:
        with self._lock:
            row = execute_query(
                self._connection,
                "SELECT * FROM generation_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_job(row)

    def get_job_by_poll_token(self, job_id: str, job_poll_token: str) -> JobState | None:
        with self._lock:
            row = execute_query(
                self._connection,
                """
                SELECT *
                FROM generation_jobs
                WHERE job_id = ? AND job_poll_token = ?
                """,
                (job_id, job_poll_token),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_job(row)

    def create_job(
        self,
        *,
        session_id: str,
        broker_id: str,
        office_id: str,
        progress_message: str,
        retry_allowed: bool,
    ) -> JobState:
        now = _utc_now()
        job = JobState(
            job_id=self.next_job_id(),
            session_id=session_id,
            broker_id=broker_id,
            office_id=office_id,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
            progress_message=progress_message,
            retry_allowed=retry_allowed,
            job_poll_token=self._new_job_poll_token(),
        )
        with self._lock:
            execute_query(
                self._connection,
                """
                INSERT INTO generation_jobs (
                    job_id,
                    session_id,
                    office_id,
                    broker_id,
                    job_kind,
                    job_status,
                    progress_message,
                    retry_allowed,
                    job_poll_token,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.session_id,
                    job.office_id,
                    job.broker_id,
                    "analytics_refresh",
                    job.status.value,
                    job.progress_message,
                    int(job.retry_allowed),
                    job.job_poll_token,
                    job.created_at,
                    job.updated_at,
                ),
            )
            self._connection.commit()
        return job

    def prepare_result(self, job_id: str, result: dict[str, object]) -> None:
        with self._lock:
            execute_query(
                self._connection,
                """
                UPDATE generation_jobs
                SET prepared_result_payload = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (json.dumps(result), _utc_now(), job_id),
            )
            self._connection.commit()

    def bind_pending_response(self, job_id: str, pending_response_id: str) -> JobState | None:
        with self._lock:
            execute_query(
                self._connection,
                """
                UPDATE generation_jobs
                SET pending_response_id = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (pending_response_id, _utc_now(), job_id),
            )
            self._connection.commit()
        return self.get_job(job_id)

    def start_job(self, job_id: str, *, progress_message: str) -> JobState | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        try:
            validate_job_transition(job.status, JobStatus.RUNNING)
        except InvalidJobTransitionError:
            return job

        now = _utc_now()
        with self._lock:
            execute_query(
                self._connection,
                """
                UPDATE generation_jobs
                SET job_status = ?,
                    progress_message = ?,
                    completion_refreshes_remaining = ?,
                    completion_ready_at = ?,
                    updated_at = ?
                WHERE job_id = ?
                """,
                (
                    JobStatus.RUNNING.value,
                    progress_message,
                    self._completion_refresh_polls,
                    None,
                    now,
                    job_id,
                ),
            )
            self._connection.commit()
        return self.get_job(job_id)

    def fail_job(
        self,
        job_id: str,
        *,
        error_message: str,
        progress_message: str | None = None,
    ) -> JobState | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        try:
            validate_job_transition(job.status, JobStatus.FAILED)
        except InvalidJobTransitionError:
            return job

        now = _utc_now()
        with self._lock:
            execute_query(
                self._connection,
                """
                UPDATE generation_jobs
                SET job_status = ?,
                    progress_message = ?,
                    error_message = ?,
                    failed_at = ?,
                    completion_refreshes_remaining = NULL,
                    completion_ready_at = NULL,
                    updated_at = ?
                WHERE job_id = ?
                """,
                (
                    JobStatus.FAILED.value,
                    progress_message or job.progress_message,
                    error_message,
                    now,
                    now,
                    job_id,
                ),
            )
            self._connection.commit()
        return self.get_job(job_id)

    def cancel_job(
        self,
        job_id: str,
        *,
        progress_message: str = "Job cancelled.",
    ) -> JobState | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        try:
            validate_job_transition(job.status, JobStatus.CANCELLED)
        except InvalidJobTransitionError:
            return job

        now = _utc_now()
        with self._lock:
            execute_query(
                self._connection,
                """
                UPDATE generation_jobs
                SET job_status = ?,
                    progress_message = ?,
                    completion_refreshes_remaining = NULL,
                    completion_ready_at = NULL,
                    updated_at = ?
                WHERE job_id = ?
                """,
                (
                    JobStatus.CANCELLED.value,
                    progress_message,
                    now,
                    job_id,
                ),
            )
            self._connection.commit()
        return self.get_job(job_id)

    def expire_job(
        self,
        job_id: str,
        *,
        progress_message: str = "Job expired due to timeout.",
    ) -> JobState | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        try:
            validate_job_transition(job.status, JobStatus.EXPIRED)
        except InvalidJobTransitionError:
            return job

        now = _utc_now()
        with self._lock:
            execute_query(
                self._connection,
                """
                UPDATE generation_jobs
                SET job_status = ?,
                    progress_message = ?,
                    error_message = ?,
                    completion_refreshes_remaining = NULL,
                    completion_ready_at = NULL,
                    updated_at = ?
                WHERE job_id = ?
                """,
                (
                    JobStatus.EXPIRED.value,
                    progress_message,
                    "Job exceeded maximum execution time.",
                    now,
                    job_id,
                ),
            )
            self._connection.commit()
        return self.get_job(job_id)

    def complete_job(
        self,
        job_id: str,
        *,
        result: dict[str, object],
        progress_message: str,
    ) -> JobState | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        try:
            validate_job_transition(job.status, JobStatus.SUCCEEDED)
        except InvalidJobTransitionError:
            return job

        completed_response_id = str(result["response_id"])
        now = _utc_now()
        with self._lock:
            execute_query(
                self._connection,
                """
                UPDATE generation_jobs
                SET job_status = ?,
                    progress_message = ?,
                    completed_response_id = ?,
                    result_payload = ?,
                    completion_refreshes_remaining = NULL,
                    completion_ready_at = NULL,
                    error_message = NULL,
                    updated_at = ?,
                    completed_at = ?
                WHERE job_id = ?
                """,
                (
                    JobStatus.SUCCEEDED.value,
                    progress_message,
                    completed_response_id,
                    json.dumps(result),
                    now,
                    now,
                    job_id,
                ),
            )
            self._connection.commit()
        return self.get_job(job_id)

    def refresh_job(self, job_id: str) -> JobState | None:
        job = self.get_job(job_id)
        if job is None or job.status != JobStatus.RUNNING:
            return job
        with self._lock:
            row = execute_query(
                self._connection,
                """
                SELECT prepared_result_payload, completion_refreshes_remaining
                FROM generation_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            if row is None or row["prepared_result_payload"] is None:
                return job
            remaining = int(row["completion_refreshes_remaining"] or 0)
            if remaining == 0:
                prepared_result = _decode_json_payload(row["prepared_result_payload"])
                return self.complete_job(
                    job_id,
                    result=prepared_result,
                    progress_message=str(prepared_result.get("summary", "Background refresh completed for Memphis exceptions.")),
                )
            new_remaining = remaining - 1
            execute_query(
                self._connection,
                """
                UPDATE generation_jobs
                SET completion_refreshes_remaining = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (new_remaining, _utc_now(), job_id),
            )
            self._connection.commit()
        return self.get_job(job_id)

    def materialize_job(self, job_id: str) -> JobState | None:
        return self.refresh_job(job_id)

    def list_jobs(
        self,
        *,
        session_id: str | None = None,
        status: JobStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[JobState]:
        conditions = []
        params = []
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if status:
            conditions.append("job_status = ?")
            params.append(status.value)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT * FROM generation_jobs
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        with self._lock:
            rows = execute_query(self._connection, query, params).fetchall()
        return [self._row_to_job(row) for row in rows]

    def reset(self) -> None:
        with self._lock:
            execute_query(self._connection, "DELETE FROM generation_jobs")
            self._connection.commit()

    def update_autonomy_metadata(
        self,
        job_id: str,
        autonomy_metadata: dict[str, object],
        *,
        trigger_completion: bool = False,
    ) -> JobState | None:
        """Update autonomy metadata for a job.

        If trigger_completion is True, sets completion_refreshes_remaining to 0
        so the next refresh will immediately materialize the prepared result.
        """
        job = self.get_job(job_id)
        if job is None:
            return None

        now = _utc_now()
        with self._lock:
            if trigger_completion:
                execute_query(
                    self._connection,
                    """
                    UPDATE generation_jobs
                    SET autonomy_metadata = ?, updated_at = ?, completion_refreshes_remaining = 0
                    WHERE job_id = ?
                    """,
                    (json.dumps(autonomy_metadata), now, job_id),
                )
            else:
                execute_query(
                    self._connection,
                    """
                    UPDATE generation_jobs
                    SET autonomy_metadata = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (json.dumps(autonomy_metadata), now, job_id),
                )
            self._connection.commit()
        return self.get_job(job_id)
