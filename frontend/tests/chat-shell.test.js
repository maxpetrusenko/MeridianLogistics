import test from "node:test";
import assert from "node:assert/strict";
import {
  CHAT_SHELL_COPY,
  applyChatResponse,
  buildChatRequest,
  clearJobState,
  createInitialChatShellState,
  cyclePanelState,
  getBindingBadge,
  getJobDisplayState,
  markJobError,
  replacePendingJobResponse,
  updateJobPollingState,
} from "../src/chat-state.js";

test("buildChatRequest includes session metadata and optional active resource only", () => {
  const request = buildChatRequest({
    prompt: "Show shipment 88219 details.",
    sessionId: "chat_s_20260314_0001",
    sessionAccessToken: "session_token_123456",
    currentModule: "dispatch_board",
    resourceId: "88219",
  });

  assert.deepEqual(request, {
    prompt: "Show shipment 88219 details.",
    session_id: "chat_s_20260314_0001",
    session_access_token: "session_token_123456",
    current_module: "dispatch_board",
    current_resource: {
      resource_type: "shipment",
      resource_id: "88219",
      resource_fingerprint: "shipment:88219:v1",
    },
  });
});

test("applyChatResponse stores session metadata and latest structured response", () => {
  const initialState = createInitialChatShellState();
  const nextState = applyChatResponse(initialState, {
    session_id: "chat_s_20260314_0001",
    session_access_token: "session_token_123456",
    conversation_scope: "shipment",
    context_binding_state: "bound",
    screen_sync_state: "not_applicable",
    active_resource: {
      resource_type: "shipment",
      resource_id: "88219",
      resource_fingerprint: "shipment:88219:v1",
    },
    job_id: null,
    response_id: "resp-1",
    request_id: "req-1",
    trace_id: "trace-1",
    intent_class: "read_result",
    status: "success",
    summary: "Shipment 88219 is on the Memphis board.",
    follow_up_prompt: null,
    components: [
      {
        component_id: "msg-1",
        component_type: "message_block",
        body: "Shipment 88219 is on the Memphis board.",
        tone: "informational",
      },
    ],
    actions: [],
    policy: {
      permission_context_applied: true,
      sensitive_fields_redacted: true,
      write_confirmation_required: false,
      denial_reason_class: "none",
    },
    audit: {
      actor_role: "broker",
      office_scope: "memphis",
      tool_path: ["shipment_exception_lookup"],
      response_generated_at: "2026-03-14T12:00:00Z",
    },
  });

  assert.equal(nextState.sessionId, "chat_s_20260314_0001");
  assert.equal(nextState.sessionAccessToken, "session_token_123456");
  assert.equal(nextState.conversationScope, "shipment");
  assert.equal(nextState.contextBindingState, "bound");
  assert.equal(nextState.activeResource.resource_id, "88219");
  assert.equal(nextState.messages.at(-1).response.response_id, "resp-1");
  assert.equal(nextState.activeJobPollToken, null);
});

test("getBindingBadge surfaces stale resource state", () => {
  const badge = getBindingBadge({
    conversationScope: "shipment",
    contextBindingState: "stale",
    activeResource: {
      resource_type: "shipment",
      resource_id: "99117",
      resource_fingerprint: "shipment:99117:v2",
    },
  });

  assert.equal(badge.label, "Shipment 99117");
  assert.match(badge.detail, /stale/i);
});

test("replacePendingJobResponse swaps the pending assistant payload with the completed result", () => {
  const initialState = {
    ...createInitialChatShellState(),
    sessionId: "chat_s_20260314_0001",
    activeJobId: "job_20260314_0001",
    messages: [
      {
        id: "resp-pending",
        role: "assistant",
        response: {
          response_id: "resp-pending",
          job_id: "job_20260314_0001",
          job_poll_token: "jobpoll_token_123456",
          summary: "Refresh started.",
        },
      },
    ],
  };

  const nextState = replacePendingJobResponse(initialState, {
    response_id: "resp-complete",
    job_id: "job_20260314_0001",
    summary: "Refresh completed.",
  });

  assert.equal(nextState.activeJobId, null);
  assert.equal(nextState.activeJobPollToken, null);
  assert.equal(nextState.sessionState, "ready");
  assert.equal(nextState.messages[0].response.response_id, "resp-complete");
});

test("applyChatResponse retains opaque polling token for pending jobs", () => {
  const initialState = createInitialChatShellState();
  const nextState = applyChatResponse(initialState, {
    session_id: "chat_s_20260314_0001",
    session_access_token: "session_token_123456",
    conversation_scope: "analytics",
    context_binding_state: "bound",
    screen_sync_state: "not_applicable",
    active_resource: null,
    job_id: "job_20260314_0001",
    job_poll_token: "jobpoll_token_123456",
    response_id: "resp-pending",
    request_id: "req-pending",
    trace_id: "trace-pending",
    intent_class: "read_pending",
    status: "pending",
    summary: "Refresh started.",
    follow_up_prompt: null,
    components: [
      {
        component_id: "msg-pending",
        component_type: "message_block",
        body: "Refresh started.",
        tone: "informational",
      },
    ],
    actions: [],
    policy: {
      permission_context_applied: true,
      sensitive_fields_redacted: true,
      write_confirmation_required: false,
      denial_reason_class: "none",
    },
    audit: {
      actor_role: "broker",
      office_scope: "memphis",
      tool_path: [],
      response_generated_at: "2026-03-14T12:00:00Z",
    },
  });

  assert.equal(nextState.activeJobId, "job_20260314_0001");
  assert.equal(nextState.activeJobPollToken, "jobpoll_token_123456");
  assert.equal(nextState.sessionAccessToken, "session_token_123456");
});

test("cyclePanelState rotates through the visible shell modes", () => {
  assert.equal(cyclePanelState("peek"), "open");
  assert.equal(cyclePanelState("open"), "expanded");
  assert.equal(cyclePanelState("expanded"), "peek");
});

test("shell copy points at the live chat shell and not the legacy fixture demo", () => {
  assert.equal(CHAT_SHELL_COPY.title, "Chat session");
  assert.equal(CHAT_SHELL_COPY.promptLabel, "Ask Meridian");
  assert.notEqual(CHAT_SHELL_COPY.title, CHAT_SHELL_COPY.legacyTitle);
});

test("updateJobPollingState updates job status and progress message", () => {
  const initialState = {
    ...createInitialChatShellState(),
    activeJobId: "job_123",
    activeJobPollToken: "token_123",
  };

  const nextState = updateJobPollingState(initialState, {
    status: "running",
    message: "Processing Memphis data...",
  });

  assert.equal(nextState.activeJobId, "job_123");
  assert.equal(nextState.activeJobPollToken, "token_123");
  assert.equal(nextState.activeJobStatus, "running");
  assert.equal(nextState.activeJobProgressMessage, "Processing Memphis data...");
});

test("clearJobState clears all job-related fields and sets ready", () => {
  const stateWithJob = {
    ...createInitialChatShellState(),
    sessionState: "loading",
    activeJobId: "job_123",
    activeJobPollToken: "token_123",
    activeJobStatus: "running",
    activeJobProgressMessage: "Processing...",
  };

  const clearedState = clearJobState(stateWithJob);

  assert.equal(clearedState.sessionState, "ready");
  assert.equal(clearedState.activeJobId, null);
  assert.equal(clearedState.activeJobPollToken, null);
  assert.equal(clearedState.activeJobStatus, null);
  assert.equal(clearedState.activeJobProgressMessage, null);
});

test("markJobError sets error state and clears job fields", () => {
  const stateWithJob = {
    ...createInitialChatShellState(),
    activeJobId: "job_123",
    activeJobPollToken: "token_123",
  };

  const errorState = markJobError(stateWithJob, "Job failed due to timeout");

  assert.equal(errorState.sessionState, "error");
  assert.equal(errorState.activeJobId, null);
  assert.equal(errorState.activeJobPollToken, null);
  assert.equal(errorState.activeJobStatus, "error");
  assert.equal(errorState.activeJobProgressMessage, "Job failed due to timeout");
});

test("getJobDisplayState returns no job when no active job", () => {
  const state = createInitialChatShellState();
  const display = getJobDisplayState(state);

  assert.equal(display.hasJob, false);
  assert.equal(display.status, null);
  assert.equal(display.message, "No background task in flight.");
});

test("getJobDisplayState surfaces queued job status", () => {
  const state = {
    ...createInitialChatShellState(),
    activeJobId: "job_123",
    activeJobStatus: "queued",
    activeJobProgressMessage: "Waiting for worker...",
  };

  const display = getJobDisplayState(state);

  assert.equal(display.hasJob, true);
  assert.equal(display.status, "queued");
  assert.equal(display.message, "Waiting for worker...");
});

test("getJobDisplayState surfaces running job status", () => {
  const state = {
    ...createInitialChatShellState(),
    activeJobId: "job_123",
    activeJobStatus: "running",
    activeJobProgressMessage: "Refreshing Memphis analytics...",
  };

  const display = getJobDisplayState(state);

  assert.equal(display.hasJob, true);
  assert.equal(display.status, "running");
  assert.equal(display.message, "Refreshing Memphis analytics...");
});

test("getJobDisplayState defaults message when not provided", () => {
  const state = {
    ...createInitialChatShellState(),
    activeJobId: "job_123",
    activeJobStatus: "running",
    activeJobProgressMessage: null,
  };

  const display = getJobDisplayState(state);

  assert.equal(display.hasJob, true);
  assert.equal(display.status, "running");
  assert.equal(display.message, "In progress");
});

test("getJobDisplayState handles succeeded status", () => {
  const state = {
    ...createInitialChatShellState(),
    activeJobId: "job_123",
    activeJobStatus: "succeeded",
    activeJobProgressMessage: "Analytics refreshed successfully",
  };

  const display = getJobDisplayState(state);

  assert.equal(display.hasJob, true);
  assert.equal(display.status, "succeeded");
  assert.equal(display.message, "Analytics refreshed successfully");
});

test("getJobDisplayState handles failed status", () => {
  const state = {
    ...createInitialChatShellState(),
    activeJobId: "job_123",
    activeJobStatus: "failed",
    activeJobProgressMessage: "Memphis connection timeout",
  };

  const display = getJobDisplayState(state);

  assert.equal(display.hasJob, true);
  assert.equal(display.status, "failed");
  assert.equal(display.message, "Memphis connection timeout");
});

test("getJobDisplayState handles cancelled status", () => {
  const state = {
    ...createInitialChatShellState(),
    activeJobId: "job_123",
    activeJobStatus: "cancelled",
    activeJobProgressMessage: null,
  };

  const display = getJobDisplayState(state);

  assert.equal(display.hasJob, true);
  assert.equal(display.status, "cancelled");
  assert.equal(display.message, "Cancelled");
});

test("getJobDisplayState handles expired status", () => {
  const state = {
    ...createInitialChatShellState(),
    activeJobId: "job_123",
    activeJobStatus: "expired",
    activeJobProgressMessage: null,
  };

  const display = getJobDisplayState(state);

  assert.equal(display.hasJob, true);
  assert.equal(display.status, "expired");
  assert.equal(display.message, "Expired");
});

test("getJobDisplayState handles unknown status", () => {
  const state = {
    ...createInitialChatShellState(),
    activeJobId: "job_123",
    activeJobStatus: "unknown",
    activeJobProgressMessage: null,
  };

  const display = getJobDisplayState(state);

  assert.equal(display.hasJob, true);
  assert.equal(display.status, "unknown");
  assert.equal(display.message, "Unknown status");
});
