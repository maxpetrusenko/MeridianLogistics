export const CHAT_SHELL_COPY = {
  title: "Chat session",
  promptLabel: "Ask Meridian",
  legacyTitle: "Structured response renderer",
};

export function createInitialChatShellState() {
  return {
    panelState: "open",
    sessionState: "idle",
    sessionId: null,
    sessionAccessToken: null,
    conversationScope: "global",
    contextBindingState: "missing",
    screenSyncState: "not_applicable",
    activeResource: null,
    activeJobId: null,
    activeJobPollToken: null,
    activeJobStatus: null,
    activeJobProgressMessage: null,
    messages: [],
  };
}

export function buildChatRequest({
  prompt,
  sessionId,
  sessionAccessToken,
  currentModule,
  resourceId,
}) {
  const request = {
    prompt,
    current_module: currentModule,
  };

  if (sessionId) {
    request.session_id = sessionId;
    request.session_access_token = sessionAccessToken;
  }

  if (resourceId) {
    request.current_resource = {
      resource_type: "shipment",
      resource_id: resourceId,
      resource_fingerprint: `shipment:${resourceId}:v1`,
    };
  }

  return request;
}

export function applyChatResponse(state, response, prompt = null) {
  const nextMessages = [...state.messages];

  if (prompt) {
    nextMessages.push({
      id: `user-${state.messages.length + 1}`,
      role: "user",
      prompt,
    });
  }

  nextMessages.push({
    id: response.response_id,
    role: "assistant",
    response,
  });

  return {
    ...state,
    sessionState: response.job_id ? "loading" : "ready",
    sessionId: response.session_id,
    sessionAccessToken: response.session_access_token ?? state.sessionAccessToken,
    conversationScope: response.conversation_scope ?? state.conversationScope,
    contextBindingState: response.context_binding_state ?? state.contextBindingState,
    screenSyncState: response.screen_sync_state ?? state.screenSyncState,
    activeResource: response.active_resource ?? null,
    activeJobId: response.job_id ?? null,
    activeJobPollToken: response.job_poll_token ?? null,
    messages: nextMessages,
  };
}

export function replacePendingJobResponse(state, response) {
  return {
    ...state,
    sessionState: "ready",
    activeJobId: null,
    activeJobPollToken: null,
    messages: state.messages.map((message) => {
      if (message.role !== "assistant") {
        return message;
      }
      if (message.response?.job_id && message.response.job_id === response.job_id) {
        return {
          ...message,
          response,
          id: response.response_id,
        };
      }
      return message;
    }),
  };
}

export function getBindingBadge({ conversationScope, contextBindingState, activeResource }) {
  if (!activeResource) {
    return {
      label: conversationScope === "office" ? "Office scope" : "Global scope",
      detail: contextBindingState === "missing" ? "No bound resource yet." : "Context available.",
      tone: contextBindingState === "missing" ? "neutral" : "live",
    };
  }

  const resourceLabel = `${capitalize(activeResource.resource_type)} ${activeResource.resource_id}`;
  const detailMap = {
    bound: "Bound to active resource.",
    partial: "Partial context. Ask a narrower follow-up.",
    stale: "Stale context. Refresh before actioning.",
    missing: "No bound resource yet.",
  };

  return {
    label: resourceLabel,
    detail: detailMap[contextBindingState] ?? "Context available.",
    tone: contextBindingState === "stale" ? "warning" : contextBindingState === "bound" ? "live" : "neutral",
  };
}

export function cyclePanelState(panelState) {
  const states = ["peek", "open", "expanded"];
  const currentIndex = states.indexOf(panelState);
  return states[(currentIndex + 1) % states.length];
}

export function updateJobPollingState(state, { status, message }) {
  return {
    ...state,
    activeJobStatus: status,
    activeJobProgressMessage: message,
  };
}

export function clearJobState(state) {
  return {
    ...state,
    sessionState: "ready",
    activeJobId: null,
    activeJobPollToken: null,
    activeJobStatus: null,
    activeJobProgressMessage: null,
  };
}

export function markJobError(state, message) {
  return {
    ...state,
    sessionState: "error",
    activeJobId: null,
    activeJobPollToken: null,
    activeJobStatus: "error",
    activeJobProgressMessage: message,
  };
}

export function getJobDisplayState(state) {
  if (!state.activeJobId) {
    return {
      hasJob: false,
      status: null,
      message: "No background task in flight.",
    };
  }

  const status = state.activeJobStatus ?? "unknown";

  const statusMessages = {
    queued: "Queued, waiting to start",
    running: "In progress",
    succeeded: "Completed",
    failed: "Failed",
    cancelled: "Cancelled",
    expired: "Expired",
    error: "Error",
    unknown: "Unknown status",
  };

  const message = state.activeJobProgressMessage ?? statusMessages[status] ?? "Unknown status";

  return {
    hasJob: true,
    status,
    message,
  };
}

function capitalize(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
