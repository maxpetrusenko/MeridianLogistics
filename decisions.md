# Meridian Decisions

## Authoritative Source Facts

- Meridian is a mid market freight brokerage with FreightView as the current in house platform.
- The target is a single chat interface replacing FreightView's six-module CRUD workflow.
- Initial scope is a Memphis only 90 day PoC covering read queries plus single-step bookings.
- Core constraints are office scoped permissions, sensitive field protection, safe SQL, and confirmation before writes.
- The current system exposes 34 REST endpoints behind JWT based auth with office and role context.

## Locked Operating Decisions

- Workspace control uses a controller-first model.
- Execution model is sequential trunk plus parallel sibling branches.
- Controller default cap is `2` drafting workers in parallel plus reviewer coverage.
- Do not open more than one downstream layer at a time.
- Local `AGENTS.md` and local `CLAUDE.md` are both canonical and stricter rule wins on conflict.
- Every worker task must load local docs, subagent guide, and skills guide before work.
- When `.agents/` exists, every worker task must also load the project-local agent config files before work.
- Mandatory skill checkout is part of every task preflight.
- Any OSS or external tool clone goes under `/Users/maxpetrusenko/Desktop/Projects/oss`.
- Operational truth lives in `agent-registry.md`, `runbook.md`, `artifact-ledger.md`, and `dispatch-board.md`.
- `dispatch-board.md` is the only place allowed to assign or change next ownership.
- Healthy lanes stay untouched when a peer lane blocks; replace only the blocked worker.
- Parallel drafting requires the same accepted parent artifact plus different owned outputs.
- Non-controller lanes emit advisory stage verdicts only.
- Only controller may emit final `ABORT`.
- Final controller decisions are limited to `PROCEED`, `REPAIR`, `REVIEW`, `VERIFY`, `HOLD`, `ABORT`.
- Controller precedence order is `verifier` > `review` > `repair` > `triage`.
- Stage evidence ties break by evidence strength, then recency.
- Missing packet fields or missing evidence must fail soft; default route is not `ABORT`.
- Every handoff, resume, repair request, review request, verifier request, compaction, and final decision must carry a compact controller checkpoint.
- Every compaction or handoff must preserve the protected carry-forward block verbatim.
- Controller runtime-hook capability is additive and available only behind explicit flags.
- Default-off legacy behavior remains the baseline execution mode until explicit controller opt-in.
- After every completed wave, controller must immediately evaluate queue state instead of stopping on status reporting alone.
- Each queued wave must carry `run_policy`, `eligible`, and `approval_authority` state in controller truth.
- Valid `run_policy` values are `auto`, `explicit_request`, and `blocked_until_input`.
- Valid `approval_authority` values are `main` and `user`.
- Terminal controller states are limited to `DONE`, `BLOCKED`, `WAITING_USER_APPROVAL`, and `ABORTED`.
- The latest controller checkpoint must persist queue snapshot truth plus terminal-state truth.
- `WAITING_USER_APPROVAL` is the terminal state when no eligible, self-approvable, or safely instantiable work remains and at least one queued wave still requires user approval.
- Internal approval authority is separate from initial queue shape; when Main self-approves an internal `explicit_request` wave, controller converts it to `run_policy: auto`, marks `eligible: true`, and continues.
- If no queued eligible `auto` wave exists, controller must self-approve any safe internal approval-gated wave before checking whether the broader approved project has a safe next stage that can be instantiated from repo or context and continuing or returning `DONE` or `WAITING_USER_APPROVAL`.
- A valid auto-instantiable next-stage candidate must include `wave_name`, `owner`, `objective`, exact files or artifacts in scope, `success_check`, `why_next`, and `run_policy`.
- Main is the primary orchestrator and should continue automatically across eligible `auto` waves.
- Repair opens only on an exact blocker packet.
- Review is selective, not the default lane.
- Do not open a separate control-hardening lane unless controller behavior itself regresses.
- Bounded parallel subagents are allowed only for Drift Review, Research, and isolated Repair.
- Parallel subagents are advisory only until Main explicitly merges their result.
- Parallel lanes must not mutate the same artifact concurrently or change controller truth directly.

## Locked Contract Decisions

- Day-one runtime role is `broker`.
- `office_manager` and `vp` stay in the PoC only as controlled boundary-review roles for permission and eval coverage.
- Accepted PoC write contract is `single_step_booking` only.
- `single_step_booking` means one booking action where `quote_id`, `carrier_id`, and `pickup_date` are already known, booking eligibility can be checked in one pass, and no negotiation, multi-leg planning, or follow-up workflow is required.
- General status-update writes are out of PoC contract scope.
- Notification behavior may be rendered as informational state only. No notification dispatch action is in PoC contract scope.
- Permission context is injected below the prompt and tool-selection layer, not authored by the model.
- Lower-order operational defaults may stay provisional in contract `v0` when they do not change interface shape.

## Locked Control-Plane Routing Decisions

- Triage advisory verdicts: `PROCEED`, `HOLD`, `ESCALATE_REPAIR`, `ESCALATE_REVIEW`
- Repair advisory verdicts: `REPAIRED`, `PARTIAL_REPAIR`, `NEEDS_REVIEW`, `BLOCKED`
- Review advisory verdicts: `APPROVE`, `REQUEST_REPAIR`, `NEEDS_VERIFICATION`, `HOLD`
- Verifier advisory verdicts: `PASS`, `FAIL_SOFT`, `FAIL_HARD`, `INCONCLUSIVE`
- `FAIL_HARD` is still advisory until controller applies protected constraints, precedence, and evidence strength.
- Stronger downstream evidence may supersede weaker earlier negatives.
- Controller may emit `ABORT` only for a proven, in-scope, non-repairable hard-constraint breach.
- If repair, review, or verifier evidence provides a viable path forward, controller routes to `REPAIR`, `REVIEW`, `VERIFY`, or `HOLD`.

## Locked Queue Execution Decisions

- Wave completion is not a terminal action by itself.
- Queue truth, checkpoint truth, report truth, and dispatch truth must agree on terminal state and next wave before a terminal stop is trusted.
- After every completed wave, controller must:
  1. mark the wave complete
  2. scan queue eligibility
  3. auto-promote the next `auto` wave when `eligible: true`
  4. if no queued eligible `auto` wave exists, self-approve any queued internal `explicit_request` wave that stays within approved scope, is reversible or sandboxed, is non-destructive, is not a business-logic redesign, is not a framework migration, is not prod or global enablement, and does not require user authority
  5. if no queued eligible or self-approved `auto` wave exists, attempt to auto-instantiate the next approved project stage when it is within scope, non-destructive, repo-grounded, and does not require explicit approval
  6. return `WAITING_USER_APPROVAL` when no eligible, self-approvable, or instantiable work remains and at least one queued wave still requires user approval
  7. return `DONE` only when no runnable or safely instantiable next wave remains
  8. return `BLOCKED` only with an exact artifact-backed blocker packet
  9. persist the resulting queue snapshot and terminal state into the latest controller checkpoint
- Status reporting alone is never a terminal reason to stop.

## Locked Approval Policy By Layer

### Main approval policy

- Main may proceed without asking on internal hardening, docs or report or checkpoint sync, bounded repo-grounded fixes, local validation, and safe research for current facts.
- Main also self-approves internal design and internal controller-owned waves inside already approved scope when business logic stays unchanged, checkpoint schema does not widen, framework migration does not start, and no destructive or irreversible action is involved.
- Main must ask only for destructive changes, production-affecting enablement, external spend, irreversible actions, or genuinely missing required input.
- Main must not stop for architecture subsection approval, policy-surface approval, integration or testing-section approval, or file-boundary approval when the work stays inside approved scope.
- Main must stop only on `DONE`, `WAITING_USER_APPROVAL`, `BLOCKED`, or `ABORTED`.

### Repair approval policy

- Repair may open only when an exact blocker packet exists.
- Exact blocker packet means exact failing assertion or runtime error, exact file path, exact contradiction text or failing check, and bounded affected scope.
- Without that packet, Main handles the work directly or continues.

### Review approval policy

- Review opens only when runtime or control-plane logic changed, more than one file changed, contract or checkpoint or routing semantics changed, blocker history previously stalled execution, or confidence is low.
- Otherwise Main merges the bounded change and continues.

### Research and web approval policy

- Main may open research or use web without asking when freshness matters, framework or vendor or current-product claims are involved, repo evidence is insufficient, or architecture comparison needs current evidence.
- Repo truth, local code, and tests remain local-first.

### Parallel lane policy

- Drift Review Lane may run in parallel to detect drift from task goal, approved scope, repo truth, queue truth, and current wave objective.
- Open Drift Review when a wave runs longer than one major step, plan changed after new evidence, multiple reports or checkpoints or docs changed, or Main is about to close or promote a wave.
- Research Lane may run in parallel when current framework or vendor or product facts matter and repo truth cannot ground the answer.
- Repair Lane may run in parallel only with an exact blocker packet and only when the fix scope is isolated from Main's active artifact.
- Main may continue while Drift Review or Research runs.
- Main may continue while Repair runs only when the blocker does not affect the current reasoning path and does not conflict with Main's active artifact.
- Main must wait when the repair slice affects the current reasoning path.
- Advisory parallel output cannot override controller truth without explicit Main-side merge.

### Completion and queue approval policy

- A wave is complete only when the intended change exists, required checks passed, and no unsuperseded exact blocker remains.
- If queue, checkpoint, report, and dispatch truth diverge on terminal state or next wave, controller must resolve that drift before returning `DONE` or `WAITING_USER_APPROVAL`.
- After closeout controller must do exactly one: activate next eligible `auto` wave, self-approve the next safe internal approval-gated wave when Main owns approval authority, auto-instantiate the next approved safe project stage, emit `WAITING_USER_APPROVAL` only for queued user-authority approval waves when no auto work remains, emit `DONE` only when no runnable or safely instantiable wave remains, or emit `BLOCKED` only with exact blocker evidence.
- The latest checkpoint must record the same queue snapshot and terminal state that the controller report and dispatch board claim.

### Reopen approval policy

- A closed wave may reopen only with a fresh exact blocker packet and an explicit controller reopen decision.
- Stale notes, vague review commentary, and contradictory old reports cannot reopen a wave.

## Proposed Architecture Under Evaluation

- React based chat client with structured responses
- FastAPI aligned gateway or extension layer
- Graph or workflow orchestrator separating read and write paths
- Curated Postgres view or tool layer instead of raw schema exposure
- Redis or equivalent suspend and resume state for multi-step workflows

These are design candidates, not source facts.

## Source Hygiene Rules

- `meridian-logistics-case-study.txt` and `source-brief.md` are the authoritative business source set.
- `plan.md` and `thoughts.md` are controller working docs, not raw source material.
- `meridian-logistics-deck-summary.md` and raw deck extracts are quarantined until reconciled.

## Current Assumptions

- The 34 REST endpoints already cover most business operations needed for the PoC.
- About 25 SQL tools are enough for first-pass read coverage.
- Structured response components are required from day one, not polish work.
- Security review cannot be left to final QA.
- Automation and skills librarian stays explicit in baseline because repo rules are dense.

## Known Gaps

- Exact Memphis tenant data constraints still missing
- Exact endpoint to workflow mapping still missing
- Exact eval dataset sample sizes and acceptance thresholds still missing
- Exact replay retention and redaction operating policy still missing
- Exact latency-budget split across orchestration, tool execution, and response shaping still missing

## Next Decisions Needed

1. Which proposed architecture choices get promoted from candidate to locked implementation choices
2. Which endpoint and resource-state checks back `single_step_booking`
3. Exact eval sample sizes and acceptance thresholds
4. Exact replay retention and redaction policy
5. Exact latency-budget split by system segment
6. When to split extra frontend and backend burst agents
7. Whether startup preflight should be logged in every report or only in task manifests

## Watch Items

- Scope creep beyond Memphis-only PoC
- Too many agents doing analysis without owned artifacts
- Too many simultaneous drafting lanes
- Contract drift when sibling artifacts define overlapping truth
- Data leakage risk if office filter injection is inconsistent
- Write-path risk if confirmation cards and confirmation gate drift apart
- Controller overload if reports are long or irregular
- False stops caused by weak triage signals outranking stronger downstream evidence
- Compaction drift that drops task goal, protected constraints, or resume point
