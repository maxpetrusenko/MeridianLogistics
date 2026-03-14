# B4 Frontend Implementation Brief

## Scope boundary

- Memphis office only
- 90 day PoC only
- Read answers plus single-step booking confirmation only
- Multi-office, multi-step workflows, general status-update writes, and notification behavior stay out

## Required response components

- Summary text block for every response
- Structured table for ranked, filtered, or multi-row operational answers
- Metric cards for compact KPI or summary values
- Timeline component for shipment or event-sequenced views when the accepted response schema calls for it
- Confirmation card for any booking action that reaches the confirmation gate
- Error and denial message blocks for unsupported, blocked, or failed requests
- Action buttons only where the accepted response schema and confirmation flow justify them

## Render and interaction model

- Render from `contracts/agent-response-schema.json`, not from prompt-specific UI branching
- Treat `intent_class` and `status` as the primary frontend routing inputs
- Keep component rendering deterministic:
  - `read_result` maps to summary plus zero or more table, metric-card, or timeline components
  - `read_denied` maps to summary plus denial/error message block
  - `write_confirmation_required` maps to summary plus confirmation card
  - `write_submitted` maps to summary plus completion or status message block
  - `write_denied` maps to summary plus denial/error message block
  - `error` maps to summary plus error message block
- Render `actions` only when present in the accepted response payload
- Keep response composition schema-driven so QA can validate output against the accepted contract

## Confirmation-card behavior

- Confirmation card appears only for accepted single-step booking flows
- Card must show enough booking context for review before user confirmation
- Confirmation action stays explicit and user-triggered
- No write action fires from generic action buttons outside the confirmation flow
- Missing, stale, or denied confirmation state must keep the UI in a non-submitted state and show a clear denial/error block

## Error, empty, and loading states

- Loading:
  - show request-in-progress state without implying a result or write completion
  - keep prior confirmed state stable until a new payload arrives
- Empty:
  - show a clear no-results message when scoped queries return nothing valid
  - do not render empty tables or empty timelines without explanatory copy
- Error:
  - render schema-valid error blocks for unsupported requests, permission denial, stale state, or system failure
  - never expose protected fields, raw SQL, or internal tool traces in user-visible error states
- Denial:
  - keep denial messaging distinct from generic failure so users can tell permission/scope limits from transient errors

## Acceptance checks

- Frontend rendering stays within Memphis-only PoC scope
- All accepted response component classes render from the schema without ad hoc payload assumptions
- Confirmation card is the only path to single-step booking confirmation in the UI
- Error, denial, empty, and loading states are explicit and non-leaky
- Action buttons and confirmation behavior remain consistent with the accepted response schema and accepted write scope
- The brief leaves implementation blocked on controller review before frontend implementation starts

## Open implementation decisions

- Whether `action_id` values must map one-to-one to tool-schema ids or can use frontend-local aliases
- Exact timestamp formatting and locale display rules
- Whether `action_buttons` are ever allowed on `error` responses
- Exact presentation priority when a response legitimately contains table, metric-card, and timeline components together
- Whether office-manager and VP role-specific UI variants are needed in Memphis PoC review paths or can stay visually identical to broker flows
