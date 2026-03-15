# B2+B3 Backend Orchestrator Implementation Brief

## Scope boundary

- Memphis office only
- 90 day PoC only
- In scope: approved read queries plus single-step booking with explicit confirmation
- Out of scope: multi-office rollout, multi-step workflows, status-update writes, notification dispatch, open-ended autonomous actions

## Endpoint/write-gateway responsibilities

- Map approved write intent `booking_create_confirmed` to the existing write gateway path only after confirmation-token validation
- Re-check trusted permission context, office scope, and current resource state at execution time
- Keep request normalization, endpoint mapping, retry handling, and outcome classification inside the backend gateway layer
- Reject unsupported write shapes before endpoint invocation
- Emit a stable execution result for the response-shaping lane and audit trail

## Read/write orchestration responsibilities

- Classify read intent vs write intent before any tool or endpoint selection
- Route reads only to allowlisted read tools from `contracts/tool-schema.yaml`
- Inject trusted permission context below prompt and tool selection on every path
- Keep read orchestration separate from write orchestration so confirmation and audit gates cannot drift
- Build a reviewable write summary before gateway execution and halt until explicit confirmation arrives
- Deny on missing context, scope mismatch, protected-field request, unsupported workflow, or stale confirmation state

## Contract integration points

- `contracts/tool-schema.yaml`
  - tool family selection, blocked query shapes, write-tool preconditions
- `contracts/permission-context.json`
  - trusted claims, office scope, role shape, deny behavior
- `contracts/agent-response-schema.json`
  - response envelope for read results, denials, confirmation-required states, submitted writes, and errors
- Upstream docs:
  - `architecture-overview.md` for system boundary and flow split
  - `security-model.md` for safeguards and audit requirements

## Confirmation and audit flow

1. Classify request as write-capable only if it matches approved single-step booking scope.
2. Resolve trusted execution context from signed claims.
3. Build confirmation payload with actor, office, quote, carrier, pickup date, and expiry conditions.
4. Return confirmation-required response without invoking the write endpoint.
5. On confirmation, revalidate permission context, resource state, and confirmation token.
6. Execute the gateway call.
7. Emit audit record with requester, confirmer, tool path, endpoint action, latency, and outcome class.

## Acceptance checks

- Read and write paths stay separated in the brief
- Only approved PoC write behavior is described
- Backend responsibilities align with `contracts/tool-schema.yaml` and `contracts/permission-context.json`
- Confirmation and audit gates are explicit
- Unsupported scopes remain explicitly out
- Next consumer can implement gateway/orchestration without inventing new contract semantics

## Open implementation decisions

- Exact single-step booking payload shape behind `booking_create_confirmed`
- Final broker ownership rule: `assigned_only` vs `assigned_or_office`
- Whether `office_scope` is always implicit from trusted context or sometimes user-selectable within allowed scope
- Whether `action_id` values in response payloads map directly to tool ids or to gateway action aliases
- Final treatment of office-manager and VP review scenarios in runtime vs evaluation only
