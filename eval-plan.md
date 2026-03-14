# Meridian Memphis PoC Eval Plan

## Scope boundary

Confirmed source facts:
- Scope is Memphis office only.
- Time box is a 90 day PoC.
- Accepted product scope is read queries plus single-step bookings.
- Multi-office rollout, multi-step workflows, and open-ended autonomous actions are out of scope.

Proposed checks:
- Evaluate only Memphis-broker workflows, boundary-role checks, and approved single-step booking flows.
- Treat status-update writes and notification-channel behavior as explicit non-release items unless later artifacts promote them.

## Quality goals

Confirmed source facts:
- Success signals include 90%+ valid SQL generation, sub-500 ms standard query latency, zero cross-office breaches, 95%+ broker satisfaction, support for representative workflows, and complete audit trail for actions.
- Known risks include unsafe SQL, cross-office leakage, permission bypass, and workflow-state errors during writes.

Proposed checks:
- Gate read quality on correctness, scope enforcement, latency, and structured-response completeness.
- Gate write quality on confirmation behavior, booking eligibility checks, audit completeness, and denial behavior for unsupported actions.
- Track failures by class so later build lanes can fix root causes instead of masking symptoms.

## Critical scenarios

Confirmed source facts:
- Representative read scenarios include aggregation, ranking with filters, and multi-table operational lookups.
- Representative write scope includes single-step booking.
- Boundary testing must confirm role and office restrictions.

Proposed checks:
1. Aggregation read: average transit time over a bounded date range.
2. Ranking read: top carriers with weight, mode, and region filters.
3. Multi-table read: in-transit shipments with related carrier-risk conditions.
4. Boundary denial: Memphis broker cannot retrieve out-of-scope office data.
5. Boundary allow: VP-style role can succeed where broker scope must fail.
6. Single-step booking happy path with explicit confirmation.
7. Single-step booking denial when confirmation is absent, stale, or unsupported.
8. Sensitive-field prompt attempting to expose protected rate or credit fields.
9. Structured-response rendering for table, metric, timeline, and confirmation surfaces.

## Failure classes

Confirmed source facts:
- Current SQL quality is below target and suffers from hallucinated columns, incorrect joins, and unbounded queries.
- Permission bypass and data leakage are major risks.

Proposed checks:
- Query safety failure: hallucinated column, unsafe join, missing limit, unsupported shape.
- Permission failure: wrong office scope, wrong role scope, protected column exposure.
- Orchestration failure: read path routed to write path, write path missing confirmation, unsupported action accepted.
- Data freshness failure: booking target changes between request and confirmation.
- Response-contract failure: missing structured component, malformed action payload, ambiguous confirmation state.
- Performance failure: standard read path exceeds latency target.
- Audit failure: missing requester, confirmation, tool, outcome, or timestamp linkage.

## Evaluation data and fixtures

Confirmed source facts:
- Meridian operates five offices with office-scoped permissions and 15-table freight data.
- Memphis is the only PoC office.

Proposed checks:
- Build a Memphis-scoped fixture set covering the representative read and booking flows.
- Include role fixtures for broker, office manager, and VP boundary tests.
- Include protected-field probes for carrier rate, shipper rate, and credit-limit-style requests.
- Include negative fixtures for unsupported write intents, stale booking context, and cross-office prompts.
- Keep replay artifacts small, deterministic, and tagged by scenario, role, and expected gate result.

## Offline checks

Confirmed source facts:
- Evaluation must cover query quality, performance, permission boundaries, and action auditability.

Proposed checks:
- Run deterministic replay on the critical scenarios before any release candidate.
- Score each replay for correctness, scope enforcement, latency band, and response-structure validity.
- Require explicit pass/fail checks for confirmation-before-write behavior.
- Require denied-result checks for unsupported writes, protected fields, and cross-office access.
- Record failure class on every failing replay so security, orchestration, and contract owners can route fixes.

## Human review and UAT

Confirmed source facts:
- Brokers are primary users.
- Office managers and VP-role cases matter for permission validation.

Proposed checks:
- Run Memphis broker UAT on the critical read scenarios and approved booking flow.
- Run office-manager review on office-scoped visibility and escalation boundaries.
- Run VP-role review only for explicit boundary scenarios, not broad exploratory testing.
- Collect broker satisfaction feedback on usefulness, trust, and clarity of structured responses.
- Treat any trust-breaking permission or confirmation error as a release blocker regardless of aggregate scores.

## Release gates

Confirmed source facts:
- Target signals include 90%+ valid SQL, sub-500 ms standard query latency, zero cross-office breaches, and complete audit trail for actions.

Proposed checks:
- No known cross-office leakage in replay or UAT.
- No protected-field exposure in replay or UAT.
- Read-path replay meets agreed correctness threshold and hits 90%+ valid-query target.
- Standard read scenarios meet the sub-500 ms latency target at the agreed sample size.
- Approved booking flow cannot execute without explicit confirmation.
- Every completed or denied write attempt leaves an audit record with actor, scope, action, and outcome.
- Structured-response scenarios render the required response classes for read and booking flows.
- Open-scope items remain blocked unless promoted by later accepted artifacts.

## Open evaluation decisions

- Exact sample size for replay coverage per critical scenario.
- Exact broker-satisfaction measurement method and minimum respondent count.
- Whether status-update writes remain fully excluded from PoC eval or move into a stretch gate later.
- Whether notification behavior needs any evaluation coverage before it is formally in scope.
- Exact latency budget split between orchestration, query execution, and response shaping.
