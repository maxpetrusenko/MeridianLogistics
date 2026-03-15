# B1 Data and SQL Implementation Brief

## Scope boundary

- Memphis office only
- 90 day PoC only
- Read coverage only for approved operational queries in accepted docs
- Write support only as contract support for single-step booking confirmation paths
- Out of scope: multi-office rollout, multi-step workflows, status-update writes, notification dispatch, raw SQL access

## Required data/query capabilities

- Office-scoped shipment metrics lookup for approved aggregations
- Office-scoped carrier ranking lookup for approved freight segments
- Office-scoped shipment exception lookup for approved multi-table operational reads
- Data shapes needed to support booking confirmation context for `booking_create_confirmed`
- Result support for accepted response components:
  - metric cards
  - tables
  - timelines

## Safe SQL/tool mapping approach

- Implement only allowlisted read shapes from `contracts/tool-schema.yaml`
- Map each approved tool to one curated query template or view-backed query family
- Inject trusted permission context before query construction, not after result retrieval
- Keep read tooling bounded by:
  - approved aggregations
  - approved filters
  - approved joins
  - explicit limits
  - explicit time windows
- Deny these shapes at the data layer:
  - raw schema exploration
  - unrestricted column selection
  - unbounded scans
  - unsupported joins
  - unrestricted cross-office comparison
  - protected-field projection
- Treat booking support data as lookup-only until confirmation token and write gateway take over

## Permission-context usage

- Require trusted `broker_id`, `office_id`, and `role` on every query path
- Default to deny when context is missing, expired, malformed, or mismatched
- Use `contracts/permission-context.json` as the execution contract for:
  - deployment scope
  - allowed office ids
  - record-scope mode
  - sensitive-field policy
  - read-path safety posture
- Enforce office scope in the data access layer
- Keep broker ownership filtering available for flows that require assigned-record enforcement
- Keep day-one runtime assumptions broker-first; office-manager and VP behavior stay boundary/eval-oriented until later controller decisions tighten them

## Protected-field handling

- Exclude sensitive columns from agent-accessible views and query templates by construction
- Return minimum required fields per workflow only
- Redact protected values from query logs, traces, and replay artifacts
- Treat protected-field prompts as deny cases, not degraded success
- Keep downstream response shaping dependent on already-safe result sets, not UI-layer hiding

## Acceptance checks

- Every approved read tool has a documented bounded query shape
- Every approved read tool consumes trusted permission context
- Office scoping is enforced below the prompt layer
- Sensitive fields cannot be selected or returned
- Representative read workflows from the PRD map to explicit data/query support
- Booking confirmation support data remains read-only until the confirmed write gateway executes
- Denied query classes are explicit and testable
- B1 output is sufficient for backend implementation lane and QA review

## Open implementation decisions

- Final broker ownership rule: `assigned_only` vs `assigned_or_office`
- Exact Memphis runtime role enablement beyond brokers
- Exact list and count of approved read templates for v0
- Boundary between curated SQL templates and any REST-backed read fallbacks
- Whether booking support lookups need separate freshness/version checks before confirmation
