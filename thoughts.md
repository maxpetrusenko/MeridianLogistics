# Meridian Logistics Controller Notes

## Current Read

The case study is enough to start. The extracted deck conflicts with it and is quarantined. That is useful as a warning, not as source material.

## Missing Inputs

- full schema appendix
- any existing codebase for FreightView
- real KPI targets for accuracy, latency, and broker adoption
- preferred deployment environment and auth stack details

## Key Risks

### Architecture risk

The naive LLM to SQL path already fails too often. Query planning must be constrained before execution work starts.

### Security risk

Cross-office leakage and sensitive rate exposure are the primary failure modes. Security cannot be a late review layer.

### Workflow risk

Multi-step booking flows can sprawl quickly. The PoC must stay on single-step booking with explicit confirmation boundaries.

### Delivery risk

Too many parallel agents will create conflicting plans. Cap active specialists at five.

## Nonstop Guidance

- Keep the controller on `dispatch-board.md` and `artifact-ledger.md`.
- Do not spawn build agents before PRD, architecture, and security artifacts exist.
- Do not treat proposed architecture choices as source facts.
- Do not allow quarantined deck material into PM or architecture work.

## Controller Rules

- controller does routing, synthesis, prioritization
- specialists do reading, drafting, coding, and review
- one artifact owner at a time
- every artifact must name its next consumer
- blockers older than two loops get escalated and reframed

## What To Materialize First

1. PRD
2. architecture diagram
3. security model
4. interface contracts
5. eval plan
6. execution backlog
7. dispatch board
8. artifact ledger

## Suggested Artifact Set

- `plan.md` for phase plan and swarm roster
- `thoughts.md` for risks, gaps, controller rules
- `agent-map.md` for visual orientation
- `artifact-ledger.md` for exact owner and status per artifact
- `dispatch-board.md` for live queue and next assignments
- later: `prd.md`, `architecture-overview.md`, `security-model.md`, `eval-plan.md`, `backlog.md`

## Success Definition

Good for now means:

- future agents can start from files instead of chat history
- controller can name the next agent in under one minute
- scope is split clearly into PoC now vs later
- security and evaluation are first-class tracks, not cleanup work
- no worker can accidentally read a quarantined source and steer the project off course
