# Meridian Memphis PoC Security Model

## Scope boundary

Confirmed source facts:
- Scope is Memphis office only.
- Time box is a 90 day PoC.
- Accepted write scope is single-step bookings.
- Multi-office rollout, multi-step workflows, and open-ended autonomous actions are out of scope.

Proposed controls:
- Treat this security model as the minimum gate before contract and build work starts.
- Apply the same controls to chat reads, confirmation flows, and write execution paths.

## Identity and claims

Confirmed source facts:
- Requests arrive behind JWT-based auth.
- Identity context includes broker, office, and role information.
- Authorization depends on office and role boundaries.

Proposed controls:
- Require a verified execution context carrying `broker_id`, `office_id`, and `role` before any planner, tool, or write path runs.
- Reject requests with missing, expired, or malformed claims before orchestration starts.
- Treat client-supplied office or role text as untrusted; only signed claims may define scope.

## Authorization rules

Confirmed source facts:
- Brokers are restricted to assigned or office-scoped records.
- Office managers are office scoped.
- VPs may span offices where role allows it.
- Cross-office leakage is unacceptable.

Proposed controls:
- Enforce authorization in system controls, not only prompt instructions.
- Apply row and tool filters from execution context on every query and write path.
- Default to deny when role scope, office scope, or resource ownership cannot be proven.
- Keep explicit role checks for broker, office manager, and VP in a later permission contract artifact.

## Read-path safeguards

Confirmed source facts:
- Query safety is a major risk.
- Unsafe SQL, incorrect joins, and unbounded result sets are known failure modes.
- Sensitive fields must stay hidden from both display and agent access.

Proposed controls:
- Allow reads only through approved tools, curated views, or equivalent constrained query shapes.
- Enforce office and role filters before execution, not after result retrieval.
- Block raw schema exploration, arbitrary joins, unbounded scans, and unrestricted column selection.
- Apply result-size limits, timeout limits, and explicit deny handling for unsupported requests.
- Log denied reads with reason class for replay and review.

## Write-path safeguards

Confirmed source facts:
- Writes require explicit human confirmation.
- PoC write scope is single-step bookings only.
- Unauthorized action escalation is a major risk.

Proposed controls:
- Keep read and write orchestration paths separate.
- Allow writes only through allowlisted booking actions approved for PoC scope.
- Require a reviewable confirmation payload before the underlying write endpoint can execute.
- Bind the confirmation to the requesting identity, target action, and current resource state.
- Re-check authorization and state at execution time so stale or changed records cannot bypass the gate.

## Sensitive data handling

Confirmed source facts:
- Fourteen sensitive columns exist, including financial and rate data.
- Protected columns must remain hidden from display and AI access.

Proposed controls:
- Exclude sensitive columns from agent-accessible views and tool outputs by construction.
- Return only minimum required fields for each approved workflow.
- Redact sensitive fields in logs, traces, and replay artifacts unless a later controller-approved audit need says otherwise.
- Treat prompt attempts to request protected fields as policy violations, not normal queries.

## Audit and observability

Confirmed source facts:
- Complete audit trail is a PoC success signal.
- Zero cross-office breaches is a success signal.

Proposed controls:
- Record per-request identity context, intent class, tool path, policy decision, latency, and outcome.
- Record every write confirmation event with actor, target action, confirmation time, and final execution result.
- Keep replayable artifacts for denied boundary tests, successful reads, and confirmed write flows.
- Tag incidents by class: auth failure, authz failure, query safety, sensitive-field request, stale-state write, and system error.

## Abuse and failure cases

Confirmed source facts:
- Major risks include prompt injection, permission bypass, cross-office leakage, and quote expiration mid-workflow.

Proposed controls:
- Treat prompt content as hostile when it conflicts with claims, role, or tool policy.
- Deny requests that attempt cross-office comparison without authorized VP scope.
- Fail closed when tool output, claim context, or resource state is incomplete.
- Expire or invalidate booking confirmations when quote validity or shipment state changes before execution.
- Surface safe denial responses without leaking hidden fields or policy internals.

## Open security decisions

- Which Memphis roles beyond brokers are enabled on day one?
- What exact ownership rule applies for broker access: assigned records only, office records, or both by workflow?
- Does status-update write scope stay out of PoC, or move into accepted write scope later?
- Which notification channels, if any, create security obligations inside the PoC?
- What retention and redaction standard applies to replay artifacts and audit traces?
