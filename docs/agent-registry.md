# Meridian Agent Registry

## Baseline Roster

| Agent | Lane | Mission | Core Inputs | Core Outputs | Spawn When | Merge When |
| --- | --- | --- | --- | --- | --- | --- |
| Controller | Control | Own intake, dispatch, acceptance, and shared docs | User goals, reports, authoritative source artifacts | `dispatch-board.md`, `artifact-ledger.md`, `decisions.md`, acceptance calls | Always | Never |
| Product and PM owner | Product | Turn source facts into PRD, backlog, priorities, meeting decisions, and handoff criteria | Case study, source brief, stakeholder notes, controller decisions | `prd.md`, `backlog.md`, meeting notes, open questions | Discovery starts or scope shifts | Split into product strategist plus PM if coordination load rises |
| Orchestrator architect | Architecture | Design system flow, read and write orchestration, suspend and resume rules | PRD, proposed stack notes, security constraints | `architecture-overview.md`, interface plan, dependency map | Once PRD draft exists | Do not merge with controller |
| Automation and skills librarian | Control | Enforce worker startup checklist, mandatory skill checkout, project-local agent configs, prompt templates, report hygiene, and safe external tool setup | Local AGENTS, local CLAUDE, subagent guide, skills guide, controller rules | startup checklist, `.agents/` files, task manifests, worker prompts, skill selections, safe clone notes | Any new worker task or tooling change | Can merge with controller only in very short bursts |
| Data and SQL tools engineer | Architecture | Own query tool catalog, office filter propagation, and read guardrails | architecture overview, security model, endpoint list | `contracts/tool-schema.yaml`, query contracts, data risk notes | Contract layer is accepted | Can merge with backend briefly |
| Frontend structured chat engineer | Build | Build React chat shell and structured response components | PRD, architecture overview, action specs | `contracts/agent-response-schema.json`, UI flows, response components, client state behavior | Contract layer is accepted | Keep separate once build load rises |
| Backend integration engineer | Build | Wire gateway behavior, endpoint mapping, and notification hooks | architecture overview, endpoint catalog, auth constraints | endpoint mapping, gateway notes, write flow plumbing | Contract layer is accepted | Can merge with data engineer briefly |
| Security and permissions reviewer | Architecture | Validate JWT passthrough, office filtering, sensitive column exposure, and write confirmation gates | source brief, PRD, architecture overview | `security-model.md`, `contracts/permission-context.json`, required fixes | Before any write flow or auth decision lands | Can merge with architect in lean mode only |
| QA and eval lead | Quality | Own evals, regression checks, write confirmation tests, and PoC exit criteria | PRD, architecture overview, UI and API behavior | `eval-plan.md`, `contracts/eval-test-schema.yaml`, QA matrix, readiness call | PRD and architecture drafts exist | Can absorb docs and release in baseline |

## Peak Burst Roster

| Agent | Mission | Trigger |
| --- | --- | --- |
| Product strategist | Split discovery, meetings, and requirement synthesis away from PM | Scope churn or stakeholder traffic rises |
| UX reviewer | Tighten tables, timelines, metric cards, buttons, and confirmation cards | FE parallel work or UX drift |
| Extra frontend engineer | Split chat shell from response component backlog | FE queue exceeds one worker |
| Extra backend engineer | Split endpoint and graph plumbing work | BE queue exceeds one worker |
| Release and docs owner | Own launch checklist, demos, handoff docs, and report packaging | Final 2 to 3 weeks |
| Meeting recorder | Convert calls into decisions and action items | Meeting volume starts hurting PM bandwidth |

## Non Goals For Baseline

- No separate design system owner yet
- No separate DevOps owner yet
- No separate release manager until PoC nears exit
- No external clone outside `/Users/maxpetrusenko/Desktop/Projects/oss`
