from __future__ import annotations

import copy
import json
import time
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from fastapi.testclient import TestClient

from backend.app.db.read_repository import ReadRepository, build_seeded_read_connection
from backend.app.main import create_app
from backend.app.orchestrator import graph
from evals import contracts as eval_contracts
from evals import runner


ROOT = Path(__file__).resolve().parents[2]


class B5ScaffoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.eval_contract = eval_contracts.load_eval_contract()
        cls.response_contract = eval_contracts.load_response_contract()
        cls.response_validator = Draft202012Validator(cls.response_contract)
        cls.required_release_gates = {
            "permission_boundary",
            "query_quality",
            "write_confirmation",
            "structured_response",
            "auditability",
            "performance",
        }

    def make_valid_case(self) -> dict[str, object]:
        return {
            "scenario_id": "read_aggregation_broker",
            "intent_class": "read_result",
            "actor_role": "broker",
            "prompt": "Average transit time for LTL Dallas to Chicago over the last 90 days.",
            "expected_gate": "allow",
            "expected_tool_path": ["shipment_metrics_lookup"],
            "expected_response_components": ["metric_card"],
            "assertions": [
                "permission_context_applied",
                "bounded_date_range",
                "no_sensitive_fields",
                "latency_under_budget",
            ],
        }

    def make_valid_read_response(self) -> dict[str, object]:
        return {
            "contract_version": "0.1.0",
            "response_id": "resp-001",
            "request_id": "req-001",
            "intent_class": "read_result",
            "status": "success",
            "summary": "Average transit time is 2.4 days.",
            "components": [
                {
                    "component_id": "metric-1",
                    "component_type": "metric_card",
                    "title": "Transit time",
                    "metrics": [
                        {
                            "label": "Average transit time",
                            "value": 2.4,
                            "unit": "days",
                        }
                    ],
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
                "tool_path": ["shipment_metrics_lookup"],
                "response_generated_at": "2026-03-13T12:00:00Z",
            },
        }

    def make_complete_gate_result(self) -> dict[str, object]:
        return {
            "release_gate_results": {gate: "pass" for gate in self.required_release_gates},
            "release_gate_evidence": {
                gate: {
                    "expected_gate": "allow",
                    "assertions_checked": ["permission_context_applied"],
                    "pass_fail_criteria": ["criteria-recorded"],
                    "release_gate_flag": "pass",
                }
                for gate in self.required_release_gates
            },
        }

    def load_replay_bundle(self) -> dict[str, object]:
        return json.loads((ROOT / "db/seeds/replay_bundle.json").read_text())

    def replay_case(self, scenario_id: str) -> dict[str, object]:
        bundle = self.load_replay_bundle()
        return copy.deepcopy(next(case for case in bundle["cases"] if case["scenario_id"] == scenario_id))

    def make_live_chat_request(
        self,
        *,
        prompt: str,
        session_id: str | None = None,
        session_access_token: str | None = None,
        resource_id: str | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "prompt": prompt,
            "current_module": "dispatch_board",
        }
        if session_id is not None:
            payload["session_id"] = session_id
        if session_access_token is not None:
            payload["session_access_token"] = session_access_token
        if resource_id is not None:
            payload["current_resource"] = {
                "resource_type": "shipment",
                "resource_id": resource_id,
                "resource_fingerprint": f"shipment:{resource_id}:v1",
            }
        return payload

    def make_write_bundle(self) -> dict[str, object]:
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
                }
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
                }
            ],
            "shipments": [],
            "shipment_events": [],
            "booking_confirmations": [
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
            ],
        }

    def test_contract_layer_exposes_current_eval_and_response_contracts(self) -> None:
        self.assertEqual(self.eval_contract["artifact"], "contracts/eval-test-schema.yaml")
        self.assertEqual(self.response_contract["contract_name"], "agent_response")
        self.assertEqual(
            set(self.eval_contract["bundle_schema"]["allowed_actor_roles"]),
            {"broker"},
        )

    def test_runner_rejects_eval_cases_with_disallowed_contract_enums(self) -> None:
        bundle_schema = self.eval_contract["bundle_schema"]
        invalid_cases = [
            ("actor_role", "office_manager", bundle_schema["allowed_actor_roles"]),
            ("intent_class", "error", bundle_schema["allowed_intent_classes"]),
            ("expected_gate", "pass", bundle_schema["allowed_gate_results"]),
        ]

        for field, invalid_value, allowed_values in invalid_cases:
            with self.subTest(field=field, invalid_value=invalid_value):
                self.assertNotIn(invalid_value, allowed_values)
                case = self.make_valid_case()
                case[field] = invalid_value
                with self.assertRaisesRegex(ValueError, "eval contract validation failed"):
                    runner.run_eval_case(case)

    def test_runner_rejects_eval_cases_with_unknown_assertions(self) -> None:
        case = self.make_valid_case()
        case["assertions"] = ["not_in_eval_contract"]

        with self.assertRaisesRegex(ValueError, "eval contract validation failed"):
            runner.run_eval_case(case)

    def test_runner_marks_invalid_captured_responses_as_response_contract_failures(self) -> None:
        invalid_responses = []

        missing_policy = self.make_valid_read_response()
        del missing_policy["policy"]
        invalid_responses.append(("missing_required_top_level_field", missing_policy))

        denied_status_mismatch = self.make_valid_read_response()
        denied_status_mismatch["intent_class"] = "read_denied"
        invalid_responses.append(("intent_status_mismatch", denied_status_mismatch))

        for label, response in invalid_responses:
            with self.subTest(label=label):
                self.assertFalse(self.response_validator.is_valid(response))
                case = self.make_valid_case()
                case["captured_response"] = response
                result = runner.run_eval_case(case)
                self.assertEqual(result["contract_validation"]["status"], "failed")
                self.assertEqual(
                    result["contract_validation"]["failure_class"],
                    "response_contract",
                )
                self.assertEqual(result["release_gate_results"]["structured_response"], "fail")

    def test_score_release_gates_requires_all_in_scope_gate_results(self) -> None:
        result = self.make_complete_gate_result()
        del result["release_gate_results"]["performance"]

        score = runner.score_release_gates(result)

        self.assertEqual(score["overall"], "fail")
        self.assertIn("performance", score["missing_gates"])

    def test_score_release_gates_requires_gate_evidence_not_just_pass_strings(self) -> None:
        no_evidence_result = {"release_gate_results": copy.deepcopy(self.make_complete_gate_result()["release_gate_results"])}
        no_evidence_score = runner.score_release_gates(no_evidence_result)
        self.assertEqual(no_evidence_score["overall"], "fail")

        contradictory_evidence_result = self.make_complete_gate_result()
        contradictory_evidence_result["release_gate_evidence"]["auditability"]["release_gate_flag"] = "fail"
        contradictory_score = runner.score_release_gates(contradictory_evidence_result)

        self.assertEqual(contradictory_score["overall"], "fail")
        self.assertIn("auditability", contradictory_score["failed_evidence_gates"])

    def test_runner_fails_async_trace_cases_without_completed_job_linkage(self) -> None:
        client = TestClient(create_app())

        seed = client.post(
            "/chat",
            json=self.make_live_chat_request(
                prompt="Show shipment 88219 details.",
                resource_id="88219",
            ),
        )
        self.assertEqual(seed.status_code, 200)
        seed_payload = seed.json()

        pending = client.post(
            "/chat",
            json=self.make_live_chat_request(
                prompt="Run a background analytics refresh for Memphis exceptions.",
                session_id=seed_payload["session_id"],
                session_access_token=seed_payload["session_access_token"],
            ),
        )
        self.assertEqual(pending.status_code, 200)
        pending_payload = pending.json()

        case = {
            "scenario_id": "read_async_refresh_pending",
            "intent_class": "read_pending",
            "actor_role": "broker",
            "prompt": "Run a background analytics refresh for Memphis exceptions.",
            "expected_gate": "allow",
            "expected_tool_path": [],
            "expected_response_components": ["message_block"],
            "assertions": [
                "session_metadata_present",
                "async_job_id_present",
                "trace_linked_async_completion",
            ],
            "captured_response": pending_payload,
        }

        result = runner.run_eval_case(case)

        self.assertEqual(result["release_gate_results"]["auditability"], "fail")
        self.assertEqual(result["release_gate_results"]["structured_response"], "fail")

    def test_runner_scores_live_write_replay_cases_from_real_runtime_evidence(self) -> None:
        repository = ReadRepository(connection=build_seeded_read_connection(self.make_write_bundle()))
        idempotency_store: dict[str, dict[str, object]] = {}
        case = {
            "scenario_id": "booking_submit_after_confirmation",
            "intent_class": "write_submitted",
            "actor_role": "broker",
            "prompt": "Confirm booking quote 88219 with carrier 4412 for Tuesday pickup.",
            "expected_gate": "allow",
            "expected_tool_path": ["booking_create_confirmed"],
            "expected_response_components": ["message_block"],
            "assertions": [
                "confirmation_token_validated",
                "resource_state_revalidated",
                "audit_record_present",
                "idempotent_replay_linked",
                "action_outcome_timestamp_present",
            ],
            "captured_write_result": graph.execute_write_path(
                confirmation_token="confirm-quote-88219",
                idempotency_key="book-quote-88219-carrier-4412-pickup-2026-03-17-v1",
                broker_id="broker-123",
                office_id="memphis",
                role="broker",
                repository=repository,
                idempotency_store=idempotency_store,
            ),
        }
        case["captured_write_replay"] = graph.execute_write_path(
            confirmation_token="confirm-quote-88219",
            idempotency_key="book-quote-88219-carrier-4412-pickup-2026-03-17-v1",
            broker_id="broker-123",
            office_id="memphis",
            role="broker",
            repository=repository,
            idempotency_store=idempotency_store,
        )

        result = runner.run_eval_case(case)
        score = runner.score_release_gates(result)

        self.assertEqual(result["release_gate_results"]["write_confirmation"], "pass")
        self.assertEqual(result["release_gate_results"]["auditability"], "pass")
        self.assertEqual(score["overall"], "pass")

    def test_runner_fails_preconfirmation_case_without_confirmation_token_or_audit_stub(self) -> None:
        case = self.replay_case("booking_confirmation_happy_path")
        confirmation_card = case["captured_response"]["components"][0]
        action = case["captured_response"]["actions"][0]
        del confirmation_card["confirmation_token"]
        del action["confirmation_token"]
        del action["idempotency_key"]

        result = runner.run_eval_case(case)
        score = runner.score_release_gates(result)

        self.assertEqual(result["release_gate_results"]["write_confirmation"], "fail")
        self.assertEqual(score["overall"], "fail")

    def test_runner_fails_no_write_executed_assertion_when_write_artifact_is_present(self) -> None:
        case = self.replay_case("booking_deny_without_confirmation")
        case["captured_write_result"] = {
            "status": "submitted",
            "action_name": "booking_create_confirmed",
            "quote_id": "quote-88219",
            "office_id": "memphis",
            "actor_broker_id": "broker-mem-001",
            "audit": {
                "tool_path": ["booking_create_confirmed"],
                "idempotency_key": "book-quote-88219-v1",
                "outcome": "submitted",
                "actor_broker_id": "broker-mem-001",
                "office_id": "memphis",
            },
        }

        result = runner.run_eval_case(case)
        score = runner.score_release_gates(result)

        self.assertEqual(result["release_gate_results"]["write_confirmation"], "fail")
        self.assertEqual(score["overall"], "fail")

    def test_runner_fails_async_trace_assertion_when_completion_trace_mismatches_pending_trace(self) -> None:
        case = self.replay_case("read_async_refresh_pending")
        case["captured_job"]["result"]["trace_id"] = "trace-unrelated-999"

        result = runner.run_eval_case(case)
        score = runner.score_release_gates(result)

        self.assertEqual(result["release_gate_results"]["auditability"], "fail")
        self.assertEqual(result["release_gate_results"]["structured_response"], "fail")
        self.assertEqual(score["overall"], "fail")

    def test_runner_fails_confirmation_token_validation_when_write_result_omits_token(self) -> None:
        case = self.replay_case("booking_submit_after_confirmation")
        del case["captured_write_result"]["confirmation_token"]

        result = runner.run_eval_case(case)
        score = runner.score_release_gates(result)

        self.assertEqual(result["release_gate_results"]["write_confirmation"], "fail")
        self.assertEqual(score["overall"], "fail")

    def test_runner_fails_write_submitted_case_when_runtime_write_result_is_denied(self) -> None:
        case = self.replay_case("booking_submit_after_confirmation")
        case["captured_write_result"]["status"] = "denied"

        result = runner.run_eval_case(case)
        score = runner.score_release_gates(result)

        self.assertEqual(result["release_gate_results"]["write_confirmation"], "fail")
        self.assertEqual(score["overall"], "fail")

    def test_runner_scores_live_stale_binding_and_latency_evidence(self) -> None:
        client = TestClient(create_app())

        seed = client.post(
            "/chat",
            json=self.make_live_chat_request(
                prompt="Show shipment 88219 details.",
                resource_id="88219",
            ),
        )
        self.assertEqual(seed.status_code, 200)
        seed_payload = seed.json()

        started_at = time.perf_counter()
        stale = client.post(
            "/chat",
            json=self.make_live_chat_request(
                prompt="Switch to shipment 99117.",
                session_id=seed_payload["session_id"],
                session_access_token=seed_payload["session_access_token"],
                resource_id="99117",
            ),
        )
        latency_ms = (time.perf_counter() - started_at) * 1000
        self.assertEqual(stale.status_code, 200)

        case = {
            "scenario_id": "read_stale_binding_broker",
            "intent_class": "read_result",
            "actor_role": "broker",
            "prompt": "Switch to shipment 99117.",
            "expected_gate": "allow",
            "expected_tool_path": ["shipment_exception_lookup"],
            "expected_response_components": ["message_block"],
            "assertions": [
                "stale_binding_emitted",
                "session_metadata_present",
                "latency_under_budget",
            ],
            "captured_response": stale.json(),
            "captured_latency_ms": latency_ms,
        }

        result = runner.run_eval_case(case)
        score = runner.score_release_gates(result)

        self.assertEqual(result["release_gate_results"]["permission_boundary"], "pass")
        self.assertEqual(result["release_gate_results"]["performance"], "pass")
        self.assertEqual(score["overall"], "pass")

    def test_runner_scores_replay_bundle_fixture_for_required_end_to_end_coverage(self) -> None:
        bundle = self.load_replay_bundle()

        result = runner.run_eval_bundle(bundle)

        self.assertEqual(result["bundle_validation"]["status"], "passed")
        self.assertEqual(result["coverage_validation"]["status"], "passed")
        self.assertEqual(result["score"]["overall"], "pass")
        self.assertEqual(result["score"]["case_counts"]["pass"], len(bundle["cases"]))
        self.assertEqual(result["score"]["case_counts"]["fail"], 0)

    def test_runner_rejects_replay_bundle_missing_required_coverage_slice(self) -> None:
        bundle = self.load_replay_bundle()
        bundle["cases"] = [
            case
            for case in bundle["cases"]
            if case["scenario_id"] != "read_async_refresh_pending"
        ]

        with self.assertRaisesRegex(ValueError, "replay bundle validation failed"):
            runner.run_eval_bundle(bundle)

    def test_runner_rejects_replay_bundle_when_case_assertions_drift_from_catalog(self) -> None:
        bundle = self.load_replay_bundle()
        target = next(case for case in bundle["cases"] if case["scenario_id"] == "read_async_refresh_pending")
        target["assertions"] = [
            "session_metadata_present",
            "async_job_id_present",
            "trace_linked_async_completion",
        ]

        with self.assertRaisesRegex(ValueError, "replay bundle validation failed"):
            runner.run_eval_bundle(bundle)

    def test_replay_bundle_fixture_assertions_match_contract_catalog(self) -> None:
        bundle_cases = {
            case["scenario_id"]: case["assertions"]
            for case in self.load_replay_bundle()["cases"]
        }
        contract_cases = {
            scenario["scenario_id"]: scenario["assertions"]
            for scenario in self.eval_contract["scenario_catalog"]
        }

        for scenario_id, contract_assertions in contract_cases.items():
            with self.subTest(scenario_id=scenario_id):
                self.assertEqual(bundle_cases[scenario_id], contract_assertions)


if __name__ == "__main__":
    unittest.main()
