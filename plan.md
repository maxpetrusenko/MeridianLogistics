# Meridian Logistics Agent Plan

## Goal

Produce the architecture package for the Meridian conversational freight agent, then execute the 90 day PoC with the controller agent doing orchestration only.

## Source Facts

- `meridian-logistics-case-study.pdf` extracted successfully to `/tmp/meridian-case-study.txt`
- `meridian-logistics-deck.pdf` extracted, but the resulting narrative conflicts with the case study and is quarantined
- 90 day PoC scope from case study: Memphis office only, read queries plus single-step bookings
- Main hard constraints: office-scoped permissions, sensitive column exclusion, safe SQL, confirmation before writes, rich chat responses

## Current State

- Control docs exist and are usable.
- First-wave delivery artifacts do not exist yet.
- The next nonstop loop must create delivery artifacts, not more meta-docs.
- Do not let quarantined deck material leak into PRD or architecture work.

## Recommended Approach

Use a controller plus a named specialist swarm. Do not let the controller do deep analysis or implementation. Every specialist returns a short artifact, status, blockers, and next action.

### Recommended Agent Count

- `1` controller
- `8` baseline workers
- burst to `12` to `14` total only when parallel build or review spikes justify it

Active cap at one time: `4` to `5`

Reason:

- enough specialization to avoid context bloat
- small enough to avoid merge and planning chaos
- matches the case-study split between product, architecture, security, build, and evaluation

## Immediate Nonstop Sequence

1. Refresh `dispatch-board.md` and `artifact-ledger.md`
2. PM owner writes `prd.md`
3. PM owner writes `backlog.md`
4. Architect writes `architecture-overview.md`
5. Security reviewer writes `security-model.md`
6. QA lead writes `eval-plan.md`
7. Contract artifacts are created from those accepted docs
8. Only then split data, backend, frontend, and workflow implementation agents

## Recommended Active Set Right Now

- Controller
- Automation and skills librarian
- Product and PM owner
- Orchestrator architect
- Security reviewer joins once PRD draft exists

Do not start data, tooling, frontend, or eval implementation agents until the contract layer exists.

## Delivery Artifacts To Create Next

- `prd.md`
- `backlog.md`
- `architecture-overview.md`
- `security-model.md`
- `eval-plan.md`
- `contracts/tool-schema.yaml`
- `contracts/agent-response-schema.json`
- `contracts/eval-test-schema.yaml`
- `contracts/permission-context.json`

## Phase Breakdown

### Phase 0: Control and Source Hygiene

- quarantine bad source inputs
- freeze controller truth docs
- create artifact ledger and dispatch board

### Phase 1: Product and Architecture Contracts

- PRD
- backlog
- architecture overview
- security model
- eval plan
- contract files

### Phase 2: Data and Tool Layer

- safe query tool catalog
- permission context propagation
- write tool boundaries

### Phase 3: Agent and Workflow Layer

- planner and router
- read and write graph split
- suspend and resume behavior

### Phase 4: UI and Structured Responses

- chat shell
- structured response renderer
- confirmation cards and timelines

### Phase 5: Evaluation and Iteration

- replay harness
- red-team prompts
- latency and accuracy loops

## Parallelization Rules

Safe to parallelize:

- PRD drafting and architecture sketching
- backlog drafting and eval-plan drafting
- docs updates after contract stabilization

Do not parallelize:

- PRD finalization and security acceptance
- contract files owned by different agents in the same path at the same time
- backend, data, or frontend implementation before accepted contracts exist

## Read This First

- `decisions.md`
- `agent-registry.md`
- `artifact-ledger.md`
- `dispatch-board.md`
