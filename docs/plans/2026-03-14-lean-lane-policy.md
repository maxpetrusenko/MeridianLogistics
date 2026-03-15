# Lean Lane Policy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a pure lean-lane controller policy layer plus minimal runtime, doc, and test enforcement so Main continues automatically unless a real terminal state is reached.

**Architecture:** Introduce a stateless `backend/app/controller/policy.py` module that decides controller routing, delegation, approval, and queue finalization. Keep `graph.py` as the orchestrator surface, keep `runtime.py` responsible for applying policy and writing checkpoints, and preserve existing business logic and checkpoint semantics.

**Tech Stack:** Python 3.10+, dataclasses, existing unittest style, existing controller runtime hooks, markdown control docs.

---

### Task 1: Add failing policy tests

**Files:**
- Create: `tests/controller/test_controller_policy.py`

**Step 1: Write the failing tests**

Cover:
- exact blocker packet acceptance and rejection
- review selective gate behavior
- repair selective gate behavior
- missing-info inference vs request-input routing
- web and research routing
- wave completion and queue finalization
- reopen only on fresh exact blocker evidence

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests/controller/test_controller_policy.py`
Expected: FAIL because `backend.app.controller.policy` does not exist yet.

**Step 3: Write minimal implementation**

Add only the narrow helper surface needed for the tests.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests/controller/test_controller_policy.py`
Expected: PASS.

### Task 2: Add minimal graph and runtime integration tests

**Files:**
- Modify: `tests/controller/test_controller_runtime.py`

**Step 1: Write the failing tests**

Add tests proving:
- Main continues automatically across eligible `auto` waves
- `WAITING_USER_APPROVAL` appears only for queued `explicit_request` waves
- repair does not open without exact blocker evidence
- review opens only for selective-gate conditions

**Step 2: Run test to verify it fails**

Run: `python -m unittest tests/controller/test_controller_runtime.py`
Expected: FAIL because the orchestrator-facing helpers do not expose lean-lane policy yet.

**Step 3: Write minimal implementation**

Wire policy helpers through `backend/app/orchestrator/graph.py` and `backend/app/controller/runtime.py` without changing existing business behavior.

**Step 4: Run test to verify it passes**

Run: `python -m unittest tests/controller/test_controller_runtime.py`
Expected: PASS.

### Task 3: Update controller docs

**Files:**
- Modify: `decisions.md`
- Modify: `runbook.md`
- Modify: `dispatch-board.md`
- Modify: `reports/README.md`

**Step 1: Update docs**

Record:
- Main approval policy
- Repair approval policy
- Review approval policy
- Research and web approval policy
- Completion and queue approval policy
- Reopen approval policy

**Step 2: Verify docs reflect the same rules as code**

Run: `rg -n "approval policy|exact blocker|WAITING_USER_APPROVAL|explicit_request|reopen|research" decisions.md runbook.md dispatch-board.md reports/README.md`
Expected: output shows all six policy groups and the lean-lane rules.

### Task 4: Run targeted verification

**Files:**
- Modify: none

**Step 1: Run controller policy tests**

Run: `python -m unittest tests/controller/test_controller_policy.py`
Expected: PASS.

**Step 2: Run controller runtime tests**

Run: `python -m unittest tests/controller/test_controller_runtime.py`
Expected: PASS.

**Step 3: Run scaffold regression tests**

Run:
- `python -m unittest tests/controller/test_controller_scaffold.py`
- `python -m unittest tests/b2b3/test_b2b3_scaffold.py`
- `python -m unittest tests/b5/test_b5_scaffold.py`
- `python contracts/tests/validate_active_contracts.py`

Expected: PASS.
