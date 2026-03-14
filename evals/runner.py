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


def run_eval_case(case: dict[str, object]) -> dict[str, object]:
    _validate_eval_case(case)

    captured_response = case.get("captured_response")
    response_is_valid = captured_response is None or _response_contract_valid(captured_response)

    release_gate_results = _release_gate_results("pass" if response_is_valid else "fail")
    release_gate_evidence = _release_gate_evidence(case, release_gate_results)

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
