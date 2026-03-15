# Bounded Autonomy In The Running App Design

Read when:
- wiring controller behavior into the FastAPI app
- deciding how async jobs should continue without manual intervention
- preserving current read, write-confirmation, and session contracts

## Goal

Land the smallest production-facing autonomy slice that reuses the existing controller checkpoint and resume machinery without importing repo-only controller semantics into the customer runtime.

## Current Gap

The controller already has:

- checkpoint persistence
- queue and terminal-state semantics
- resume-from-truth behavior
- precedence and fail-soft routing

The running FastAPI app still does not use that behavior in its live request path:

- [`backend/app/api/routes/chat.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/api/routes/chat.py) creates sessions and async jobs, but does not seed controller truth
- [`backend/app/api/routes/jobs.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/api/routes/jobs.py) refreshes stored jobs, but does not advance any bounded controller loop
- [`backend/app/main.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/main.py) exposes session, job, storage, and read services, but no running-app autonomy service
- [`backend/app/controller/runtime.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/controller/runtime.py) is reachable only as a library seam, not as live app behavior

Result: autonomy is real in isolated controller tests, but not in the app the frontend actually talks to.

## Existing Constraints

From the locked docs and current code:

- Memphis-only PoC remains the product boundary
- read path and confirmation-gated single-step booking remain the runtime scope
- `/actions/confirm` stays the only write entrypoint
- async jobs already exist and already gate long-running work behind poll tokens
- controller checkpoints are additive and default-off
- queue truth is authoritative over stale summaries

Relevant references:

- [`docs/plans/2026-03-15-main-autonomous-resume-plan.md`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/docs/plans/2026-03-15-main-autonomous-resume-plan.md)
- [`docs/plans/queue-finalization-contract.md`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/docs/plans/queue-finalization-contract.md)
- [`reports/README.md`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/reports/README.md)
- [`decisions.md`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/decisions.md)
- [`dispatch-board.md`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/dispatch-board.md)

## Approaches Considered

### 1. Route every `/chat` turn through controller state

Pros:
- single routing model
- autonomy visible on every turn

Cons:
- touches the hot synchronous read path
- widens blast radius across all chat requests
- encourages product runtime to inherit repo-style controller packet semantics too early

Verdict: rejected for phase 1.

### 2. Poll-driven bounded autonomy on top of existing async jobs

Pros:
- smallest live-path change
- reuses `job_id`, poll-token security, session carry-forward, and existing pending/result envelopes
- keeps synchronous reads unchanged
- no new queue, worker, or infra dependency
- aligns with the current app seam: `/chat` starts long-running work, `/jobs/{id}` resumes it

Cons:
- progress advances only when the client polls
- first autonomy slice is intentionally narrow

Verdict: recommended.

### 3. Separate background worker and queue

Pros:
- cleaner long-term throughput model
- less poll-coupled execution

Cons:
- new infra, failure modes, deployment surface, and local-dev burden
- more drift from the current repo state than needed

Verdict: defer until the bounded poll-driven slice proves out.

## Recommended Design

Use the existing async job surface as the execution shell for bounded autonomy.

Phase-1 autonomy is:

- internal only
- read-only
- job-backed
- poll-driven
- checkpoint-authoritative
- hard-bounded by step count and wall-clock

The controller package remains the truth engine for checkpoint and resume semantics, but the running app gets a thin autonomy adapter that translates product-runtime work into controller-safe steps.

## Exact Bounded-Autonomy Contract

### Feature gate

Add a dedicated running-app flag:

- `MERIDIAN_RUNNING_AUTONOMY_ENABLED=false` by default

Runtime preconditions:

- `MERIDIAN_RUNNING_AUTONOMY_ENABLED=true`
- `MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED=true`
- `MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED=true`

If any precondition is false, the app keeps current behavior exactly.

### Scope

Phase 1 autonomy is allowed only for long-running read work already eligible for async jobs.

Allowed:

- async read refresh requests started from [`backend/app/api/routes/chat.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/api/routes/chat.py)
- allowlisted read execution
- response building
- job completion or fail-soft termination
- replay and audit metadata emission

Explicitly disallowed:

- autonomous write execution
- calls into [`backend/app/api/routes/actions.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/api/routes/actions.py)
- confirmation bypass
- multi-job fan-out
- nested autonomy runs
- importing repo control docs such as `dispatch-board.md` into runtime decisions

### Identity and run IDs

- `session_id` stays the conversation identity
- `job_id` becomes the autonomy run identity
- controller checkpoint path is keyed by `job_id`, not `session_id`
- one async job maps to one bounded autonomy run

Reason: multiple jobs may exist for the same chat session, so session-scoped checkpoint keys would collide.

### Truth surfaces

Authoritative truth:

- controller checkpoint stored under the `job_id`

Derivative cache:

- job-store autonomy metadata persisted with the job row

Not duplicated:

- session store remains session-focused and does not become a second controller truth store

The job metadata cache may include:

- `mode`: `poll_driven`
- `task_kind`: `async_read_refresh`
- `checkpoint_id`
- `step_index`
- `step_budget`
- `last_controller_action`

If job metadata and checkpoint disagree, checkpoint wins.

### Step model

Each autonomy run may execute only these step kinds:

1. `seed_context`
2. `execute_allowlisted_read`
3. `build_response`
4. `complete_job`

Optional failure branch:

5. `fail_job`

No other step kinds are valid in phase 1.

### Bounds

Hard bounds for every autonomy run:

- max auto steps: `3` by default
- max one controller step per `GET /jobs/{job_id}` call
- max wall-clock per poll tick: `5s` by default
- allowed tool family: read-only

If the step budget is exhausted or an unsupported step is requested, the job must fail soft with a contract-valid error payload. It must not hang or silently recurse.

### Entry contract on `/chat`

[`backend/app/api/routes/chat.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/api/routes/chat.py) may seed an autonomy run only when all are true:

- request matches the existing async-refresh path
- running-app autonomy flag is enabled
- request remains read-only
- trusted identity and session checks passed

On seed:

- create the job as today
- create controller checkpoint keyed by `job_id`
- persist derivative autonomy metadata on the job row
- return the existing pending response envelope shape

Public API contract stays unchanged for phase 1.

### Resume contract on `/jobs/{job_id}`

[`backend/app/api/routes/jobs.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/api/routes/jobs.py) becomes the live autonomy tick.

When the job is transient and marked as autonomy-enabled:

1. validate poll token and session linkage first
2. load checkpoint by `job_id`
3. resume controller truth
4. execute exactly one allowed next step
5. persist updated checkpoint and derivative job metadata
6. return the current job envelope

When the step completes the run:

- materialize the existing `ChatResponseEnvelope`
- store it in the job result
- complete the job using the existing lifecycle rules

When the run cannot proceed safely:

- fail the job with a contract-valid error result
- keep poll-token and session checks intact

### Writes and confirmation

[`backend/app/api/routes/actions.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/api/routes/actions.py) stays unchanged in phase 1.

Rules:

- no autonomy step may call `execute_write_gateway`
- no autonomy step may synthesize a confirmation token
- any prompt that would require confirmation stays on the current synchronous confirmation path

### Observability contract

Every autonomy step must emit enough audit data to replay the run:

- `autonomy_run_id`
- `session_id`
- `job_id`
- `step_index`
- `step_kind`
- `controller_action`
- `checkpoint_id`
- `response_generated_at`

These fields belong in backend audit seams and replay fixtures, not in a new public frontend-only contract.

## Runtime Flow

1. User posts async-eligible chat request.
2. `/chat` creates or reuses session state.
3. `/chat` creates async job.
4. If autonomy disabled, current behavior continues.
5. If autonomy enabled, `/chat` also seeds checkpoint plus job metadata and returns pending envelope.
6. Frontend polls `/jobs/{job_id}` as it already does.
7. `/jobs/{job_id}` advances one bounded step per poll until the run completes or fails.
8. Terminal job result remains the same response-envelope family the frontend already understands.

## Why This Is The Shortest No-Drift Path

- It keeps the existing public API stable.
- It reuses current job and poll-token mechanics.
- It does not force controller semantics into every sync request.
- It does not require a worker service or new infra.
- It keeps writes confirmation-only.
- It reuses controller checkpoint truth where that machinery already exists.
- It avoids dragging repo-only dispatch-board semantics into product runtime logic.

## Non Goals

Phase 1 does not:

- introduce autonomous booking writes
- introduce free-running background workers
- make `/chat` multi-step for all prompts
- expose repo-controller wave packets to the frontend
- replace current session or job stores
- add multi-office or multi-role autonomy behavior

## Acceptance Checks

This design is correct only if the landed implementation proves:

- async read jobs can seed controller truth from the live app
- job polling advances one bounded step per request
- checkpoint truth, not stale job metadata, drives resume
- disabled flags preserve current behavior
- writes remain confirmation-gated and outside the autonomy loop
- poll-token and session checks still fail closed
- terminal success and terminal fail-soft responses stay contract-valid

## Files Expected To Change

Core runtime:

- [`backend/app/config.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/config.py)
- [`backend/app/main.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/main.py)
- [`backend/app/api/routes/chat.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/api/routes/chat.py)
- [`backend/app/api/routes/jobs.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/api/routes/jobs.py)
- [`backend/app/jobs/models.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/jobs/models.py)
- [`backend/app/jobs/store.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/jobs/store.py)

New adapter seam:

- `backend/app/autonomy/models.py`
- `backend/app/autonomy/service.py`

Verification:

- `tests/b2b3/test_async_job_lifecycle.py`
- `tests/b2b3/test_bounded_autonomy.py`
- targeted controller runtime tests where checkpoint truth is resumed via `job_id`

## Follow-on Plan

Implementation steps are captured in:

- [`docs/plans/2026-03-15-bounded-autonomy-running-app-plan.md`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/docs/plans/2026-03-15-bounded-autonomy-running-app-plan.md)
