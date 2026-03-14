# B5 Eval Harness Implementation Brief

## Scope boundary

This brief covers only the Memphis office, 90 day PoC, read-query flows, and single-step booking evaluation. It implements the accepted contracts [contracts/eval-test-schema.yaml](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/contracts/eval-test-schema.yaml) and [contracts/agent-response-schema.json](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/contracts/agent-response-schema.json). Status-update writes, notification behavior, multi-office rollout, and multi-step workflows stay out of scope.

## Fixture and replay responsibilities

- Build deterministic replay bundles shaped exactly like `contracts/eval-test-schema.yaml`.
- Maintain Memphis-scoped fixture references for broker, office-manager, and boundary-role scenarios already accepted in `eval-plan.md`.
- Keep prompts, permission-context refs, expected gates, and expected response components stable so replay results are comparable across runs.
- Treat fixture contents as minimal and redacted; no speculative production-sized dataset design in this brief.

## Schema-validation responsibilities

- Validate every replay case against `contracts/eval-test-schema.yaml` before execution.
- Validate every captured system response against `contracts/agent-response-schema.json`.
- Fail fast on malformed case metadata, missing assertions, invalid response components, or response/intent mismatches.
- Record schema-validation failures as first-class eval failures, not test harness noise.

## Release-gate responsibilities

- Enforce the accepted release-gate classes from `eval-plan.md`: permission boundary, query quality, write confirmation, structured response, auditability, and performance.
- Require replay output to preserve gate-relevant evidence: expected gate result, safety assertions, pass/fail criteria, and release-gate flag.
- Keep write evaluation constrained to confirmation-required and confirmed single-step booking flows only.
- Block release advancement when any in-scope gate fails or required evidence is missing.

## Human review and UAT support

- Export replay outcomes in a reviewable format that maps each scenario to prompt, actor role, gate result, and failure class.
- Support Memphis broker UAT and boundary-role review by linking human findings back to the same scenario ids used in replay.
- Preserve enough context for reviewers to confirm denial reasons, confirmation behavior, and structured-response validity without reading raw internals.
- Keep human review focused on accepted PoC workflows only.

## Acceptance checks

- `b5-eval-harness-implementation-brief.md` cites the exact accepted contracts it implements:
  - [contracts/eval-test-schema.yaml](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/contracts/eval-test-schema.yaml)
  - [contracts/agent-response-schema.json](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/contracts/agent-response-schema.json)
- Replay harness responsibilities cover fixture loading, case validation, execution, response validation, and gate scoring.
- Human review support is explicit for broker UAT and boundary-role checks.
- Scope remains Memphis-only and PoC-only.
- No speculative dataset expansion or out-of-scope workflows appear in the brief.

## Open implementation decisions

- Exact replay runner shape: single command runner or split validation and execution phases.
- Storage location and retention shape for replay outputs and human-review annotations.
- Whether boundary-role scenarios use synthetic-only fixtures or a separate controlled tenant fixture set.
- Exact packaging of performance evidence per scenario family versus one aggregate report.
