from __future__ import annotations

from datetime import UTC, datetime
import os
import tempfile
import threading
import unittest

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.jobs.models import JobStatus, is_terminal_status, InvalidJobTransitionError
from backend.app.jobs.store import InMemoryJobStore
from backend.app.session.store import InMemorySessionStore
from backend.app.state.database import execute_query


class AsyncJobLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._previous_state_database_url = os.environ.get("MERIDIAN_STATE_DATABASE_URL")
        os.environ["MERIDIAN_STATE_DATABASE_URL"] = f"sqlite:///{self._temp_dir.name}/state.sqlite3"

    def tearDown(self) -> None:
        if self._previous_state_database_url is None:
            os.environ.pop("MERIDIAN_STATE_DATABASE_URL", None)
        else:
            os.environ["MERIDIAN_STATE_DATABASE_URL"] = self._previous_state_database_url
        self._temp_dir.cleanup()

    def _make_chat_request(
        self,
        *,
        prompt: str,
        session_id: str | None = None,
        session_access_token: str | None = None,
        resource_id: str | None = None,
    ) -> dict[str, object]:
        request = {
            "prompt": prompt,
            "broker_id": "broker-123",
            "office_id": "memphis",
            "role": "broker",
            "current_module": "dispatch_board",
        }
        if session_id is not None:
            request["session_id"] = session_id
        if session_access_token is not None:
            request["session_access_token"] = session_access_token
        if resource_id is not None:
            request["current_resource"] = {
                "resource_type": "shipment",
                "resource_id": resource_id,
                "resource_fingerprint": f"shipment:{resource_id}:v1",
            }
        return request

    def _job_query(self, *, job_poll_token: str) -> dict[str, str]:
        return {"job_poll_token": job_poll_token}

    def _prepared_result(self, *, session_id: str, job_id: str) -> dict[str, object]:
        return {
            "contract_version": "0.1.0",
            "response_id": "resp_test_complete",
            "request_id": "req_test_complete",
            "trace_id": "trace_test_complete",
            "session_id": session_id,
            "conversation_scope": "analytics",
            "context_binding_state": "bound",
            "screen_sync_state": "not_applicable",
            "active_resource": None,
            "job_id": job_id,
            "intent_class": "read_result",
            "status": "success",
            "summary": "Background refresh completed for Memphis exceptions.",
            "follow_up_prompt": None,
            "components": [
                {
                    "component_id": "msg-job-complete",
                    "component_type": "message_block",
                    "body": "Background refresh completed for Memphis exceptions.",
                    "tone": "informational",
                }
            ],
            "actions": [],
            "policy": {
                "permission_context_applied": True,
                "sensitive_fields_redacted": True,
                "write_confirmation_required": False,
                "denial_reason_class": "none",
            },
            "audit": {
                "actor_role": "broker",
                "office_scope": "memphis",
                "tool_path": ["shipment_exception_lookup"],
                "response_generated_at": "2026-03-14T00:00:00Z",
            },
        }

    def test_session_store_next_session_id_is_unique_under_concurrent_calls(self) -> None:
        store = InMemorySessionStore()
        ready = threading.Barrier(8)
        issued_ids: list[str] = []
        errors: list[BaseException] = []
        write_lock = threading.Lock()

        def mint_id() -> None:
            try:
                ready.wait()
                session_id = store.next_session_id()
                with write_lock:
                    issued_ids.append(session_id)
            except BaseException as exc:  # pragma: no cover - failure path only
                with write_lock:
                    errors.append(exc)

        threads = [threading.Thread(target=mint_id) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(issued_ids), 8)
        self.assertEqual(len(set(issued_ids)), 8)

    def test_session_store_next_session_id_is_unique_across_store_instances(self) -> None:
        database_url = f"sqlite:///{self._temp_dir.name}/shared-state.sqlite3"
        stores = [InMemorySessionStore(database_url=database_url) for _ in range(8)]
        ready = threading.Barrier(len(stores))
        issued_ids: list[str] = []
        errors: list[BaseException] = []
        write_lock = threading.Lock()

        def mint_id(store: InMemorySessionStore) -> None:
            try:
                ready.wait()
                session_id = store.next_session_id()
                with write_lock:
                    issued_ids.append(session_id)
            except BaseException as exc:  # pragma: no cover - failure path only
                with write_lock:
                    errors.append(exc)

        threads = [threading.Thread(target=mint_id, args=(store,)) for store in stores]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(issued_ids), len(stores))
        self.assertEqual(len(set(issued_ids)), len(stores))

    def test_session_store_next_session_id_advances_past_four_digits(self) -> None:
        store = InMemorySessionStore()
        stamp = datetime.now(UTC).strftime("%Y%m%d")
        execute_query(
            store._connection,
            """
            INSERT INTO chat_session_counters (session_date, last_index)
            VALUES (?, ?)
            """,
            (stamp, 9999),
        )
        store._connection.commit()

        self.assertEqual(store.next_session_id(), f"chat_s_{stamp}_10000")
        self.assertEqual(store.next_session_id(), f"chat_s_{stamp}_10001")

    def test_job_store_supports_explicit_running_and_completion_transitions(self) -> None:
        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh queued for Memphis exceptions.",
            retry_allowed=True,
        )
        store.bind_pending_response(job.job_id, "resp_pending")

        running = store.start_job(
            job.job_id,
            progress_message="Background refresh running for Memphis exceptions.",
        )
        self.assertIsNotNone(running)
        assert running is not None
        self.assertEqual(running.status, "running")
        self.assertEqual(running.pending_response_id, "resp_pending")

        completed = store.complete_job(
            job.job_id,
            result=self._prepared_result(session_id=job.session_id, job_id=job.job_id),
            progress_message="Background refresh completed for Memphis exceptions.",
        )
        self.assertIsNotNone(completed)
        assert completed is not None
        self.assertEqual(completed.status, "succeeded")
        self.assertEqual(completed.completed_response_id, "resp_test_complete")
        self.assertEqual(completed.result["job_id"], job.job_id)
        self.assertEqual(store.get_job(job.job_id), completed)

    def test_job_store_backfills_poll_tokens_for_legacy_rows(self) -> None:
        database_url = f"sqlite:///{self._temp_dir.name}/legacy-state.sqlite3"
        legacy_store = InMemoryJobStore(database_url=database_url)
        job = legacy_store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh queued for Memphis exceptions.",
            retry_allowed=True,
        )
        execute_query(
            legacy_store._connection,
            """
            UPDATE generation_jobs
            SET job_poll_token = NULL
            WHERE job_id = ?
            """,
            (job.job_id,),
        )
        legacy_store._connection.commit()

        reopened_store = InMemoryJobStore(database_url=database_url)
        reopened_job = reopened_store.get_job(job.job_id)

        self.assertIsNotNone(reopened_job)
        assert reopened_job is not None
        self.assertIsNotNone(reopened_job.job_poll_token)
        assert reopened_job.job_poll_token is not None
        self.assertGreaterEqual(len(reopened_job.job_poll_token), 16)

    def test_job_store_promotes_completion_only_when_session_last_response_matches(self) -> None:
        client = TestClient(create_app())

        seed = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Show shipment 88219 details.",
                resource_id="88219",
            ),
        )
        self.assertEqual(seed.status_code, 200)
        seed_payload = seed.json()
        session_access_token = seed_payload["session_access_token"]

        pending = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Run a background analytics refresh for Memphis exceptions.",
                session_id=seed_payload["session_id"],
                session_access_token=session_access_token,
            ),
        )
        self.assertEqual(pending.status_code, 200)
        pending_payload = pending.json()

        client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Switch to shipment 99117.",
                session_id=seed_payload["session_id"],
                session_access_token=session_access_token,
                resource_id="99117",
            ),
        )

        promoted = client.app.state.session_store.promote_job_completion(
            session_id=seed_payload["session_id"],
            expected_last_response_id=pending_payload["response_id"],
            completed_response_id="resp_completed_late",
            job_id=pending_payload["job_id"],
        )
        self.assertIsNone(promoted)

        latest_session = client.app.state.session_store.get_session(seed_payload["session_id"])
        self.assertIsNotNone(latest_session)
        assert latest_session is not None
        self.assertNotEqual(latest_session.last_response_id, "resp_completed_late")

    def test_jobs_route_keeps_running_state_until_background_completion_is_ready(self) -> None:
        client = TestClient(create_app())

        seed = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Show shipment 88219 details.",
                resource_id="88219",
            ),
        )
        self.assertEqual(seed.status_code, 200)
        seed_payload = seed.json()
        session_access_token = seed_payload["session_access_token"]

        response = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Run a background analytics refresh for Memphis exceptions.",
                session_id=seed_payload["session_id"],
                session_access_token=session_access_token,
            ),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("job_poll_token", payload)

        first_job = client.get(
            f"/jobs/{payload['job_id']}",
            params=self._job_query(job_poll_token=payload["job_poll_token"]),
        )
        self.assertEqual(first_job.status_code, 200)
        first_job_payload = first_job.json()
        self.assertEqual(first_job_payload["status"], "running")

        second_job = client.get(
            f"/jobs/{payload['job_id']}",
            params=self._job_query(job_poll_token=payload["job_poll_token"]),
        )
        self.assertEqual(second_job.status_code, 200)
        second_job_payload = second_job.json()
        self.assertEqual(second_job_payload["status"], "running")
        self.assertIsNone(second_job_payload["completed_response_id"])
        self.assertIsNone(second_job_payload["result"])

        third_job = client.get(
            f"/jobs/{payload['job_id']}",
            params=self._job_query(job_poll_token=payload["job_poll_token"]),
        )
        self.assertEqual(third_job.status_code, 200)
        third_job_payload = third_job.json()
        self.assertEqual(third_job_payload["status"], "succeeded")
        self.assertEqual(third_job_payload["completed_response_id"], third_job_payload["result"]["response_id"])

    def test_restart_reopens_persisted_session_and_job_state(self) -> None:
        first_client = TestClient(create_app())

        seed = first_client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Show shipment 88219 details.",
                resource_id="88219",
            ),
        )
        self.assertEqual(seed.status_code, 200)
        seed_payload = seed.json()
        session_id = seed_payload["session_id"]
        session_access_token = seed_payload["session_access_token"]

        pending = first_client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Run a background analytics refresh for Memphis exceptions.",
                session_id=session_id,
                session_access_token=session_access_token,
            ),
        )
        self.assertEqual(pending.status_code, 200)
        pending_payload = pending.json()
        session_access_token = pending_payload["session_access_token"]

        reopened_client = TestClient(create_app())

        reopened_session = reopened_client.get(
            f"/sessions/{session_id}",
            params={"session_access_token": session_access_token},
        )
        self.assertEqual(reopened_session.status_code, 200)
        reopened_session_payload = reopened_session.json()
        self.assertEqual(reopened_session_payload["session_id"], session_id)
        self.assertEqual(reopened_session_payload["last_job_id"], pending_payload["job_id"])

        reopened_client.get(
            f"/jobs/{pending_payload['job_id']}",
            params=self._job_query(job_poll_token=pending_payload["job_poll_token"]),
        )
        reopened_client.get(
            f"/jobs/{pending_payload['job_id']}",
            params=self._job_query(job_poll_token=pending_payload["job_poll_token"]),
        )
        completed = reopened_client.get(
            f"/jobs/{pending_payload['job_id']}",
            params=self._job_query(job_poll_token=pending_payload["job_poll_token"]),
        )
        self.assertEqual(completed.status_code, 200)
        completed_payload = completed.json()
        self.assertEqual(completed_payload["result"]["response_id"], completed_payload["completed_response_id"])


    def test_job_create_sets_initial_queued_state_with_poll_token(self) -> None:
        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh queued for Memphis exceptions.",
            retry_allowed=True,
        )

        self.assertEqual(job.status, "pending")
        self.assertEqual(job.session_id, "chat_s_20260314_0001")
        self.assertEqual(job.broker_id, "broker-123")
        self.assertEqual(job.office_id, "memphis")
        self.assertIsNone(job.pending_response_id)
        self.assertIsNone(job.completed_response_id)
        self.assertIsNone(job.result)
        self.assertTrue(job.retry_allowed)
        self.assertIsNotNone(job.job_poll_token)
        self.assertGreaterEqual(len(job.job_poll_token), 16)
        self.assertEqual(job.job_id[:6], "job_20")

    def test_job_create_persists_across_store_reopen(self) -> None:
        database_url = f"sqlite:///{self._temp_dir.name}/job-persistence.sqlite3"
        first_store = InMemoryJobStore(database_url=database_url)

        job = first_store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh queued.",
            retry_allowed=False,
        )

        reopened_store = InMemoryJobStore(database_url=database_url)
        retrieved_job = reopened_store.get_job(job.job_id)

        self.assertIsNotNone(retrieved_job)
        assert retrieved_job is not None
        self.assertEqual(retrieved_job.job_id, job.job_id)
        self.assertEqual(retrieved_job.session_id, job.session_id)
        self.assertEqual(retrieved_job.status, "pending")
        self.assertEqual(retrieved_job.job_poll_token, job.job_poll_token)
        self.assertFalse(retrieved_job.retry_allowed)

    def test_job_start_fails_for_non_queued_jobs(self) -> None:
        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh queued.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")
        already_running = store.start_job(job.job_id, progress_message="Still running")

        self.assertIsNotNone(already_running)
        assert already_running is not None
        self.assertEqual(already_running.status, "running")

    def test_job_complete_transitions_from_running_to_succeeded(self) -> None:
        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh queued.",
            retry_allowed=True,
        )

        running = store.start_job(job.job_id, progress_message="Running")
        self.assertIsNotNone(running)
        assert running is not None
        self.assertEqual(running.status, "running")

        result = self._prepared_result(session_id=job.session_id, job_id=job.job_id)
        completed = store.complete_job(
            job.job_id,
            result=result,
            progress_message="Background refresh completed.",
        )

        self.assertIsNotNone(completed)
        assert completed is not None
        self.assertEqual(completed.status, "succeeded")
        self.assertEqual(completed.completed_response_id, "resp_test_complete")
        self.assertEqual(completed.result["response_id"], "resp_test_complete")
        self.assertIsNone(completed.completion_refreshes_remaining)
        self.assertIsNone(completed.completion_ready_at)

    def test_job_prepare_result_stores_payload_for_later_materialization(self) -> None:
        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh queued.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")

        result = self._prepared_result(session_id=job.session_id, job_id=job.job_id)
        store.prepare_result(job.job_id, result)

        row = execute_query(
            store._connection,
            "SELECT prepared_result_payload FROM generation_jobs WHERE job_id = ?",
            (job.job_id,),
        ).fetchone()

        self.assertIsNotNone(row)
        assert row is not None
        self.assertIsNotNone(row["prepared_result_payload"])

    def test_job_refresh_materializes_prepared_result_after_refresh_polls_exhausted(self) -> None:
        store = InMemoryJobStore(completion_refresh_polls=3)

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh queued.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")

        result = self._prepared_result(session_id=job.session_id, job_id=job.job_id)
        store.prepare_result(job.job_id, result)

        first_refresh = store.refresh_job(job.job_id)
        self.assertIsNotNone(first_refresh)
        assert first_refresh is not None
        self.assertEqual(first_refresh.status, "running")
        assert first_refresh.completion_refreshes_remaining is not None
        self.assertEqual(first_refresh.completion_refreshes_remaining, 2)

        second_refresh = store.refresh_job(job.job_id)
        self.assertIsNotNone(second_refresh)
        assert second_refresh is not None
        self.assertEqual(second_refresh.status, "running")
        assert second_refresh.completion_refreshes_remaining is not None
        self.assertEqual(second_refresh.completion_refreshes_remaining, 1)

        third_refresh = store.refresh_job(job.job_id)
        self.assertIsNotNone(third_refresh)
        assert third_refresh is not None
        self.assertEqual(third_refresh.status, "running")
        self.assertEqual(third_refresh.completion_refreshes_remaining, 0)

        fourth_refresh = store.refresh_job(job.job_id)
        self.assertIsNotNone(fourth_refresh)
        assert fourth_refresh is not None
        self.assertEqual(fourth_refresh.status, "succeeded")
        self.assertEqual(fourth_refresh.completed_response_id, "resp_test_complete")

    def test_job_refresh_returns_job_as_is_when_no_prepared_result(self) -> None:
        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh queued.",
            retry_allowed=True,
        )

        running = store.start_job(job.job_id, progress_message="Running")

        refreshed = store.refresh_job(job.job_id)

        self.assertEqual(refreshed.status, running.status)
        self.assertEqual(refreshed.job_id, running.job_id)

    def test_job_refresh_returns_completed_job_unchanged(self) -> None:
        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh queued.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")
        completed = store.complete_job(
            job.job_id,
            result=self._prepared_result(session_id=job.session_id, job_id=job.job_id),
            progress_message="Completed.",
        )

        refreshed = store.refresh_job(job.job_id)

        self.assertEqual(refreshed.status, "succeeded")
        self.assertEqual(refreshed.completed_response_id, completed.completed_response_id)

    def test_job_bind_pending_response_updates_pending_response_id(self) -> None:
        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh queued.",
            retry_allowed=True,
        )

        bound = store.bind_pending_response(job.job_id, "resp_pending_abc")

        self.assertIsNotNone(bound)
        assert bound is not None
        self.assertEqual(bound.pending_response_id, "resp_pending_abc")

    def test_job_get_by_poll_token_requires_matching_token(self) -> None:
        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh queued.",
            retry_allowed=True,
        )

        valid_job = store.get_job_by_poll_token(job.job_id, job.job_poll_token or "")
        self.assertIsNotNone(valid_job)
        assert valid_job is not None
        self.assertEqual(valid_job.job_id, job.job_id)

        invalid_job = store.get_job_by_poll_token(job.job_id, "invalid_poll_token")
        self.assertIsNone(invalid_job)

    def test_job_get_by_poll_token_returns_none_for_unknown_job_id(self) -> None:
        store = InMemoryJobStore()

        result = store.get_job_by_poll_token("unknown_job_id", "any_token")
        self.assertIsNone(result)

    def test_job_get_returns_none_for_unknown_job_id(self) -> None:
        store = InMemoryJobStore()

        result = store.get_job("unknown_job_id")
        self.assertIsNone(result)

    def test_job_reset_clears_all_jobs(self) -> None:
        store = InMemoryJobStore()

        store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Job 1 queued.",
            retry_allowed=True,
        )
        store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Job 2 queued.",
            retry_allowed=True,
        )

        store.reset()

        job = store.get_job("job_20260314_")
        self.assertIsNone(job)

        rows = execute_query(
            store._connection,
            "SELECT COUNT(*) as count FROM generation_jobs",
        ).fetchone()

        assert rows is not None
        self.assertEqual(rows["count"], 0)

    def test_job_list_jobs_by_session_id(self) -> None:
        store = InMemoryJobStore()
        session_id = "chat_s_20260314_0001"

        job1 = store.create_job(
            session_id=session_id,
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Job 1 queued.",
            retry_allowed=True,
        )
        job2 = store.create_job(
            session_id=session_id,
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Job 2 queued.",
            retry_allowed=True,
        )
        store.create_job(
            session_id="chat_s_20260314_0002",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Other session job.",
            retry_allowed=True,
        )

        rows = execute_query(
            store._connection,
            "SELECT job_id FROM generation_jobs WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()

        self.assertEqual(len(rows), 2)
        job_ids = [row["job_id"] for row in rows]
        self.assertIn(job1.job_id, job_ids)
        self.assertIn(job2.job_id, job_ids)

    def test_job_filter_by_status(self) -> None:
        store = InMemoryJobStore()

        queued_job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Queued job.",
            retry_allowed=True,
        )

        running_job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Running job.",
            retry_allowed=True,
        )
        store.start_job(running_job.job_id, progress_message="Running")

        completed_job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Completed job.",
            retry_allowed=True,
        )
        store.start_job(completed_job.job_id, progress_message="Running")
        store.complete_job(
            completed_job.job_id,
            result=self._prepared_result(session_id=completed_job.session_id, job_id=completed_job.job_id),
            progress_message="Completed.",
        )

        running_rows = execute_query(
            store._connection,
            "SELECT job_id FROM generation_jobs WHERE job_status = ?",
            ("running",),
        ).fetchall()

        self.assertEqual(len(running_rows), 1)
        self.assertEqual(running_rows[0]["job_id"], running_job.job_id)

        succeeded_rows = execute_query(
            store._connection,
            "SELECT job_id FROM generation_jobs WHERE job_status = ?",
            ("succeeded",),
        ).fetchall()

        self.assertEqual(len(succeeded_rows), 1)
        self.assertEqual(succeeded_rows[0]["job_id"], completed_job.job_id)

    def test_job_to_dict_excludes_sensitive_poll_token(self) -> None:
        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Queued.",
            retry_allowed=True,
        )

        job_dict = job.to_dict()

        self.assertNotIn("job_poll_token", job_dict)
        self.assertIn("job_id", job_dict)
        self.assertIn("status", job_dict)
        self.assertIn("session_id", job_dict)

    def test_concurrent_job_creation_produces_unique_ids(self) -> None:
        store = InMemoryJobStore()
        ready = threading.Barrier(8)
        created_jobs: list[object] = []
        errors: list[BaseException] = []
        write_lock = threading.Lock()

        def create_job() -> None:
            try:
                ready.wait()
                job = store.create_job(
                    session_id="chat_s_20260314_0001",
                    broker_id="broker-123",
                    office_id="memphis",
                    progress_message="Concurrent job.",
                    retry_allowed=True,
                )
                with write_lock:
                    created_jobs.append(job)
            except BaseException as exc:
                with write_lock:
                    errors.append(exc)

        threads = [threading.Thread(target=create_job) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(created_jobs), 8)

        job_ids = [job.job_id for job in created_jobs]
        self.assertEqual(len(set(job_ids)), 8)

    def test_concurrent_job_start_is_serialized_by_lock(self) -> None:
        store = InMemoryJobStore()
        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Queued.",
            retry_allowed=True,
        )

        results: list[object] = []
        errors: list[BaseException] = []

        def start_job() -> None:
            try:
                result = store.start_job(job.job_id, progress_message="Running")
                results.append(result)
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=start_job) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 4)

        running_count = sum(1 for r in results if r is not None and r.status == "running")
        self.assertEqual(running_count, 4)

    def test_job_route_returns_404_for_invalid_poll_token(self) -> None:
        client = TestClient(create_app())

        response = client.get(
            "/jobs/job_20260314_000000",
            params=self._job_query(job_poll_token="invalid_token"),
        )
        self.assertEqual(response.status_code, 404)

    def test_job_route_returns_404_for_unknown_job_id(self) -> None:
        client = TestClient(create_app())

        response = client.get(
            "/jobs/job_unknown",
            params=self._job_query(job_poll_token="some_token"),
        )
        self.assertEqual(response.status_code, 404)

    def test_job_poll_token_is_cryptographically_random(self) -> None:
        store = InMemoryJobStore()

        tokens = set()
        for _ in range(100):
            job = store.create_job(
                session_id="chat_s_20260314_0001",
                broker_id="broker-123",
                office_id="memphis",
                progress_message="Queued.",
                retry_allowed=True,
            )
            assert job.job_poll_token is not None
            tokens.add(job.job_poll_token)

        self.assertEqual(len(tokens), 100)

    def test_job_completed_at_timestamp_set_on_completion(self) -> None:
        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Queued.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")
        store.complete_job(
            job.job_id,
            result=self._prepared_result(session_id=job.session_id, job_id=job.job_id),
            progress_message="Completed.",
        )

        row = execute_query(
            store._connection,
            "SELECT completed_at FROM generation_jobs WHERE job_id = ?",
            (job.job_id,),
        ).fetchone()

        self.assertIsNotNone(row)
        assert row is not None
        self.assertIsNotNone(row["completed_at"])

    def test_session_store_reset_clears_all_sessions(self) -> None:
        store = InMemorySessionStore()

        store.save_session(
            store.get_session(store.next_session_id()) or type('obj', (object,), {'session_id': 's1', 'session_access_token': 't1', 'broker_id': 'b1', 'office_id': 'o1', 'role': 'broker', 'current_module': 'm', 'conversation_scope': 'global', 'context_binding_state': 'bound', 'screen_sync_state': 'not_applicable', 'active_resource': None, 'last_response_id': None, 'last_job_id': None})()
        )

        store.reset()

        rows = execute_query(
            store._connection,
            "SELECT COUNT(*) as count FROM chat_sessions",
        ).fetchone()

        assert rows is not None
        self.assertEqual(rows["count"], 0)

    def test_job_fail_transitions_from_running_to_failed(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh pending.",
            retry_allowed=True,
        )

        running = store.start_job(job.job_id, progress_message="Running")
        self.assertIsNotNone(running)
        assert running is not None
        self.assertEqual(running.status, JobStatus.RUNNING)

        failed = store.fail_job(
            job.job_id,
            error_message="Connection timeout",
            progress_message="Background refresh failed due to timeout.",
        )

        self.assertIsNotNone(failed)
        assert failed is not None
        self.assertEqual(failed.status, JobStatus.FAILED)
        self.assertEqual(failed.error_message, "Connection timeout")
        self.assertIsNotNone(failed.failed_at)

    def test_job_fail_from_pending_transitions_to_failed(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh pending.",
            retry_allowed=True,
        )

        failed = store.fail_job(
            job.job_id,
            error_message="Job rejected",
            progress_message="Job rejected before start.",
        )

        self.assertIsNotNone(failed)
        assert failed is not None
        self.assertEqual(failed.status, JobStatus.FAILED)
        self.assertEqual(failed.error_message, "Job rejected")

    def test_job_fail_from_running_transitions_to_failed(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh pending.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")

        failed = store.fail_job(
            job.job_id,
            error_message="Processing failed",
            progress_message="Job failed during processing.",
        )

        self.assertIsNotNone(failed)
        assert failed is not None
        self.assertEqual(failed.status, JobStatus.FAILED)
        self.assertEqual(failed.error_message, "Processing failed")

    def test_job_fail_returns_job_unchanged_for_terminal_status(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh pending.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")
        completed = store.complete_job(
            job.job_id,
            result=self._prepared_result(session_id=job.session_id, job_id=job.job_id),
            progress_message="Completed.",
        )

        failed = store.fail_job(
            job.job_id,
            error_message="Should not fail",
        )

        self.assertEqual(failed.status, JobStatus.SUCCEEDED)
        self.assertIsNone(failed.error_message)

    def test_job_cancel_transitions_from_pending_to_cancelled(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh pending.",
            retry_allowed=True,
        )

        cancelled = store.cancel_job(
            job.job_id,
            progress_message="Job cancelled by user request.",
        )

        self.assertIsNotNone(cancelled)
        assert cancelled is not None
        self.assertEqual(cancelled.status, JobStatus.CANCELLED)

    def test_job_cancel_transitions_from_running_to_cancelled(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh pending.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")

        cancelled = store.cancel_job(
            job.job_id,
            progress_message="Job cancelled during execution.",
        )

        self.assertIsNotNone(cancelled)
        assert cancelled is not None
        self.assertEqual(cancelled.status, JobStatus.CANCELLED)

    def test_job_cancel_returns_job_unchanged_for_terminal_status(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh pending.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")
        completed = store.complete_job(
            job.job_id,
            result=self._prepared_result(session_id=job.session_id, job_id=job.job_id),
            progress_message="Completed.",
        )

        cancelled = store.cancel_job(job.job_id)

        self.assertEqual(cancelled.status, JobStatus.SUCCEEDED)

    def test_job_expire_transitions_from_pending_to_expired(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh pending.",
            retry_allowed=True,
        )

        expired = store.expire_job(
            job.job_id,
            progress_message="Job expired due to timeout.",
        )

        self.assertIsNotNone(expired)
        assert expired is not None
        self.assertEqual(expired.status, JobStatus.EXPIRED)
        self.assertEqual(expired.error_message, "Job exceeded maximum execution time.")

    def test_job_expire_transitions_from_running_to_expired(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh pending.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")

        expired = store.expire_job(
            job.job_id,
            progress_message="Job exceeded execution time limit.",
        )

        self.assertIsNotNone(expired)
        assert expired is not None
        self.assertEqual(expired.status, JobStatus.EXPIRED)

    def test_job_expire_returns_job_unchanged_for_terminal_status(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Background refresh pending.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")
        completed = store.complete_job(
            job.job_id,
            result=self._prepared_result(session_id=job.session_id, job_id=job.job_id),
            progress_message="Completed.",
        )

        expired = store.expire_job(job.job_id)

        self.assertEqual(expired.status, JobStatus.SUCCEEDED)

    def test_job_fail_returns_none_for_unknown_job_id(self) -> None:
        store = InMemoryJobStore()

        result = store.fail_job(
            "unknown_job_id",
            error_message="Test error",
        )

        self.assertIsNone(result)

    def test_job_cancel_returns_none_for_unknown_job_id(self) -> None:
        store = InMemoryJobStore()

        result = store.cancel_job("unknown_job_id")

        self.assertIsNone(result)

    def test_job_expire_returns_none_for_unknown_job_id(self) -> None:
        store = InMemoryJobStore()

        result = store.expire_job("unknown_job_id")

        self.assertIsNone(result)

    def test_is_terminal_status_identifies_terminal_states(self) -> None:
        self.assertTrue(is_terminal_status(JobStatus.SUCCEEDED))
        self.assertTrue(is_terminal_status(JobStatus.FAILED))
        self.assertTrue(is_terminal_status(JobStatus.CANCELLED))
        self.assertTrue(is_terminal_status(JobStatus.EXPIRED))

        self.assertFalse(is_terminal_status(JobStatus.PENDING))
        self.assertFalse(is_terminal_status(JobStatus.RUNNING))

    def test_is_terminal_status_accepts_string_values(self) -> None:
        self.assertTrue(is_terminal_status("succeeded"))
        self.assertTrue(is_terminal_status("failed"))
        self.assertTrue(is_terminal_status("cancelled"))
        self.assertTrue(is_terminal_status("expired"))

        self.assertFalse(is_terminal_status("pending"))
        self.assertFalse(is_terminal_status("running"))

    def test_job_state_can_transition_to_validates_transitions(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        pending_job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Pending job.",
            retry_allowed=True,
        )

        self.assertTrue(pending_job.can_transition_to(JobStatus.RUNNING))
        self.assertTrue(pending_job.can_transition_to(JobStatus.CANCELLED))
        self.assertTrue(pending_job.can_transition_to(JobStatus.EXPIRED))
        self.assertTrue(pending_job.can_transition_to(JobStatus.FAILED))
        self.assertFalse(pending_job.can_transition_to(JobStatus.SUCCEEDED))

        running_job = store.start_job(pending_job.job_id, progress_message="Running")
        assert running_job is not None

        self.assertTrue(running_job.can_transition_to(JobStatus.SUCCEEDED))
        self.assertTrue(running_job.can_transition_to(JobStatus.FAILED))
        self.assertTrue(running_job.can_transition_to(JobStatus.CANCELLED))
        self.assertTrue(running_job.can_transition_to(JobStatus.EXPIRED))
        self.assertFalse(running_job.can_transition_to(JobStatus.PENDING))
        self.assertFalse(running_job.can_transition_to(JobStatus.RUNNING))

    def test_job_state_is_terminal_identifies_terminal_states(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Pending job.",
            retry_allowed=True,
        )

        self.assertFalse(job.is_terminal())
        self.assertTrue(job.is_transient())

        running = store.start_job(job.job_id, progress_message="Running")
        assert running is not None

        self.assertFalse(running.is_terminal())
        self.assertTrue(running.is_transient())

        completed = store.complete_job(
            job.job_id,
            result=self._prepared_result(session_id=job.session_id, job_id=job.job_id),
            progress_message="Completed.",
        )
        assert completed is not None

        self.assertTrue(completed.is_terminal())
        self.assertFalse(completed.is_transient())

    def test_job_state_status_literal_returns_string_value(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Pending job.",
            retry_allowed=True,
        )

        self.assertEqual(job.status_literal, "pending")

        running = store.start_job(job.job_id, progress_message="Running")
        assert running is not None

        self.assertEqual(running.status_literal, "running")

    def test_job_to_dict_includes_error_message_for_failed_jobs(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Pending job.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")

        failed = store.fail_job(
            job.job_id,
            error_message="Connection failed",
            progress_message="Job failed.",
        )
        assert failed is not None

        job_dict = failed.to_dict()

        self.assertIn("error_message", job_dict)
        self.assertEqual(job_dict["error_message"], "Connection failed")

    def test_job_to_dict_includes_result_for_succeeded_jobs(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Pending job.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")
        result = self._prepared_result(session_id=job.session_id, job_id=job.job_id)
        completed = store.complete_job(
            job.job_id,
            result=result,
            progress_message="Completed.",
        )
        assert completed is not None

        job_dict = completed.to_dict()

        self.assertIn("result", job_dict)
        self.assertIn("completed_response_id", job_dict)
        self.assertEqual(job_dict["completed_response_id"], "resp_test_complete")

    def test_job_to_dict_excludes_empty_optional_fields(self) -> None:
        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Pending job.",
            retry_allowed=True,
        )

        job_dict = job.to_dict()

        self.assertNotIn("completed_response_id", job_dict)
        self.assertNotIn("result", job_dict)
        self.assertNotIn("error_message", job_dict)

    def test_concurrent_job_operations_are_thread_safe(self) -> None:
        from backend.app.jobs.models import JobStatus
        import time

        store = InMemoryJobStore()
        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Pending job.",
            retry_allowed=True,
        )

        results: list[object] = []
        errors: list[BaseException] = []

        def mixed_operations() -> None:
            try:
                time.sleep(0.001)
                result = store.start_job(job.job_id, progress_message="Running")
                results.append(result)
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=mixed_operations) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 8)

    def test_job_complete_ignores_already_completed_jobs(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Pending job.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")
        first_complete = store.complete_job(
            job.job_id,
            result=self._prepared_result(session_id=job.session_id, job_id=job.job_id),
            progress_message="Completed.",
        )
        assert first_complete is not None

        second_complete = store.complete_job(
            job.job_id,
            result={"response_id": "resp_second", "status": "success"},
            progress_message="Second completion.",
        )

        self.assertEqual(second_complete.status, JobStatus.SUCCEEDED)
        self.assertEqual(second_complete.completed_response_id, "resp_test_complete")

    def test_multiple_jobs_can_be_tracked_per_session(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore()
        session_id = "chat_s_20260314_0001"

        job1 = store.create_job(
            session_id=session_id,
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Job 1 pending.",
            retry_allowed=True,
        )
        job2 = store.create_job(
            session_id=session_id,
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Job 2 pending.",
            retry_allowed=True,
        )

        store.start_job(job1.job_id, progress_message="Job 1 running")
        store.complete_job(
            job1.job_id,
            result=self._prepared_result(session_id=session_id, job_id=job1.job_id),
            progress_message="Job 1 completed.",
        )

        job2_state = store.get_job(job2.job_id)
        assert job2_state is not None

        self.assertEqual(job1.session_id, session_id)
        self.assertEqual(job2.session_id, session_id)
        self.assertEqual(job2_state.status, JobStatus.PENDING)

    def test_job_with_prepared_result_materializes_immediately_with_zero_refresh_polls(self) -> None:
        from backend.app.jobs.models import JobStatus

        store = InMemoryJobStore(completion_refresh_polls=0)

        job = store.create_job(
            session_id="chat_s_20260314_0001",
            broker_id="broker-123",
            office_id="memphis",
            progress_message="Pending job.",
            retry_allowed=True,
        )

        store.start_job(job.job_id, progress_message="Running")

        result = self._prepared_result(session_id=job.session_id, job_id=job.job_id)
        store.prepare_result(job.job_id, result)

        materialized = store.materialize_job(job.job_id)

        self.assertIsNotNone(materialized)
        assert materialized is not None
        self.assertEqual(materialized.status, JobStatus.SUCCEEDED)
        self.assertEqual(materialized.completed_response_id, "resp_test_complete")


if __name__ == "__main__":
    unittest.main()
