# Meridian Memphis PoC PRD

## Document Status

- Owner: Product and PM owner
- Status: draft
- Scope boundary: Memphis office only, 90 day PoC
- Source authority: `source-brief.md`, `decisions.md`
- Quarantined source excluded: `meridian-logistics-deck-summary.md`

## Confirmed Source Facts

- Meridian is a mid market freight brokerage using FreightView as the current in-house platform.
- The current workflow spans six modules and heavy CRUD navigation.
- The PoC target is a single chat interface for the Memphis office only.
- The 90 day PoC scope is read queries plus single-step bookings.
- The current platform exposes 34 REST endpoints behind JWT auth.
- Access boundaries depend on office and role context.
- Sensitive fields must stay hidden.
- Query safety and confirmation before writes are hard constraints.

## Problem

Brokers spend too much time moving across FreightView screens for routine lookup and action tasks. Analytics requests are backlogged, and natural-language query quality is currently unreliable. Meridian needs a constrained assistant that reduces lookup time without creating data leakage, unsafe SQL, or uncontrolled write behavior.

## Product Goal

Deliver a Memphis-only conversational assistant that lets authorized users answer operational questions and complete single-step bookings faster than the current multi-screen workflow, while preserving office-scoped permissions, sensitive-field protection, and explicit write confirmation.

## Users

### In Scope

- Brokers in the Memphis office

### Boundary and Review Users

- Office managers for permission validation and review
- VP-level access as a role-boundary acceptance scenario

## Jobs To Be Done

1. Ask operational questions without opening multiple FreightView modules.
2. Retrieve ranked, filtered, and aggregated shipment or carrier information safely.
3. Complete an eligible single-step booking from chat with explicit confirmation.
4. Trust that the assistant will not expose another office's data or sensitive rate fields.

## In Scope For This PoC

### Read Workflows

- Aggregation queries, such as transit-time summaries
- Ranking and filtering queries, such as carrier performance lists
- Multi-table operational lookups, such as in-transit shipment checks
- Role-boundary validation for office-scoped visibility

### Write Workflows

- Single-step booking only
- Human confirmation required before the write is executed
- Full audit trail expected for each completed action

## Out Of Scope For This PoC

- Multi-office rollout
- Multi-step workflow orchestration
- General status-update writes as an accepted PoC deliverable
- Notification-channel implementation beyond what is required to define future scope
- Open-ended autonomous actions
- Admin or back-office tooling changes

## Workflow Coverage

### Must Work

1. User asks a supported read question and receives a correct, office-scoped response.
2. User requests a supported booking action and receives a confirmation step before execution.
3. System denies or scopes requests correctly when role or office boundaries do not allow access.

### Must Not Happen

1. Cross-office data leakage
2. Exposure of protected columns
3. Unbounded or destructive query execution
4. Write execution without an explicit confirmation step

## Permission Rules

- JWT context includes broker, office, and role information.
- Broker access is limited to assigned or office-scoped records.
- Office-manager access is office scoped.
- VP access may span offices, but only where explicitly permitted by role.
- Every query and action must enforce office and role context before execution.
- Sensitive columns remain hidden regardless of natural-language request.

## Success Metrics

- 90% or better valid SQL generation rate
- Less than 500 ms response time for standard queries
- Zero cross-office data breaches
- 95% or better broker satisfaction with the chat interface
- Coverage for all representative read-query patterns in the source brief
- Complete audit trail for each write action

## Functional Requirements

### Read Experience

- Accept natural-language prompts for supported operational questions
- Return correct results for approved query patterns
- Enforce permission context on every request
- Prevent hallucinated-column, unsafe-join, and unbounded-query failures from reaching users

### Booking Experience

- Support eligible single-step bookings only
- Show enough booking context for the user to review before confirmation
- Require explicit confirmation before calling the underlying write path
- Record who confirmed the action and when

### Response Contract

- Responses may need structured presentation, but the exact UI contract is deferred to later artifacts
- This PRD requires the product to support structured operational answers, not plain chat only

## Non Goals

- Finalize system architecture
- Choose specific orchestration technology
- Define endpoint-to-tool mappings
- Define final response schema
- Define eval dataset format

These move to architecture, security, contract, and eval artifacts.

## Risks

- SQL accuracy remains below production quality
- Permission checks drift between query and action paths
- Quote or shipment state changes between request and booking confirmation
- Scope creep expands the PoC beyond Memphis and single-step bookings
- Unclear notification and write-action boundaries create churn in later artifacts

## Dependencies

- Accepted `source-brief.md`
- Controller decisions in `decisions.md`
- Follow-on `architecture-overview.md`
- Follow-on `security-model.md`
- Follow-on `eval-plan.md`
- Later contract artifacts for response schema, permission context, and tool definitions

## Open Decisions Needed From Follow-On Artifacts

- Which Memphis user roles are fully enabled in the PoC UI
- Which booking cases qualify as single-step
- Whether status-update writes are future scope or a stretch goal
- Which notification channels, if any, are in PoC scope
- Exact evaluation thresholds beyond the source-level success signals

## Acceptance Criteria

1. The document states Memphis-only, 90-day scope.
2. The document limits accepted write scope to single-step bookings with confirmation.
3. User roles, jobs to be done, workflow coverage, permission rules, and non-goals are explicit.
4. Success metrics are stated without relying on quarantined deck material.
5. Risks and dependencies for architecture, security, and eval follow-on work are explicit.
6. Proposed architecture choices remain outside the confirmed-source section.
