# Meridian Front + Backend Productization Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the current Meridian Memphis PoC scaffold into a working end-to-end conversational product slice with real frontend shell state, real backend chat/session endpoints, safe read execution, confirmed booking execution, async job handling, and replayable observability.

**Architecture:** Keep the current contract-first shape. Frontend stays a React SPA that renders only server-declared response envelopes. Backend stays a FastAPI service that separates read routing, write confirmation, and controller logic, but now grows real session, action, and job APIs on top of the accepted contracts.

**Tech Stack:** FastAPI, Python 3.11, React 19, Vite, PostgreSQL, Redis, JSON Schema, Node test runner, unittest/contract scripts

---

## Current Repo Status

What is already real enough to build on:

- accepted product, architecture, security, and eval docs
- accepted response, tool, permission, eval, and checkpoint contracts
- frontend response renderer that can render accepted response fixtures
- backend response-envelope validation
- backend write-gateway validation for confirmation token and idempotency-key presence
- controller checkpoint and routing hardening

What is still scaffold / placeholder:

- no real chat/session API
- no real read endpoint beyond health route
- no real session memory or resource binding model
- no async job lifecycle
- no live frontend chat shell or network state
- no real DB-backed read tools wired into API routes
- no real booking execution persistence or stale-state recheck
- no replay-grade observability fields flowing end to end

## Task 1: Lock Working Scope And Delivery Order

**Files:**
- Modify: `decisions.md`
- Modify: `dispatch-board.md`
- Modify: `artifact-ledger.md`
- Reference: `prd.md`
- Reference: `architecture-overview.md`
- Reference: `security-model.md`
- Reference: `eval-plan.md`

**Step 1: Record the next implementation wave**

Write the next owned wave in `dispatch-board.md` for:
- frontend shell and context binding
- session/resource binding and async job state
- backend read/write API productization
- replay/observability closure

**Step 2: Lock the sequencing**

Record the required order:
1. frontend shell state
2. backend session and response APIs
3. read execution path
4. write execution path
5. async jobs
6. observability and replay gate

**Step 3: Run doc consistency check**

Run:
```bash
git diff -- decisions.md dispatch-board.md artifact-ledger.md
```

Expected:
- wave ownership and ordering are explicit
- no new out-of-scope features appear

**Step 4: Commit**

```bash
git add decisions.md dispatch-board.md artifact-ledger.md
git commit -m "docs: lock next front and backend delivery waves"
```

## Task 2: Add Real Chat Session Contracts

**Files:**
- Create: `backend/app/api/schemas/chat.py`
- Modify: `backend/app/contracts.py`
- Modify: `contracts/agent-response-schema.json`
- Modify: `contracts/eval-test-schema.yaml`
- Test: `tests/b2b3/test_b2b3_scaffold.py`
- Test: `contracts/tests/validate_active_contracts.py`

**Step 1: Write the failing backend contract test**

Extend `tests/b2b3/test_b2b3_scaffold.py` with assertions for:
- `session_id`
- `conversation_scope`
- `context_binding_state`
- optional `active_resource`
- `job_id` for async responses

**Step 2: Run the failing test**

Run:
```bash
python3 -m unittest tests/b2b3/test_b2b3_scaffold.py
```

Expected:
- FAIL because the schema and helper payloads do not include the new fields yet

**Step 3: Define request/response schemas**

Add `backend/app/api/schemas/chat.py` with Pydantic models for:
- `ChatRequest`
- `ChatResponseEnvelope`
- `ChatSessionSummary`
- `AsyncJobEnvelope`

Update contracts so response metadata can carry:
- `session_id`
- `conversation_scope`
- `context_binding_state`
- `screen_sync_state`
- `job_id`

**Step 4: Update contract validation script**

Teach `contracts/tests/validate_active_contracts.py` to validate:
- read responses with session metadata
- async pending responses
- stale-context responses

**Step 5: Re-run verification**

Run:
```bash
python3 -m unittest tests/b2b3/test_b2b3_scaffold.py
python3 contracts/tests/validate_active_contracts.py
```

Expected:
- PASS with new contract metadata enforced

**Step 6: Commit**

```bash
git add backend/app/api/schemas/chat.py backend/app/contracts.py contracts/agent-response-schema.json contracts/eval-test-schema.yaml tests/b2b3/test_b2b3_scaffold.py contracts/tests/validate_active_contracts.py
git commit -m "feat: add chat session and async response contracts"
```

## Task 3: Expose Product API Routes

**Files:**
- Modify: `backend/app/api/router.py`
- Create: `backend/app/api/routes/chat.py`
- Create: `backend/app/api/routes/sessions.py`
- Create: `backend/app/api/routes/jobs.py`
- Modify: `backend/app/main.py`
- Test: `tests/b2b3/test_b2b3_scaffold.py`

**Step 1: Write failing route tests**

Add route-level tests for:
- `POST /chat`
- `GET /sessions/{session_id}`
- `GET /jobs/{job_id}`

Verify:
- JSON shape matches contract-backed schema
- unsupported payloads fail closed

**Step 2: Run the failing tests**

Run:
```bash
python3 -m unittest tests/b2b3/test_b2b3_scaffold.py
```

Expected:
- FAIL because only the health route exists now

**Step 3: Implement routes**

Add routes that:
- accept trusted context fields
- call orchestrator services
- return contract-valid payloads
- return pending responses for long-running reads

**Step 4: Wire the router**

Include the new route modules in `backend/app/api/router.py`.

**Step 5: Re-run verification**

Run:
```bash
python3 -m unittest tests/b2b3/test_b2b3_scaffold.py
python3 -c "from backend.app.main import app; print(app.routes)"
```

Expected:
- tests pass
- app contains chat, session, and job routes

**Step 6: Commit**

```bash
git add backend/app/api/router.py backend/app/api/routes/chat.py backend/app/api/routes/sessions.py backend/app/api/routes/jobs.py backend/app/main.py tests/b2b3/test_b2b3_scaffold.py
git commit -m "feat: add chat session and job api routes"
```

## Task 4: Implement Session Memory And Resource Binding

**Files:**
- Create: `backend/app/session/store.py`
- Create: `backend/app/session/models.py`
- Modify: `backend/app/orchestrator/graph.py`
- Modify: `backend/app/db/context.py`
- Modify: `backend/app/config.py`
- Test: `tests/b2b3/test_b2b3_scaffold.py`

**Step 1: Write failing tests for state transitions**

Cover:
- create session on first prompt
- preserve session on second prompt
- bind active resource after detail request
- mark binding stale when resource fingerprint changes

**Step 2: Run the failing tests**

Run:
```bash
python3 -m unittest tests/b2b3/test_b2b3_scaffold.py
```

Expected:
- FAIL because no session store or stale-binding logic exists

**Step 3: Add session models**

Implement minimal session state:
- `session_id`
- trusted actor scope
- bound resource snapshot
- stale flag
- prior response linkage

Use in-memory store first with config seam for Redis later.

**Step 4: Teach orchestrator graph about session state**

Replace the static graph-only behavior with helpers that:
- read session state
- classify intent
- attach binding metadata
- emit stale-state response modes

**Step 5: Re-run verification**

Run:
```bash
python3 -m unittest tests/b2b3/test_b2b3_scaffold.py
python3 contracts/tests/validate_active_contracts.py
```

Expected:
- PASS with session and stale-binding behavior enforced

**Step 6: Commit**

```bash
git add backend/app/session/store.py backend/app/session/models.py backend/app/orchestrator/graph.py backend/app/db/context.py backend/app/config.py tests/b2b3/test_b2b3_scaffold.py
git commit -m "feat: add session memory and resource binding state"
```

## Task 5: Build Safe Read Tool Execution

**Files:**
- Modify: `backend/app/tools/registry.py`
- Create: `backend/app/tools/read_tools.py`
- Modify: `backend/app/db/context.py`
- Modify: `backend/app/responses/builder.py`
- Modify: `db/views.sql`
- Test: `tests/b1/test_b1_scaffold.py`
- Test: `tests/b2b3/test_b2b3_scaffold.py`

**Step 1: Write failing read-path tests**

Cover:
- aggregation query
- ranking query
- shipment detail query
- cross-office denial
- protected-field denial

**Step 2: Run the failing tests**

Run:
```bash
python3 -m unittest tests/b1/test_b1_scaffold.py
python3 -m unittest tests/b2b3/test_b2b3_scaffold.py
```

Expected:
- FAIL because registry and DB context are not executing real tool-backed reads

**Step 3: Implement allowlisted read tools**

Add explicit Python tool functions backed by curated query shapes for:
- transit metrics
- carrier ranking
- shipment exception detail

Make the registry map intent keys to tool functions and parameter validators.

**Step 4: Emit structured response envelopes**

Update `backend/app/responses/builder.py` so read results generate:
- metric cards
- tables
- timelines
- safe denial blocks

**Step 5: Re-run verification**

Run:
```bash
python3 -m unittest tests/b1/test_b1_scaffold.py
python3 -m unittest tests/b2b3/test_b2b3_scaffold.py
python3 contracts/tests/validate_active_contracts.py
```

Expected:
- PASS with read path producing contract-valid structured results

**Step 6: Commit**

```bash
git add backend/app/tools/registry.py backend/app/tools/read_tools.py backend/app/db/context.py backend/app/responses/builder.py db/views.sql tests/b1/test_b1_scaffold.py tests/b2b3/test_b2b3_scaffold.py
git commit -m "feat: implement allowlisted read tool execution"
```

## Task 6: Finish Write Confirmation And Execution Path

**Files:**
- Modify: `backend/app/gateway/write_gateway.py`
- Create: `backend/app/gateway/idempotency_store.py`
- Create: `backend/app/gateway/booking_actions.py`
- Modify: `backend/app/responses/builder.py`
- Modify: `contracts/tool-schema.yaml`
- Test: `tests/b2b3/test_b2b3_scaffold.py`
- Test: `contracts/tests/validate_active_contracts.py`

**Step 1: Write failing write-path tests**

Cover:
- confirmation-required response
- successful confirmed booking
- expired confirmation denial
- stale-resource denial
- duplicate idempotency-key replay returns deterministic prior outcome

**Step 2: Run the failing tests**

Run:
```bash
python3 -m unittest tests/b2b3/test_b2b3_scaffold.py
python3 contracts/tests/validate_active_contracts.py
```

Expected:
- FAIL because the gateway only validates fields and does not persist or replay outcomes

**Step 3: Implement booking action service**

Add services that:
- re-check permission scope
- re-check current resource fingerprint
- store idempotent outcome by key
- return success, denied, or stale-state response payloads

**Step 4: Update response builder**

Ensure write responses distinguish:
- `write_confirmation_required`
- `write_submitted`
- `write_denied`
- `write_completed`

**Step 5: Re-run verification**

Run:
```bash
python3 -m unittest tests/b2b3/test_b2b3_scaffold.py
python3 contracts/tests/validate_active_contracts.py
```

Expected:
- PASS with deterministic idempotent behavior and explicit stale denial

**Step 6: Commit**

```bash
git add backend/app/gateway/write_gateway.py backend/app/gateway/idempotency_store.py backend/app/gateway/booking_actions.py backend/app/responses/builder.py contracts/tool-schema.yaml tests/b2b3/test_b2b3_scaffold.py contracts/tests/validate_active_contracts.py
git commit -m "feat: implement confirmed booking execution flow"
```

## Task 7: Add Async Read Jobs

**Files:**
- Create: `backend/app/jobs/store.py`
- Create: `backend/app/jobs/models.py`
- Modify: `backend/app/orchestrator/graph.py`
- Modify: `backend/app/api/routes/jobs.py`
- Modify: `backend/app/responses/builder.py`
- Test: `tests/b5/test_b5_scaffold.py`
- Test: `tests/b2b3/test_b2b3_scaffold.py`

**Step 1: Write failing async job tests**

Cover:
- long-running read returns `job_id`
- job lookup returns `pending`
- completed job links to prior response envelope
- stale session does not lose history

**Step 2: Run the failing tests**

Run:
```bash
python3 -m unittest tests/b5/test_b5_scaffold.py
python3 -m unittest tests/b2b3/test_b2b3_scaffold.py
```

Expected:
- FAIL because no job lifecycle exists

**Step 3: Implement job store**

Add minimal async job persistence with:
- `job_id`
- `session_id`
- `status`
- `created_at`
- `completed_response_id`

**Step 4: Wire pending/completed responses**

Teach chat route and builder to emit:
- pending message block plus job metadata
- completed response lookup

**Step 5: Re-run verification**

Run:
```bash
python3 -m unittest tests/b5/test_b5_scaffold.py
python3 -m unittest tests/b2b3/test_b2b3_scaffold.py
```

Expected:
- PASS with job lifecycle covered

**Step 6: Commit**

```bash
git add backend/app/jobs/store.py backend/app/jobs/models.py backend/app/orchestrator/graph.py backend/app/api/routes/jobs.py backend/app/responses/builder.py tests/b5/test_b5_scaffold.py tests/b2b3/test_b2b3_scaffold.py
git commit -m "feat: add async read job lifecycle"
```

## Task 8: Replace Fixture Demo With Real Chat Shell

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/main.jsx`
- Modify: `frontend/src/app.css`
- Create: `frontend/src/chat-client.js`
- Create: `frontend/src/chat-state.js`
- Create: `frontend/src/components/ChatShell.jsx`
- Create: `frontend/src/components/ContextBadge.jsx`
- Create: `frontend/src/components/Composer.jsx`
- Test: `frontend/tests/response-model.test.js`
- Create: `frontend/tests/chat-shell.test.js`

**Step 1: Write the failing frontend tests**

Cover:
- shell states `closed | peek | open | expanded`
- stale context badge rendering
- pending response while prior confirmed state stays visible
- advisory response stays panel-only
- structured action with `ui_behavior` can request screen sync

**Step 2: Run the failing tests**

Run:
```bash
cd frontend
npm test
```

Expected:
- FAIL because the app is still a fixture-tab renderer

**Step 3: Add client and local state**

Implement:
- API fetch layer
- panel state machine
- current session state
- current bound resource state
- current active response and prior confirmed response

**Step 4: Break App into real shell components**

Move away from one large renderer into:
- shell container
- composer
- context badge
- response region
- main-surface sync indicator

**Step 5: Re-run verification**

Run:
```bash
cd frontend
npm test
npm run build
```

Expected:
- PASS with real shell behavior and green production build

**Step 6: Commit**

```bash
git add frontend/src/App.jsx frontend/src/main.jsx frontend/src/app.css frontend/src/chat-client.js frontend/src/chat-state.js frontend/src/components/ChatShell.jsx frontend/src/components/ContextBadge.jsx frontend/src/components/Composer.jsx frontend/tests/response-model.test.js frontend/tests/chat-shell.test.js
git commit -m "feat: build real chat shell and context binding ui"
```

## Task 9: Wire Action Execution And Screen Sync

**Files:**
- Modify: `frontend/src/response-model.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/chat-state.js`
- Test: `frontend/tests/chat-shell.test.js`
- Test: `frontend/tests/response-model.test.js`

**Step 1: Write failing action-routing tests**

Cover:
- confirm action posts to backend with idempotency key
- stale action disables itself with server-declared reason
- success mode `sync_chat_and_screen` triggers sync state
- failure mode `stay_in_confirmation` preserves confirmation card

**Step 2: Run the failing tests**

Run:
```bash
cd frontend
npm test
```

Expected:
- FAIL because actions are still fixture-local

**Step 3: Implement action dispatch**

Use only server-declared action metadata:
- endpoint
- permission scope display
- confirmation token
- idempotency key
- `ui_behavior`

**Step 4: Re-run verification**

Run:
```bash
cd frontend
npm test
npm run build
```

Expected:
- PASS with live action execution wiring

**Step 5: Commit**

```bash
git add frontend/src/response-model.js frontend/src/App.jsx frontend/src/chat-state.js frontend/tests/chat-shell.test.js frontend/tests/response-model.test.js
git commit -m "feat: wire chat actions to backend execution and screen sync"
```

## Task 10: Close Observability, Replay, And Release Gates

**Files:**
- Modify: `eval-plan.md`
- Modify: `evals/runner.py`
- Modify: `contracts/eval-test-schema.yaml`
- Modify: `backend/app/gateway/write_gateway.py`
- Modify: `backend/app/orchestrator/graph.py`
- Test: `tests/b5/test_b5_scaffold.py`

**Step 1: Write failing replay tests**

Cover required scenarios:
- successful booking
- expired quote
- stale-resource denial
- duplicate idempotency replay
- protected-field denial
- async read completion

**Step 2: Run the failing tests**

Run:
```bash
python3 -m unittest tests/b5/test_b5_scaffold.py
```

Expected:
- FAIL because the runner does not yet require all new trace and replay fields

**Step 3: Expand replay schema and runner**

Require:
- `session_id`
- `job_id` when async
- binding state transitions
- idempotency outcome linkage
- action outcome timestamps

**Step 4: Re-run full verification gate**

Run:
```bash
python3 contracts/tests/validate_active_contracts.py
PYTHONPATH=. python3 contracts/tests/validate_controller_checkpoint_contract.py
python3 -m unittest tests/b1/test_b1_scaffold.py
python3 -m unittest tests/b2b3/test_b2b3_scaffold.py
python3 -m unittest tests/b5/test_b5_scaffold.py
cd frontend && npm test && npm run build
```

Expected:
- all gates pass
- replay runner fails if observability fields drift

**Step 5: Commit**

```bash
git add eval-plan.md evals/runner.py contracts/eval-test-schema.yaml backend/app/gateway/write_gateway.py backend/app/orchestrator/graph.py tests/b5/test_b5_scaffold.py
git commit -m "test: enforce replay and observability release gates"
```

## Task 11: Final Docs And Handoff

**Files:**
- Modify: `README.md`
- Modify: `architecture-overview.md`
- Modify: `security-model.md`
- Modify: `artifact-ledger.md`
- Modify: `dispatch-board.md`

**Step 1: Update docs to match shipped behavior**

Document:
- actual chat/session endpoints
- actual shell states
- actual async job behavior
- actual idempotency and stale-state rules

**Step 2: Run final status check**

Run:
```bash
git status --short
git diff -- README.md architecture-overview.md security-model.md artifact-ledger.md dispatch-board.md
```

Expected:
- docs match the implementation

**Step 3: Commit**

```bash
git add README.md architecture-overview.md security-model.md artifact-ledger.md dispatch-board.md
git commit -m "docs: sync product and control docs to shipped chat flow"
```

## Full Verification Gate

Run this before claiming the slice is complete:

```bash
python3 contracts/tests/validate_active_contracts.py
PYTHONPATH=. python3 contracts/tests/validate_controller_checkpoint_contract.py
python3 -m unittest tests/b1/test_b1_scaffold.py
python3 -m unittest tests/b2b3/test_b2b3_scaffold.py
python3 -m unittest tests/b5/test_b5_scaffold.py
cd frontend && npm test && npm run build
```

Expected:
- contracts pass
- backend unit scaffolds pass
- frontend tests pass
- production build passes

## Delivery Heuristic

Stop calling it scaffold-only once all are true:

- frontend no longer depends on local fixtures to demonstrate the main flow
- backend exposes real chat/session/job routes
- read results come from allowlisted tool execution, not fixture selection
- write execution persists idempotent outcomes and enforces stale-state denial
- async jobs and replay artifacts are first-class, not doc-only
