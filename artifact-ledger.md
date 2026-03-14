# Meridian Artifact Ledger

## Status Legend

- `queued`
- `ready`
- `blocked`
- `in_progress`
- `done`

## Control Artifacts

| Artifact | Owner | Status | Depends On | Next Consumer | Done When |
| --- | --- | --- | --- | --- | --- |
| `source-brief.md` | Controller | `done` | case study | PM owner | business facts, scope, and risks captured |
| `decisions.md` | Controller | `in_progress` | source brief, controller audits | all workers | source facts and operating decisions separated from proposals |
| `agent-registry.md` | Controller | `done` | controller decisions | all workers | baseline roster and outputs are explicit |
| `runbook.md` | Controller | `done` | controller decisions | all workers | spawn, reporting, and acceptance rules are explicit |
| `dispatch-board.md` | Controller | `in_progress` | controller decisions | all workers | queue reflects current ready and blocked work |
| `reports/2026-03-14-1018-controller-checkpoint.json` | Controller | `done` | `dispatch-board.md`, `artifact-ledger.md`, `decisions.md` | controller | closeout state and resume point are contract-valid and portable |
| `reports/2026-03-14-1018-controller-post-b4-report.md` | Controller | `done` | `reports/2026-03-14-1018-controller-checkpoint.json` | controller | post-`B4` routing and evidence are recorded |
| `reports/2026-03-14-1026-controller-runtime-hook-checkpoint.json` | Controller | `done` | runtime-hook validation, `dispatch-board.md`, `artifact-ledger.md`, `decisions.md` | controller | post-Instinct8 state and resume point are contract-valid and portable |
| `reports/2026-03-14-1026-controller-runtime-hook-closeout.md` | Controller | `done` | `reports/2026-03-14-1026-controller-runtime-hook-checkpoint.json` | controller | runtime-hook closeout and default-off routing are recorded |
| `reports/2026-03-14-1027-controller-next-wave-checkpoint.json` | Controller | `done` | `reports/2026-03-14-1026-controller-runtime-hook-checkpoint.json`, current repo validation | controller | next-wave state and resume point are contract-valid and portable |
| `reports/2026-03-14-1027-controller-next-wave-report.md` | Controller | `done` | `reports/2026-03-14-1027-controller-next-wave-checkpoint.json` | controller | next-wave routing is recorded after runtime-hook completion |
| `reports/2026-03-14-1038-controller-post-repair-checkpoint.json` | Controller | `done` | fresh runtime-hook and contract validation | controller | post-repair verification state and resume point are contract-valid and portable |
| `reports/2026-03-14-1038-controller-post-repair-report.md` | Controller | `done` | `reports/2026-03-14-1038-controller-post-repair-checkpoint.json` | controller | stale blocker text is superseded by fresh verification evidence |
| `reports/2026-03-14-1110-controller-no-active-wave-checkpoint.json` | Controller | `done` | `reports/2026-03-14-1038-controller-post-repair-checkpoint.json`, current queue truth | controller | no-active-wave state and resume point are contract-valid and portable |
| `reports/2026-03-14-1110-controller-no-active-wave-report.md` | Controller | `done` | `reports/2026-03-14-1110-controller-no-active-wave-checkpoint.json` | controller | finished-wave closeout and no-active-wave queue truth are recorded |
| `reports/2026-03-14-1121-controller-run-policy-checkpoint.json` | Controller | `done` | current queue truth, controller routing docs | controller | run-policy and terminal-state semantics are contract-valid and portable |
| `reports/2026-03-14-1121-controller-run-policy-report.md` | Controller | `done` | `reports/2026-03-14-1121-controller-run-policy-checkpoint.json` | controller | deterministic queue-promotion rules are recorded and supersede the prior implicit-stop behavior |
| `reports/2026-03-14-1332-controller-hardening-closeout-checkpoint.json` | Controller | `done` | controller policy/runtime validation, current queue truth | controller | hardened controller closeout state is contract-valid and portable |
| `reports/2026-03-14-1332-controller-hardening-closeout-report.md` | Controller | `done` | `reports/2026-03-14-1332-controller-hardening-closeout-checkpoint.json` | controller | hardening completion and current terminal state are recorded |
| `reports/2026-03-14-1352-controlled-flag-on-validation-checkpoint.json` | Controller | `done` | controlled flag-on validation evidence, current control docs | controller | post-validation closeout state is contract-valid and portable |
| `reports/2026-03-14-1352-controlled-flag-on-validation-report.md` | Controller | `done` | `reports/2026-03-14-1352-controlled-flag-on-validation-checkpoint.json` | controller | Main-owned internal validation closeout and final `DONE` state are recorded |
| `reports/2026-03-14-1439-controller-approval-authority-resync-checkpoint.json` | Controller | `done` | approval-authority semantics, current control docs, `reports/2026-03-14-1352-controlled-flag-on-validation-report.md` | controller | post-resync active-wave state is contract-valid and portable |
| `reports/2026-03-14-1439-controller-approval-authority-resync-report.md` | Controller | `done` | `reports/2026-03-14-1439-controller-approval-authority-resync-checkpoint.json` | controller | stale `DONE` closeout is superseded and current active-wave truth is recorded |
| `.agents/skills.must.txt` | Automation and skills librarian | `done` | controller decisions, runbook | all workers | locked project invariants are explicit |
| `.agents/skills.good.txt` | Automation and skills librarian | `done` | controller decisions, runbook | all workers | conventions are explicit |
| `.agents/skills.task.txt` | Automation and skills librarian | `done` | dispatch board, artifact ledger | all workers | current phase context is explicit |
| `.agents/skills.lock.json` | Automation and skills librarian | `done` | `.agents/skills.task.txt` | all workers | current skill manifest is pinned for local loading |
| `.agents/agents/*.md` | Automation and skills librarian | `done` | registry, dispatch board, artifact ledger | matching worker roles | each role has a local prompt shell with scope and no-touch rules |
| `.gitignore` | Automation and skills librarian | `done` | local repo conventions | all workers | transient agent/runtime paths are ignored without hiding tracked control docs |

## Next Delivery Artifacts

| Artifact | Owner | Status | Depends On | Next Consumer | Done When |
| --- | --- | --- | --- | --- | --- |
| `prd.md` | Product and PM owner | `done` | `source-brief.md`, `decisions.md` | Architect, QA, Security | PoC scope, user roles, success metrics, and non-goals are explicit |
| `backlog.md` | Product and PM owner | `done` | `prd.md` draft | Controller, build agents | phases, slices, and acceptance checks are sequenced |
| `architecture-overview.md` | Orchestrator architect | `done` | `prd.md` draft, `source-brief.md` | Security, Data, Backend, Frontend, QA | system flow, read and write split, and dependency map are explicit |
| `security-model.md` | Security reviewer | `done` | `prd.md` draft, `architecture-overview.md` draft | Data, Backend, QA | auth flow, permission model, sensitive field rules, and confirmation gates are explicit |
| `eval-plan.md` | QA and eval lead | `done` | `prd.md` draft, `architecture-overview.md` draft | Controller, build agents | eval prompts, thresholds, latency targets, and replay loop are explicit |

## Contract Artifacts

| Artifact | Owner | Status | Depends On | Next Consumer | Done When |
| --- | --- | --- | --- | --- | --- |
| `contracts/tool-schema.yaml` | Data and SQL tools engineer | `done` | accepted `architecture-overview.md`, accepted `security-model.md`, accepted `contracts/permission-context.json` | Backend, Orchestrator, QA | read and write tool boundaries plus allowed parameters are explicit |
| `contracts/agent-response-schema.json` | Frontend structured chat engineer | `done` | accepted `prd.md`, accepted `architecture-overview.md` | Frontend, QA | tables, timelines, metric cards, and confirmation cards are defined |
| `contracts/eval-test-schema.yaml` | QA and eval lead | `done` | accepted `eval-plan.md`, accepted contract artifacts | QA, Controller | replay cases and expected outputs are machine readable |
| `contracts/permission-context.json` | Security reviewer | `done` | accepted `security-model.md`, accepted `architecture-overview.md` | Data, Backend, QA | broker, office, role, and sensitive-field context are explicit |
| `contracts/controller-checkpoint-schema.json` | Controller | `done` | accepted controller routing rules | Controller, QA | compact checkpoint state is machine readable |

## Build Brief Artifacts

| Artifact | Owner | Status | Depends On | Next Consumer | Done When |
| --- | --- | --- | --- | --- | --- |
| `B1 data and SQL notes` | Data and SQL tools engineer | `done` | accepted `contracts/tool-schema.yaml`, accepted `contracts/permission-context.json` | Backend implementation lane, QA | query mappings, allowed read shapes, and protected-field handling are explicit |
| `B2+B3 backend and orchestrator notes` | Backend and orchestrator engineer | `done` | accepted `contracts/tool-schema.yaml`, accepted `contracts/permission-context.json` | Backend implementation lane, Controller | endpoint mapping, write gateway, and read/write orchestration flow are explicit |
| `B4 frontend structured chat notes` | Frontend structured chat engineer | `done` | accepted `contracts/agent-response-schema.json` | Frontend implementation lane, QA | response rendering rules, component mapping, and confirmation-card behavior are explicit |
| `B5 eval harness and replay notes` | QA and eval lead | `done` | accepted `contracts/eval-test-schema.yaml`, accepted `contracts/agent-response-schema.json` | QA implementation lane, release gating | replay bundle shape, schema checks, and release-gate hooks are explicit |

## Implementation Artifacts

| Artifact | Owner | Status | Depends On | Next Consumer | Done When |
| --- | --- | --- | --- | --- | --- |
| `db/schema.sql`, `db/views.sql`, `db/seeds/seed_data.py`, `backend/app/db/context.py` | Data and SQL tools engineer | `done` | accepted `B1` brief, accepted `contracts/tool-schema.yaml`, accepted `contracts/permission-context.json` | QA, controller | B1 lane passes review and verification |
| `backend/app/tools/registry.py`, `backend/app/gateway/write_gateway.py`, `backend/app/orchestrator/graph.py`, `backend/app/responses/builder.py` | Backend integration engineer | `done` | accepted `B2+B3` brief, accepted tool/permission/response contracts | QA, controller | B2+B3 lane passes review and targeted repair closes |
| `backend/app/controller/models.py`, `backend/app/controller/strategies.py`, `backend/app/controller/precedence.py`, `tests/controller/test_controller_scaffold.py` | Controller | `done` | `contracts/controller-checkpoint-schema.json`, `docs/plans/2026-03-14-compaction-control-plane.md` | controller | checkpoint scaffold, strategy adapter, and precedence tests validate cleanly |
| `frontend/src/App.jsx`, `frontend/src/response-model.js`, `frontend/tests/response-model.test.js` | Frontend structured chat engineer | `done` | accepted `B4` brief, accepted `contracts/agent-response-schema.json` | controller | B4 renderer stays schema-driven, confirmation-only writes remain enforced, frontend tests pass, and the production build stays green |
| `backend/app/config.py`, `backend/app/orchestrator/graph.py`, `backend/app/controller/runtime.py`, `tests/controller/test_controller_runtime.py` | Controller | `done` | validated checkpoint scaffold, `docs/plans/2026-03-14-compaction-control-plane.md`, `reports/2026-03-14-1018-controller-checkpoint.json` | controller | runtime-hook capability is available behind flags, additive-only, and runtime validation passes |
| `backend/app/controller/policy.py`, `backend/app/controller/models.py`, `backend/app/controller/runtime.py`, `backend/app/orchestrator/graph.py`, `tests/controller/test_controller_policy.py`, `tests/controller/test_controller_runtime.py`, `tests/controller/test_controller_scaffold.py`, `decisions.md`, `runbook.md`, `reports/README.md` | Controller | `done` | `docs/plans/2026-03-14-lean-lane-policy.md`, current controller queue truth | controller | stage packets, terminal-state handling, queue-truth persistence, and control docs validate cleanly |
| `evals/runner.py`, `tests/b5/test_b5_scaffold.py` | QA and eval lead | `done` | accepted `B5` brief, accepted `contracts/eval-test-schema.yaml`, accepted `contracts/agent-response-schema.json` | controller, release gating | eval runner validates contract enums and captured responses, enforces release-gate evidence checks, and passes fresh verification |

## Build Starts Only After

- `prd.md` accepted
- `architecture-overview.md` accepted
- `security-model.md` accepted
- at least the relevant contract artifact for that lane is accepted
- build can now start per accepted contract lane
