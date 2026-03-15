# Running App Bounded Autonomy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring the existing controller checkpoint and resume machinery into the live FastAPI app through the existing async-job surface, so bounded read-only autonomy works in the running app without changing write-confirmation rules or requiring new background infrastructure.

**Architecture:** Keep synchronous chat behavior unchanged. Add a small autonomy adapter that seeds controller truth when `/chat` opens an async read job and advances exactly one bounded step each time `/jobs/{job_id}` is polled. The controller checkpoint keyed by `job_id` is authoritative; job metadata is derivative cache only.

**Tech Stack:** FastAPI, Python 3.11, existing controller runtime, SQLite/Postgres-backed job store, pytest/unittest, contract-valid chat and job envelopes.

---

### Task 1: Lock the runtime contract in tests first

**Files:**
- Create: `tests/b2b3/test_bounded_autonomy.py`
- Modify: `tests/b2b3/test_async_job_lifecycle.py`
- Reference: `docs/plans/2026-03-15-bounded-autonomy-running-app-design.md`

**Step 1: Write the failing autonomy seed tests**

Cover:
- async-eligible `/chat` request seeds a controller checkpoint when running-app autonomy is enabled
- checkpoint key uses `job_id`, not `session_id`
- disabled autonomy flag preserves the current pending-job behavior

**Step 2: Write the failing autonomy resume tests**

Cover:
- `GET /jobs/{job_id}` advances exactly one bounded step for an autonomy-tagged transient job
- checkpoint truth overrides stale job metadata on resume
- exhausted step budget returns a fail-soft terminal job result
- invalid poll token or wrong session still fails closed before any step runs

**Step 3: Run the focused failing tests**

Run:

```bash
python -m pytest tests/b2b3/test_async_job_lifecycle.py tests/b2b3/test_bounded_autonomy.py -q
```

Expected: FAIL because no running-app autonomy adapter exists yet.

**Step 4: Commit the red tests**

```bash
git add tests/b2b3/test_async_job_lifecycle.py tests/b2b3/test_bounded_autonomy.py docs/plans/2026-03-15-bounded-autonomy-running-app-design.md docs/plans/2026-03-15-bounded-autonomy-running-app-plan.md
git commit -m "test: add bounded autonomy app regressions"
```

### Task 2: Add autonomy config and internal adapter models

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/autonomy/models.py`
- Create: `backend/app/autonomy/service.py`
- Modify: `backend/app/main.py`

**Step 1: Add config seams**

Add:
- `running_autonomy_enabled: bool`
- `running_autonomy_max_steps: int`
- `running_autonomy_poll_step_timeout_seconds: int`

Back them with env vars:
- `MERIDIAN_RUNNING_AUTONOMY_ENABLED`
- `MERIDIAN_RUNNING_AUTONOMY_MAX_STEPS`
- `MERIDIAN_RUNNING_AUTONOMY_POLL_STEP_TIMEOUT_SECONDS`

**Step 2: Add internal autonomy models**

Define exact internal shapes for:
- autonomy mode
- task kind
- persisted job metadata
- allowed step kinds
- step outcome

Keep these internal to the backend. Do not widen public request or response schemas yet.

**Step 3: Add the autonomy service**

Implement a small adapter that can:
- decide whether a chat request is autonomy-eligible
- seed checkpoint plus job metadata for a new `job_id`
- resume one bounded step for a transient autonomy job
- materialize either success or fail-soft job results

Use existing controller runtime APIs. Do not import repo control-doc routing into the adapter.

**Step 4: Wire service into app state**

In [`backend/app/main.py`](/Users/maxpetrusenko/Desktop/Gauntlet/MeridianLogistics/backend/app/main.py), initialize and attach the service to `app.state`.

**Step 5: Run the focused tests**

Run:

```bash
python -m pytest tests/b2b3/test_bounded_autonomy.py -q
```

Expected: still FAIL on route wiring, but config and adapter seams exist.

**Step 6: Commit**

```bash
git add backend/app/config.py backend/app/autonomy/models.py backend/app/autonomy/service.py backend/app/main.py
git commit -m "feat: add running app autonomy adapter"
```

### Task 3: Seed autonomy runs from `/chat`

**Files:**
- Modify: `backend/app/api/routes/chat.py`
- Modify: `backend/app/jobs/models.py`
- Modify: `backend/app/jobs/store.py`
- Test: `tests/b2b3/test_bounded_autonomy.py`

**Step 1: Extend job persistence for derivative autonomy metadata**

Add the smallest metadata field needed to persist:
- `mode`
- `task_kind`
- `checkpoint_id`
- `step_index`
- `step_budget`
- `last_controller_action`

Prefer one JSON metadata field over several narrow columns unless the current store shape makes that impractical.

**Step 2: Seed autonomy on async chat requests**

When the request already qualifies for the async-refresh path and the feature flag is enabled:
- create the job as today
- call the autonomy service to seed checkpoint plus metadata keyed by `job_id`
- keep the public pending response envelope shape unchanged

When autonomy is disabled or request is not eligible:
- keep current route behavior unchanged

**Step 3: Run the targeted route tests**

Run:

```bash
python -m pytest tests/b2b3/test_bounded_autonomy.py -q
```

Expected: seed-path assertions now pass; resume-path assertions still fail.

**Step 4: Commit**

```bash
git add backend/app/api/routes/chat.py backend/app/jobs/models.py backend/app/jobs/store.py tests/b2b3/test_bounded_autonomy.py
git commit -m "feat: seed bounded autonomy from chat jobs"
```

### Task 4: Advance exactly one autonomy step per job poll

**Files:**
- Modify: `backend/app/api/routes/jobs.py`
- Modify: `backend/app/autonomy/service.py`
- Modify: `backend/app/jobs/store.py`
- Test: `tests/b2b3/test_bounded_autonomy.py`
- Test: `tests/b2b3/test_async_job_lifecycle.py`

**Step 1: Implement the poll-time resume hook**

Before returning a transient job from `GET /jobs/{job_id}`:
- validate poll token
- detect autonomy-tagged transient job
- ask the autonomy service to resume exactly one bounded step
- persist updated job metadata and job lifecycle state

Do not loop inside the request. One poll, one step.

**Step 2: Implement allowed step execution**

The autonomy service may execute only:
- `seed_context`
- `execute_allowlisted_read`
- `build_response`
- `complete_job`
- fail-soft termination

Do not call write gateway code.

**Step 3: Preserve existing lifecycle rules**

Ensure current lifecycle behavior still holds:
- terminal jobs remain terminal
- poll-token checks still fail closed
- session promotion after completed responses still works

**Step 4: Run the focused tests**

Run:

```bash
python -m pytest tests/b2b3/test_bounded_autonomy.py tests/b2b3/test_async_job_lifecycle.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/routes/jobs.py backend/app/autonomy/service.py backend/app/jobs/store.py tests/b2b3/test_bounded_autonomy.py tests/b2b3/test_async_job_lifecycle.py
git commit -m "feat: advance bounded autonomy from job polling"
```

### Task 5: Add audit and replay fields without widening the public contract unnecessarily

**Files:**
- Modify: `backend/app/autonomy/service.py`
- Modify: `backend/app/api/routes/chat.py`
- Modify: `backend/app/api/routes/jobs.py`
- Modify: `evals/runner.py`
- Modify: `contracts/eval-test-schema.yaml`
- Test: `tests/b5/test_b5_scaffold.py`

**Step 1: Add autonomy audit fields to backend-produced payloads**

Include:
- `autonomy_run_id`
- `step_index`
- `step_kind`
- `controller_action`
- `checkpoint_id`

Place them in audit-friendly surfaces that replay tooling can consume. Do not require a frontend renderer change unless existing schema validation forces one.

**Step 2: Update replay and eval fixtures**

Teach replay and eval coverage to assert:
- autonomy-enabled async read runs have stable trace fields
- fail-soft autonomy terminations are captured distinctly from normal read failures

**Step 3: Run the focused eval tests**

Run:

```bash
python -m pytest tests/b5/test_b5_scaffold.py -q
```

Expected: PASS.

**Step 4: Commit**

```bash
git add backend/app/autonomy/service.py backend/app/api/routes/chat.py backend/app/api/routes/jobs.py evals/runner.py contracts/eval-test-schema.yaml tests/b5/test_b5_scaffold.py
git commit -m "feat: add bounded autonomy replay metadata"
```

### Task 6: Full verification and doc sync

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `docs/api/async-jobs.md`
- Modify: none other unless verification forces it

**Step 1: Document the new flags and runtime behavior**

Record:
- feature flags
- poll-driven execution model
- one-poll-one-step bound
- read-only phase-1 scope
- confirmation-gated writes unchanged

**Step 2: Run backend verification**

Run:

```bash
python -m pytest tests/b2b3/test_async_job_lifecycle.py tests/b2b3/test_bounded_autonomy.py tests/b5/test_b5_scaffold.py tests/controller/test_controller_runtime.py -q
```

Expected: PASS.

**Step 3: Run contract and app smoke checks**

Run:

```bash
python contracts/tests/validate_active_contracts.py
python -c "from backend.app.main import create_app; app = create_app(); print(sorted(route.path for route in app.routes))"
```

Expected:
- active contracts validate
- chat and jobs routes still register cleanly

**Step 4: Commit**

```bash
git add README.md .env.example docs/api/async-jobs.md docs/plans/2026-03-15-bounded-autonomy-running-app-design.md docs/plans/2026-03-15-bounded-autonomy-running-app-plan.md
git commit -m "docs: add bounded autonomy running app plan"
```

### Task 7: Optional fast follow once phase 1 is green

**Files:**
- Modify: `backend/app/autonomy/service.py`
- Modify: `backend/app/api/routes/chat.py`
- Test: `tests/b2b3/test_bounded_autonomy.py`

**Step 1: Add one more regression**

Cover:
- a bounded autonomy run that completes in fewer than the full step budget leaves no stale derivative metadata behind

**Step 2: Run the focused test**

Run:

```bash
python -m pytest tests/b2b3/test_bounded_autonomy.py -q
```

Expected: FAIL until cleanup behavior is explicit.

**Step 3: Implement the cleanup**

Clear derivative job metadata fields that should not outlive the completed run. Keep checkpoint truth for replay and diagnostics.

**Step 4: Re-run the test**

Run:

```bash
python -m pytest tests/b2b3/test_bounded_autonomy.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/autonomy/service.py backend/app/api/routes/chat.py tests/b2b3/test_bounded_autonomy.py
git commit -m "refactor: clean bounded autonomy terminal metadata"
```

Plan complete and saved to `docs/plans/2026-03-15-bounded-autonomy-running-app-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
