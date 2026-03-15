# Meridian Memphis PoC Architecture Overview

## Scope boundary

Confirmed source facts:
- Scope is Memphis office only.
- Time box is a 90 day PoC.
- Accepted product scope is read queries plus single-step bookings.
- Multi-office rollout, multi-step workflows, and open-ended autonomous actions are out of scope.

Proposed architecture choices:
- Treat this document as the architecture boundary for PoC acceptance only.
- Leave detailed API, schema, and UI contracts to later contract artifacts.

## Trusted inputs and identities

Confirmed source facts:
- Requests arrive with JWT-based identity and role context.
- Authorization depends on broker, office, and role boundaries.
- Sensitive fields must stay hidden from both display and agent access.

Proposed architecture choices:
- Normalize each request into a trusted execution context carrying `broker_id`, `office_id`, and `role`.
- Make that context mandatory for every query tool and every write action.
- Reject any execution path that cannot prove identity context before planning or tool execution.

## Major components

Confirmed source facts:
- FreightView is the current system of record.
- Current platform exposes 34 REST endpoints.
- Data lives in PostgreSQL and current workflows are CRUD-heavy.
- Structured responses are required for the product surface.

Proposed architecture choices:
- Chat application layer for user interaction and structured response rendering.
- Gateway/orchestrator layer that separates read planning from write execution.
- Safe query layer over curated database views or equivalent scoped tools.
- Action gateway over existing REST endpoints for approved write operations.
- Audit/eval layer capturing prompts, tool calls, confirmations, outcomes, and replay artifacts.

## Read path

Confirmed source facts:
- Read workflows include aggregation, ranking/filtering, and multi-table operational lookups.
- Query accuracy and unbounded query risk are known failure modes.

Proposed architecture choices:
- User request enters the orchestrator with trusted identity context.
- Orchestrator routes only to approved read tools backed by curated views or constrained SQL shapes.
- Query generation or selection must apply office and role scoping before execution.
- Results are transformed into a structured response payload for tables, metrics, or timelines.
- Read-path logging records prompt, scoped tool choice, execution time, and result classification for later eval.

## Write path

Confirmed source facts:
- Accepted PoC write scope is single-step bookings only.
- Writes require explicit human confirmation.

Proposed architecture choices:
- Write intents are classified separately from read intents and never share the same execution path.
- The system assembles a reviewable action summary before any write call.
- User confirmation becomes a required gate artifact before the action gateway calls the underlying endpoint.
- Completed writes emit audit records linking requester, confirmation, target action, and outcome.

## Permission and safety controls

Confirmed source facts:
- Cross-office leakage is unacceptable.
- Sensitive columns must remain hidden.
- Unsafe SQL, incorrect joins, and unbounded queries are known risks.

Proposed architecture choices:
- Enforce office and role filters in the execution context, not only in prompt text.
- Restrict read access to allowlisted tools, views, joins, and result limits.
- Keep write tools allowlisted and limited to approved PoC actions.
- Apply explicit deny behavior for cross-office requests, protected fields, and unsupported write intents.
- Keep read and write orchestration separated so confirmation and permission logic cannot drift.

## Structured response surface

Confirmed source facts:
- Product cannot be plain chat only.
- Structured response components are required.
- Some operations (analytics refreshes, bulk processing) take longer than acceptable request timeout.

Proposed architecture choices:
- Support a response envelope that can render tables, metric cards, timelines, action buttons, and confirmation cards.
- Keep business logic independent from final frontend schema details until the contract artifact is written.
- Require every write-capable response to use an explicit confirmation card or equivalent gated interaction.
- Async jobs API for long-running operations with secure poll-token-based status checking.

### Async Jobs Layer

Long-running operations spawn background jobs:
- Chat response includes `job_id` and opaque `job_poll_token`
- Frontend polls `/jobs/{job_id}?job_poll_token={token}` until completion
- Job states: `queued` -> `running` -> `succeeded`/`failed`/`cancelled`/`expired`
- Completion promotion only succeeds if session state matches job creation context
- See `docs/api/async-jobs.md` for complete API documentation

## Observability and evaluation hooks

Confirmed source facts:
- Success signals include valid SQL rate, sub-500 ms standard query latency, zero cross-office breaches, and complete audit trail for actions.

Proposed architecture choices:
- Capture per-request traces for prompt class, tool path, latency, scoped identity, and outcome.
- Persist replayable artifacts for representative read cases, denied boundary tests, and booking confirmation flows.
- Tag failures by class: permission, query safety, latency, orchestration, and write confirmation.
- Feed those artifacts into the later eval plan rather than embedding detailed thresholds here.

## Open architecture questions

- Which Memphis roles are enabled in the PoC UI on day one beyond brokers?
- Which booking shapes count as valid single-step bookings?
- Does status-update write scope stay deferred or move into PoC acceptance later?
- Which notification channels, if any, must exist in the write path for the PoC?
- What exact boundary exists between the safe query layer and existing REST-backed read endpoints?
