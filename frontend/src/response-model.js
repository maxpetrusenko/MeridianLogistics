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
      actions: [{ action_id: "refine-empty", label: "Refine search", action_type: "request_refinement" }],
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
      actions: [{ action_id: "details-metrics", label: "Open details", action_type: "open_details" }],
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
      actions: [{ action_id: "refine-table", label: "Refine search", action_type: "request_refinement" }],
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
      actions: [{ action_id: "details-timeline", label: "Open details", action_type: "open_details" }],
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
        { action_id: "confirm-booking", label: "Confirm booking", action_type: "confirm_booking" },
        { action_id: "cancel-booking", label: "Cancel", action_type: "cancel_booking" },
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
  if (action.action_type === "confirm_booking") {
    const confirmationCard = getConfirmationCard(response);

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

    if (isExpired(confirmationCard.expires_at, referenceTime)) {
      return {
        nextResponse: response,
        actionNotice: {
          ...getStaleConfirmationNotice(confirmationCard.expires_at),
          component_id: "msg-action-confirm-expired",
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
