# Meridian Controller Runbook

## Core Rules

1. Controller owns truth.
2. Child agents report to controller only.
3. One active artifact per worker.
4. Shared control docs have explicit owners.
5. No child agent edits another child's active artifact.
6. Every write path gets security review and QA coverage before acceptance.
7. Every report must state exact inputs used and exact asks back.
8. `AGENTS.md` and `CLAUDE.md` are both canonical; on conflict, follow the stricter rule.
9. `dispatch-board.md` is the only file allowed to assign or change next ownership.
10. Parallel drafting is allowed only across sibling artifacts unlocked by the same accepted parent.
11. A healthy lane stays untouched when a peer lane wedges; replace only the wedged worker.

## Source Authority

- Authoritative business source:
  - `meridian-logistics-case-study.txt`
  - `source-brief.md`
- Operational controller truth:
  - `agent-registry.md`
  - `artifact-ledger.md`
  - `dispatch-board.md`
  - `decisions.md`
- Project-local agent config, when present:
  - `.agents/skills.must.txt`
  - `.agents/skills.good.txt`
  - `.agents/skills.task.txt`
  - `.agents/agents/<role>.md`
- Working docs:
  - `plan.md`
  - `thoughts.md`
- Quarantined until reconciled:
  - `meridian-logistics-deck-summary.md`
  - `meridian-logistics-deck-extracted.txt`
  - other raw deck extracts

Do not treat proposed architecture choices as source facts until the controller promotes them in `decisions.md`.

## Worker Startup Checklist

Every worker task starts by reading:
- local `AGENTS.md`
- local `CLAUDE.md`
- `/Users/maxpetrusenko/Desktop/Projects/agent-scripts/docs/subagent.md`
- `/Users/maxpetrusenko/Desktop/Projects/skills/AGENTS.md`

If present, also read:
- `.agents/skills.must.txt`
- `.agents/skills.good.txt`
- `.agents/skills.task.txt`
- matching `.agents/agents/<role>.md`

Then the worker must:
- load or check out the needed skills for that task
- confirm workspace rules are loaded
- name its owned artifact before editing

If cloning OSS or external tools:
- destination must be `/Users/maxpetrusenko/Desktop/Projects/oss`

## Status Vocabulary

- `queued`
- `ready`
- `in_progress`
- `blocked`
- `done`

## Spawn Rules

Spawn a child agent when:
- work is independent
- artifact owner is clear
- output format is clear
- success criteria are testable
- startup checklist can be satisfied
- parent artifact is already accepted
- owned output does not overlap another active lane

Do not spawn when:
- task is ambiguous
- multiple agents would edit the same file at once
- root cause is still unknown
- controller has not named the artifact owner
- worker has not loaded required docs or skills
- upstream artifact is still drafting or under review
- two workers would define the same contract from different angles

## Parallel Lane Policy

- Parallelize only across siblings, never across ancestor and descendant artifacts.
- Controller default cap is `2` drafting workers in parallel.
- Reviewer lane is separate from drafting lanes and can run after each artifact lands.
- A downstream lane stays blocked until its required upstream artifact passes review.
- If two candidate artifacts share mutable files, a contract boundary, or the same truth surface, run them sequentially.

Safe pattern:

```text
accepted parent artifact
├─ child artifact A
└─ child artifact B
```

Unsafe pattern:

```text
artifact A still drafting
└─ artifact B starts anyway
```

## Reviewer Gates

- Every drafted artifact gets a controller or reviewer gate before it unlocks downstream work.
- Sibling artifacts may draft in parallel, but each sibling needs its own pass or fail result.
- Controller unlocks the next layer only after all required siblings pass.

## Stage Verdict Lanes

- Non-controller lanes emit advisory stage verdicts only. They do not stop the system finally.
- Only the controller may emit final control actions: `PROCEED`, `REPAIR`, `REVIEW`, `VERIFY`, `HOLD`, `ABORT`.
- Missing packet fields, weak evidence, or partial outputs must fail soft as `HOLD`, `REPAIR`, `REVIEW`, or `VERIFY`, not `ABORT`.

### Triage lane

- Allowed verdicts:
  - `PROCEED`
  - `HOLD`
  - `ESCALATE_REPAIR`
  - `ESCALATE_REVIEW`
- Meaning:
  - `PROCEED`: packet is sufficient for the next lane
  - `HOLD`: packet is incomplete and needs more evidence or a stronger checkpoint
  - `ESCALATE_REPAIR`: packet or artifact is fixable without reopening scope
  - `ESCALATE_REVIEW`: packet is ambiguous and needs a human or reviewer judgment

### Repair lane

- Allowed verdicts:
  - `REPAIRED`
  - `PARTIAL_REPAIR`
  - `NEEDS_REVIEW`
  - `BLOCKED`
- Meaning:
  - `REPAIRED`: the cited defect is closed and can supersede weaker earlier negatives
  - `PARTIAL_REPAIR`: some work landed, but the lane is not ready to pass forward
  - `NEEDS_REVIEW`: a code or doc change landed and should be reviewed before acceptance
  - `BLOCKED`: repair cannot continue without controller input, but this is still advisory only

### Review lane

- Allowed verdicts:
  - `APPROVE`
  - `REQUEST_REPAIR`
  - `NEEDS_VERIFICATION`
  - `HOLD`
- Meaning:
  - `APPROVE`: reviewed artifact is acceptable for the next gate
  - `REQUEST_REPAIR`: a fix is needed before acceptance
  - `NEEDS_VERIFICATION`: reviewer sees acceptable direction but wants explicit verification evidence
  - `HOLD`: evidence is too weak or conflicting to route forward confidently

### Verifier lane

- Allowed verdicts:
  - `PASS`
  - `FAIL_SOFT`
  - `FAIL_HARD`
  - `INCONCLUSIVE`
- Meaning:
  - `PASS`: verification evidence supports the current artifact and may supersede weaker negatives
  - `FAIL_SOFT`: verification found a fixable problem or missing evidence
  - `FAIL_HARD`: verification found a likely hard-constraint breach; controller must still make the final decision
  - `INCONCLUSIVE`: verification evidence is weak, partial, stale, or contradictory

## Controller Decision Function

Controller final routing uses this order:

1. Load the latest controller checkpoint and its protected carry-forward block.
2. Discard stale lane verdicts already superseded by a newer artifact, newer checkpoint, or stronger later-stage evidence.
3. Check for a proven hard-constraint breach against accepted truth and protected constraints.
4. Apply stage precedence across remaining lane verdicts: `verifier` > `review` > `repair` > `triage`.
5. Break same-stage ties by evidence strength, then by recency.
6. Emit exactly one final controller action.

Controller may emit `ABORT` only when all are true:

- the breach hits a protected constraint or accepted truth
- the evidence is strong
- the evidence is not stale or superseded
- no defined repair or review path remains inside current scope

Controller must not emit `ABORT` when:

- triage is missing packet fields
- repair, review, or verifier evidence is stronger than the earlier stop signal
- evidence is weak, partial, stale, or contradictory
- the checkpoint is missing a clear resume point

Default controller routing:

- strongest verdict is positive and no stronger negative remains: `PROCEED`
- fixable defect is present: `REPAIR`
- review judgment is missing or requested: `REVIEW`
- review passed but explicit proof is still needed: `VERIFY`
- evidence is incomplete, ambiguous, or checkpoint state is weak: `HOLD`
- only the hard-breach test above passes: `ABORT`

## Queue Finalization Contract

Controller queue transitions MUST follow the Queue Finalization Tightening Contract.

Reference:
- `docs/plans/queue-finalization-contract.md`

When evaluating wave closeout, controller must enforce:
- completion predicates
- closeout decision rules
- state machine transitions
- acceptance tests

Queue transitions that violate this contract are invalid.

## Wave Promotion Rule

After every completed wave, controller must immediately evaluate queue state.

Controller run-to-completion logic:

1. mark the current wave complete or closed
2. scan queued waves for the next eligible item
3. if an eligible `auto` wave exists, activate it immediately and continue execution
4. if no queued eligible `auto` wave exists, self-approve any queued internal `explicit_request` wave that stays within approved scope, is reversible or sandboxed, is non-destructive, is not a business-logic redesign, is not a framework migration, is not prod or global enablement, and does not require user authority
5. if no queued eligible or self-approved `auto` wave exists, check for a safe next approved project stage that can be derived from repo or context and instantiate it as a new `auto` wave
6. if no eligible, self-approvable, or instantiable work remains but a queued wave still requires user approval, return `WAITING_USER_APPROVAL` with the exact wave name
7. if no runnable or safely instantiable wave remains, return `DONE`
8. if an artifact-backed blocker exists, return `BLOCKED` with the exact blocker packet
9. persist the resulting queue snapshot plus terminal state into the latest controller checkpoint

Valid next-stage candidate packet:

- `wave_name`
- `owner`
- `objective`
- exact files or artifacts in scope
- `success_check`
- `why_next`
- `run_policy`

Status reporting alone is never a terminal reason to stop.

## Approval Policy Layers

### Main approval policy

- Main continues automatically for internal hardening, docs sync, checkpoint sync, bounded code fixes, local validation, repo-grounded next steps, and safe research.
- Main self-approves internal design choices and internal controller-owned approval waves when scope is already approved, business logic is unchanged, the work is reversible or sandboxed, no checkpoint schema widening is required, no framework migration begins, no prod or global enablement is involved, and no destructive or irreversible action is involved.
- Main requests approval only for destructive work, production-affecting enablement, external spend, irreversible actions, or truly missing required input.
- Do not interrupt for architecture subsection approval, policy-function boundary approval, integration/testing section approval, or file-boundary approval when the work remains inside approved scope.
- Main stops only on `DONE`, `WAITING_USER_APPROVAL`, `BLOCKED`, or `ABORTED`.

### Repair approval policy

- Open Repair only when an exact blocker packet exists.
- Exact blocker packet requires exact failing assertion or runtime error, exact file path, exact contradiction text or failing check, and bounded scope.
- If that packet does not exist, do not open Repair.

### Review approval policy

- Review is selective.
- Open Review only when runtime or control-plane logic changed, more than one file changed, contract or checkpoint or routing semantics changed, blocker history previously stalled execution, or confidence is low.
- Otherwise Main continues directly.

### Research and web approval policy

- Use research or web without interrupting the user when freshness matters, framework or vendor or current-product claims are involved, repo evidence does not answer the question, or architectural comparison needs current evidence.
- Stay local-first for repo truth, code, and tests.

### Parallel lane policy

- Main remains the only controller lane.
- Drift Review Lane is advisory and bounded.
- Open Drift Review in parallel when a wave runs longer than one major step, plan changed after new evidence, multiple reports or checkpoints or docs were touched, or Main is about to close or promote a wave.
- Research Lane is advisory and bounded.
- Open Research in parallel when framework or vendor or current-product claims need current facts and repo truth cannot answer safely.
- Repair Lane is still exact-blocker only.
- Open parallel Repair only when exact blocker evidence exists, scope is isolated, and the repair does not mutate Main's active artifact concurrently.
- Main may continue while Drift Review or Research runs.
- Main may continue while Repair runs only if the blocker does not affect Main's current reasoning path.
- If the blocker affects Main's current reasoning path, pause that slice and wait for Repair.
- Advisory subagent results do not change controller truth unless Main explicitly merges them.

### Completion and queue approval policy

- Close a wave only when intended change exists, required checks passed, and no unsuperseded exact blocker remains.
- Queue state, checkpoint state, report state, and dispatch truth must align on terminal state and next wave before controller returns a terminal stop.
- If those control-plane truth surfaces diverge, controller opens a bounded sync wave instead of trusting the terminal result.
- After closeout:
  1. activate the next eligible `auto` wave immediately
  2. if no queued eligible `auto` wave exists, self-approve any queued internal `explicit_request` wave that remains within approved scope, is reversible or sandboxed, is non-destructive, is not a business-logic redesign, is not a framework migration, is not prod or global enablement, and does not require user authority
  3. if no queued eligible or self-approved `auto` wave exists, auto-instantiate the next approved safe project stage when it is within scope, non-destructive, repo-grounded, and does not require explicit approval
  4. emit `WAITING_USER_APPROVAL` only for queued waves that still require user approval when no auto work remains
  5. emit `DONE` only when no runnable or safely instantiable wave remains
  6. emit `BLOCKED` only with exact blocker evidence
  7. persist the same queue snapshot and terminal state into the latest controller checkpoint

### Abort terminal policy

- `ABORTED` is reserved for hard invariant or unsafe states only.
- Queue finalization must not emit `ABORTED` for weak evidence, missing packet fields, or routine closeout.

### Reopen approval policy

- Reopen only with a fresh exact blocker packet and an explicit controller reopen decision.
- Never reopen from stale notes, vague commentary, or contradictory old reports.

Wave queue fields:

```yaml
wave_queue_item:
  wave_name: string
  status: queued|active|done|blocked
  run_policy: auto|explicit_request|blocked_until_input
  eligible: true|false
  approval_authority: main|user
  depends_on:
    - string
  requires_explicit_request: true|false
```

Controller checkpoint queue fields:

```yaml
controller_checkpoint_queue:
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

## Wedged Worker Recovery

- Mark the wedged lane `blocked`.
- Keep healthy sibling lanes running.
- Re-spawn only the blocked lane with the same owned artifact and narrower ask.
- Use repo state and accepted artifacts as recovery context, not prior chat history.
- If the second replacement also wedges, escalate to controller with options instead of widening scope.

## Controller Checkpoint

Write a compact checkpoint on:

- handoff
- resume
- repair request
- review request
- verifier request
- pre-compaction
- final controller decision

Checkpoint schema:

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
    triage:
      verdict: PROCEED|HOLD|ESCALATE_REPAIR|ESCALATE_REVIEW|null
      evidence_strength: weak|medium|strong|null
      artifact_ref: string|null
      supersedes: string|null
    repair:
      verdict: REPAIRED|PARTIAL_REPAIR|NEEDS_REVIEW|BLOCKED|null
      evidence_strength: weak|medium|strong|null
      artifact_ref: string|null
      supersedes: string|null
    review:
      verdict: APPROVE|REQUEST_REPAIR|NEEDS_VERIFICATION|HOLD|null
      evidence_strength: weak|medium|strong|null
      artifact_ref: string|null
      supersedes: string|null
    verifier:
      verdict: PASS|FAIL_SOFT|FAIL_HARD|INCONCLUSIVE|null
      evidence_strength: weak|medium|strong|null
      artifact_ref: string|null
      supersedes: string|null
  hard_stop_candidate: string|null
  protected:
    task_goal: string
    hard_constraints:
      - string
    accepted_truth:
      - string
    active_artifact: string
    resume_point: string
```

## Compaction-Safe Carry-Forward

Before any summary or context compaction, copy this block forward verbatim:

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

Never summarize away:

- task goal
- hard constraints
- accepted truth refs
- active artifact
- current stage
- next owner
- exact resume point
- any hard-stop candidate under evaluation

## Dispatch Loop

1. Read `dispatch-board.md`
2. Read `artifact-ledger.md`
3. Pick up to two sibling `ready` artifacts with named owners and no shared mutable file
4. Spawn one worker per active sibling artifact
5. Queue all other ready artifacts until an active lane passes or fails
6. Require a report update before changing ownership or status
7. Record any ownership change only in `dispatch-board.md`
8. Record gate result in `dispatch-board.md`
9. Move only after acceptance or explicit rejection

## Baseline Sequence

1. Controller refreshes source authority, dispatch board, and artifact ledger.
2. Product and PM owner turns facts into `prd.md` and `backlog.md`.
3. Automation and skills librarian keeps task manifests, skill checkout, and reporting hygiene current.
4. Architect defines system flow, contracts, and dependencies.
5. Security reviewer checks auth, permission filters, and write gates before build work starts.
6. QA and eval lead writes readiness criteria and eval coverage from PRD plus architecture.
7. Data, backend, and frontend agents build against accepted contracts.
8. Controller accepts or sends back.

## Reporting Template

```md
# Agent Report

Agent: <name>
Status: queued|ready|in_progress|blocked|done
Mission: <single sentence>
Owned artifact:
- <path>
Inputs used:
- <file or artifact>
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
- <path>

Decisions needed:
- <question or "none">

Next actions:
- <next step>

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

Reports may recommend a next consumer, but they do not assign ownership. Only `dispatch-board.md` can do that.
Non-controller reports may not emit final `ABORT`.

## Ownership Model

- Controller owns:
  - `agent-map.md`
  - `agent-registry.md`
  - `runbook.md`
  - `decisions.md`
  - `artifact-ledger.md`
  - `dispatch-board.md`
- Automation and skills librarian owns startup manifests, worker prompt shells, and skill-selection notes
- Worker owns only assigned delivery artifacts
- QA owns test matrix and defect log
- PM owns PRD and backlog
- Architect owns system contracts

## Escalation Rules

Escalate to controller when:
- source facts conflict
- quarantined source looks necessary
- security rules are unclear
- write behavior might exceed PoC scope
- new dependency appears
- stricter-rule conflicts between `AGENTS.md` and `CLAUDE.md` need interpretation
- two agents need the same file
- blocker survives 2 attempts
- a report recommendation conflicts with `dispatch-board.md`

## Acceptance Gates

- PRD gate: Memphis-only PoC, 90-day scope, target workflows, and success criteria are written
- Architecture gate: system flow, tool boundaries, contract ownership, and permission flow are written
- Build gate: UI contracts and API contracts align
- Security gate: JWT passthrough, office filter injection, hidden columns, and confirmation gate are checked
- QA gate: evals cover reads, single-step bookings, status updates, notifications, and write confirmations
