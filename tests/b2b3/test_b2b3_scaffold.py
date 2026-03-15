from __future__ import annotations

import inspect
import json
import threading
import unittest
from unittest import mock
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.db.read_repository import ReadRepository, build_seeded_read_connection
from backend.app.gateway import booking_actions
from backend.app.gateway import write_gateway
from backend.app.main import create_app
from backend.app.orchestrator import graph
from backend.app.responses import builder
from backend.app.tools import registry as registry_module
from backend.app.tools.read_executor import execute_allowlisted_read


ROOT_DIR = Path(__file__).resolve().parents[2]
RESPONSE_CONTRACT = ROOT_DIR / "contracts" / "agent-response-schema.json"


class B2B3ScaffoldTests(unittest.TestCase):
    def _session_query(self, *, session_access_token: str) -> dict[str, str]:
        return {"session_access_token": session_access_token}

    def _job_query(self, *, job_poll_token: str) -> dict[str, str]:
        return {"job_poll_token": job_poll_token}

    def _make_read_bundle(self) -> dict[str, object]:
        return {
            "office": {
                "office_id": "memphis",
                "office_name": "Memphis Brokerage",
                "deployment_scope": "memphis_only",
            },
            "brokers": [
                {
                    "broker_id": "broker-123",
                    "office_id": "memphis",
                    "display_name": "Maya Brooks",
                    "role": "broker",
                }
            ],
            "carriers": [
                {
                    "carrier_id": "carrier-4412",
                    "carrier_name": "Acme Freight",
                    "shipment_mode": "FTL",
                    "on_time_rate": 97.2,
                    "insurance_expiry_date": "2026-04-10",
                },
                {
                    "carrier_id": "carrier-7721",
                    "carrier_name": "RiverSouth",
                    "shipment_mode": "FTL",
                    "on_time_rate": 88.4,
                    "insurance_expiry_date": "2026-06-15",
                },
            ],
            "shipment_quotes": [
                {
                    "quote_id": "quote-88219",
                    "office_id": "memphis",
                    "broker_id": "broker-123",
                    "carrier_id": "carrier-4412",
                    "origin_region": "Dallas",
                    "destination_region": "Chicago",
                    "shipment_mode": "FTL",
                    "weight_class": "20000_plus",
                    "pickup_date": "2026-03-17",
                    "quote_status": "eligible_for_booking",
                },
                {
                    "quote_id": "quote-99117",
                    "office_id": "memphis",
                    "broker_id": "broker-123",
                    "carrier_id": "carrier-7721",
                    "origin_region": "Dallas",
                    "destination_region": "Chicago",
                    "shipment_mode": "FTL",
                    "weight_class": "20000_plus",
                    "pickup_date": "2025-10-10",
                    "quote_status": "eligible_for_booking",
                },
                {
                    "quote_id": "quote-55100",
                    "office_id": "memphis",
                    "broker_id": "broker-123",
                    "carrier_id": "carrier-7721",
                    "origin_region": "Atlanta",
                    "destination_region": "Miami",
                    "shipment_mode": "FTL",
                    "weight_class": "20000_plus",
                    "pickup_date": "2026-03-12",
                    "quote_status": "eligible_for_booking",
                },
            ],
            "shipments": [
                {
                    "shipment_id": "ship-100",
                    "office_id": "memphis",
                    "broker_id": "broker-123",
                    "carrier_id": "carrier-4412",
                    "quote_id": "quote-88219",
                    "origin_region": "Dallas",
                    "destination_region": "Chicago",
                    "shipment_mode": "FTL",
                    "shipment_status": "in_transit",
                    "exception_type": "insurance_expiring",
                    "transit_hours": 36,
                    "eta_at": "2026-03-18T17:00:00Z",
                    "created_at": "2026-03-13T12:00:00Z",
                },
                {
                    "shipment_id": "ship-200",
                    "office_id": "memphis",
                    "broker_id": "broker-123",
                    "carrier_id": "carrier-7721",
                    "quote_id": "quote-99117",
                    "origin_region": "Dallas",
                    "destination_region": "Chicago",
                    "shipment_mode": "FTL",
                    "shipment_status": "delivered",
                    "exception_type": None,
                    "transit_hours": 96,
                    "eta_at": "2025-10-12T10:00:00Z",
                    "created_at": "2025-10-09T12:00:00Z",
                },
                {
                    "shipment_id": "ship-300",
                    "office_id": "memphis",
                    "broker_id": "broker-123",
                    "carrier_id": "carrier-7721",
                    "quote_id": "quote-55100",
                    "origin_region": "Atlanta",
                    "destination_region": "Miami",
                    "shipment_mode": "FTL",
                    "shipment_status": "in_transit",
                    "exception_type": "delay",
                    "transit_hours": 48,
                    "eta_at": "2026-03-19T09:00:00Z",
                    "created_at": "2026-03-12T09:00:00Z",
                },
            ],
            "shipment_events": [
                {
                    "shipment_id": "ship-100",
                    "office_id": "memphis",
                    "event_type": "departed_origin",
                    "event_at": "2026-03-14T08:00:00Z",
                    "event_summary": "Departed Dallas terminal",
                }
            ],
            "booking_confirmations": [],
        }

    def _make_chat_request(
        self,
        *,
        prompt: str,
        session_id: str | None = None,
        session_access_token: str | None = None,
        resource_id: str | None = None,
        resource_fingerprint: str | None = None,
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
                "resource_fingerprint": resource_fingerprint or f"shipment:{resource_id}:v1",
            }
        return request

    def test_tool_registry_exposes_typed_tool_access(self) -> None:
        registry = registry_module.load_tool_registry()

        self.assertTrue(hasattr(registry_module, "ToolRegistry"))
        self.assertIsInstance(registry, registry_module.ToolRegistry)
        self.assertTrue(hasattr(registry, "get_tool"))

        shipment_metrics_tool = registry.get_tool("shipment_metrics_lookup")
        self.assertEqual(shipment_metrics_tool["mode"], "read")

    def test_orchestrator_graph_exposes_read_and_write_paths(self) -> None:
        try:
            orchestration_graph = graph.build_orchestrator_graph()
        except NotImplementedError as exc:
            self.fail(f"build_orchestrator_graph not implemented: {exc}")

        self.assertIsInstance(orchestration_graph, dict)
        self.assertIn("read_path", orchestration_graph)
        self.assertIn("write_path", orchestration_graph)
        self.assertEqual(orchestration_graph["read_path"]["tool_families"], ["read_tools"])
        self.assertNotIn("write_tools", orchestration_graph["read_path"]["tool_families"])
        self.assertNotIn(
            "pre_confirmation_tools",
            orchestration_graph["read_path"]["tool_families"],
        )

    def test_orchestrator_write_path_executes_confirmed_booking(self) -> None:
        bundle = self._make_read_bundle()
        bundle["booking_confirmations"] = [
            {
                "confirmation_token": "confirm-quote-88219",
                "quote_id": "quote-88219",
                "office_id": "memphis",
                "broker_id": "broker-123",
                "carrier_id": "carrier-4412",
                "pickup_date": "2026-03-17",
                "confirmation_status": "pending",
                "expires_at": "2099-03-16T12:00:00Z",
            }
        ]
        repository = ReadRepository(connection=build_seeded_read_connection(bundle))
        result = graph.execute_write_path(
            confirmation_token="confirm-quote-88219",
            idempotency_key="book-quote-88219-carrier-4412-pickup-2026-03-17-v1",
            broker_id="broker-123",
            office_id="memphis",
            role="broker",
            repository=repository,
            idempotency_store={},
        )

        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["audit"]["tool_path"], ["booking_create_confirmed"])

    def test_write_gateway_requires_permission_context_and_confirmation_boundary(self) -> None:
        parameters = inspect.signature(write_gateway.execute_write_gateway).parameters

        self.assertEqual(
            list(parameters),
            ["request", "permission_context"],
        )

        request = write_gateway.WriteGatewayRequest(
            action_name="booking_create_confirmed",
            confirmation_token="token-123",
            idempotency_key="book-quote-88219-carrier-4412-pickup-2026-03-14-v1",
            actor_broker_id="broker-123",
            office_id="memphis",
        )
        permission_context = {
            "claims": {
                "broker_id": "broker-123",
                "office_id": "memphis",
                "role": "broker",
            }
        }

        result = write_gateway.execute_write_gateway(request, permission_context)
        self.assertIn("audit", result)
        self.assertEqual(result["audit"]["tool_path"], ["booking_create_confirmed"])

        with self.assertRaisesRegex(ValueError, "unsupported action"):
            write_gateway.execute_write_gateway(
                write_gateway.WriteGatewayRequest(
                    action_name="booking_create_prepare",
                    confirmation_token="token-123",
                    idempotency_key="book-quote-88219-carrier-4412-pickup-2026-03-14-v1",
                    actor_broker_id="broker-123",
                    office_id="memphis",
                ),
                permission_context,
            )

        with self.assertRaisesRegex(ValueError, "broker role"):
            write_gateway.execute_write_gateway(
                request,
                {
                    "claims": {
                        "broker_id": "broker-123",
                        "office_id": "memphis",
                        "role": "office_manager",
                    }
                },
            )

        with self.assertRaisesRegex(ValueError, "idempotency key"):
            write_gateway.execute_write_gateway(
                write_gateway.WriteGatewayRequest(
                    action_name="booking_create_confirmed",
                    confirmation_token="token-123",
                    idempotency_key="",
                    actor_broker_id="broker-123",
                    office_id="memphis",
                ),
                permission_context,
            )

    def test_write_gateway_persists_outcome_and_replays_by_idempotency_key(self) -> None:
        bundle = self._make_read_bundle()
        bundle["booking_confirmations"] = [
            {
                "confirmation_token": "confirm-quote-88219",
                "quote_id": "quote-88219",
                "office_id": "memphis",
                "broker_id": "broker-123",
                "carrier_id": "carrier-4412",
                "pickup_date": "2026-03-17",
                "confirmation_status": "pending",
                "expires_at": "2099-03-16T12:00:00Z",
            }
        ]
        repository = ReadRepository(connection=build_seeded_read_connection(bundle))
        permission_context = {
            "claims": {
                "broker_id": "broker-123",
                "office_id": "memphis",
                "role": "broker",
            },
            "repository": repository,
            "idempotency_store": {},
        }
        request = write_gateway.WriteGatewayRequest(
            action_name="booking_create_confirmed",
            confirmation_token="confirm-quote-88219",
            idempotency_key="book-quote-88219-carrier-4412-pickup-2026-03-17-v1",
            actor_broker_id="broker-123",
            office_id="memphis",
        )

        result = write_gateway.execute_write_gateway(request, permission_context)
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["confirmation_token"], "confirm-quote-88219")
        self.assertEqual(result["quote_id"], "quote-88219")
        self.assertEqual(result["carrier_id"], "carrier-4412")
        self.assertEqual(result["pickup_date"], "2026-03-17")
        self.assertEqual(result["audit"]["outcome"], "submitted")
        self.assertEqual(result["audit"]["actor_broker_id"], "broker-123")
        self.assertEqual(result["audit"]["office_id"], "memphis")

        replay = write_gateway.execute_write_gateway(request, permission_context)
        self.assertEqual(replay, result)

        quote_row = repository.connection.execute(
            "SELECT quote_status FROM shipment_quotes WHERE quote_id = ?",
            ("quote-88219",),
        ).fetchone()
        self.assertEqual(quote_row["quote_status"], "booked")

        confirmation_row = repository.connection.execute(
            "SELECT confirmation_status FROM booking_confirmations WHERE confirmation_token = ?",
            ("confirm-quote-88219",),
        ).fetchone()
        self.assertEqual(confirmation_row["confirmation_status"], "consumed")

    def test_write_gateway_denies_stale_or_conflicting_submissions_deterministically(self) -> None:
        bundle = self._make_read_bundle()
        bundle["booking_confirmations"] = [
            {
                "confirmation_token": "confirm-quote-88219",
                "quote_id": "quote-88219",
                "office_id": "memphis",
                "broker_id": "broker-123",
                "carrier_id": "carrier-4412",
                "pickup_date": "2026-03-17",
                "confirmation_status": "pending",
                "expires_at": "2099-03-16T12:00:00Z",
            },
            {
                "confirmation_token": "confirm-quote-55100",
                "quote_id": "quote-55100",
                "office_id": "memphis",
                "broker_id": "broker-123",
                "carrier_id": "carrier-7721",
                "pickup_date": "2026-03-12",
                "confirmation_status": "pending",
                "expires_at": "2099-03-16T12:00:00Z",
            },
        ]
        repository = ReadRepository(connection=build_seeded_read_connection(bundle))
        permission_context = {
            "claims": {
                "broker_id": "broker-123",
                "office_id": "memphis",
                "role": "broker",
            },
            "repository": repository,
            "idempotency_store": {},
        }

        first = write_gateway.execute_write_gateway(
            write_gateway.WriteGatewayRequest(
                action_name="booking_create_confirmed",
                confirmation_token="confirm-quote-88219",
                idempotency_key="book-quote-88219-carrier-4412-pickup-2026-03-17-v1",
                actor_broker_id="broker-123",
                office_id="memphis",
            ),
            permission_context,
        )
        self.assertEqual(first["status"], "submitted")

        stale = write_gateway.execute_write_gateway(
            write_gateway.WriteGatewayRequest(
                action_name="booking_create_confirmed",
                confirmation_token="confirm-quote-88219",
                idempotency_key="book-quote-88219-carrier-4412-pickup-2026-03-17-v2",
                actor_broker_id="broker-123",
                office_id="memphis",
            ),
            permission_context,
        )
        self.assertEqual(stale["status"], "denied")
        self.assertEqual(stale["confirmation_token"], "confirm-quote-88219")
        self.assertEqual(stale["denial_reason_class"], "stale_state")

        stale_replay = write_gateway.execute_write_gateway(
            write_gateway.WriteGatewayRequest(
                action_name="booking_create_confirmed",
                confirmation_token="confirm-quote-88219",
                idempotency_key="book-quote-88219-carrier-4412-pickup-2026-03-17-v2",
                actor_broker_id="broker-123",
                office_id="memphis",
            ),
            permission_context,
        )
        self.assertEqual(stale_replay, stale)

        conflict = write_gateway.execute_write_gateway(
            write_gateway.WriteGatewayRequest(
                action_name="booking_create_confirmed",
                confirmation_token="confirm-quote-55100",
                idempotency_key="book-quote-88219-carrier-4412-pickup-2026-03-17-v1",
                actor_broker_id="broker-123",
                office_id="memphis",
            ),
            permission_context,
        )
        self.assertEqual(conflict["status"], "denied")
        self.assertEqual(conflict["denial_reason_class"], "idempotency_conflict")

        conflict_replay = write_gateway.execute_write_gateway(
            write_gateway.WriteGatewayRequest(
                action_name="booking_create_confirmed",
                confirmation_token="confirm-quote-55100",
                idempotency_key="book-quote-88219-carrier-4412-pickup-2026-03-17-v1",
                actor_broker_id="broker-123",
                office_id="memphis",
            ),
            permission_context,
        )
        self.assertEqual(conflict_replay, conflict)

    def test_write_gateway_serializes_concurrent_same_key_replays(self) -> None:
        bundle = self._make_read_bundle()
        bundle["booking_confirmations"] = [
            {
                "confirmation_token": "confirm-quote-88219",
                "quote_id": "quote-88219",
                "office_id": "memphis",
                "broker_id": "broker-123",
                "carrier_id": "carrier-4412",
                "pickup_date": "2026-03-17",
                "confirmation_status": "pending",
                "expires_at": "2099-03-16T12:00:00Z",
            }
        ]
        repository = ReadRepository(connection=build_seeded_read_connection(bundle))
        permission_context = {
            "claims": {
                "broker_id": "broker-123",
                "office_id": "memphis",
                "role": "broker",
            },
            "repository": repository,
            "idempotency_store": {},
        }
        request = write_gateway.WriteGatewayRequest(
            action_name="booking_create_confirmed",
            confirmation_token="confirm-quote-88219",
            idempotency_key="book-quote-88219-carrier-4412-pickup-2026-03-17-v1",
            actor_broker_id="broker-123",
            office_id="memphis",
        )
        load_barrier = threading.Barrier(2)
        submitted_lock = threading.Lock()
        submitted_count = 0
        results: list[dict[str, object] | None] = [None, None]
        errors: list[BaseException] = []

        original_claim_record = booking_actions.claim_record
        original_submitted_result = booking_actions._submitted_result

        def synchronized_claim_record(*args: object, **kwargs: object) -> object:
            try:
                load_barrier.wait(timeout=2)
            except threading.BrokenBarrierError as exc:
                raise AssertionError("concurrent idempotency race test did not synchronize") from exc
            return original_claim_record(*args, **kwargs)

        def counted_submitted_result(**kwargs: object) -> dict[str, object]:
            nonlocal submitted_count
            with submitted_lock:
                submitted_count += 1
            return original_submitted_result(**kwargs)

        def invoke(index: int) -> None:
            try:
                results[index] = write_gateway.execute_write_gateway(request, permission_context)
            except BaseException as exc:
                errors.append(exc)

        with (
            mock.patch(
                "backend.app.gateway.booking_actions.claim_record",
                side_effect=synchronized_claim_record,
            ),
            mock.patch(
                "backend.app.gateway.booking_actions._submitted_result",
                side_effect=counted_submitted_result,
            ),
        ):
            first = threading.Thread(target=invoke, args=(0,))
            second = threading.Thread(target=invoke, args=(1,))
            first.start()
            second.start()
            first.join()
            second.join()

        self.assertEqual(errors, [])
        self.assertEqual(submitted_count, 1)
        self.assertIsNotNone(results[0])
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0]["status"], "submitted")

    def test_write_gateway_prevents_concurrent_double_submit_for_same_confirmation_token(self) -> None:
        bundle = self._make_read_bundle()
        bundle["booking_confirmations"] = [
            {
                "confirmation_token": "confirm-quote-88219",
                "quote_id": "quote-88219",
                "office_id": "memphis",
                "broker_id": "broker-123",
                "carrier_id": "carrier-4412",
                "pickup_date": "2026-03-17",
                "confirmation_status": "pending",
                "expires_at": "2099-03-16T12:00:00Z",
            }
        ]
        repository = ReadRepository(connection=build_seeded_read_connection(bundle))
        before_submit_release = threading.Event()
        before_submit_count_lock = threading.Lock()
        before_submit_count = 0
        first_submit_entered = threading.Event()
        permission_context = {
            "claims": {
                "broker_id": "broker-123",
                "office_id": "memphis",
                "role": "broker",
            },
            "repository": repository,
            "idempotency_store": {},
        }

        def before_submit_hook() -> None:
            nonlocal before_submit_count
            with before_submit_count_lock:
                before_submit_count += 1
                current_count = before_submit_count
            if current_count == 1:
                first_submit_entered.set()
            before_submit_release.wait(timeout=1)

        permission_context["before_submit_hook"] = before_submit_hook
        first_request = write_gateway.WriteGatewayRequest(
            action_name="booking_create_confirmed",
            confirmation_token="confirm-quote-88219",
            idempotency_key="book-quote-88219-carrier-4412-pickup-2026-03-17-v1",
            actor_broker_id="broker-123",
            office_id="memphis",
        )
        second_request = write_gateway.WriteGatewayRequest(
            action_name="booking_create_confirmed",
            confirmation_token="confirm-quote-88219",
            idempotency_key="book-quote-88219-carrier-4412-pickup-2026-03-17-v2",
            actor_broker_id="broker-123",
            office_id="memphis",
        )
        results: list[dict[str, object] | None] = [None, None]
        errors: list[BaseException] = []

        def invoke(index: int, request: write_gateway.WriteGatewayRequest) -> None:
            try:
                results[index] = write_gateway.execute_write_gateway(request, permission_context)
            except BaseException as exc:
                errors.append(exc)

        first = threading.Thread(target=invoke, args=(0, first_request))
        second = threading.Thread(target=invoke, args=(1, second_request))
        first.start()
        self.assertTrue(first_submit_entered.wait(timeout=1))
        second.start()
        with before_submit_count_lock:
            self.assertEqual(before_submit_count, 1)
        before_submit_release.set()
        first.join()
        second.join()

        self.assertEqual(errors, [])
        self.assertIsNotNone(results[0])
        self.assertIsNotNone(results[1])
        statuses = sorted([results[0]["status"], results[1]["status"]])
        self.assertEqual(statuses, ["denied", "submitted"])
        denied = results[0] if results[0]["status"] == "denied" else results[1]
        submitted = results[0] if results[0]["status"] == "submitted" else results[1]
        self.assertEqual(denied["denial_reason_class"], "stale_state")
        self.assertEqual(submitted["quote_id"], "quote-88219")

        quote_row = repository.connection.execute(
            "SELECT quote_status FROM shipment_quotes WHERE quote_id = ?",
            ("quote-88219",),
        ).fetchone()
        self.assertEqual(quote_row["quote_status"], "booked")

    def test_response_builder_emits_schema_valid_envelopes(self) -> None:
        contract = json.loads(RESPONSE_CONTRACT.read_text())

        self.assertTrue(hasattr(builder, "build_response_envelope"))
        parameters = inspect.signature(builder.build_response_envelope).parameters
        self.assertEqual(list(parameters), ["payload"])

        payload = builder.build_response_envelope(
            {
                "contract_version": contract["contract_version"],
                "response_id": "resp-red",
                "request_id": "req-red",
                "session_id": "chat_s_123",
                "conversation_scope": "shipment",
                "context_binding_state": "bound",
                "screen_sync_state": "not_applicable",
                "active_resource": {
                    "resource_type": "shipment",
                    "resource_id": "S-100",
                    "resource_fingerprint": "shipment:S-100:v1",
                },
                "intent_class": "read_result",
                "status": "success",
                "summary": "stub",
                "components": [],
                "policy": {
                    "permission_context_applied": True,
                    "sensitive_fields_redacted": True,
                    "write_confirmation_required": False,
                    "denial_reason_class": "none",
                },
                "audit": {
                    "actor_role": "broker",
                    "office_scope": "memphis",
                    "tool_path": ["shipment_metrics_lookup"],
                    "response_generated_at": "2026-03-13T22:00:00Z",
                },
            }
        )

        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["intent_class"], "read_result")
        self.assertEqual(payload["session_id"], "chat_s_123")
        self.assertEqual(payload["context_binding_state"], "bound")

        with self.assertRaisesRegex(ValueError, "schema validation failed"):
            builder.build_response_envelope(
                {
                    **payload,
                    "intent_class": "read_denied",
                    "status": "denied",
                    "actions": [
                        {
                            "action_id": "details-1",
                            "label": "Open details",
                            "action_type": "open_details",
                            "resource_type": "shipment",
                            "resource_id": "S-100",
                            "surface": "chat",
                            "requires_confirmation": False,
                            "enabled": True,
                            "disabled_reason": None,
                        }
                    ],
                }
            )

    def test_chat_route_creates_session_reuses_binding_and_flags_stale_resource_state(self) -> None:
        client = TestClient(create_app())

        first = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Show shipment 88219 details.",
                resource_id="88219",
            ),
        )
        self.assertEqual(first.status_code, 200)
        first_payload = first.json()
        self.assertEqual(first_payload["session_id"][:7], "chat_s_")
        self.assertEqual(first_payload["conversation_scope"], "shipment")
        self.assertEqual(first_payload["context_binding_state"], "bound")
        self.assertEqual(first_payload["active_resource"]["resource_id"], "88219")
        self.assertIsNone(first_payload["job_id"])

        session_id = first_payload["session_id"]
        session_access_token = first_payload["session_access_token"]

        second = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Keep the same shipment open.",
                session_id=session_id,
                session_access_token=session_access_token,
                resource_id="88219",
            ),
        )
        self.assertEqual(second.status_code, 200)
        second_payload = second.json()
        self.assertEqual(second_payload["session_id"], session_id)
        self.assertEqual(second_payload["context_binding_state"], "bound")
        session_access_token = second_payload["session_access_token"]

        carry_forward = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Keep the same shipment in focus.",
                session_id=session_id,
                session_access_token=session_access_token,
            ),
        )
        self.assertEqual(carry_forward.status_code, 200)
        carry_forward_payload = carry_forward.json()
        self.assertEqual(carry_forward_payload["session_id"], session_id)
        self.assertEqual(carry_forward_payload["context_binding_state"], "bound")
        self.assertEqual(carry_forward_payload["active_resource"]["resource_id"], "88219")

        session = client.get(
            f"/sessions/{session_id}",
            params=self._session_query(session_access_token=session_access_token),
        )
        self.assertEqual(session.status_code, 200)
        session_payload = session.json()
        self.assertEqual(session_payload["session_id"], session_id)
        self.assertEqual(session_payload["active_resource"]["resource_id"], "88219")
        self.assertEqual(session_payload["last_response_id"], carry_forward_payload["response_id"])
        self.assertIsNone(session_payload["last_job_id"])

        stale = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Switch to shipment 99117.",
                session_id=session_id,
                session_access_token=session_access_token,
                resource_id="99117",
            ),
        )
        self.assertEqual(stale.status_code, 200)
        stale_payload = stale.json()
        self.assertEqual(stale_payload["session_id"], session_id)
        self.assertEqual(stale_payload["context_binding_state"], "stale")
        self.assertEqual(stale_payload["active_resource"]["resource_id"], "99117")

    def test_chat_route_uses_trusted_server_identity_for_new_sessions(self) -> None:
        client = TestClient(create_app())

        response = client.post(
            "/chat",
            json={
                **self._make_chat_request(
                    prompt="Show shipment 88219 details.",
                    resource_id="88219",
                ),
                "broker_id": "broker-999",
                "office_id": "atlanta",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["audit"]["actor_role"], "broker")
        self.assertEqual(payload["audit"]["office_scope"], "memphis")

        session = client.get(
            f"/sessions/{payload['session_id']}",
            params=self._session_query(session_access_token=payload["session_access_token"]),
        )
        self.assertEqual(session.status_code, 200)
        session_payload = session.json()
        self.assertNotEqual(session_payload["broker_id"], "broker-999")
        self.assertEqual(session_payload["office_id"], "memphis")
        self.assertEqual(session_payload["role"], "broker")

    def test_chat_route_rejects_cross_broker_session_reuse_and_keeps_job_private(self) -> None:
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

        job_start = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Run a background analytics refresh for Memphis exceptions.",
                session_id=seed_payload["session_id"],
                session_access_token=session_access_token,
            ),
        )
        self.assertEqual(job_start.status_code, 200)
        job_payload = job_start.json()

        hijack = client.post(
            "/chat",
            json={
                **self._make_chat_request(
                    prompt="Resume someone else's session.",
                    session_id=seed_payload["session_id"],
                    session_access_token="session_invalid_token",
                ),
                "broker_id": "broker-999",
            },
        )
        self.assertEqual(hijack.status_code, 404)

        unauthorized_session = client.get(
            f"/sessions/{seed_payload['session_id']}",
            params=self._session_query(session_access_token="session_invalid_token"),
        )
        self.assertEqual(unauthorized_session.status_code, 404)

        authorized_session = client.get(
            f"/sessions/{seed_payload['session_id']}",
            params=self._session_query(session_access_token=session_access_token),
        )
        self.assertEqual(authorized_session.status_code, 200)

        unauthorized_job = client.get(
            f"/jobs/{job_payload['job_id']}",
            params=self._job_query(job_poll_token="jobpoll_invalid"),
        )
        self.assertEqual(unauthorized_job.status_code, 404)

    def test_chat_route_can_return_async_job_and_jobs_route_returns_status(self) -> None:
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
        session_access_token = payload["session_access_token"]
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(payload["job_id"][:6], "job_20")
        self.assertRegex(payload["job_poll_token"], r"^[A-Za-z0-9_-]{16,}$")
        self.assertEqual(payload["context_binding_state"], "bound")
        self.assertEqual(payload["active_resource"]["resource_id"], "88219")

        unauthorized = client.get(
            f"/jobs/{payload['job_id']}",
            params=self._job_query(job_poll_token="jobpoll_invalid"),
        )
        self.assertEqual(unauthorized.status_code, 404)

        first_job = client.get(
            f"/jobs/{payload['job_id']}",
            params=self._job_query(job_poll_token=payload["job_poll_token"]),
        )
        self.assertEqual(first_job.status_code, 200)
        first_job_payload = first_job.json()
        self.assertEqual(first_job_payload["job_id"], payload["job_id"])
        self.assertEqual(first_job_payload["session_id"], payload["session_id"])
        self.assertEqual(first_job_payload["status"], "running")
        self.assertEqual(first_job_payload["progress_message"], "Background refresh running for Memphis exceptions.")
        self.assertIsNone(first_job_payload["completed_response_id"])
        self.assertIsNone(first_job_payload["result"])

        second_job = client.get(
            f"/jobs/{payload['job_id']}",
            params=self._job_query(job_poll_token=payload["job_poll_token"]),
        )
        self.assertEqual(second_job.status_code, 200)
        second_job_payload = second_job.json()
        self.assertEqual(second_job_payload["status"], "running")
        self.assertIsNone(second_job_payload["completed_response_id"])
        self.assertIsNone(second_job_payload["result"])

        job = client.get(
            f"/jobs/{payload['job_id']}",
            params=self._job_query(job_poll_token=payload["job_poll_token"]),
        )
        self.assertEqual(job.status_code, 200)
        job_payload = job.json()
        self.assertEqual(job_payload["job_id"], payload["job_id"])
        self.assertEqual(job_payload["session_id"], payload["session_id"])
        self.assertEqual(job_payload["status"], "succeeded")
        self.assertRegex(job_payload["completed_response_id"], r"^resp_")
        self.assertEqual(job_payload["progress_message"], "No Memphis shipment exceptions matched the current scope.")
        self.assertIsInstance(job_payload["result"], dict)
        self.assertEqual(job_payload["result"]["session_id"], payload["session_id"])
        self.assertEqual(job_payload["result"]["status"], "success")
        self.assertEqual(job_payload["result"]["job_id"], payload["job_id"])
        self.assertEqual(job_payload["result"]["response_id"], job_payload["completed_response_id"])
        self.assertEqual(job_payload["result"]["summary"], "No Memphis shipment exceptions matched the current scope.")
        self.assertEqual(job_payload["result"]["audit"]["tool_path"], ["shipment_exception_lookup"])
        self.assertEqual(job_payload["result"]["components"][0]["component_type"], "message_block")

        session = client.get(
            f"/sessions/{payload['session_id']}",
            params=self._session_query(session_access_token=session_access_token),
        )
        self.assertEqual(session.status_code, 200)
        session_payload = session.json()
        self.assertEqual(session_payload["last_job_id"], payload["job_id"])
        self.assertEqual(session_payload["last_response_id"], job_payload["completed_response_id"])

        stale = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Switch to shipment 99117.",
                session_id=payload["session_id"],
                session_access_token=session_access_token,
                resource_id="99117",
            ),
        )
        self.assertEqual(stale.status_code, 200)
        stale_payload = stale.json()
        self.assertEqual(stale_payload["context_binding_state"], "stale")

        completed_again = client.get(
            f"/jobs/{payload['job_id']}",
            params=self._job_query(job_poll_token=payload["job_poll_token"]),
        )
        self.assertEqual(completed_again.status_code, 200)
        completed_again_payload = completed_again.json()
        self.assertEqual(completed_again_payload["status"], "succeeded")
        self.assertEqual(completed_again_payload["completed_response_id"], job_payload["completed_response_id"])
        self.assertEqual(completed_again_payload["result"]["response_id"], job_payload["completed_response_id"])

        latest_session = client.get(
            f"/sessions/{payload['session_id']}",
            params=self._session_query(session_access_token=session_access_token),
        )
        self.assertEqual(latest_session.status_code, 200)
        latest_session_payload = latest_session.json()
        self.assertEqual(latest_session_payload["last_response_id"], stale_payload["response_id"])

    def test_chat_route_keeps_shipment_refresh_prompt_on_sync_read_path(self) -> None:
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

        refresh = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Refresh shipment 88219.",
                session_id=seed_payload["session_id"],
                session_access_token=session_access_token,
            ),
        )
        self.assertEqual(refresh.status_code, 200)
        refresh_payload = refresh.json()
        self.assertEqual(refresh_payload["intent_class"], "read_result")
        self.assertEqual(refresh_payload["status"], "success")
        self.assertIsNone(refresh_payload["job_id"])
        self.assertEqual(refresh_payload["audit"]["tool_path"], ["shipment_exception_lookup"])
        self.assertEqual(refresh_payload["summary"], "No Memphis shipment exceptions matched the current scope.")

        missing_token = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Keep the same shipment open.",
                session_id=seed_payload["session_id"],
            ),
        )
        self.assertEqual(missing_token.status_code, 404)

    def test_chat_route_rejects_untrusted_or_incomplete_payloads(self) -> None:
        client = TestClient(create_app())

        response = client.post(
            "/chat",
            json={
                "prompt": "Show all Memphis shipments.",
                "broker_id": "broker-123",
                "office_id": "memphis",
            },
        )
        self.assertEqual(response.status_code, 422)

        missing_session_post = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Resume the missing session.",
                session_id="chat_s_missing",
            ),
        )
        self.assertEqual(missing_session_post.status_code, 404)

        missing_session = client.get(
            "/sessions/chat_s_missing",
            params=self._session_query(session_access_token="session_missing"),
        )
        self.assertEqual(missing_session.status_code, 404)

        missing_job = client.get(
            "/jobs/job_20260314_missing",
            params=self._job_query(job_poll_token="jobpoll_missing"),
        )
        self.assertEqual(missing_job.status_code, 404)

    def test_chat_route_executes_allowlisted_read_tools_with_db_backed_shapes(self) -> None:
        client = TestClient(create_app())

        metrics = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Average transit time for Memphis shipments over the last 90 days.",
            ),
        )
        self.assertEqual(metrics.status_code, 200)
        metrics_payload = metrics.json()
        self.assertEqual(metrics_payload["audit"]["tool_path"], ["shipment_metrics_lookup"])
        self.assertIn("metric_card", [component["component_type"] for component in metrics_payload["components"]])
        self.assertEqual(metrics_payload["components"][0]["metrics"][0]["value"], 1.5)

        ranking = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Top 1 carriers by on-time rate for FTL shipments over the last 30 days.",
            ),
        )
        self.assertEqual(ranking.status_code, 200)
        ranking_payload = ranking.json()
        self.assertEqual(ranking_payload["audit"]["tool_path"], ["carrier_ranking_lookup"])
        self.assertIn("table", [component["component_type"] for component in ranking_payload["components"]])
        self.assertEqual(ranking_payload["components"][0]["rows"][0][0], "Acme Freight")
        self.assertEqual(len(ranking_payload["components"][0]["rows"]), 1)

        exceptions = client.post(
            "/chat",
            json=self._make_chat_request(
                prompt="Show in-transit shipments with insurance expiring in the next 30 days.",
            ),
        )
        self.assertEqual(exceptions.status_code, 200)
        exceptions_payload = exceptions.json()
        self.assertEqual(exceptions_payload["audit"]["tool_path"], ["shipment_exception_lookup"])
        component_types = [component["component_type"] for component in exceptions_payload["components"]]
        self.assertIn("table", component_types)
        self.assertIn("timeline", component_types)
        self.assertEqual(exceptions_payload["components"][0]["rows"][0][0], "ship-100")
        self.assertEqual(len(exceptions_payload["components"][0]["rows"]), 1)

    def test_read_executor_honors_db_filters_for_metrics_ranking_and_exception_windows(self) -> None:
        repository = ReadRepository(connection=build_seeded_read_connection(self._make_read_bundle()))
        permission_context = {
            "broker_id": "broker-123",
            "office_id": "memphis",
            "role": "broker",
        }

        metrics = execute_allowlisted_read(
            prompt="Average transit time for FTL Dallas to Chicago over the last 90 days.",
            permission_context=permission_context,
            repository=repository,
        )
        self.assertEqual(metrics["components"][0]["metrics"][0]["value"], 1.5)
        self.assertEqual(metrics["components"][0]["metrics"][0]["label"], "Average transit time")

        shipment_count = execute_allowlisted_read(
            prompt="Shipment count for FTL Dallas to Chicago over the last 365 days.",
            permission_context=permission_context,
            repository=repository,
        )
        self.assertEqual(shipment_count["components"][0]["metrics"][0]["label"], "Loads")
        self.assertEqual(shipment_count["components"][0]["metrics"][0]["value"], 1)

        ranking = execute_allowlisted_read(
            prompt="Top 1 carriers by on-time rate for FTL shipments over the last 30 days.",
            permission_context=permission_context,
            repository=repository,
        )
        self.assertEqual(ranking["components"][0]["rows"], [["Acme Freight", 97.2, 1]])

        ranking_bundle = self._make_read_bundle()
        ranking_bundle["shipment_quotes"].append(
            {
                "quote_id": "quote-66110",
                "office_id": "memphis",
                "broker_id": "broker-123",
                "carrier_id": "carrier-7721",
                "origin_region": "Memphis",
                "destination_region": "Orlando",
                "shipment_mode": "FTL",
                "weight_class": "20000_plus",
                "pickup_date": "2026-03-11",
                "quote_status": "eligible_for_booking",
            }
        )
        ranking_bundle["shipments"].append(
            {
                "shipment_id": "ship-400",
                "office_id": "memphis",
                "broker_id": "broker-123",
                "carrier_id": "carrier-7721",
                "quote_id": "quote-66110",
                "origin_region": "Memphis",
                "destination_region": "Orlando",
                "shipment_mode": "FTL",
                "shipment_status": "delivered",
                "exception_type": None,
                "transit_hours": 60,
                "eta_at": "2026-03-12T14:00:00Z",
                "created_at": "2026-03-11T08:00:00Z",
            }
        )
        ranking_repository = ReadRepository(connection=build_seeded_read_connection(ranking_bundle))

        ranking_by_count = execute_allowlisted_read(
            prompt="Top 5 carriers by shipment count for FTL shipments over the last 90 days.",
            permission_context=permission_context,
            repository=ranking_repository,
        )
        self.assertEqual(ranking_by_count["components"][0]["rows"][0], ["RiverSouth", 88.4, 2])

        exceptions = execute_allowlisted_read(
            prompt="Show in-transit shipments with insurance expiring in the next 30 days.",
            permission_context=permission_context,
            repository=repository,
        )
        self.assertEqual(exceptions["components"][0]["rows"], [["ship-100", "insurance_expiring", "Acme Freight", "2026-03-18T17:00:00Z"]])

    def test_read_executor_clamps_contract_bounds_before_repository_execution(self) -> None:
        class RecordingRepository:
            def __init__(self) -> None:
                self.metrics_kwargs: dict[str, object] | None = None
                self.ranking_kwargs: dict[str, object] | None = None

            def shipments_for_metrics(
                self,
                office_id: str,
                *,
                date_range_days: int,
                shipment_mode: str | None = None,
                origin_region: str | None = None,
                destination_region: str | None = None,
            ) -> list[dict[str, object]]:
                self.metrics_kwargs = {
                    "office_id": office_id,
                    "date_range_days": date_range_days,
                    "shipment_mode": shipment_mode,
                    "origin_region": origin_region,
                    "destination_region": destination_region,
                }
                return [{"transit_hours": 36}]

            def carrier_rankings(
                self,
                office_id: str,
                *,
                ranking_metric: str,
                date_range_days: int,
                shipment_mode: str | None = None,
                weight_class: str | None = None,
                region: str | None = None,
                limit: int | None = None,
            ) -> list[dict[str, object]]:
                self.ranking_kwargs = {
                    "office_id": office_id,
                    "ranking_metric": ranking_metric,
                    "date_range_days": date_range_days,
                    "shipment_mode": shipment_mode,
                    "weight_class": weight_class,
                    "region": region,
                    "limit": limit,
                }
                return [{"carrier_name": "Acme Freight", "on_time_rate": 97.2, "shipment_count": 1}]

            def shipments_for_exception_view(self, *args: object, **kwargs: object) -> list[dict[str, object]]:
                return []

            def shipment_events(self, *args: object, **kwargs: object) -> list[dict[str, object]]:
                return []

        repository = RecordingRepository()
        permission_context = {
            "broker_id": "broker-123",
            "office_id": "memphis",
            "role": "broker",
        }

        execute_allowlisted_read(
            prompt="Shipment count for FTL Dallas to Chicago over the last 365 days.",
            permission_context=permission_context,
            repository=repository,
        )
        self.assertEqual(repository.metrics_kwargs["date_range_days"], 90)

        execute_allowlisted_read(
            prompt="Top 50 carriers by shipment count for FTL shipments over 20,000 pounds in the Southeast over the last 365 days.",
            permission_context=permission_context,
            repository=repository,
        )
        self.assertEqual(repository.ranking_kwargs["ranking_metric"], "shipment_count")
        self.assertEqual(repository.ranking_kwargs["date_range_days"], 90)
        self.assertEqual(repository.ranking_kwargs["limit"], 5)

    def test_read_executor_honors_contract_parameters_and_office_scope(self) -> None:
        bundle = self._make_read_bundle()
        bundle["carriers"].append(
            {
                "carrier_id": "carrier-8888",
                "carrier_name": "Cross Office Express",
                "shipment_mode": "FTL",
                "on_time_rate": 99.9,
                "insurance_expiry_date": "2026-05-01",
            }
        )
        bundle["shipment_quotes"].extend(
            [
                {
                    "quote_id": "quote-66100",
                    "office_id": "memphis",
                    "broker_id": "broker-123",
                    "carrier_id": "carrier-7721",
                    "origin_region": "Dallas",
                    "destination_region": "Chicago",
                    "shipment_mode": "FTL",
                    "weight_class": "20000_plus",
                    "pickup_date": "2026-03-14",
                    "quote_status": "eligible_for_booking",
                },
                {
                    "quote_id": "quote-atl-1",
                    "office_id": "atlanta",
                    "broker_id": "broker-123",
                    "carrier_id": "carrier-8888",
                    "origin_region": "Dallas",
                    "destination_region": "Chicago",
                    "shipment_mode": "FTL",
                    "weight_class": "20000_plus",
                    "pickup_date": "2026-03-14",
                    "quote_status": "eligible_for_booking",
                },
                {
                    "quote_id": "quote-atl-2",
                    "office_id": "atlanta",
                    "broker_id": "broker-123",
                    "carrier_id": "carrier-8888",
                    "origin_region": "Atlanta",
                    "destination_region": "Miami",
                    "shipment_mode": "FTL",
                    "weight_class": "20000_plus",
                    "pickup_date": "2026-03-13",
                    "quote_status": "eligible_for_booking",
                },
            ]
        )
        bundle["shipments"].extend(
            [
                {
                    "shipment_id": "ship-310",
                    "office_id": "memphis",
                    "broker_id": "broker-123",
                    "carrier_id": "carrier-7721",
                    "quote_id": "quote-66100",
                    "origin_region": "Dallas",
                    "destination_region": "Chicago",
                    "shipment_mode": "FTL",
                    "shipment_status": "delivered",
                    "exception_type": None,
                    "transit_hours": 60,
                    "eta_at": "2026-03-15T17:00:00Z",
                    "created_at": "2026-03-11T12:00:00Z",
                },
                {
                    "shipment_id": "ship-atl-1",
                    "office_id": "atlanta",
                    "broker_id": "broker-123",
                    "carrier_id": "carrier-8888",
                    "quote_id": "quote-atl-1",
                    "origin_region": "Dallas",
                    "destination_region": "Chicago",
                    "shipment_mode": "FTL",
                    "shipment_status": "delivered",
                    "exception_type": None,
                    "transit_hours": 24,
                    "eta_at": "2026-03-15T17:00:00Z",
                    "created_at": "2026-03-13T08:00:00Z",
                },
                {
                    "shipment_id": "ship-atl-2",
                    "office_id": "atlanta",
                    "broker_id": "broker-123",
                    "carrier_id": "carrier-8888",
                    "quote_id": "quote-atl-2",
                    "origin_region": "Atlanta",
                    "destination_region": "Miami",
                    "shipment_mode": "FTL",
                    "shipment_status": "delivered",
                    "exception_type": None,
                    "transit_hours": 30,
                    "eta_at": "2026-03-14T17:00:00Z",
                    "created_at": "2026-03-12T08:00:00Z",
                },
            ]
        )
        repository = ReadRepository(connection=build_seeded_read_connection(bundle))
        permission_context = {
            "broker_id": "broker-123",
            "office_id": "memphis",
            "role": "broker",
        }

        metrics = execute_allowlisted_read(
            prompt="Average transit time for Memphis shipments over the last 500 days.",
            permission_context=permission_context,
            repository=repository,
            tool_name="shipment_metrics_lookup",
            tool_arguments={
                "metric": "shipment_count",
                "date_range": 500,
                "shipment_mode": "FTL",
                "origin_region": "Dallas",
                "destination_region": "Chicago",
            },
        )
        self.assertEqual(metrics["components"][0]["metrics"][0]["label"], "Loads")
        self.assertEqual(metrics["components"][0]["metrics"][0]["value"], 2)
        self.assertEqual(metrics["components"][0]["metrics"][1]["value"], 2.0)

        ranking = execute_allowlisted_read(
            prompt="Top 1 carriers by on-time rate for FTL shipments over the last 30 days.",
            permission_context=permission_context,
            repository=repository,
            tool_name="carrier_ranking_lookup",
            tool_arguments={
                "ranking_metric": "shipment_count",
                "date_range": 30,
                "shipment_mode": "FTL",
                "limit": 1,
            },
        )
        self.assertEqual(ranking["components"][0]["rows"], [["RiverSouth", 88.4, 2]])

    def test_read_executor_validates_contract_read_arguments(self) -> None:
        repository = ReadRepository(connection=build_seeded_read_connection(self._make_read_bundle()))
        permission_context = {
            "broker_id": "broker-123",
            "office_id": "memphis",
            "role": "broker",
        }

        with self.assertRaisesRegex(ValueError, "metric"):
            execute_allowlisted_read(
                prompt="Average transit time for Memphis shipments over the last 30 days.",
                permission_context=permission_context,
                repository=repository,
                tool_name="shipment_metrics_lookup",
                tool_arguments={"metric": "margin", "date_range": 30},
            )

        with self.assertRaisesRegex(ValueError, "date_range"):
            execute_allowlisted_read(
                prompt="Average transit time for Memphis shipments over the last 30 days.",
                permission_context=permission_context,
                repository=repository,
                tool_name="shipment_metrics_lookup",
                tool_arguments={"metric": "shipment_count", "date_range": 0},
            )

        with self.assertRaisesRegex(ValueError, "ranking_metric"):
            execute_allowlisted_read(
                prompt="Top 1 carriers by on-time rate for FTL shipments over the last 30 days.",
                permission_context=permission_context,
                repository=repository,
                tool_name="carrier_ranking_lookup",
                tool_arguments={
                    "ranking_metric": "margin",
                    "date_range": 30,
                    "shipment_mode": "FTL",
                    "limit": 1,
                },
            )

        with self.assertRaisesRegex(ValueError, "limit"):
            execute_allowlisted_read(
                prompt="Top 1 carriers by on-time rate for FTL shipments over the last 30 days.",
                permission_context=permission_context,
                repository=repository,
                tool_name="carrier_ranking_lookup",
                tool_arguments={
                    "ranking_metric": "shipment_count",
                    "date_range": 30,
                    "shipment_mode": "FTL",
                    "limit": 0,
                },
            )


if __name__ == "__main__":
    unittest.main()
