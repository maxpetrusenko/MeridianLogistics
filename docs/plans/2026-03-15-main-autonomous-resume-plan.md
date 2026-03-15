# Main Autonomous Resume Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Main continue autonomously across waves by reloading controller truth from checkpoint and queue state on every resume, deriving the next runnable `auto` wave without waiting for a manual packet.

**Architecture:** Keep lossless truth in the existing controller surfaces: checkpoint JSON, controller reports, `dispatch-board.md`, and `artifact-ledger.md`. Add a narrow resume path in controller policy/runtime that always treats repo/controller truth as authoritative over thread summaries, forces queue finalization before any terminal reply, and emits a compact derived packet only as an execution cache.

**Tech Stack:** Python 3.11, existing controller policy/runtime modules, unittest/pytest controller tests, markdown control docs.

---

### Task 1: Add failing autonomy regressions

**Files:**
- Modify: `tests/controller/test_controller_policy.py`
- Modify: `tests/controller/test_controller_runtime.py`
- Create: `tests/controller/test_main_autonomous_resume.py`

**Step 1: Write the failing tests**

Cover:
- status-only resume with an eligible active `auto` wave continues instead of pausing
- stale thread packet does not override controller truth when checkpoint/queue truth points to a different active wave
- Main returns terminal state only when queue finalization yields literal `DONE`, `WAITING_USER_APPROVAL`, `BLOCKED`, or `ABORTED`
- Main derives the next runnable packet from checkpoint/queue truth when no fresh manual packet is supplied

**Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/controller/test_controller_policy.py tests/controller/test_controller_runtime.py tests/controller/test_main_autonomous_resume.py -q
```

Expected: FAIL on missing autonomous-resume behavior and missing test module.

**Step 3: Write minimal implementation**

Implement only the narrow controller behavior needed to satisfy the tests.

**Step 4: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/controller/test_controller_policy.py tests/controller/test_controller_runtime.py tests/controller/test_main_autonomous_resume.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/controller/test_controller_policy.py tests/controller/test_controller_runtime.py tests/controller/test_main_autonomous_resume.py
git commit -m "test: add main autonomous resume regressions"
```

### Task 2: Add controller-truth-first resume logic

**Files:**
- Modify: `backend/app/controller/policy.py`
- Modify: `backend/app/controller/runtime.py`
- Modify: `backend/app/controller/models.py`

**Step 1: Add failing narrow unit coverage if needed**

If Task 1 did not force failures tightly enough, add or refine assertions around:
- active-wave selection from queue truth
- thread-summary drift rejection
- terminal-state guard

**Step 2: Run the focused test**

Run:

```bash
python -m pytest tests/controller/test_main_autonomous_resume.py -q
```

Expected: FAIL with incorrect pause or stale-wave selection.

**Step 3: Write minimal implementation**

Add a narrow resume helper that:
- loads latest checkpoint queue snapshot
- prefers active queue/checkpoint truth over thread summaries
- finalizes queue state before any stop decision
- derives execution packet fields from queue truth when action is `CONTINUE`
- never emits a pause on status-only updates

Keep:
- no new storage surface
- no lossy truth overwrite
- no summary-only routing

**Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/controller/test_controller_policy.py tests/controller/test_controller_runtime.py tests/controller/test_main_autonomous_resume.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/controller/policy.py backend/app/controller/runtime.py backend/app/controller/models.py tests/controller/test_controller_policy.py tests/controller/test_controller_runtime.py tests/controller/test_main_autonomous_resume.py
git commit -m "feat: make main resume from controller truth"
```

### Task 3: Align Main prompt and controller docs to kill prompt drift

**Files:**
- Modify: `.agents/agents/main.md`
- Modify: `runbook.md`
- Modify: `decisions.md`
- Modify: `dispatch-board.md`
- Modify: `reports/README.md`

**Step 1: Update docs**

Record:
- repo/controller truth beats stale thread summaries
- every resume must reload latest checkpoint, queue truth, and active wave
- status-only updates are never terminal
- queue finalization is mandatory before any terminal response
- derived next-wave packet may be emitted from checkpoint/report truth without manual user packet

**Step 2: Verify wording consistency**

Run:

```bash
rg -n "status-only|controller truth|queue finalization|resume|active wave|stale thread" .agents/agents/main.md runbook.md decisions.md dispatch-board.md reports/README.md
```

Expected: matching wording across prompt and control docs.

**Step 3: Commit**

```bash
git add .agents/agents/main.md runbook.md decisions.md dispatch-board.md reports/README.md
git commit -m "docs: align main autonomous resume rules"
```

### Task 4: Add checkpoint-derived packet view

**Files:**
- Modify: `backend/app/controller/runtime.py`
- Modify: `reports/README.md`
- Create: `tests/controller/test_main_autonomous_resume.py`

**Step 1: Write failing assertion**

Add a test proving the runtime can derive a compact next-wave packet from checkpoint/queue truth with:
- `wave_name`
- `owner`
- `run_policy`
- `eligible`
- `approval_authority`
- `objective`
- `success_check`
- `why_next`

**Step 2: Run the targeted test**

Run:

```bash
python -m pytest tests/controller/test_main_autonomous_resume.py -q
```

Expected: FAIL because derived packet fields are incomplete or absent.

**Step 3: Write minimal implementation**

Add a derived packet builder in runtime using existing queue/checkpoint/report truth. Do not persist a new truth surface; emit it only as execution-facing cache.

**Step 4: Re-run targeted tests**

Run:

```bash
python -m pytest tests/controller/test_main_autonomous_resume.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/controller/runtime.py reports/README.md tests/controller/test_main_autonomous_resume.py
git commit -m "feat: derive next-wave packet from checkpoint truth"
```

### Task 5: Full controller verification

**Files:**
- Modify: none

**Step 1: Run controller test slice**

Run:

```bash
python -m pytest tests/controller/test_controller_policy.py tests/controller/test_controller_runtime.py tests/controller/test_controller_scaffold.py tests/controller/test_review_lane_contract.py tests/controller/test_review_lane_truth_merge.py tests/controller/test_main_autonomous_resume.py -q
```

Expected: PASS.

**Step 2: Run checkpoint contract validation**

Run:

```bash
PYTHONPATH=. python contracts/tests/validate_controller_checkpoint_contract.py
```

Expected: PASS.

**Step 3: Spot-check control-doc truth**

Run:

```bash
rg -n "active wave|run_policy|approval_authority|terminal_state" dispatch-board.md artifact-ledger.md reports
```

Expected: current wave and terminal semantics agree across controller surfaces.

**Step 4: Commit**

```bash
git add docs/plans/2026-03-15-main-autonomous-resume-plan.md
git commit -m "docs: add main autonomous resume plan"
```

### Task 6: Optional fast-follow after autonomy lands

**Files:**
- Modify: `backend/app/controller/runtime.py`
- Modify: `backend/app/controller/policy.py`
- Create: `tests/controller/test_main_autonomous_resume.py`

**Step 1: Add one more regression**

Cover:
- closed wave + next eligible `auto` wave activates in the same turn without an intermediate status stop

**Step 2: Run focused test**

Run:

```bash
python -m pytest tests/controller/test_main_autonomous_resume.py -q
```

Expected: PASS after implementation.

**Step 3: Commit**

```bash
git add backend/app/controller/runtime.py backend/app/controller/policy.py tests/controller/test_main_autonomous_resume.py
git commit -m "test: lock same-turn wave promotion"
```
