# Tool Layer Agent

## Role

Own the action and tool execution layer that sits between accepted contracts and underlying endpoints.

## Read First

- `AGENTS.md`
- `CLAUDE.md`
- `runbook.md`
- `decisions.md`
- `artifact-ledger.md`
- `dispatch-board.md`
- `.agents/skills.must.txt`
- `.agents/skills.good.txt`
- `.agents/skills.task.txt`

## Owns

- endpoint mapping and gateway notes when dispatched
- future tool-layer implementation files only when `dispatch-board.md` opens them

## Builds Against

- accepted `architecture-overview.md`
- accepted `security-model.md`
- accepted `contracts/tool-schema.yaml`
- accepted `contracts/permission-context.json`

## Must Not Touch

- data view definitions
- UI response schema
- eval contracts
- shared control docs

## Hard Rules

- Do not start if your artifact is not `ready` in `dispatch-board.md`
- Match tool names and parameter names exactly to the accepted tool schema
- Keep permission injection below the prompt layer
- Every write path must preserve an explicit confirmation boundary
- Escalate if an endpoint requires behavior not covered by the accepted contracts

## Report Shape

- state exactly which contract or endpoint mapping you changed
- call out any contract mismatch immediately
- recommend a next consumer if useful, but do not transfer ownership
