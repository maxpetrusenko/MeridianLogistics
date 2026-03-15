# Reports

## Goal

Keep child-agent output out of the main thread. Every child agent writes one report per meaningful task and sends the result back to the controller.

## Filename Pattern

`YYYY-MM-DD-HHMM-<agent>-report.md`

Example:

`2026-03-13-1930-data-tools-report.md`

## Required Template

```md
# Agent Report

Agent: <name>
Status: queued|running|blocked|done
Mission: <single sentence>
Owned artifact:
- <path>
Inputs used:
- <path or artifact>
Stage:
- triage|repair|review|verifier|controller
Stage verdict:
- <lane-specific verdict or controller final action>
Evidence strength:
- weak|medium|strong
Supersedes:
- <prior report id, artifact ref, or "none">

Findings:
- <fact>

Artifacts produced:
- <path or "none">

Decisions needed:
- <question or "none">

Next actions:
- <step>

Next consumer:
- <agent or "controller">

Gate result:
- <none|drafted|accepted|rejected>
Resume point:
- <single next concrete step>
Hard stop candidate:
- <constraint breach under evaluation or "none">
Checkpoint:
- <compact checkpoint block or checkpoint ref>

Blockers:
- <blocker or "none">

Confidence: low|medium|high
```

## Rules

- Report to controller only
- Start each task by reading local `AGENTS.md`, local `CLAUDE.md`, subagent guide, and skills guide
- Load or check out needed skills on every task
- Name the owned artifact explicitly
- Include exact files read
- Include exact artifacts produced
- Keep findings factual
- Ask for decisions explicitly
- Include the next consumer and gate result
- Use only lane-specific advisory verdicts unless you are the controller
- Do not write raw `ABORT` unless the controller is issuing the final decision
- If packet fields are missing, prefer `HOLD`, `ESCALATE_REPAIR`, `REQUEST_REPAIR`, `FAIL_SOFT`, or `INCONCLUSIVE`
- Record what earlier output this report supersedes when stronger downstream evidence exists
- Include an exact resume point and compact checkpoint on every meaningful handoff
- Do not assign or transfer ownership in a report; only `dispatch-board.md` can do that
- Do not edit shared control docs unless assigned as owner
- When a controller wave closes, the controller report must also state the next queue result: auto-promoted wave, `WAITING_USER_APPROVAL`, `DONE`, `BLOCKED`, or `ABORTED`
- Main controller reports should assume automatic continuation unless policy requires delegation, approval, or a terminal state
- Stored controller checkpoints must include queue snapshot plus terminal-state truth so report truth can be compared directly against checkpoint and dispatch truth
- **Controller checkpoint truth is authoritative on resume**: reports should reference checkpoint queue truth, not thread summaries
- **Derived next-wave packet may be emitted from checkpoint truth**: when no fresh manual packet exists, the checkpoint queue snapshot provides the next runnable wave
- **Status-only updates are never terminal**: resume with eligible auto wave must continue, not pause for user input
- Repair requests must include an exact blocker packet: exact failing assertion or runtime error, exact file path, exact contradiction text or failing check, bounded scope
- Review requests must state which selective-gate condition triggered review
- Review requests must stay bounded to one artifact or at most two directly related files; split larger review packets before dispatch
- Review reports must put the lane verdict on the first non-empty line using exactly one of `APPROVE`, `REQUEST_REPAIR`, `NEEDS_VERIFICATION`, or `HOLD`
- Reopen requests must include fresh exact blocker evidence and explicit controller reopen intent

## Compact Checkpoint

Copy this shape into the `Checkpoint` field or point to a stored checkpoint containing the same fields:

```yaml
controller_checkpoint:
  version: cp1
  task_id: string
  goal: string
  active_artifact: string
  current_stage: triage|repair|review|verifier|controller
  current_decision: PROCEED|REPAIR|REVIEW|VERIFY|HOLD|ABORT
  next_owner: string
  resume_point: string
  accepted_truth:
    - string
  constraints:
    - string
  lane_verdicts:
    triage: { verdict: string|null, evidence_strength: weak|medium|strong|null, artifact_ref: string|null, supersedes: string|null }
    repair: { verdict: string|null, evidence_strength: weak|medium|strong|null, artifact_ref: string|null, supersedes: string|null }
    review: { verdict: string|null, evidence_strength: weak|medium|strong|null, artifact_ref: string|null, supersedes: string|null }
    verifier: { verdict: string|null, evidence_strength: weak|medium|strong|null, artifact_ref: string|null, supersedes: string|null }
  hard_stop_candidate: string|null
  protected:
    task_goal: string
    hard_constraints:
      - string
    accepted_truth:
      - string
    active_artifact: string
    resume_point: string
  queue: null | {
    wave_name: string,
    status: queued|active|done|blocked,
    run_policy: auto|explicit_request|blocked_until_input,
    eligible: true|false,
    requires_explicit_request: true|false,
    approval_authority: main|user
  }
  terminal_state: DONE|BLOCKED|WAITING_USER_APPROVAL|ABORTED|null
```

## Approval Policy Summary

- Main may proceed without asking for internal hardening, docs or checkpoint sync, bounded fixes, local validation, repo-grounded next steps, and safe research.
- Main also self-approves internal design inside approved scope and should report only material deviations instead of asking for subsection approval.
- Main asks only for destructive work, production-affecting enablement, external spend, irreversible actions, or truly missing required input.
- Do not emit controller reports that pause only for architecture subsection approval, policy-surface approval, integration/testing section approval, or file-boundary approval inside approved scope.
- When no queued eligible `auto` wave exists, controller reports should first record whether a safe internal approval-gated wave was self-approved or a safe next approved project stage was considered for auto-instantiation before emitting `DONE` or `WAITING_USER_APPROVAL`.
- Any auto-instantiated next-stage packet recorded in a controller report must include `wave_name`, `owner`, `objective`, exact files or artifacts in scope, `success_check`, `why_next`, and `run_policy`.
- Queue state, checkpoint state, report state, and dispatch truth must agree on terminal state and next wave before a controller report claims a terminal stop.
- Drift Review and Research reports are advisory only and must not claim controller truth changes.
- Parallel Repair reports must include exact blocker evidence and confirm isolated scope.
- If a parallel lane touched or proposed changes for the same artifact Main owns, the report must mark that conflict explicitly.
- Advisory subagent output is not merged until Main records the merge decision.
- Review is selective, not default.
- Repair is exact-blocker only.
- `WAITING_USER_APPROVAL` is valid only when no eligible, self-approvable, or safely instantiable `auto` wave remains and a queued user-authority approval wave remains.
- `ABORTED` is valid only for a hard invariant or unsafe-state terminal stop.
- `queue: null` is valid only when there is no active or waiting wave snapshot to persist into the latest checkpoint.
