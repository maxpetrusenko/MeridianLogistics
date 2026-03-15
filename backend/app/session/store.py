from __future__ import annotations

from datetime import UTC, datetime
import secrets
import sqlite3
import threading

from backend.app.session.models import ActiveResourceBinding, SessionState
from backend.app.state.database import connect_state_database, execute_query


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _resource_columns(resource: ActiveResourceBinding | None) -> tuple[str | None, str | None, str | None]:
    if resource is None:
        return None, None, None
    return resource.resource_type, resource.resource_id, resource.resource_fingerprint


class InMemorySessionStore:
    def __init__(self, *, database_url: str = "sqlite:///:memory:") -> None:
        self._connection = connect_state_database(database_url)
        self._lock = threading.RLock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._lock:
            execute_query(
                self._connection,
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    session_access_token TEXT,
                    broker_id TEXT NOT NULL,
                    office_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    current_module TEXT NOT NULL,
                    conversation_scope TEXT NOT NULL,
                    context_binding_state TEXT NOT NULL,
                    screen_sync_state TEXT NOT NULL,
                    active_resource_type TEXT,
                    active_resource_id TEXT,
                    active_resource_fingerprint TEXT,
                    last_response_id TEXT,
                    last_job_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
            )
            execute_query(
                self._connection,
                """
                CREATE TABLE IF NOT EXISTS chat_session_counters (
                    session_date TEXT PRIMARY KEY,
                    last_index INTEGER NOT NULL
                )
                """,
            )
            self._ensure_column("chat_sessions", "session_access_token", "TEXT")
            self._backfill_session_access_tokens()
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

    def _new_session_access_token(self) -> str:
        return secrets.token_urlsafe(24)

    def _backfill_session_access_tokens(self) -> None:
        rows = execute_query(
            self._connection,
            """
            SELECT session_id
            FROM chat_sessions
            WHERE session_access_token IS NULL OR session_access_token = ''
            """,
        ).fetchall()
        for row in rows:
            execute_query(
                self._connection,
                """
                UPDATE chat_sessions
                SET session_access_token = ?, updated_at = COALESCE(updated_at, ?)
                WHERE session_id = ?
                """,
                (self._new_session_access_token(), _utc_now(), row["session_id"]),
            )

    def next_session_id(self) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d")
        with self._lock:
            row = execute_query(
                self._connection,
                """
                INSERT INTO chat_session_counters (session_date, last_index)
                VALUES (?, 1)
                ON CONFLICT(session_date) DO UPDATE SET
                    last_index = chat_session_counters.last_index + 1
                RETURNING last_index
                """,
                (stamp,),
            ).fetchone()
            self._connection.commit()
        next_index = int(row["last_index"]) if row is not None else 1
        return f"chat_s_{stamp}_{next_index:04d}"

    def next_session_access_token(self) -> str:
        return self._new_session_access_token()

    def get_session(self, session_id: str) -> SessionState | None:
        with self._lock:
            row = execute_query(
                self._connection,
                "SELECT * FROM chat_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        active_resource = None
        if row["active_resource_type"] is not None:
            active_resource = ActiveResourceBinding(
                resource_type=row["active_resource_type"],
                resource_id=row["active_resource_id"],
                resource_fingerprint=row["active_resource_fingerprint"],
            )
        return SessionState(
            session_id=row["session_id"],
            session_access_token=row["session_access_token"],
            broker_id=row["broker_id"],
            office_id=row["office_id"],
            role=row["role"],
            current_module=row["current_module"],
            conversation_scope=row["conversation_scope"],
            context_binding_state=row["context_binding_state"],
            screen_sync_state=row["screen_sync_state"],
            active_resource=active_resource,
            last_response_id=row["last_response_id"],
            last_job_id=row["last_job_id"],
        )

    def save_session(self, session: SessionState) -> SessionState:
        active_resource_type, active_resource_id, active_resource_fingerprint = _resource_columns(
            session.active_resource
        )
        now = _utc_now()
        with self._lock:
            created_at_row = execute_query(
                self._connection,
                "SELECT created_at FROM chat_sessions WHERE session_id = ?",
                (session.session_id,),
            ).fetchone()
            created_at = created_at_row["created_at"] if created_at_row is not None else now
            execute_query(
                self._connection,
                """
                INSERT INTO chat_sessions (
                    session_id,
                    session_access_token,
                    broker_id,
                    office_id,
                    role,
                    current_module,
                    conversation_scope,
                    context_binding_state,
                    screen_sync_state,
                    active_resource_type,
                    active_resource_id,
                    active_resource_fingerprint,
                    last_response_id,
                    last_job_id,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    session_access_token = excluded.session_access_token,
                    broker_id = excluded.broker_id,
                    office_id = excluded.office_id,
                    role = excluded.role,
                    current_module = excluded.current_module,
                    conversation_scope = excluded.conversation_scope,
                    context_binding_state = excluded.context_binding_state,
                    screen_sync_state = excluded.screen_sync_state,
                    active_resource_type = excluded.active_resource_type,
                    active_resource_id = excluded.active_resource_id,
                    active_resource_fingerprint = excluded.active_resource_fingerprint,
                    last_response_id = excluded.last_response_id,
                    last_job_id = excluded.last_job_id,
                    updated_at = excluded.updated_at
                """,
                (
                    session.session_id,
                    session.session_access_token,
                    session.broker_id,
                    session.office_id,
                    session.role,
                    session.current_module,
                    session.conversation_scope,
                    session.context_binding_state,
                    session.screen_sync_state,
                    active_resource_type,
                    active_resource_id,
                    active_resource_fingerprint,
                    session.last_response_id,
                    session.last_job_id,
                    created_at,
                    now,
                ),
            )
            self._connection.commit()
        return session

    def get_session_by_access_token(self, session_id: str, session_access_token: str) -> SessionState | None:
        with self._lock:
            row = execute_query(
                self._connection,
                """
                SELECT *
                FROM chat_sessions
                WHERE session_id = ? AND session_access_token = ?
                """,
                (session_id, session_access_token),
            ).fetchone()
        if row is None:
            return None
        active_resource = None
        if row["active_resource_type"] is not None:
            active_resource = ActiveResourceBinding(
                resource_type=row["active_resource_type"],
                resource_id=row["active_resource_id"],
                resource_fingerprint=row["active_resource_fingerprint"],
            )
        return SessionState(
            session_id=row["session_id"],
            session_access_token=row["session_access_token"],
            broker_id=row["broker_id"],
            office_id=row["office_id"],
            role=row["role"],
            current_module=row["current_module"],
            conversation_scope=row["conversation_scope"],
            context_binding_state=row["context_binding_state"],
            screen_sync_state=row["screen_sync_state"],
            active_resource=active_resource,
            last_response_id=row["last_response_id"],
            last_job_id=row["last_job_id"],
        )

    def promote_job_completion(
        self,
        *,
        session_id: str,
        expected_last_response_id: str,
        completed_response_id: str,
        job_id: str,
    ) -> SessionState | None:
        with self._lock:
            cursor = execute_query(
                self._connection,
                """
                UPDATE chat_sessions
                SET last_response_id = ?, last_job_id = ?, updated_at = ?
                WHERE session_id = ? AND last_response_id = ?
                """,
                (
                    completed_response_id,
                    job_id,
                    _utc_now(),
                    session_id,
                    expected_last_response_id,
                ),
            )
            self._connection.commit()
            if cursor.rowcount == 0:
                return None
        return self.get_session(session_id)

    def reset(self) -> None:
        with self._lock:
            execute_query(self._connection, "DELETE FROM chat_sessions")
            self._connection.commit()
