from __future__ import annotations

import copy
import unittest

from jsonschema import Draft202012Validator

from evals import contracts as eval_contracts
from evals import runner


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


if __name__ == "__main__":
    unittest.main()
