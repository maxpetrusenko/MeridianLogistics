# Meridian Memphis PoC Backlog

## Document Status

- Owner: Product and PM owner
- Status: draft
- Scope boundary: Memphis office only, 90 day PoC
- Source authority: `prd.md`, `source-brief.md`, `decisions.md`
- Quarantined source excluded: `meridian-logistics-deck-summary.md`

## Sequencing Rules

1. Finish definition artifacts before architecture acceptance.
2. Finish architecture before security and QA acceptance.
3. Finish security, QA, and the relevant contract artifact before build lanes start.
4. Keep status-update writes and notification channels out of build scope until later artifacts lock them.
5. Treat shared control docs as controller-owned.

## P0 Must-Have PoC Slices

| ID | Slice | Owner | Depends On | Produces | Next Consumer | Exit Check |
| --- | --- | --- | --- | --- | --- | --- |
| P0.1 | Accept `prd.md` | Controller | `prd.md` draft | accepted PRD scope | PM owner | Memphis-only scope, roles, metrics, and non-goals are explicit |
| P0.2 | Write `backlog.md` | Product and PM owner | `prd.md` | phased delivery plan | Controller | slices, dependencies, and gate checks are explicit |
| P0.3 | Write `architecture-overview.md` | Orchestrator architect | accepted `prd.md`, `source-brief.md` | system flow and contract ownership | Security reviewer, QA and eval lead, build lanes later | read/write split, tool boundaries, and dependency map are explicit |
| P0.4 | Write `security-model.md` | Security reviewer | accepted `prd.md`, `architecture-overview.md` draft | auth and permission rules | Data, backend, QA | JWT flow, office filter, hidden fields, and confirmation gate are explicit |
| P0.5 | Write `eval-plan.md` | QA and eval lead | accepted `prd.md`, `architecture-overview.md` draft | eval matrix and thresholds | Controller, QA, build lanes later | read cases, booking cases, latency goals, and replay loop are explicit |
| P0.6 | Write `contracts/tool-schema.yaml` | Data and SQL tools engineer | accepted `architecture-overview.md`, accepted `security-model.md` | safe tool catalog | Backend integration engineer, orchestrator architect, QA | allowed read tools, write tools, parameters, and blocked query shapes are explicit |
| P0.7 | Write `contracts/agent-response-schema.json` | Frontend structured chat engineer | accepted `prd.md`, accepted `architecture-overview.md` | structured response contract | Frontend engineer, QA | tables, timelines, metric cards, action buttons, and confirmation cards are defined |
| P0.8 | Write `contracts/permission-context.json` | Security reviewer | accepted `security-model.md` | role and office context contract | Data, backend, QA | broker, office manager, VP context and sensitive-field rules are explicit |
| P0.9 | Write `contracts/eval-test-schema.yaml` | QA and eval lead | accepted `eval-plan.md` | machine-readable eval cases | QA harness, controller | replay inputs, expected outputs, and threshold fields are explicit |

## Build Lanes Unlocked Only After P0 Contracts

| ID | Slice | Owner | Depends On | Produces | Next Consumer | Exit Check |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | Data query layer notes and mappings | Data and SQL tools engineer | P0.6, P0.8 | query-tool implementation brief | Backend integration engineer, QA | safe query coverage maps to representative read workflows |
| B2 | Endpoint mapping and write gateway notes | Backend integration engineer | P0.3, P0.4, P0.6, P0.8 | action-execution implementation brief | Orchestrator architect, QA | eligible booking path and confirmation boundary are explicit |
| B3 | Read/write orchestration design notes | Orchestrator architect | P0.3, P0.4, P0.6 | orchestration implementation brief | Backend integration engineer, QA | read path and write path stay separated |
| B4 | Structured chat UI notes | Frontend structured chat engineer | P0.7 | UI implementation brief | QA | read answers and booking confirmations render from the accepted schema |
| B5 | Eval harness and replay suite notes | QA and eval lead | P0.5, P0.9 | test implementation brief | Controller | eval plan is runnable against accepted contracts |

## Explicitly Blocked Or Later

| ID | Item | Reason Blocked Or Deferred | Unlock Condition |
| --- | --- | --- | --- |
| L1 | General status-update writes | PRD leaves this undecided for PoC acceptance | architecture plus security explicitly promote it |
| L2 | Notification-channel implementation | channel scope not locked | PRD follow-up decision plus architecture acceptance |
| L3 | Multi-office rollout | out of PoC scope | post-Memphis planning |
| L4 | Multi-step workflows | out of PoC scope | post-PoC workflow expansion |
| L5 | Open-ended autonomous actions | forbidden by current scope and security posture | new product and security decision |

## Ready Now

- Controller review and acceptance of this backlog
- Architect lane immediately after controller accepts `backlog.md`
- Security and QA lanes may draft only after architecture direction exists

## Not Ready Yet

- data-platform implementation
- endpoint and gateway implementation
- orchestration implementation
- frontend implementation
- eval harness implementation

These remain blocked until the relevant accepted contract artifact exists.

## Backlog Acceptance Criteria

1. Definition, architecture, security, QA, contract, and build lanes are sequenced explicitly.
2. Must-have PoC work is separated from blocked or future items.
3. Every slice names owner, dependency, produced artifact, next consumer, and exit check.
4. Build lanes remain blocked behind accepted contracts.
5. Quarantined deck material is excluded.
