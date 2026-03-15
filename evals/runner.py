from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator

from evals.contracts import EVAL_CONTRACT, RESPONSE_CONTRACT, load_eval_contract, load_response_contract


REQUIRED_RELEASE_GATES = (
    "permission_boundary",
    "query_quality",
    "write_confirmation",
    "structured_response",
    "auditability",
    "performance",
)

PERMISSION_ASSERTIONS = frozenset(
    {
        "permission_context_applied",
        "denial_reason_permission",
        "denial_reason_sensitive_field",
        "denial_reason_unsupported_or_missing_confirmation",
    }
)
RESPONSE_ASSERTIONS = frozenset(
    {
        "session_metadata_present",
        "async_job_id_present",
        "trace_linked_async_completion",
        "stale_binding_emitted",
    }
)
WRITE_ASSERTIONS = frozenset(
    {
        "confirmation_token_present",
        "no_write_without_confirmation",
        "audit_stub_present",
        "no_write_executed",
        "confirmation_token_validated",
        "resource_state_revalidated",
        "audit_record_present",
        "idempotent_replay_linked",
        "action_outcome_timestamp_present",
    }
)
QUERY_ASSERTIONS = frozenset(
    {
        "bounded_date_range",
        "bounded_limit",
        "no_sensitive_fields",
        "no_tool_execution",
        "no_cross_office_data",
        "office_scope_enforced",
        "no_cross_office_records",
    }
)


def describe_runtime() -> dict[str, str]:
    return {
        "eval_contract": str(Path(EVAL_CONTRACT)),
        "response_contract": str(Path(RESPONSE_CONTRACT)),
        "status": "contract_aware",
    }


def _validate_eval_case(case: dict[str, object]) -> None:
    contract = load_eval_contract()
    bundle_schema = contract["bundle_schema"]
    required_fields = bundle_schema["required_case_fields"]
    missing = [field for field in required_fields if field not in case]
    if missing:
        raise ValueError("eval contract validation failed")

    enum_constraints = {
        "actor_role": set(bundle_schema["allowed_actor_roles"]),
        "intent_class": set(bundle_schema["allowed_intent_classes"]),
        "expected_gate": set(bundle_schema["allowed_gate_results"]),
    }
    for field, allowed_values in enum_constraints.items():
        if case.get(field) not in allowed_values:
            raise ValueError("eval contract validation failed")

    assertions = case.get("assertions")
    if not isinstance(assertions, list) or not assertions or not all(isinstance(assertion, str) for assertion in assertions):
        raise ValueError("eval contract validation failed")

    known_assertions = {
        str(assertion)
        for scenario in contract.get("scenario_catalog", [])
        if isinstance(scenario, dict)
        for assertion in scenario.get("assertions", [])
        if isinstance(assertion, str)
    }
    if any(assertion not in known_assertions for assertion in assertions):
        raise ValueError("eval contract validation failed")


def _bundle_cases(bundle: dict[str, object]) -> list[dict[str, object]]:
    cases = bundle.get("cases")
    if not isinstance(cases, list):
        raise ValueError("replay bundle validation failed")
    typed_cases = [case for case in cases if isinstance(case, dict)]
    if len(typed_cases) != len(cases) or not typed_cases:
        raise ValueError("replay bundle validation failed")
    return typed_cases


def _validate_eval_bundle(bundle: dict[str, object]) -> dict[str, object]:
    contract = load_eval_contract()
    bundle_schema = contract["bundle_schema"]
    required_fields = bundle_schema["required_top_level_fields"]
    missing = [field for field in required_fields if field not in bundle]
    if missing:
        raise ValueError("replay bundle validation failed")
    if bundle.get("contract_version") != contract["version"]:
        raise ValueError("replay bundle validation failed")

    cases = _bundle_cases(bundle)
    catalog = {
        str(scenario.get("scenario_id", "")): [str(assertion) for assertion in scenario.get("assertions", [])]
        for scenario in contract.get("scenario_catalog", [])
        if isinstance(scenario, dict)
    }
    seen_scenarios: set[str] = set()
    for case in cases:
        _validate_eval_case(case)
        scenario_id = str(case.get("scenario_id", ""))
        if scenario_id in seen_scenarios:
            raise ValueError("replay bundle validation failed")
        if scenario_id not in catalog or _case_assertions(case) != catalog[scenario_id]:
            raise ValueError("replay bundle validation failed")
        seen_scenarios.add(scenario_id)

    replay_contract = contract.get("replay_bundle", {})
    required_scenario_ids = {str(scenario_id) for scenario_id in replay_contract.get("required_scenario_ids", [])}
    if not required_scenario_ids.issubset(seen_scenarios):
        raise ValueError("replay bundle validation failed")

    coverage_errors: list[str] = []
    for slice_config in replay_contract.get("required_coverage_slices", []):
        if not isinstance(slice_config, dict):
            coverage_errors.append("invalid_coverage_slice")
            continue
        coverage_id = str(slice_config.get("coverage_id", "unknown"))
        scenario_ids = {str(scenario_id) for scenario_id in slice_config.get("scenario_ids", [])}
        required_assertions = {str(assertion) for assertion in slice_config.get("required_assertions", [])}
        required_capture_fields = [str(field) for field in slice_config.get("required_capture_fields", [])]
        matching_cases = [case for case in cases if str(case.get("scenario_id", "")) in scenario_ids]
        if not matching_cases:
            coverage_errors.append(coverage_id)
            continue
        if not any(
            required_assertions.issubset(set(_case_assertions(case)))
            and all(case.get(field) is not None for field in required_capture_fields)
            for case in matching_cases
        ):
            coverage_errors.append(coverage_id)

    if coverage_errors:
        raise ValueError("replay bundle validation failed")

    return {
        "contract_version": str(contract["version"]),
        "case_count": len(cases),
        "coverage_ids": [
            str(slice_config.get("coverage_id", "unknown"))
            for slice_config in replay_contract.get("required_coverage_slices", [])
            if isinstance(slice_config, dict)
        ],
        "fixture_artifact": str(replay_contract.get("default_fixture_artifact", "")),
    }


def _release_gate_results(structured_response_result: str) -> dict[str, str]:
    return {
        "permission_boundary": "pass",
        "query_quality": "pass",
        "write_confirmation": "pass",
        "structured_response": structured_response_result,
        "auditability": "pass",
        "performance": "pass",
    }


def _release_gate_evidence(case: dict[str, object], gate_results: dict[str, str]) -> dict[str, dict[str, object]]:
    assertions = case.get("assertions", [])
    if not isinstance(assertions, list):
        assertions = []

    expected_gate = str(case.get("expected_gate", "deny"))
    return {
        gate: {
            "expected_gate": expected_gate,
            "assertions_checked": list(assertions),
            "pass_fail_criteria": ["contract-check"],
            "release_gate_flag": result,
        }
        for gate, result in gate_results.items()
    }


def _response_contract_valid(response: object) -> bool:
    if not isinstance(response, dict):
        return False
    validator = Draft202012Validator(load_response_contract())
    return validator.is_valid(response)


def _budget_ms() -> float:
    contract = load_eval_contract()
    return float(contract["provisional_defaults"]["latency_budgets_ms"]["end_to_end_read"])


def _case_assertions(case: dict[str, object]) -> list[str]:
    assertions = case.get("assertions", [])
    return list(assertions) if isinstance(assertions, list) else []


def _captured_response(case: dict[str, object]) -> dict[str, object] | None:
    response = case.get("captured_response")
    return response if isinstance(response, dict) else None


def _captured_job(case: dict[str, object]) -> dict[str, object] | None:
    job = case.get("captured_job")
    return job if isinstance(job, dict) else None


def _captured_write_result(case: dict[str, object]) -> dict[str, object] | None:
    result = case.get("captured_write_result")
    return result if isinstance(result, dict) else None


def _captured_write_replay(case: dict[str, object]) -> dict[str, object] | None:
    result = case.get("captured_write_replay")
    return result if isinstance(result, dict) else None


def _response_components(response: dict[str, object] | None) -> list[dict[str, object]]:
    components = response.get("components", []) if response else []
    return [component for component in components if isinstance(component, dict)] if isinstance(components, list) else []


def _response_actions(response: dict[str, object] | None) -> list[dict[str, object]]:
    actions = response.get("actions", []) if response else []
    return [action for action in actions if isinstance(action, dict)] if isinstance(actions, list) else []


def _write_result_matches_expected_gate(expected_gate: str, write_result: dict[str, object] | None) -> bool:
    if write_result is None:
        return True
    observed_status = write_result.get("status")
    if expected_gate == "allow":
        return observed_status == "submitted"
    if expected_gate == "deny":
        return observed_status == "denied"
    return True


def _expected_tool_path_matches(case: dict[str, object], response: dict[str, object] | None) -> bool:
    expected = case.get("expected_tool_path", [])
    if not isinstance(expected, list):
        return False
    if response is None:
        return True
    observed = response.get("audit", {}).get("tool_path")
    return isinstance(observed, list) and list(observed) == expected


def _expected_components_match(case: dict[str, object], response: dict[str, object] | None) -> bool:
    expected = case.get("expected_response_components", [])
    if not isinstance(expected, list):
        return False
    if response is None:
        return True
    components = response.get("components", [])
    if not isinstance(components, list):
        return False
    observed = [component.get("component_type") for component in components if isinstance(component, dict)]
    return observed == expected


def _assertion_results(case: dict[str, object]) -> dict[str, bool]:
    response = _captured_response(case)
    job = _captured_job(case)
    write_result = _captured_write_result(case)
    write_replay = _captured_write_replay(case)
    latency_ms = case.get("captured_latency_ms")
    components = _response_components(response)
    actions = _response_actions(response)

    results: dict[str, bool] = {}
    for assertion in _case_assertions(case):
        if assertion == "permission_context_applied":
            results[assertion] = bool(response and response.get("policy", {}).get("permission_context_applied"))
        elif assertion == "session_metadata_present":
            results[assertion] = bool(
                response
                and response.get("session_id")
                and response.get("trace_id")
                and response.get("audit", {}).get("response_generated_at")
            )
        elif assertion == "async_job_id_present":
            results[assertion] = bool(response and response.get("job_id"))
        elif assertion == "trace_linked_async_completion":
            results[assertion] = bool(
                response
                and response.get("job_id")
                and response.get("trace_id")
                and job
                and job.get("job_id") == response.get("job_id")
                and isinstance(job.get("result"), dict)
                and job.get("completed_response_id") == job["result"].get("response_id")
                and job["result"].get("job_id") == response.get("job_id")
                and job["result"].get("trace_id") == response.get("trace_id")
            )
        elif assertion == "stale_binding_emitted":
            results[assertion] = bool(
                response
                and response.get("context_binding_state") == "stale"
                and response.get("policy", {}).get("denial_reason_class") == "stale_state"
            )
        elif assertion == "bounded_date_range":
            results[assertion] = bool(
                response
                and (
                    "days" in str(response.get("summary", "")).lower()
                    or any(
                        metric.get("label") == "Date Range" and metric.get("value")
                        for component in components
                        for metric in component.get("metrics", [])
                        if isinstance(metric, dict)
                    )
                )
            )
        elif assertion == "bounded_limit":
            results[assertion] = bool(
                components
                and all(
                    component.get("component_type") != "table"
                    or (isinstance(component.get("rows"), list) and len(component.get("rows")) <= 5)
                    for component in components
                )
            )
        elif assertion == "no_sensitive_fields":
            results[assertion] = bool(response and response.get("policy", {}).get("sensitive_fields_redacted"))
        elif assertion == "no_tool_execution":
            results[assertion] = bool(response and response.get("audit", {}).get("tool_path") == [])
        elif assertion == "no_cross_office_data":
            results[assertion] = bool(
                response
                and response.get("status") == "denied"
                and all(component.get("component_type") == "message_block" for component in components)
            )
        elif assertion == "office_scope_enforced":
            results[assertion] = bool(response and response.get("audit", {}).get("office_scope"))
        elif assertion == "no_cross_office_records":
            results[assertion] = bool(
                response
                and response.get("audit", {}).get("office_scope")
                and all(
                    "office" not in str(column.get("key", "")).lower()
                    for component in components
                    for column in component.get("columns", [])
                    if isinstance(column, dict)
                )
            )
        elif assertion == "latency_under_budget":
            results[assertion] = isinstance(latency_ms, (int, float)) and float(latency_ms) <= _budget_ms()
        elif assertion == "confirmation_token_present":
            results[assertion] = bool(
                response
                and response.get("status") == "confirmation_required"
                and (
                    any(component.get("confirmation_token") for component in components)
                    or any(action.get("confirmation_token") for action in actions)
                )
            )
        elif assertion == "no_write_without_confirmation":
            results[assertion] = bool(
                response
                and response.get("status") == "confirmation_required"
                and write_result is None
                and write_replay is None
                and any(action.get("requires_confirmation") is True for action in actions)
            )
        elif assertion == "audit_stub_present":
            results[assertion] = bool(
                response
                and response.get("audit", {}).get("tool_path") == ["booking_create_prepare"]
                and response.get("audit", {}).get("response_generated_at")
                and any(
                    action.get("idempotency_key")
                    and isinstance(action.get("permission_scope"), dict)
                    and action["permission_scope"].get("office_id")
                    and action["permission_scope"].get("broker_id")
                    and action["permission_scope"].get("role")
                    for action in actions
                )
            )
        elif assertion == "no_write_executed":
            results[assertion] = bool(
                write_result is None
                and write_replay is None
                and (
                    response is None
                    or response.get("audit", {}).get("tool_path") in ([], ["booking_create_prepare"])
                )
            )
        elif assertion == "denial_reason_permission":
            results[assertion] = bool(response and response.get("policy", {}).get("denial_reason_class") == "permission")
        elif assertion == "denial_reason_sensitive_field":
            results[assertion] = bool(
                response and response.get("policy", {}).get("denial_reason_class") == "sensitive_field"
            )
        elif assertion == "denial_reason_unsupported_or_missing_confirmation":
            results[assertion] = bool(
                response
                and response.get("policy", {}).get("denial_reason_class") in {"unsupported_request", "missing_confirmation"}
            )
        elif assertion == "confirmation_token_validated":
            results[assertion] = bool(
                write_result
                and write_result.get("status") == "submitted"
                and write_result.get("action_name") == "booking_create_confirmed"
                and write_result.get("quote_id")
                and write_result.get("confirmation_token")
            )
        elif assertion == "resource_state_revalidated":
            results[assertion] = bool(
                write_result
                and write_result.get("status") == "submitted"
                and write_result.get("office_id")
                and write_result.get("actor_broker_id")
            )
        elif assertion == "audit_record_present":
            results[assertion] = bool(
                write_result
                and isinstance(write_result.get("audit"), dict)
                and write_result["audit"].get("tool_path")
                and write_result["audit"].get("idempotency_key")
                and write_result["audit"].get("outcome")
                and write_result["audit"].get("actor_broker_id") == write_result.get("actor_broker_id")
                and write_result["audit"].get("office_id") == write_result.get("office_id")
            )
        elif assertion == "idempotent_replay_linked":
            results[assertion] = bool(
                write_result
                and write_replay
                and write_result == write_replay
                and write_result.get("audit", {}).get("idempotency_key")
                == write_replay.get("audit", {}).get("idempotency_key")
            )
        elif assertion == "action_outcome_timestamp_present":
            results[assertion] = bool(write_result and write_result.get("audit", {}).get("outcome_recorded_at"))
        else:
            results[assertion] = False
    return results


def _gate_from_checks(*checks: bool) -> str:
    return "pass" if all(checks) else "fail"


def _evidence_record(
    *,
    expected_gate: str,
    assertions_checked: list[str],
    pass_fail_criteria: list[str],
    release_gate_flag: str,
) -> dict[str, object]:
    return {
        "expected_gate": expected_gate,
        "assertions_checked": assertions_checked or ["not_in_scope"],
        "pass_fail_criteria": pass_fail_criteria or ["not_applicable_to_case"],
        "release_gate_flag": release_gate_flag,
    }


def run_eval_bundle(bundle: dict[str, object]) -> dict[str, object]:
    validation = _validate_eval_bundle(bundle)
    cases = _bundle_cases(bundle)
    case_results = []
    failed_scenarios: list[str] = []
    pass_count = 0

    for case in cases:
        result = run_eval_case(case)
        score = score_release_gates(result)
        case_results.append(
            {
                "scenario_id": str(case.get("scenario_id", "unknown")),
                "result": result,
                "score": score,
            }
        )
        if score["overall"] == "pass":
            pass_count += 1
        else:
            failed_scenarios.append(str(case.get("scenario_id", "unknown")))

    return {
        "bundle_id": str(bundle.get("bundle_id", "unknown")),
        "bundle_validation": {
            "status": "passed",
            "contract_version": validation["contract_version"],
            "case_count": validation["case_count"],
        },
        "coverage_validation": {
            "status": "passed",
            "fixture_artifact": validation["fixture_artifact"],
            "coverage_ids": validation["coverage_ids"],
        },
        "cases": case_results,
        "score": {
            "overall": "pass" if not failed_scenarios else "fail",
            "case_counts": {
                "pass": pass_count,
                "fail": len(failed_scenarios),
                "total": len(cases),
            },
            "failed_scenarios": failed_scenarios,
        },
    }


def run_eval_case(case: dict[str, object]) -> dict[str, object]:
    _validate_eval_case(case)

    response = _captured_response(case)
    job = _captured_job(case)
    write_result = _captured_write_result(case)
    assertion_results = _assertion_results(case)
    captured_response = case.get("captured_response")
    response_is_valid = captured_response is None or _response_contract_valid(captured_response)

    if job is not None and isinstance(job.get("result"), dict):
        response_is_valid = response_is_valid and _response_contract_valid(job["result"])

    expected_gate = str(case.get("expected_gate", "deny"))

    permission_checks = []
    permission_assertions = [name for name in _case_assertions(case) if name in PERMISSION_ASSERTIONS]
    if response is not None:
        permission_checks.append(bool(response.get("policy", {}).get("permission_context_applied")))
        permission_checks.append(bool(response.get("audit", {}).get("office_scope")))
    elif write_result is not None:
        permission_checks.append(bool(write_result.get("office_id")))
        permission_checks.append(bool(write_result.get("actor_broker_id")))
    permission_checks.extend(assertion_results[name] for name in permission_assertions)
    permission_gate = _gate_from_checks(*permission_checks) if permission_checks else "pass"

    query_checks = []
    query_assertions = [name for name in _case_assertions(case) if name in QUERY_ASSERTIONS]
    if response is not None:
        query_checks.append(_expected_tool_path_matches(case, response))
        query_checks.append(_expected_components_match(case, response))
    query_checks.extend(assertion_results[name] for name in query_assertions)
    query_gate = _gate_from_checks(*query_checks) if query_checks else "pass"

    write_assertions = [name for name in _case_assertions(case) if name in WRITE_ASSERTIONS]
    write_checks = [assertion_results[name] for name in write_assertions]
    write_checks.append(_write_result_matches_expected_gate(expected_gate, write_result))
    write_gate = _gate_from_checks(*write_checks) if write_checks else "pass"

    structured_assertions = [name for name in _case_assertions(case) if name in RESPONSE_ASSERTIONS]
    structured_checks = []
    if response is not None:
        structured_checks.append(response_is_valid)
        structured_checks.append(_expected_tool_path_matches(case, response))
        structured_checks.append(_expected_components_match(case, response))
    if job is not None and isinstance(job.get("result"), dict):
        structured_checks.append(_response_contract_valid(job["result"]))
    structured_checks.extend(assertion_results[name] for name in structured_assertions)
    structured_gate = _gate_from_checks(*structured_checks) if structured_checks else ("pass" if response_is_valid else "fail")

    audit_checks = []
    audit_assertions = [
        name
        for name in _case_assertions(case)
        if name
        in {
            "session_metadata_present",
            "trace_linked_async_completion",
            "audit_stub_present",
            "audit_record_present",
            "action_outcome_timestamp_present",
        }
    ]
    if response is not None:
        audit_checks.append(bool(response.get("trace_id")))
        audit_checks.append(bool(response.get("audit", {}).get("response_generated_at")))
        audit_checks.append(isinstance(response.get("audit", {}).get("tool_path"), list))
    audit_checks.extend(assertion_results[name] for name in audit_assertions)
    audit_gate = _gate_from_checks(*audit_checks) if audit_checks else "pass"

    performance_assertions = [name for name in _case_assertions(case) if name == "latency_under_budget"]
    performance_checks = [assertion_results[name] for name in performance_assertions]
    performance_gate = _gate_from_checks(*performance_checks) if performance_checks else "pass"

    release_gate_results = {
        "permission_boundary": permission_gate,
        "query_quality": query_gate,
        "write_confirmation": write_gate,
        "structured_response": structured_gate,
        "auditability": audit_gate,
        "performance": performance_gate,
    }
    release_gate_evidence = {
        "permission_boundary": _evidence_record(
            expected_gate=expected_gate,
            assertions_checked=permission_assertions or (["permission_context_applied"] if response is not None else ["write_actor_scope_present"]),
            pass_fail_criteria=["permission-context-applied", "office-scope-recorded"]
            if response is not None
            else ["write-result-scope-recorded"],
            release_gate_flag=permission_gate,
        ),
        "query_quality": _evidence_record(
            expected_gate=expected_gate,
            assertions_checked=query_assertions,
            pass_fail_criteria=["expected-tool-path-matched", "expected-components-matched"],
            release_gate_flag=query_gate,
        ),
        "write_confirmation": _evidence_record(
            expected_gate=expected_gate,
            assertions_checked=write_assertions,
            pass_fail_criteria=["write-replay-evidence-linked"],
            release_gate_flag=write_gate,
        ),
        "structured_response": _evidence_record(
            expected_gate=expected_gate,
            assertions_checked=structured_assertions,
            pass_fail_criteria=["response-contract-valid", "expected-components-matched"],
            release_gate_flag=structured_gate,
        ),
        "auditability": _evidence_record(
            expected_gate=expected_gate,
            assertions_checked=audit_assertions,
            pass_fail_criteria=["trace-and-audit-linkage-present"],
            release_gate_flag=audit_gate,
        ),
        "performance": _evidence_record(
            expected_gate=expected_gate,
            assertions_checked=performance_assertions,
            pass_fail_criteria=["latency-under-budget"],
            release_gate_flag=performance_gate,
        ),
    }

    contract_validation: dict[str, object] = {
        "eval_contract": str(Path(EVAL_CONTRACT)),
        "response_contract": str(Path(RESPONSE_CONTRACT)),
        "status": "passed" if response_is_valid else "failed",
    }
    if not response_is_valid:
        contract_validation["failure_class"] = "response_contract"

    return {
        "scenario_id": str(case.get("scenario_id", "unknown")),
        "release_gate_results": release_gate_results,
        "release_gate_evidence": release_gate_evidence,
        "contract_validation": contract_validation,
    }


def score_release_gates(result: dict[str, object]) -> dict[str, object]:
    gates = result.get("release_gate_results", {})
    if not isinstance(gates, dict):
        gates = {}

    evidence = result.get("release_gate_evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}

    missing_gates = sorted(gate for gate in REQUIRED_RELEASE_GATES if gate not in gates)
    failed_gates = sorted(gate for gate in REQUIRED_RELEASE_GATES if gates.get(gate) != "pass")
    missing_evidence_gates = sorted(gate for gate in REQUIRED_RELEASE_GATES if gate not in evidence)

    failed_evidence_gates = []
    for gate in REQUIRED_RELEASE_GATES:
        gate_evidence = evidence.get(gate)
        if not isinstance(gate_evidence, dict):
            continue
        if gate_evidence.get("release_gate_flag") != "pass":
            failed_evidence_gates.append(gate)
            continue
        if not gate_evidence.get("assertions_checked") or not gate_evidence.get("pass_fail_criteria"):
            failed_evidence_gates.append(gate)

    failed_evidence_gates = sorted(set(failed_evidence_gates))
    pass_count = sum(1 for value in gates.values() if value == "pass")
    fail_count = sum(1 for value in gates.values() if value != "pass")

    return {
        "overall": (
            "pass"
            if fail_count == 0 and not missing_gates and not missing_evidence_gates and not failed_evidence_gates
            else "fail"
        ),
        "gate_counts": {
            "pass": pass_count,
            "fail": fail_count,
            "total": len(gates),
        },
        "missing_gates": missing_gates,
        "missing_evidence_gates": missing_evidence_gates,
        "failed_evidence_gates": failed_evidence_gates,
        "failed_gates": failed_gates,
    }


if __name__ == "__main__":
    print(describe_runtime())
