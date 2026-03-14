# Queue Finalization Tightening Contract

Read when:
- binding controller queue transitions
- evaluating wave closeout
- deciding whether a closed wave stays closed, promotes a successor, or reopens

## Goal

Make queue finalization rules binding on the controller instead of advisory in reports.

## Scope

This contract governs these controller queue transitions:

- `active -> finalizing`
- `finalizing -> closed`
- `closed -> next_active`
- `closed -> no_active_wave`
- `closed -> reopened`

`closed -> no_active_wave` means no successor wave is promoted immediately. The controller must then emit exactly one queue result from current accepted semantics:

- `WAITING_USER_APPROVAL`
- `DONE`
- `BLOCKED`

## Completion Predicates

Controller may move `active -> finalizing` only when all are true:

- the current wave mission is complete for its owned artifact
- required gate result is recorded
- latest checkpoint and resume point are present
- no stronger unsuperseded evidence keeps the wave in active repair or review
- queue truth is current enough to evaluate the next transition

Controller may move `finalizing -> closed` only when all are true:

- closeout decision is recorded
- successor or terminal queue result is recorded
- checkpoint state is portable and contract-valid
- any blocker packet is exact, artifact-backed, and attached to the closeout decision

## Closeout Decision Rules

When evaluating wave closeout, controller must enforce:

- completion predicates
- closeout decision rules
- state machine transitions
- acceptance tests

Closeout routing rules:

1. load the latest controller checkpoint
2. discard stale or superseded evidence
3. reject queue transitions that bypass required completion predicates
4. if an eligible `auto` wave exists, promote it immediately
5. if no eligible `auto` wave exists, self-approve any queued internal `explicit_request` wave that stays within approved scope and does not require user authority
6. if no eligible `auto` wave exists, attempt to auto-instantiate the next approved safe project stage when it is within scope, non-destructive, repo-grounded, and does not require explicit approval
7. if no eligible, self-approvable, or instantiable work remains and a queued wave still requires user approval, emit `WAITING_USER_APPROVAL`
8. if no runnable or gated wave remains, emit `DONE`
9. emit `BLOCKED` only with an exact artifact-backed blocker packet
10. persist the resulting queue snapshot plus terminal state into the latest controller checkpoint
11. reopen a closed wave only on stronger later evidence that directly contradicts the closeout record

## State Machine Transitions

Valid transitions:

- `active -> finalizing`
- `finalizing -> closed`
- `closed -> next_active`
- `closed -> no_active_wave`
- `closed -> reopened`

Invalid transitions:

- `active -> closed` without `finalizing`
- `finalizing -> next_active` without recording the closed wave
- `closed -> reopened` on advisory-only evidence
- `closed -> reopened` without an exact failing assertion, exact file path, and exact contract contradiction text when a closed-lane reopen rule requires that packet
- any queue change that skips checkpoint, gate, or terminal-state recording

## Acceptance Tests

This contract is satisfied only if controller behavior proves:

- a completed wave with an eligible `auto` successor transitions to `next_active`
- a completed wave with no queued eligible `auto` successor but an internally approvable `explicit_request` successor transitions to `next_active`
- a completed wave with no queued eligible `auto` successor but a safe instantiable next stage transitions to `next_active`
- a completed wave with no eligible, self-approvable, or instantiable `auto` successor and a user-approved `explicit_request` successor transitions to `no_active_wave` plus terminal state `WAITING_USER_APPROVAL`
- a completed wave with no successor and no blocker transitions to `no_active_wave` plus terminal state `DONE`
- a completed wave with an exact artifact-backed blocker transitions to `no_active_wave` plus terminal state `BLOCKED`
- a closed wave does not reopen on weak, stale, partial, or advisory-only evidence
- a closed wave reopens only when the blocker packet meets the exact reopen rule for that lane
- the latest controller checkpoint records the same queue snapshot and terminal state that the controller report and dispatch board claim

## Binding Rule

Queue transitions that violate this contract are invalid.
