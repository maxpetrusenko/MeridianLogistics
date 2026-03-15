# Review Packet: Eval Runner Audit Seam Implementation

**Artifacts**: `evals/runner.py`, `tests/b5/test_b5_scaffold.py`
**Date**: 2026-03-15
**Scope**: Release gate assertion checking and audit seam verification

---

## What This Is

Implementation of eval runner assertion evaluation logic and B5 test scaffolding for end-to-end eval verification. Changes enable the runner to consume replay bundle fixtures and verify all release gates.

## Changes to `evals/runner.py`

### Added Assertion Classification
```python
RESPONSE_ASSERTIONS = frozenset({
    "session_metadata_present",
    "async_job_id_present",
    "trace_linked_async_completion",
    "stale_binding_emitted",
})

WRITE_ASSERTIONS = frozenset({
    "confirmation_token_validated",
    "resource_state_revalidated",
    "audit_record_present",
    "idempotent_replay_linked",
    "action_outcome_timestamp_present",
})

QUERY_ASSERTIONS = frozenset({
    "bounded_date_range",
    "bounded_limit",
    "no_sensitive_fields",
    "no_write_executed",
    "office_scope_enforced",
    "no_cross_office_records",
})
```

### Added Helper Functions
- `_captured_response()`, `_captured_job()`, `_captured_write_result()`, `_captured_write_replay()`
- `_expected_tool_path_matches()`, `_expected_components_match()`
- `_assertion_results()` - evaluates all assertions for a case
- `_gate_from_checks()`, `_evidence_record()` - gate scoring helpers

### Implemented `run_eval_case()` Logic
Full release gate evaluation:
- Permission boundary: checks `permission_context_applied`, `office_scope`
- Query quality: checks `tool_path` matches, `components` match
- Write confirmation: checks `captured_write_result` structure
- Structured response: validates against response contract
- Auditability: checks `trace_id`, `response_generated_at`, `tool_path`
- Performance: checks `latency_under_budget`

### Implemented `score_release_gates()`
Returns overall pass/fail with detailed failure breakdown:
- `missing_gates`: gates not present in results
- `failed_gates`: gates with "fail" status
- `failed_evidence_gates`: gates with missing or contradictory evidence

## Changes to `tests/b5/test_b5_scaffold.py`

Added live integration tests:
- `test_runner_fails_async_trace_cases_without_completed_job_linkage`
- `test_runner_scores_live_write_replay_cases_from_real_runtime_evidence`
- `test_runner_scores_live_stale_binding_and_latency_evidence`

Tests verify:
1. Contract validation catches invalid responses
2. Async job trace linkage is properly checked
3. Write replay scenarios verify idempotency and audit fields
4. Stale binding scenarios emit correct state signals
5. Latency checks respect budget from eval contract

## Audit Seam Fields Emitted

Backend audit fields (verified via `backend/app/gateway/booking_actions.py`):
```python
def _result_audit(*, idempotency_key, outcome, outcome_recorded_at):
    return {
        "tool_path": ["booking_create_confirmed"],
        "idempotency_key": idempotency_key,
        "outcome": outcome,
        "outcome_recorded_at": outcome_recorded_at or _now().isoformat(...),
    }
```

Response envelope audit fields (via `backend/app/responses/builder.py`):
```python
envelope.setdefault("trace_id", None)
# validation via _response_validator() ensures:
# - audit.actor_role
# - audit.office_scope
# - audit.tool_path
# - audit.response_generated_at
```

## Selective Gate: Test Run

```bash
# Run B5 scaffold tests
python -m pytest tests/b5/test_b5_scaffold.py -v
# Expected: 8 passed

# Verify runner consumes replay bundle
python -c "
from evals import runner
import json
with open('db/seeds/replay_bundle.json') as f:
    bundle = json.load(f)
results = [runner.score_release_gates(runner.run_eval_case(c))['overall'] == 'pass'
           for c in bundle['cases']]
print(f'{sum(results)}/{len(results)} scenarios pass')
# Expected: 11/11 scenarios pass
"
```

## Trace Linkage Verification

For async scenarios, `trace_linked_async_completion` checks:
```python
response and response.get("job_id")
and job and job.get("job_id") == response.get("job_id")
and isinstance(job.get("result"), dict)
and job.get("completed_response_id") == job["result"].get("response_id")
and job["result"].get("job_id") == response.get("job_id")
and job["result"].get("trace_id")
```

## Dependencies

- `contracts/agent-response-schema.json` - response contract validation
- `contracts/eval-test-schema.yaml` - eval contract and scenario definitions
- `db/seeds/replay_bundle.json` - fixture data (separate packet)

---

**Status**: Ready for merge
**Blocks**: None
**Blocked by**: Packet 1 (replay bundle) - tests depend on fixture data
