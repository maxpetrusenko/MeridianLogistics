# Meridian Dispatch Board

## Current Mode

- controller baseline active
- source set stabilized
- contract freeze active
- build briefs accepted
- implementation phase active
- `B1` accepted
- `B2+B3` accepted after targeted repair
- `B4` renderer implementation is present in current repo state
- `B4` frontend fixtures validate against the accepted response schema and the frontend build is green
- `B5` substantive repair landed and fresh controller verification is green
- controller checkpoint written for post-`B4` carry-forward
- Instinct8 Integration Lane complete
- controller runtime-hook capability is available behind flags
- default-off legacy behavior remains the current execution mode
- runtime-hook slice complete in current repo state
- project-local `.agents/` config refreshed for contract-phase loading
- active cap: `2` drafting or review lanes at once
- healthy sibling lanes stay running if a peer lane wedges
- follow-up decisions stay non-blocking unless the controller re-opens scope
- controller-only final abort rule active
- fail-soft routing active when packet state or evidence is incomplete
- Main lane is the primary orchestrator
- Repair lane is exception-only and requires an exact blocker packet
- Review lane is selective-gate only, not default
- no separate control-hardening lane unless controller behavior itself regresses
- controller stage-packet hardening is complete
- controller checkpoint truth now carries queue snapshot and terminal state
- Controlled Flag-On Validation is complete under Main approval authority
- no queued wave remains in current repo state

## Ownership Rule

- `dispatch-board.md` is the only place allowed to assign or change next ownership.
- Reports, comments, and side notes may recommend a next consumer, but they cannot transfer ownership.
- If any report conflicts with this board, the board wins until the controller updates it.

## Routing Rule

- Non-controller lanes may report only advisory stage verdicts.
- Controller reads the latest checkpoint before any stop, resume, reroute, or acceptance move.
- Controller applies precedence in this order: `verifier` > `review` > `repair` > `triage`.
- Missing packet fields, weak evidence, stale evidence, or contradictory evidence route to `HOLD`, `REPAIR`, `REVIEW`, or `VERIFY`, not final `ABORT`.
- Controller may emit final `ABORT` only after confirming a strong, unsuperseded hard-constraint breach with no viable in-scope repair path.
- Stronger downstream evidence may reopen a lane that weaker earlier triage wanted to stop.

## Approval Policy Snapshot

- Main proceeds automatically for internal hardening, docs or checkpoint sync, bounded fixes, local validation, repo-grounded next steps, and safe research.
- Main self-approves internal design and safe internal controller-owned approval waves within approved scope and surfaces only material deviations.
- Main requests approval only for destructive changes, production-affecting enablement, external spend, irreversible actions, or truly missing required input.
- Main does not pause for architecture subsection approval, policy-surface approval, integration/testing section approval, or file-boundary approval inside approved scope.
- When no queued eligible `auto` wave exists, Main self-approves safe internal approval-gated waves before attempting to auto-instantiate the next approved safe project stage or returning `DONE` or `WAITING_USER_APPROVAL`.
- Drift Review and Research may run in parallel as advisory bounded lanes.
- Repair may run in parallel only for isolated exact-blocker slices that do not conflict with Main's active artifact.
- No parallel lane may mutate the same artifact as Main at the same time.
- Main alone owns final routing, queue state, and controller truth.
- Repair opens only with an exact blocker packet: exact failing assertion or runtime error, exact file path, exact contradiction text or failing check, bounded scope.
- Review opens only when runtime or control-plane logic changed, multi-file patch landed, contract or checkpoint or routing semantics changed, blocker history previously stalled execution, or confidence is low.
- Research or web opens without user interruption when freshness matters or framework or vendor or current-product claims require current evidence.
- Closed waves reopen only with a fresh exact blocker packet plus explicit controller reopen.

## Required Carry-Forward On Handoff Or Compaction

Copy forward verbatim:

```yaml
protected_carry_forward:
  task_goal: string
  hard_constraints:
    - string
  accepted_truth:
    - string
  active_artifact: string
  current_stage: string
  next_owner: string
  resume_point: string
  hard_stop_candidate: string|null
```

## Review Now

No active auto-runnable wave.

Current controller state:
- latest runnable wave completed
- no artifact-backed blocker remains in current repo state
- latest checkpoint, report, and dispatch truth are aligned
- `Controlled Flag-On Validation` was self-approved by Main, executed, and closed green
- terminal state: `DONE`
- no queued wave currently requires user approval

## Queued Next

No queued wave remains in current repo state.

## Blocked Lanes

No active blocked lane remains in current repo state.

## No Longer Blocked

| Priority | Owner | Artifact | Blocker | Next Step |
| --- | --- | --- | --- | --- |
| P1 | Product and PM owner | `prd.md` | none | accepted upstream |
| P1 | Product and PM owner | `backlog.md` | none | accepted upstream |
| P1 | Orchestrator architect | `architecture-overview.md` | none | accepted upstream |
| P1 | Security reviewer | `security-model.md` | none | accepted upstream |
| P1 | QA and eval lead | `eval-plan.md` | none | accepted upstream |
| P1 | Controller | `contracts/tool-schema.yaml` | none | accepted upstream |
| P1 | Controller | `contracts/agent-response-schema.json` | none | accepted upstream |
| P1 | Controller | `contracts/permission-context.json` | none | accepted upstream |
| P1 | Controller | `contracts/eval-test-schema.yaml` | none | accepted upstream |
| P1 | Controller | `B1 data/sql implementation brief` | none | accepted upstream |
| P1 | Controller | `B2+B3 backend/orchestrator implementation brief` | none | accepted upstream |
| P1 | Controller | `B4 frontend implementation brief` | none | accepted upstream |
| P1 | Controller | `B5 eval harness implementation brief` | none | accepted upstream |
| P1 | Data and SQL tools engineer | `B1` implementation lane | none | accepted after review |
| P1 | Backend integration engineer | `B2+B3` implementation lane | none | accepted after review and repair |
| P1 | Frontend structured chat engineer | `B4` implementation lane | none | renderer present, fixtures schema-valid, frontend tests green, build green |
| P1 | QA and eval lead | `B5` implementation lane | none | repaired and green on fresh controller verification |
| P1 | Controller | post-`B4` closeout | none | checkpoint written and queue advanced |
| P1 | Controller | controller checkpoint scaffold | none | contract and scaffold tests validated |
| P1 | Controller | Instinct8 Integration Lane | none | complete, additive, and default-off preserved |
| P1 | Controller | controller runtime-hook repair slice | none | complete and green in current repo state |
| P1 | Controller | follow-up decision tightening | none | complete and queue truth aligned |

## Explicit Do Not Start Yet

- contract redefinition
- scope expansion beyond Memphis PoC
- multi-office rollout
- multi-step workflow implementation
- status-update writes
- notification behavior

Reason: implementation lanes are unlocked, but accepted contracts and accepted build briefs remain frozen; follow-up decisions stay advisory until the controller re-opens scope.

## Completed Recently

- Automation and skills librarian installed project-local `.agents/` config for data, tool, orchestration, and eval lanes.
- PM lane delivered `prd.md` and `backlog.md`.
- Architect, security, and QA lanes delivered accepted prerequisite docs for contract fan-out.
- Contract drafts landed for tool, permission, response, and eval interfaces.
- Controller accepted all 4 contract artifacts and unlocked the build-brief layer.
- Repo hygiene landed for `.gitignore`, manifest lockfile, and stale startup-path fixes.
- `B1` semantic data layer landed and passed review.
- `B2+B3` registry, gateway, graph, and response builder landed and passed review after targeted repair.
- `B5` red tests now enforce contract-invalid enum rejection, response-contract failure handling, and evidence-based release-gate scoring.
- `B5` runner now validates allowed eval enums, marks invalid captured responses as `response_contract` failures, and fails release scoring on missing or contradictory evidence.
- `B4` frontend was recovered to a buildable single-file renderer after an interrupted worker deleted `frontend/src/App.jsx`.
- Controller closed the current `B4` lane and wrote a contract-valid post-`B4` checkpoint instead of reopening on advisory-only evidence.
- Fresh frontend verification now shows the `B4` renderer is present, fixture payloads validate against `contracts/agent-response-schema.json`, frontend tests pass, and the production build completes cleanly.
- Instinct8 runtime-hook integration landed behind flags and passed runtime validation.
- Default-off legacy behavior remains preserved; no global flag enablement was applied.
- Runtime-hook slice is complete, so the next queued wave is decision tightening rather than repair.
- Fresh post-repair validation superseded the stale blocker note in `reports/2026-03-14-1018-controller-post-b4-report.md`.
- Decision-tightening wave is complete, so there is no active wave in current repo state.
- Queue semantics now encode `run_policy`, `eligible`, and `approval_authority`, so Main can self-approve safe internal controller waves without pausing for the user.
- Controller checkpoints now encode queue snapshot and terminal-state truth, so terminal-state comparisons are no longer report-only.
- Controller policy now enforces full next-stage packet metadata, control-truth alignment checks, and `ABORTED` as a hard-invariant-only terminal state.
- Stored controller checkpoint reports now carry queue snapshot and terminal state so report truth matches the hardened checkpoint contract.
- Controlled flag-on validation was executed under Main approval authority and closed without requiring user approval.

## Acceptance Rule

Controller advances work only when:

- source authority is clean
- artifact owner is named
- dependency status is clear
- active lane count is within cap
- gate result is recorded in the incoming report
- any ownership change is recorded here first
- latest checkpoint exists and includes a clear resume point
- any hard-stop candidate has been evaluated under controller precedence rules
