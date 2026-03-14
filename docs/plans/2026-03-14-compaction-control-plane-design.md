# Compaction Control Plane Design

## Goal

Adopt instinct8 as the compaction and control-memory baseline without replacing Meridian's main runtime. Add only the smallest protected-core, checkpoint, and controller-precedence layer needed for non-stoppage, compaction-safe resume, and goal preservation.

## Current repo reality

- Current Meridian backend is a scaffold. It has contracts, a read/write graph stub, a write gateway, a response builder, and an eval runner.
- There is no first-class checkpoint object, no compaction strategy adapter, and no controller precedence resolver.
- Existing business behavior is frozen around Memphis-only PoC constraints, broker-first runtime scope, read queries, and confirmation-gated single-step booking writes.

## Instinct8 baseline to adopt

Use instinct8 only as a control-plane sidecar pattern:

- `strategies/strategy_base.py`: stable interface shape worth preserving
- `strategies/strategy_b_codex.py`: baseline checkpoint behavior for before-vs-after comparison
- `strategies/strategy_f_protected_core.py`: explicit protected core and goal re-assertion framing
- `evaluation/harness.py` and `evaluation/metrics.py`: drift-measurement direction for later eval parity
- `openclaw-integration/`: reference for sidecar integration boundaries instead of runtime replacement

Do not import instinct8 wholesale into request handling. Copy the interface ideas, then bind them to Meridian's controller state.

## Minimal protected core

Protected core must stay tiny and authoritative. Required fields:

- `task_goal`
- `expected_output`
- `current_step`
- `resume_point`
- `hard_constraints`
- `business_invariants`

Rationale:

- `task_goal` and `expected_output` protect why the loop exists
- `current_step` and `resume_point` make compaction-safe resume deterministic
- `hard_constraints` preserves safety and scope boundaries
- `business_invariants` prevents compaction from mutating Memphis PoC behavior

## Minimal checkpoint

Checkpoint adds only the state needed to resume safely and route controller actions:

- `checkpoint_id`
- `checkpoint_version`
- `created_at`
- `protected_core`
- `compaction.strategy_name`
- `compaction.compaction_sequence`
- `compaction.halo_summary`
- `compaction.recent_turn_ids`
- `compaction.drift_status`
- `validated_artifacts`
- `active_failure_signal`
- `controller_last_decision`

Not included yet:

- full transcript persistence
- storage backends
- runtime hooks into FastAPI or LangGraph
- automatic compaction triggering

Those stay phase two work.

## Controller loop mapping

Map instinct8 strategy interfaces into Meridian like this:

1. `initialize(original_goal, constraints)`
   Meridian controller bootstraps the strategy from `protected_core.task_goal` and `protected_core.hard_constraints`.
2. `update_goal(new_goal, rationale)`
   Controller calls this only when a reviewed goal update lands. Not on every turn.
3. `compress(context, trigger_point)`
   Controller passes the compactable halo only. Protected core stays outside compression. Recent turns stay raw.
4. `name()`
   Controller records the exact strategy in checkpoint metadata for eval parity and replay.

Resume shape becomes:

- protected core snapshot
- compacted halo summary
- recent turns
- controller last decision
- validated artifacts

That gives compaction-safe resume without touching business execution paths.

## Fail-soft precedence

Safe precedence order:

1. Unsafe or destructive state -> `abort`
2. Review `approve` and no concrete failure -> `continue`
3. Validator `pass` and no concrete failure -> `continue`
4. Review `changes_requested` -> `repair`
5. Concrete recoverable failure or validator `fail` -> `repair`
6. Safe triage `abort` request without proof of danger -> demote to `review`
7. Otherwise -> `review`

This matches the desired non-stoppage rule: triage cannot stop healthy work unless safety is concretely breached.

## Behavior preservation guardrails

The control-plane patch must not change:

- `backend/app/orchestrator/graph.py`
- `backend/app/gateway/write_gateway.py`
- `backend/app/responses/builder.py`
- `evals/runner.py`

Any future runtime integration must remain additive and behind an explicit controller hook.

## Minimal patch set

- Add `backend/app/controller/models.py`
- Add `backend/app/controller/strategies.py`
- Add `backend/app/controller/precedence.py`
- Add `contracts/controller-checkpoint-schema.json`
- Add contract validation and scaffold tests
- Add implementation plan doc

This is enough to freeze the schema, routing rules, and instinct8 interface mapping while keeping current runtime behavior intact.
