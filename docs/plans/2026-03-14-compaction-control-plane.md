# Compaction Control Plane Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an isolated compaction control-plane scaffold based on instinct8 so Meridian gains protected-core checkpoints, compaction-safe resume state, and fail-soft controller precedence without replacing the main runtime.

**Architecture:** Add a new `backend/app/controller/` package that is not yet wired into FastAPI or the orchestrator graph. Define a contract-backed checkpoint schema, an instinct8-style strategy adapter, and a precedence resolver that demotes safe triage aborts into review or repair while preserving unsafe aborts. Keep existing Memphis business behavior unchanged by leaving current graph, gateway, response, and eval code paths untouched.

**Tech Stack:** Python 3.10+, dataclasses, `jsonschema`, existing unittest style, existing contract loader.

---

### Task 1: Add the protected-core and checkpoint models

**Files:**
- Create: `backend/app/controller/models.py`
- Create: `backend/app/controller/__init__.py`
- Modify: `backend/app/contracts.py`
- Test: `contracts/tests/validate_controller_checkpoint_contract.py`

**Step 1: Write the failing contract test**

Create a new controller checkpoint contract validation test that expects:
- a valid checkpoint with protected-core fields
- an invalid decision source to fail schema validation

**Step 2: Run test to verify it fails**

Run: `python -m contracts.tests.validate_controller_checkpoint_contract`
Expected: FAIL because the checkpoint contract and model types do not exist yet.

**Step 3: Write minimal implementation**

Add:
- `ProtectedCore`
- `FailureSignal`
- `ControllerDecision`
- `CompactionState`
- `ControllerCheckpoint`

Also add `controller_checkpoint` to `backend/app/contracts.py`.

**Step 4: Run test to verify it passes**

Run: `python -m contracts.tests.validate_controller_checkpoint_contract`
Expected: PASS with `controller checkpoint contract validation tests passed`.

**Step 5: Commit**

```bash
git add backend/app/controller/__init__.py backend/app/controller/models.py backend/app/contracts.py contracts/controller-checkpoint-schema.json contracts/tests/validate_controller_checkpoint_contract.py
git commit -m "feat: add controller checkpoint contract scaffold"
```

### Task 2: Add instinct8 strategy adapter mapping

**Files:**
- Create: `backend/app/controller/strategies.py`
- Modify: `backend/app/controller/__init__.py`
- Test: `tests/controller/test_controller_scaffold.py`

**Step 1: Write the failing scaffold test**

Add a fake instinct8-style strategy and assert that:
- `prime()` forwards goal and constraints into `initialize()`
- `compact()` returns protected core plus compressed halo plus recent turns

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests/controller -p 'test_*.py'`
Expected: FAIL because the adapter module does not exist yet.

**Step 3: Write minimal implementation**

Add:
- `Instinct8StrategyProtocol`
- `CompressionEnvelope`
- `CompressionControllerAdapter`

Map only the interface points Meridian needs now:
- `initialize`
- `update_goal`
- `compress`
- `name`

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s tests/controller -p 'test_*.py'`
Expected: PASS for the adapter preservation test.

**Step 5: Commit**

```bash
git add backend/app/controller/strategies.py backend/app/controller/__init__.py tests/controller/test_controller_scaffold.py
git commit -m "feat: add instinct8 strategy adapter scaffold"
```

### Task 3: Add fail-soft controller precedence

**Files:**
- Create: `backend/app/controller/precedence.py`
- Modify: `backend/app/controller/__init__.py`
- Test: `tests/controller/test_controller_scaffold.py`

**Step 1: Write the failing precedence tests**

Add tests for:
- review approve beats safe triage abort
- validator pass beats safe triage abort when no concrete failure exists
- unsafe failure forces abort
- recoverable failure routes to repair

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests/controller -p 'test_*.py'`
Expected: FAIL because precedence logic does not exist yet.

**Step 3: Write minimal implementation**

Add:
- `ControllerSignals`
- `resolve_controller_action()`

Implement this exact precedence:
1. unsafe -> abort
2. approved review with no concrete failure -> continue
3. validator pass with no concrete failure -> continue
4. review changes requested -> repair
5. recoverable failure or validator fail -> repair
6. safe triage abort -> review
7. default -> review

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s tests/controller -p 'test_*.py'`
Expected: PASS for all controller precedence tests.

**Step 5: Commit**

```bash
git add backend/app/controller/precedence.py backend/app/controller/__init__.py tests/controller/test_controller_scaffold.py
git commit -m "feat: add fail-soft controller precedence"
```

### Task 4: Verify runtime non-regression

**Files:**
- Modify: none
- Test: `tests/b2b3/test_b2b3_scaffold.py`
- Test: `tests/b5/test_b5_scaffold.py`
- Test: `contracts/tests/validate_active_contracts.py`

**Step 1: Run backend scaffold tests**

Run: `python -m unittest tests/b2b3/test_b2b3_scaffold.py`
Expected: PASS.

**Step 2: Run eval scaffold tests**

Run: `python -m unittest tests/b5/test_b5_scaffold.py`
Expected: PASS.

**Step 3: Run contract checks**

Run: `python contracts/tests/validate_active_contracts.py`
Expected: PASS with `active contract validation tests passed`.

**Step 4: Commit**

```bash
git add docs/plans/2026-03-14-compaction-control-plane-design.md docs/plans/2026-03-14-compaction-control-plane.md
git commit -m "docs: add compaction control-plane design and plan"
```

### Task 5: Phase-two integration after approval

**Files:**
- Modify: `backend/app/orchestrator/graph.py`
- Modify: `evals/runner.py`
- Create: `backend/app/controller/runtime.py`
- Create: `tests/controller/test_controller_runtime.py`

**Step 1: Add controller hook points behind explicit flags**

Keep current runtime default behavior unchanged. Add optional hook points only.

**Step 2: Add drift and compaction replay coverage**

Reuse the checkpoint schema and strategy adapter in eval flows before production routing.

**Step 3: Run targeted tests**

Run:
- `python -m unittest discover -s tests/controller -p 'test_*.py'`
- `python -m unittest tests/b2b3/test_b2b3_scaffold.py`
- `python -m unittest tests/b5/test_b5_scaffold.py`

Expected: PASS.

**Step 4: Commit**

```bash
git add backend/app/orchestrator/graph.py evals/runner.py backend/app/controller/runtime.py tests/controller/test_controller_runtime.py
git commit -m "feat: add optional controller runtime hooks"
```

Plan complete and saved to `docs/plans/2026-03-14-compaction-control-plane.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
