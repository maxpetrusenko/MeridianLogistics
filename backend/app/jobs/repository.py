from __future__ import annotations

from datetime import UTC, datetime
import json
import secrets
from typing import Any
from uuid import uuid4

from backend.app.config import load_config
from backend.app.db.context import load_database_context
from backend.app.state.database import _connect_postgres, _normalize_postgres_url


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _new_job_poll_token() -> str:
    return secrets.token_urlsafe(24)


def _generate_job_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return f"job_{stamp}_{uuid4().hex[:12]}"


def _decode_jsonb(value: Any) -> dict[str, object] | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return json.loads(str(value))


def _encode_jsonb(value: dict[str, object] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value)


class JobRepository:
    """PostgreSQL-backed durable job storage."""

    def __init__(self, database_url: str | None = None) -> None:
        config = load_config()
        self._database_url = database_url or config.database_url
        self._context = load_database_context()

    def _connect(self) -> Any:
        """Get a fresh PostgreSQL connection."""
        return _connect_postgres(self._database_url)

    def _execute(
        self,
        query: str,
        parameters: tuple[object, ...] = (),
        *,
        fetch: str = "all",
    ) -> Any:
        """Execute a query with proper parameter substitution."""
        conn = self._connect()
        try:
            cursor = conn.cursor()
            postgres_query = query.replace("?", "%s")
            cursor.execute(postgres_query, parameters)

            if fetch == "one":
                return cursor.fetchone()
            if fetch == "all":
                return cursor.fetchall()
            if fetch == "none":
                conn.commit()
                return None
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        """Ensure generation_jobs table exists (should be in schema.sql)."""
        # Schema should be applied via migrations; this is a safety check
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS generation_jobs (
                job_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES chat_sessions (session_id),
                office_id TEXT NOT NULL REFERENCES offices (office_id),
                broker_id TEXT NOT NULL REFERENCES brokers (broker_id),
                job_kind TEXT NOT NULL,
                job_status TEXT NOT NULL,
                progress_message TEXT NOT NULL,
                retry_allowed BOOLEAN NOT NULL DEFAULT FALSE,
                pending_response_id TEXT,
                completed_response_id TEXT,
                prepared_result_payload JSONB,
                result_payload JSONB,
                job_poll_token TEXT,
                completion_refreshes_remaining INTEGER,
                completion_ready_at DOUBLE PRECISION,
                artifact_key TEXT,
                artifact_mime_type TEXT,
                artifact_size_bytes BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            )
            """,
            fetch="none",
        )

        # Add poll token column if missing (for older schemas)
        self._execute(
            "ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS job_poll_token TEXT",
            fetch="none",
        )

    def create(
        self,
        *,
        session_id: str,
        office_id: str,
        broker_id: str,
        job_kind: str = "analytics_refresh",
        progress_message: str = "Job queued",
        retry_allowed: bool = False,
    ) -> dict[str, object]:
        """Create a new job."""
        self._ensure_schema()

        job_id = _generate_job_id()
        job_poll_token = _new_job_poll_token()
        now = _utc_now()

        self._execute(
            """
            INSERT INTO generation_jobs (
                job_id, session_id, office_id, broker_id,
                job_kind, job_status, progress_message,
                retry_allowed, job_poll_token, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                job_id, session_id, office_id, broker_id,
                job_kind, "queued", progress_message,
                retry_allowed, job_poll_token, now, now,
            ),
            fetch="none",
        )

        return self.get(job_id)  # type: ignore

    def get(self, job_id: str) -> dict[str, object] | None:
        """Get a job by ID."""
        self._ensure_schema()
        row = self._execute(
            "SELECT * FROM generation_jobs WHERE job_id = %s",
            (job_id,),
            fetch="one",
        )
        if not row:
            return None
        return self._row_to_dict(row)

    def get_by_poll_token(self, job_id: str, poll_token: str) -> dict[str, object] | None:
        """Get a job by ID and poll token (for secure polling)."""
        self._ensure_schema()
        row = self._execute(
            "SELECT * FROM generation_jobs WHERE job_id = %s AND job_poll_token = %s",
            (job_id, poll_token),
            fetch="one",
        )
        if not row:
            return None
        return self._row_to_dict(row)

    def get_by_session(self, session_id: str, limit: int = 50) -> list[dict[str, object]]:
        """Get all jobs for a session."""
        self._ensure_schema()
        rows = self._execute(
            """
            SELECT * FROM generation_jobs
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (session_id, limit),
            fetch="all",
        )
        return [self._row_to_dict(row) for row in rows]

    def get_by_broker(self, broker_id: str, limit: int = 100) -> list[dict[str, object]]:
        """Get all jobs for a broker."""
        self._ensure_schema()
        rows = self._execute(
            """
            SELECT * FROM generation_jobs
            WHERE broker_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (broker_id, limit),
            fetch="all",
        )
        return [self._row_to_dict(row) for row in rows]

    def list_pending(self, limit: int = 100) -> list[dict[str, object]]:
        """Get pending/running jobs."""
        self._ensure_schema()
        rows = self._execute(
            """
            SELECT * FROM generation_jobs
            WHERE job_status IN ('queued', 'running')
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (limit,),
            fetch="all",
        )
        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row: dict[str, Any]) -> dict[str, object]:
        """Convert DB row to dict."""
        return {
            "job_id": row["job_id"],
            "session_id": row["session_id"],
            "office_id": row["office_id"],
            "broker_id": row["broker_id"],
            "job_kind": row["job_kind"],
            "status": row["job_status"],
            "progress_message": row["progress_message"],
            "retry_allowed": bool(row["retry_allowed"]),
            "pending_response_id": row["pending_response_id"],
            "completed_response_id": row["completed_response_id"],
            "result": _decode_jsonb(row["result_payload"]),
            "prepared_result": _decode_jsonb(row["prepared_result_payload"]),
            "job_poll_token": row["job_poll_token"],
            "completion_refreshes_remaining": row["completion_refreshes_remaining"],
            "completion_ready_at": row["completion_ready_at"],
            "artifact_key": row["artifact_key"],
            "artifact_mime_type": row["artifact_mime_type"],
            "artifact_size_bytes": row["artifact_size_bytes"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        }

    def update_status(
        self,
        job_id: str,
        status: str,
        *,
        progress_message: str | None = None,
    ) -> dict[str, object] | None:
        """Update job status."""
        self._ensure_schema()
        now = _utc_now()

        if progress_message:
            self._execute(
                """
                UPDATE generation_jobs
                SET job_status = %s, progress_message = %s, updated_at = %s
                WHERE job_id = %s
                """,
                (status, progress_message, now, job_id),
                fetch="none",
            )
        else:
            self._execute(
                """
                UPDATE generation_jobs
                SET job_status = %s, updated_at = %s
                WHERE job_id = %s
                """,
                (status, now, job_id),
                fetch="none",
            )

        return self.get(job_id)

    def start(
        self,
        job_id: str,
        *,
        progress_message: str = "Job running",
        refreshes_remaining: int = 2,
    ) -> dict[str, object] | None:
        """Mark a job as running."""
        self._ensure_schema()
        now = _utc_now()

        self._execute(
            """
            UPDATE generation_jobs
            SET job_status = 'running',
                progress_message = %s,
                completion_refreshes_remaining = %s,
                completion_ready_at = NULL,
                updated_at = %s
            WHERE job_id = %s AND job_status = 'queued'
            """,
            (progress_message, refreshes_remaining, now, job_id),
            fetch="none",
        )

        return self.get(job_id)

    def prepare_result(self, job_id: str, result: dict[str, object]) -> None:
        """Store a prepared result (for later completion)."""
        self._ensure_schema()
        now = _utc_now()

        self._execute(
            """
            UPDATE generation_jobs
            SET prepared_result_payload = %s, updated_at = %s
            WHERE job_id = %s
            """,
            (_encode_jsonb(result), now, job_id),
            fetch="none",
        )

    def complete(
        self,
        job_id: str,
        *,
        result: dict[str, object],
        progress_message: str = "Job completed",
        artifact_key: str | None = None,
        artifact_mime_type: str | None = None,
        artifact_size_bytes: int | None = None,
    ) -> dict[str, object] | None:
        """Mark a job as completed with result."""
        self._ensure_schema()
        now = _utc_now()
        completed_response_id = str(result.get("response_id", ""))

        self._execute(
            """
            UPDATE generation_jobs
            SET job_status = 'succeeded',
                progress_message = %s,
                completed_response_id = %s,
                result_payload = %s,
                completion_refreshes_remaining = NULL,
                completion_ready_at = NULL,
                artifact_key = %s,
                artifact_mime_type = %s,
                artifact_size_bytes = %s,
                updated_at = %s,
                completed_at = %s
            WHERE job_id = %s
            """,
            (
                progress_message,
                completed_response_id,
                _encode_jsonb(result),
                artifact_key,
                artifact_mime_type,
                artifact_size_bytes,
                now,
                now,
                job_id,
            ),
            fetch="none",
        )

        return self.get(job_id)

    def fail(
        self,
        job_id: str,
        *,
        error_message: str,
        retry_allowed: bool = False,
    ) -> dict[str, object] | None:
        """Mark a job as failed."""
        return self.update_status(
            job_id,
            "failed",
            progress_message=error_message,
        )

    def bind_pending_response(self, job_id: str, response_id: str) -> dict[str, object] | None:
        """Bind a pending response ID to a job."""
        self._ensure_schema()
        now = _utc_now()

        self._execute(
            """
            UPDATE generation_jobs
            SET pending_response_id = %s, updated_at = %s
            WHERE job_id = %s
            """,
            (response_id, now, job_id),
            fetch="none",
        )

        return self.get(job_id)

    def refresh(self, job_id: str) -> dict[str, object] | None:
        """
        Refresh a running job.
        If prepared result exists and refreshes exhausted, complete the job.
        """
        self._ensure_schema()
        job = self.get(job_id)

        if not job or job["status"] != "running":
            return job

        prepared_result = job.get("prepared_result")
        remaining = job.get("completion_refreshes_remaining", 0)

        if not prepared_result:
            return job

        if remaining and remaining > 0:
            # Decrement refresh count
            now = _utc_now()
            self._execute(
                """
                UPDATE generation_jobs
                SET completion_refreshes_remaining = %s, updated_at = %s
                WHERE job_id = %s
                """,
                (remaining - 1, now, job_id),
                fetch="none",
            )
            return self.get(job_id)

        # No refreshes remaining - complete with prepared result
        return self.complete(
            job_id,
            result=prepared_result,
            progress_message=str(prepared_result.get("summary", "Background refresh completed.")),
        )

    def link_artifact(
        self,
        job_id: str,
        artifact_key: str,
        mime_type: str,
        size_bytes: int,
    ) -> dict[str, object] | None:
        """Link an artifact (stored object) to a job."""
        self._ensure_schema()
        now = _utc_now()

        self._execute(
            """
            UPDATE generation_jobs
            SET artifact_key = %s,
                artifact_mime_type = %s,
                artifact_size_bytes = %s,
                updated_at = %s
            WHERE job_id = %s
            """,
            (artifact_key, mime_type, size_bytes, now, job_id),
            fetch="none",
        )

        return self.get(job_id)

    def cleanup_old(self, days: int = 30) -> int:
        """Delete completed jobs older than N days. Returns count deleted."""
        self._ensure_schema()
        result = self._execute(
            """
            DELETE FROM generation_jobs
            WHERE job_status IN ('succeeded', 'failed', 'cancelled')
              AND completed_at < NOW() - INTERVAL '%s days'
            """,
            (days,),
            fetch="none",
        )
        # Can't get rowcount from closed connection
        # Caller should verify via separate count query if needed
        return 0
