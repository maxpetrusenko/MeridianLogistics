export const FIXTURE_RENDER_TIME = "2026-03-14T00:00:00-05:00";

export function makeResponse({
  id,
  intentClass,
  status,
  summary,
  components,
  actions = [],
  denialReasonClass = "none",
  writeConfirmationRequired = false,
  toolPath,
}) {
  return {
    contract_version: "0.1.0",
    response_id: `resp-${id}`,
    request_id: `req-${id}`,
    trace_id: `trace-${id}`,
    intent_class: intentClass,
    status,
    summary,
    follow_up_prompt: null,
    components,
    actions,
    policy: {
      permission_context_applied: true,
      sensitive_fields_redacted: true,
      write_confirmation_required: writeConfirmationRequired,
      denial_reason_class: denialReasonClass,
    },
    audit: {
      actor_role: "broker",
      office_scope: "memphis",
      tool_path: toolPath,
      response_generated_at: "2026-03-14T09:00:00Z",
    },
  };
}

function makeAction({
  actionId,
  label,
  actionType,
  resourceType,
  resourceId,
  surface = "chat",
  requiresConfirmation = false,
  enabled = true,
  disabledReason = null,
  serverEndpoint,
  permissionScope,
  confirmationToken,
  confirmationExpiresAt,
  idempotencyKey,
  uiBehavior,
}) {
  const action = {
    action_id: actionId,
    label,
    action_type: actionType,
    resource_type: resourceType,
    resource_id: resourceId,
    surface,
    requires_confirmation: requiresConfirmation,
    enabled,
    disabled_reason: disabledReason,
  };

  if (serverEndpoint) {
    action.server_endpoint = serverEndpoint;
  }
  if (permissionScope) {
    action.permission_scope = permissionScope;
  }
  if (confirmationToken) {
    action.confirmation_token = confirmationToken;
  }
  if (confirmationExpiresAt) {
    action.confirmation_expires_at = confirmationExpiresAt;
  }
  if (idempotencyKey) {
    action.idempotency_key = idempotencyKey;
  }
  if (uiBehavior) {
    action.ui_behavior = uiBehavior;
  }

  return action;
}

export const fixtures = {
  loading: null,
  empty: {
    label: "Empty",
    response: makeResponse({
      id: "empty",
      intentClass: "read_result",
      status: "success",
      summary: "No Memphis shipments matched the scoped query.",
      toolPath: ["shipment_metrics_lookup"],
      components: [
        {
          component_id: "msg-empty",
          component_type: "message_block",
          title: "No results",
          body: "Try a narrower date range or different lane filter.",
          tone: "informational",
        },
      ],
      actions: [
        makeAction({
          actionId: "refine-empty",
          label: "Refine search",
          actionType: "request_refinement",
          resourceType: "analytics",
          resourceId: "empty-query",
        }),
      ],
    }),
  },
  metrics: {
    label: "Metrics",
    response: makeResponse({
      id: "metrics",
      intentClass: "read_result",
      status: "success",
      summary: "Memphis LTL transit time stayed inside the 90 day target window.",
      toolPath: ["shipment_metrics_lookup"],
      components: [
        {
          component_id: "metric-memphis",
          component_type: "metric_card",
          title: "Lane metrics",
          metrics: [
            { label: "Average transit", value: 2.8, unit: "days" },
            { label: "Loads", value: 124, unit: null },
            { label: "On time", value: 96, unit: "%" },
          ],
        },
      ],
      actions: [
        makeAction({
          actionId: "details-metrics",
          label: "Open details",
          actionType: "open_details",
          resourceType: "analytics",
          resourceId: "memphis-ltl-metrics",
        }),
      ],
    }),
  },
  table: {
    label: "Table",
    response: makeResponse({
      id: "table",
      intentClass: "read_result",
      status: "success",
      summary: "Top Memphis carriers by on time performance.",
      toolPath: ["carrier_ranking_lookup"],
      components: [
        {
          component_id: "table-carriers",
          component_type: "table",
          title: "Carrier ranking",
          columns: [
            { key: "carrier", label: "Carrier", data_type: "string" },
            { key: "ontime", label: "On time", data_type: "number" },
            { key: "status", label: "Status", data_type: "status" },
          ],
          rows: [
            ["Arrow Freight", 98, "stable"],
            ["RiverSouth", 95, "watch"],
            ["Delta Linehaul", 93, "stable"],
          ],
        },
      ],
      actions: [
        makeAction({
          actionId: "refine-table",
          label: "Refine search",
          actionType: "request_refinement",
          resourceType: "analytics",
          resourceId: "carrier-ranking",
        }),
      ],
    }),
  },
  timeline: {
    label: "Timeline",
    response: makeResponse({
      id: "timeline",
      intentClass: "read_result",
      status: "success",
      summary: "Shipment 44128 is on the Memphis exception watch list with sequence detail below.",
      toolPath: ["shipment_exception_lookup"],
      components: [
        {
          component_id: "table-exceptions",
          component_type: "table",
          title: "Shipment exceptions",
          columns: [
            { key: "shipment", label: "Shipment", data_type: "string" },
            { key: "exception", label: "Exception", data_type: "string" },
            { key: "eta", label: "ETA", data_type: "string" },
            { key: "status", label: "Status", data_type: "status" },
          ],
          rows: [["44128", "Tight delivery window", "2026-03-14 09:00", "watch"]],
        },
        {
          component_id: "timeline-shipment",
          component_type: "timeline",
          title: "Shipment timeline",
          events: [
            { label: "Pickup confirmed", timestamp: "2026-03-12 08:15", state: "done" },
            { label: "Linehaul departed", timestamp: "2026-03-12 18:40", state: "active" },
            { label: "Chicago delivery window", timestamp: "2026-03-14 09:00", state: "next" },
          ],
        },
      ],
      actions: [
        makeAction({
          actionId: "details-timeline",
          label: "Open details",
          actionType: "open_details",
          resourceType: "shipment",
          resourceId: "44128",
        }),
      ],
    }),
  },
  confirm: {
    label: "Confirm",
    response: makeResponse({
      id: "confirm",
      intentClass: "write_confirmation_required",
      status: "confirmation_required",
      summary: "Booking is ready for broker confirmation.",
      toolPath: ["booking_create_prepare"],
      writeConfirmationRequired: true,
      components: [
        {
          component_id: "confirm-booking",
          component_type: "confirmation_card",
          title: "Confirm booking",
          action_name: "booking_create_confirmed",
          confirmation_token: "memphis-booking-token",
          expires_at: "2026-03-15T23:59:00Z",
          fields: [
            { key: "quote_id", label: "Quote", value: "88219" },
            { key: "carrier", label: "Carrier", value: "Arrow Freight" },
            { key: "pickup", label: "Pickup", value: "Tuesday 09:00" },
          ],
        },
      ],
      actions: [
        makeAction({
          actionId: "confirm-booking",
          label: "Confirm booking",
          actionType: "confirm_booking",
          resourceType: "shipment",
          resourceId: "88219",
          requiresConfirmation: true,
          serverEndpoint: { method: "POST", path: "/shipments/88219/book" },
          permissionScope: { office_id: "memphis", role: "broker", broker_id: "broker-123" },
          confirmationToken: "memphis-booking-token",
          confirmationExpiresAt: "2026-03-15T23:59:00Z",
          idempotencyKey: "book-88219-arrow-freight-2026-03-15-v1",
          uiBehavior: {
            success_mode: "sync_chat_and_screen",
            failure_mode: "stay_in_confirmation",
            post_success_refresh: ["shipment_detail", "dispatch_board"],
          },
        }),
        makeAction({
          actionId: "cancel-booking",
          label: "Cancel",
          actionType: "cancel_booking",
          resourceType: "shipment",
          resourceId: "88219",
        }),
      ],
    }),
  },
  denied: {
    label: "Denied",
    response: makeResponse({
      id: "denied",
      intentClass: "read_denied",
      status: "denied",
      summary: "This request crosses Memphis office scope and cannot be shown.",
      denialReasonClass: "permission",
      toolPath: [],
      components: [
        {
          component_id: "msg-denied",
          component_type: "message_block",
          title: "Permission boundary",
          body: "Permission boundary enforced. Cross-office comparison is outside the PoC.",
          tone: "warning",
        },
      ],
      actions: [],
    }),
  },
  error: {
    label: "Error",
    response: makeResponse({
      id: "error",
      intentClass: "error",
      status: "error",
      summary: "The request could not be completed safely.",
      denialReasonClass: "query_safety",
      toolPath: [],
      components: [
        {
          component_id: "msg-error",
          component_type: "message_block",
          title: "Request blocked",
          body: "The system blocked the request before exposing protected fields.",
          tone: "error",
        },
      ],
      actions: [],
    }),
  },
};

export const sampleKeys = Object.keys(fixtures);

export function getResponseMode(response) {
  const routeKey = `${response.intent_class}:${response.status}`;
  switch (routeKey) {
    case "read_result:success":
      return "read";
    case "read_denied:denied":
      return "denied";
    case "write_confirmation_required:confirmation_required":
      return "confirmation";
    case "write_submitted:submitted":
      return "submitted";
    case "write_denied:denied":
      return "denied";
    case "error:error":
      return "error";
    default:
      return "error";
  }
}

export function isExpired(dateTime, referenceTime = new Date().toISOString()) {
  return Date.parse(dateTime) <= Date.parse(referenceTime);
}

export function getConfirmationCard(response) {
  return response?.components?.find((component) => component.component_type === "confirmation_card") ?? null;
}

export function getStaleConfirmationNotice(expiresAt) {
  return {
    component_id: "msg-stale-confirmation",
    component_type: "message_block",
    body: expiresAt
      ? `Confirmation expired at ${expiresAt}. Refresh booking context before any write execution.`
      : "Confirmation expired. Refresh booking context before any write execution.",
    tone: "warning",
  };
}

export function getActionInteractivity(action, { confirmationExpired = false } = {}) {
  if (confirmationExpired) {
    return {
      disabled: true,
      reason: getStaleConfirmationNotice(action.confirmation_expires_at).body,
    };
  }

  if (action.enabled === false) {
    return {
      disabled: true,
      reason: action.disabled_reason ?? "Action disabled by the server.",
    };
  }

  return {
    disabled: false,
    reason: null,
  };
}

function buildSubmittedResponse(response, confirmationCard) {
  const quoteField = confirmationCard.fields.find((field) => field.key === "quote_id");

  return makeResponse({
    id: `${response.response_id}-submitted`,
    intentClass: "write_submitted",
    status: "submitted",
    summary: "Booking confirmation passed review and moved into write execution.",
    toolPath: [confirmationCard.action_name],
    components: [
      {
        component_id: "msg-booking-submitted",
        component_type: "message_block",
        title: "Booking submitted",
        body: `Submitted ${confirmationCard.action_name} for quote ${quoteField?.value ?? "unknown"} with the current confirmation token.`,
        tone: "informational",
      },
    ],
  });
}

export function buildActionResult({ action, response, referenceTime }) {
  const confirmationCard = getConfirmationCard(response);
  const actionExpiry = action.confirmation_expires_at ?? confirmationCard?.expires_at ?? null;
  const actionState = getActionInteractivity(action, {
    confirmationExpired: Boolean(actionExpiry) && isExpired(actionExpiry, referenceTime),
  });

  if (actionState.disabled) {
    return {
      nextResponse: response,
      actionNotice: {
        component_id: `msg-action-disabled-${action.action_id}`,
        component_type: "message_block",
        body: actionState.reason,
        tone: "warning",
      },
    };
  }

  if (action.action_type === "confirm_booking") {
    if (!confirmationCard) {
      return {
        nextResponse: response,
        actionNotice: {
          component_id: "msg-action-confirm-missing",
          component_type: "message_block",
          body: "Confirmation context missing. Refresh booking context before any write execution.",
          tone: "warning",
        },
      };
    }

    if (!action.idempotency_key) {
      return {
        nextResponse: response,
        actionNotice: {
          component_id: "msg-action-confirm-idempotency-missing",
          component_type: "message_block",
          body: "Idempotency key missing. Refresh booking context before any write execution.",
          tone: "warning",
        },
      };
    }

    if (!action.confirmation_token || action.confirmation_token !== confirmationCard.confirmation_token) {
      return {
        nextResponse: response,
        actionNotice: {
          component_id: "msg-action-confirm-token-mismatch",
          component_type: "message_block",
          body: "Confirmation token mismatch. Refresh booking context before any write execution.",
          tone: "warning",
        },
      };
    }

    return {
      nextResponse: buildSubmittedResponse(response, confirmationCard),
      actionNotice: null,
    };
  }

  if (action.action_type === "cancel_booking") {
    return {
      nextResponse: response,
      actionNotice: {
        component_id: "msg-action-cancel",
        component_type: "message_block",
        body: "Booking confirmation cleared. No write executed.",
        tone: "informational",
      },
    };
  }

  if (action.action_type === "request_refinement") {
    return {
      nextResponse: response,
      actionNotice: {
        component_id: "msg-action-refine",
        component_type: "message_block",
        body: "Refinement requested. Narrow the Memphis query and resubmit.",
        tone: "informational",
      },
    };
  }

  if (action.action_type === "open_details") {
    return {
      nextResponse: response,
      actionNotice: {
        component_id: "msg-action-details",
        component_type: "message_block",
        body: "Detail request captured for the selected Memphis result.",
        tone: "informational",
      },
    };
  }

  return {
    nextResponse: response,
    actionNotice: null,
  };
}
