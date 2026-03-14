# Lean Lane Policy Design

## Goal

Update Meridian's controller operating model so Main acts as the primary orchestrator, continues automatically across eligible auto waves, opens Repair only on exact blocker packets, opens Review only on selective gate conditions, and stops only on true terminal states.

## Scope

- Add a pure, stateless controller policy module for lean-lane decisions.
- Keep `backend/app/orchestrator/graph.py` as the orchestrator surface.
- Keep checkpoint and run-policy semantics intact.
- Add the smallest runtime and test wiring needed to enforce routing behavior.
- Update controller docs where routing and approval policy are defined.

## Non-goals

- No business logic changes to read or write orchestration.
- No controller redesign or framework migration.
- No new persistence model.
- No checkpoint schema widening unless tests force it.

## Architecture

Add `backend/app/controller/policy.py` as a pure decision layer. The module will not perform I/O, read env vars, write checkpoints, log, or inspect the filesystem. It will expose narrow helpers that return routing decisions and terminal-state truth.

`backend/app/orchestrator/graph.py` and `backend/app/controller/runtime.py` remain the application boundary. They call the policy helpers, apply the result, and preserve the current checkpoint and routing hooks.

## Policy Groups

### Main approval policy

Main may proceed without asking when work is internal hardening, docs or checkpoint sync, a bounded code fix with exact scope, local tests, repo-grounded next steps, or safe research for current facts.

Main must stop only on:

- `DONE`
- `WAITING_APPROVAL`
- `BLOCKED`
- `ABORTED`

### Repair approval policy

Repair opens only when an exact blocker packet exists. Exact blocker evidence means:

- exact failing assertion or runtime error
- exact file path
- exact contradiction text or failing check
- bounded affected scope

Otherwise Main continues directly or routes to another non-terminal action.

### Review approval policy

Review is selective, not default. Review opens only when at least one policy condition is true:

- runtime or control-plane logic changed
- more than one file changed
- contract, checkpoint, or routing semantics changed
- blocker previously stalled execution
- confidence is low

Otherwise Main merges the bounded change and continues.

### Research and web approval policy

Main may use research or web search without user interruption when freshness matters, framework or vendor or current-product claims are involved, local repo evidence is insufficient, or an architectural comparison needs current evidence.

Local code, repo truth, and tests should stay local-first.

### Completion and queue policy

A wave is complete only when the intended change exists, required checks passed, and no unsuperseded exact blocker remains. After closeout the controller must do exactly one:

1. activate the next eligible `auto` wave
2. return `WAITING_APPROVAL` for a queued `explicit_request` wave
3. return `DONE` when no runnable wave remains
4. return `BLOCKED` only with exact blocker evidence

### Reopen policy

A closed wave may reopen only when a fresh exact blocker packet appears and the controller explicitly reopens it. Stale notes, vague commentary, and contradictory old reports cannot reopen a wave.

## Planned API

Add pure helpers and small enums or dataclasses in `backend/app/controller/policy.py`:

- `Action = CONTINUE | REPAIR | REVIEW | RESEARCH | WAITING_APPROVAL | BLOCKED | DONE`
- `MissingInfoAction = INFER | RESEARCH | REQUEST_INPUT | BLOCK`
- `QueueDecision`
- `is_exact_blocker_packet(...)`
- `is_fresh_blocker(...)`
- `can_reopen_wave(...)`
- `should_open_repair(...)`
- `should_open_review(...)`
- `is_review_required(...)`
- `should_open_research(...)`
- `should_use_web_search(...)`
- `can_continue_without_user_input(...)`
- `requires_explicit_user_approval(...)`
- `can_main_proceed(...)`
- `should_delegate(...)`
- `can_main_handle_directly(...)`
- `is_blocked_by_missing_required_input(...)`
- `can_infer_from_repo_or_context(...)`
- `missing_info_action(...)`
- `is_safe_auto_wave(...)`
- `is_wave_complete(...)`
- `can_promote_next_wave(...)`
- `finalize_queue_state(...)`
- `next_terminal_or_runnable_state(...)`

## Runtime Wiring

The runtime integration stays narrow:

- `policy.py` decides
- `graph.py` exposes orchestrator-facing helpers that use the policy results
- `runtime.py` preserves current checkpoint writes and controller-route behavior

No business-path logic should depend on the lean-lane policy module beyond controller routing and queue decisions.

## Testing

Add focused unit tests for each policy group. Add minimal integration tests proving:

- repair is not opened without exact blocker evidence
- review is opened only on selective gate conditions
- Main continues automatically across eligible `auto` waves
- `WAITING_APPROVAL` occurs only for queued `explicit_request` waves
- closed waves do not reopen on stale or vague evidence

## Risks and Guardrails

- The new policy layer must not become a hidden controller blob; keep helpers small and composable.
- Do not duplicate business rules already owned by contracts or the gateway.
- Keep queue semantics aligned with current `run_policy` and terminal-state docs.
