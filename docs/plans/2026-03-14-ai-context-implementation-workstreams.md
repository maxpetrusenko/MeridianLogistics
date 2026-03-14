# AI Context Implementation Workstreams

## Purpose

Translate `meridian-logistics-ai-context.md` into the next concrete implementation slices that remain after controller hardening, backend/orchestrator scaffolding, frontend renderer recovery, and eval harness repair.

## Current Repo Truth

- Controller hardening is complete and terminal state is `DONE`.
- `B1`, `B2+B3`, `B4`, and `B5` all have implementation evidence in the repo.
- `frontend/src/App.jsx` now renders the accepted response contract and current fixtures validate against `contracts/agent-response-schema.json`.
- The expanded AI context doc defines product, UI, action, memory, async, observability, and idempotency behavior that is broader than what the current contracts and runtime encode.

## Remaining Workstreams

### 1. Frontend Shell And Context Binding

- Owner: Frontend structured chat engineer
- Objective: Move from a contract-demo renderer to a real chat surface with explicit panel state, context badges, stale-context handling, and chat-to-screen coordination.
- In-scope artifacts:
  - `frontend/src/App.jsx`
  - `frontend/src/main.jsx`
  - `frontend/src/app.css`
  - new frontend state helpers if needed under `frontend/src/`
  - frontend tests under `frontend/tests/`
- Repo gap:
  - current frontend shows fixture tabs, not a top-menu launch model
  - no explicit `panel_state`, `conversation_scope`, `context_binding_state`, or `screen_sync_state`
  - no chat-plus-main-sync or pinned-result behavior
- Success check:
  - chat shell supports `closed | peek | open | expanded`
  - bound context is visibly rendered and can become `stale`
  - advisory responses remain panel-only
  - only structured actions can request main-surface sync
  - frontend tests cover stale-context and response-surface routing behavior
- Why next:
  - the expanded spec is now frontend-heavy and current UI only proves contract rendering, not real interaction semantics

### 2. Canonical Action Contract Alignment

- Owner: Backend integration engineer plus frontend structured chat engineer
- Objective: Promote the action object from a lightweight response button shape into the shared contract described in the AI context doc.
- In-scope artifacts:
  - `contracts/agent-response-schema.json`
  - `contracts/tool-schema.yaml`
  - `backend/app/gateway/write_gateway.py`
  - `backend/app/responses/builder.py`
  - `frontend/src/response-model.js`
  - contract validation tests
- Repo gap:
  - current action payloads are minimal and frontend-local
  - canonical fields like `resource_type`, `resource_id`, `permission_scope`, `ui_behavior`, and `idempotency_key` are not fully propagated end-to-end
  - chat and main-surface actions are not yet modeled as one shared contract
- Success check:
  - write-capable actions carry confirmation token plus idempotency metadata
  - response builder emits one canonical action envelope
  - frontend renders only server-declared actions
  - contract tests fail on missing canonical action metadata
- Why next:
  - this is the shared seam between UI, gateway, and policy; leaving it underspecified will reintroduce drift

### 3. Session Memory, Resource Binding, And Async Job State

- Owner: Orchestrator architect plus backend integration engineer
- Objective: Encode session scope, resource binding, and background job state so the chat panel can survive reopen, stale context, and async reads without guessing.
- In-scope artifacts:
  - `architecture-overview.md`
  - `backend/app/orchestrator/graph.py`
  - `backend/app/contracts.py`
  - `backend/app/api/router.py`
  - new or updated contracts if required
  - eval fixtures for async and stale-state flows
- Repo gap:
  - no explicit session-memory envelope or resource-bound thread model in runtime code
  - no visible async job contract for long-running reads or pending write execution states
  - no canonical stale-binding transition behavior
- Success check:
  - request envelope includes trusted session and resource binding fields
  - async read jobs expose stable `job_id`, status, and result linkage
  - stale resource changes invalidate actionability without losing history
  - eval coverage exists for reopen, stale-resource, and async-complete flows
- Why next:
  - the expanded UX depends on these state transitions; without them the frontend shell becomes cosmetic

### 4. Observability, Replay, And Idempotent Write Protection

- Owner: QA and eval lead plus backend integration engineer
- Objective: Close the gap between current replay coverage and the new per-request trace, duplicate-protection, and failure-state requirements.
- In-scope artifacts:
  - `eval-plan.md`
  - `contracts/eval-test-schema.yaml`
  - `evals/runner.py`
  - `backend/app/gateway/write_gateway.py`
  - `backend/app/orchestrator/graph.py`
  - release-gate tests
- Repo gap:
  - replay coverage exists, but the AI context doc adds stronger trace fields, failure classes, and duplicate-protection expectations
  - exact idempotent outcome behavior is not yet enforced through evals
  - replay library does not yet prove stale-resource denial, uncertain write retry, and chat-to-screen sync attribution
- Success check:
  - replay fixtures cover successful booking, expired quote, stale-resource write denial, uncertain write retry, and protected-field denial
  - release gating fails when required observability fields are missing
  - write gateway rejects stale or conflicting idempotency submissions deterministically
- Why next:
  - this is the enforcement layer that keeps the broader product surface safe as more UX semantics go live

### 5. Decision Lockdown Before Broader Product Build

- Owner: Controller plus product and architecture owners
- Objective: Convert the remaining open decisions into explicit locked choices before broadening implementation scope.
- In-scope artifacts:
  - `decisions.md`
  - `architecture-overview.md`
  - `eval-plan.md`
  - any contract file affected by the final decision
- Remaining open items:
  - exact Memphis tenant data constraints
  - exact endpoint-to-workflow mapping for `single_step_booking`
  - exact replay sample sizes per critical scenario
  - exact replay retention and redaction policy
  - exact latency split across orchestration, tool execution, and response shaping
- Success check:
  - each item above is either locked in docs or explicitly deferred with rationale and no hidden dependency
  - no implementation lane depends on an unstated assumption in these areas
- Why next:
  - current repo truth is strong on scaffolding and control semantics, but these gaps still block confident product-surface expansion

## Recommended Execution Order

1. Canonical Action Contract Alignment
2. Frontend Shell And Context Binding
3. Session Memory, Resource Binding, And Async Job State
4. Observability, Replay, And Idempotent Write Protection
5. Decision Lockdown Before Broader Product Build

## Not In Scope For These Workstreams

- framework migration
- global flag enablement
- multi-office rollout
- general status-update writes
- notification-channel implementation
- multi-step workflow execution
