import { useEffect, useState } from "react";

import { getJob, postChat, postConfirmAction } from "./chat-client.js";
import {
  getJobPollResultAction,
  getJobPollFailureAction,
  INITIAL_JOB_POLL_DELAY_MS,
} from "./job-polling.js";
import {
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
} from "./chat-state.js";
import {
  buildActionResult,
  getActionInteractivity,
  getConfirmationCard,
  getResponseMode,
  getStaleConfirmationNotice,
  isExpired,
} from "./response-model.js";

const shellStyle = {
  width: "min(1200px, 100%)",
};

const appLayoutStyle = {
  display: "grid",
  gap: "24px",
};

const gridStyle = {
  display: "grid",
  gap: "12px",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
};

const sectionStyle = {
  display: "grid",
  gap: "16px",
};

const cardStyle = {
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: "20px",
  padding: "18px",
  background: "rgba(255,255,255,0.03)",
};

const transcriptStyle = {
  ...cardStyle,
  display: "grid",
  gap: "14px",
};

const composerStyle = {
  ...cardStyle,
  display: "grid",
  gap: "14px",
};

const toneStyle = {
  informational: { borderColor: "rgba(113, 196, 255, 0.35)" },
  warning: { borderColor: "rgba(255, 179, 117, 0.5)" },
  error: { borderColor: "rgba(255, 112, 112, 0.55)" },
};

const actionRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: "10px",
};

const actionItemStyle = {
  display: "grid",
  gap: "6px",
};

const actionHintStyle = {
  margin: 0,
  color: "#ffb375",
  fontSize: "0.82rem",
  maxWidth: "260px",
};

const inputStyle = {
  width: "100%",
  borderRadius: "14px",
  border: "1px solid rgba(255,255,255,0.12)",
  background: "rgba(255,255,255,0.04)",
  color: "#f7f4ef",
  padding: "12px 14px",
  font: "inherit",
};

const badgeToneStyle = {
  live: {
    border: "1px solid rgba(95, 216, 161, 0.35)",
    background: "rgba(95, 216, 161, 0.08)",
    color: "#b8f3d7",
  },
  warning: {
    border: "1px solid rgba(255, 179, 117, 0.35)",
    background: "rgba(255, 179, 117, 0.08)",
    color: "#ffd6a7",
  },
  neutral: {
    border: "1px solid rgba(255,255,255,0.12)",
    background: "rgba(255,255,255,0.04)",
    color: "#d7dfef",
  },
};

const actionStyle = (kind, disabled = false) => ({
  border: "none",
  borderRadius: "12px",
  padding: "12px 14px",
  font: "inherit",
  cursor: disabled ? "not-allowed" : "pointer",
  background: kind === "confirm_booking" ? "#ffb375" : "rgba(255,255,255,0.08)",
  color: kind === "confirm_booking" ? "#0f1422" : "#f7f4ef",
  opacity: disabled ? 0.55 : kind === "confirm_booking" || kind === "cancel_booking" ? 1 : 0.9,
});

function ActionButton({ action, actionState, onAction }) {
  return (
    <div style={actionItemStyle}>
      <button
        type="button"
        style={actionStyle(action.action_type, actionState.disabled)}
        disabled={actionState.disabled}
        title={actionState.reason ?? undefined}
        onClick={() => {
          if (!actionState.disabled) {
            onAction(action);
          }
        }}
      >
        {action.label}
      </button>
      {actionState.reason ? <p style={actionHintStyle}>{actionState.reason}</p> : null}
    </div>
  );
}

function SummaryBlock({ text }) {
  return (
    <section style={cardStyle}>
      <p className="eyebrow">Summary</p>
      <p className="body" style={{ marginBottom: 0 }}>
        {text}
      </p>
    </section>
  );
}

function MessageBlock({ component }) {
  return (
    <section style={{ ...cardStyle, ...toneStyle[component.tone ?? "informational"] }}>
      <p className="eyebrow">{component.tone ?? "informational"}</p>
      <p className="body" style={{ marginBottom: 0 }}>
        {component.body}
      </p>
    </section>
  );
}

function MetricCard({ component }) {
  return (
    <section style={cardStyle}>
      <p className="eyebrow">Metrics</p>
      <div style={gridStyle}>
        {component.metrics.map((metric) => (
          <article key={metric.label} style={{ ...cardStyle, padding: "14px" }}>
            <p className="eyebrow" style={{ marginBottom: "6px" }}>
              {metric.label}
            </p>
            <strong style={{ fontSize: "1.6rem" }}>
              {metric.value}
              {metric.unit ? ` ${metric.unit}` : ""}
            </strong>
          </article>
        ))}
      </div>
    </section>
  );
}

function TableBlock({ component }) {
  return (
    <section style={cardStyle}>
      <p className="eyebrow">Table</p>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", color: "#d7dfef" }}>
          <thead>
            <tr>
              {component.columns.map((column) => (
                <th
                  key={column.key}
                  style={{
                    textAlign: "left",
                    padding: "0 0 12px",
                    fontSize: "0.8rem",
                    color: "#ffb375",
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                  }}
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {component.rows.map((row, index) => (
              <tr key={index}>
                {row.map((value, cellIndex) => (
                  <td
                    key={`${index}-${cellIndex}`}
                    style={{ padding: "12px 0", borderTop: "1px solid rgba(255,255,255,0.08)" }}
                  >
                    {String(value)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function TimelineBlock({ component }) {
  return (
    <section style={cardStyle}>
      <p className="eyebrow">Timeline</p>
      <div style={{ display: "grid", gap: "12px" }}>
        {component.events.map((event) => (
          <article key={`${event.label}-${event.timestamp}`} style={{ ...cardStyle, padding: "14px" }}>
            <strong>{event.label}</strong>
            <p className="body" style={{ margin: "6px 0 0" }}>
              {event.timestamp}
              {event.state ? ` • ${event.state}` : ""}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}

function ConfirmationCard({ component, actions, onAction, confirmationExpired }) {
  const confirmationActions = actions.filter((action) =>
    ["confirm_booking", "cancel_booking"].includes(action.action_type),
  );

  return (
    <section style={{ ...cardStyle, borderColor: "rgba(255,179,117,0.45)" }}>
      <p className="eyebrow">Confirmation Required</p>
      <div style={{ display: "grid", gap: "10px", marginBottom: "16px" }}>
        {component.fields.map((field) => (
          <div key={field.key} style={{ display: "flex", justifyContent: "space-between", gap: "16px" }}>
            <span style={{ color: "#b9c7dd" }}>{field.label}</span>
            <strong>{field.value}</strong>
          </div>
        ))}
      </div>
      <p className="body">
        Confirmation token: <code>{component.confirmation_token}</code>
      </p>
      <p className="body">Expires: {component.expires_at}</p>
      <div style={actionRowStyle}>
        {confirmationActions.map((action) => {
          const actionState = getActionInteractivity(action, { confirmationExpired });
          return <ActionButton key={action.action_id} action={action} actionState={actionState} onAction={onAction} />;
        })}
      </div>
    </section>
  );
}

function ActionBar({ actions, intentClass, onAction }) {
  const visibleActions =
    intentClass === "write_confirmation_required"
      ? []
      : actions.filter((action) => !["confirm_booking", "cancel_booking"].includes(action.action_type));

  if (visibleActions.length === 0) {
    return null;
  }

  return (
    <section style={cardStyle}>
      <p className="eyebrow">Actions</p>
      <div style={actionRowStyle}>
        {visibleActions.map((action) => {
          const actionState = getActionInteractivity(action);
          return <ActionButton key={action.action_id} action={action} actionState={actionState} onAction={onAction} />;
        })}
      </div>
    </section>
  );
}

function ResponseRenderer({ response, actionNotice, onAction }) {
  if (!response) {
    return null;
  }

  const responseMode = getResponseMode(response);
  const actions = response.actions ?? [];
  const confirmationCard = getConfirmationCard(response);
  const renderTime = new Date().toISOString();
  const confirmationExpired = confirmationCard ? isExpired(confirmationCard.expires_at, renderTime) : false;
  const visibleComponents = response.components.filter((component) => {
    if (responseMode === "read") {
      return ["message_block", "metric_card", "table", "timeline"].includes(component.component_type);
    }
    if (responseMode === "confirmation") {
      return !confirmationExpired && component.component_type === "confirmation_card";
    }
    return component.component_type === "message_block";
  });

  return (
    <div style={sectionStyle}>
      <SummaryBlock text={response.summary} />
      {confirmationExpired ? <MessageBlock component={getStaleConfirmationNotice(confirmationCard?.expires_at)} /> : null}
      {actionNotice ? <MessageBlock component={actionNotice} /> : null}
      {visibleComponents.map((component, index) => {
        const key = `${component.component_type}-${index}`;

        switch (component.component_type) {
          case "message_block":
            return <MessageBlock key={key} component={component} />;
          case "metric_card":
            return <MetricCard key={key} component={component} />;
          case "table":
            return <TableBlock key={key} component={component} />;
          case "timeline":
            return <TimelineBlock key={key} component={component} />;
          case "confirmation_card":
            return (
              <ConfirmationCard
                key={key}
                component={component}
                actions={actions}
                onAction={onAction}
                confirmationExpired={confirmationExpired}
              />
            );
          default:
            return null;
        }
      })}
      <ActionBar actions={actions} intentClass={response.intent_class} onAction={onAction} />
    </div>
  );
}

function AssistantMessage({ message, actionNotice, onAction }) {
  return (
    <article style={{ ...cardStyle, padding: "16px" }}>
      <p className="eyebrow">Meridian</p>
      <ResponseRenderer response={message.response} actionNotice={actionNotice} onAction={onAction} />
    </article>
  );
}

function UserMessage({ message }) {
  return (
    <article style={{ ...cardStyle, padding: "16px", borderColor: "rgba(255,179,117,0.25)" }}>
      <p className="eyebrow">Broker</p>
      <p className="body" style={{ marginBottom: 0 }}>
        {message.prompt}
      </p>
    </article>
  );
}

function EmptyTranscript() {
  return (
    <section style={cardStyle}>
      <p className="eyebrow">Session idle</p>
      <p className="body" style={{ marginBottom: 0 }}>
        Start with a Memphis shipment question. The shell will keep session scope, visible context binding, and async job status.
      </p>
    </section>
  );
}

export default function App() {
  const [shellState, setShellState] = useState(createInitialChatShellState);
  const [prompt, setPrompt] = useState("");
  const [currentModule, setCurrentModule] = useState("dispatch_board");
  const [resourceId, setResourceId] = useState("");
  const [errorMessage, setErrorMessage] = useState(null);
  const [actionNotices, setActionNotices] = useState({});

  const bindingBadge = getBindingBadge(shellState);

  useEffect(() => {
    if (!shellState.activeJobId || !shellState.activeJobPollToken) {
      return undefined;
    }

    let cancelled = false;
    let timeoutId = null;
    let consecutiveFailures = 0;

    const schedulePoll = (delayMs) => {
      timeoutId = window.setTimeout(async () => {
        try {
          const job = await getJob(shellState.activeJobId, {
            jobPollToken: shellState.activeJobPollToken,
          });
          if (cancelled) {
            return;
          }

          setErrorMessage(null);
          consecutiveFailures = 0;
          const resultAction = getJobPollResultAction(job, { delayMs });
          if (resultAction.type === "complete") {
            setShellState((currentState) => replacePendingJobResponse(currentState, resultAction.result));
            return;
          }
          if (resultAction.type === "retry") {
            setShellState((currentState) =>
              updateJobPollingState(currentState, {
                status: resultAction.status,
                message: resultAction.message,
              }),
            );
            schedulePoll(resultAction.delayMs);
            return;
          }
          setErrorMessage(resultAction.message);
          setShellState((currentState) => markJobError(currentState, resultAction.message));
        } catch (error) {
          if (cancelled) {
            return;
          }
          const failureAction = getJobPollFailureAction(error, {
            delayMs,
            consecutiveFailures,
          });
          consecutiveFailures = failureAction.consecutiveFailures;
          if (failureAction.retry) {
            setErrorMessage(failureAction.message);
            schedulePoll(failureAction.delayMs);
            return;
          }
          setErrorMessage(failureAction.message);
          setShellState((currentState) => markJobError(currentState, failureAction.message));
        }
      }, delayMs);
    };

    schedulePoll(INITIAL_JOB_POLL_DELAY_MS);

    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [shellState.activeJobId, shellState.activeJobPollToken]);

  async function handleSubmit(event) {
    event.preventDefault();

    const trimmedPrompt = prompt.trim();
    if (!trimmedPrompt) {
      return;
    }

    const request = buildChatRequest({
      prompt: trimmedPrompt,
      sessionId: shellState.sessionId,
      sessionAccessToken: shellState.sessionAccessToken,
      currentModule,
      resourceId: resourceId.trim(),
    });

    setErrorMessage(null);
    setShellState((currentState) => ({
      ...currentState,
      sessionState: currentState.sessionId ? "loading" : "loading",
    }));

    try {
      const response = await postChat(request);
      setShellState((currentState) => applyChatResponse(currentState, response, trimmedPrompt));
      setPrompt("");
    } catch (error) {
      setErrorMessage(error.message);
      setShellState((currentState) => ({
        ...currentState,
        sessionState: "error",
      }));
    }
  }

  async function handleAction(messageId, action) {
    const confirmationCard = action.action_type === "confirm_booking"
      ? shellState.messages.find((m) => m.id === messageId)?.response?.components?.find(
          (c) => c.component_type === "confirmation_card"
        )
      : null;

    if (confirmationCard && action.confirmation_token && action.idempotency_key) {
      setActionNotices((currentNotices) => ({
        ...currentNotices,
        [messageId]: {
          component_id: `msg-action-pending-${action.action_id}`,
          component_type: "message_block",
          body: "Confirming booking...",
          tone: "informational",
        },
      }));

      try {
        const response = await postConfirmAction({
          actionName: confirmationCard.action_name || "booking_create_confirmed",
          confirmationToken: action.confirmation_token,
          idempotencyKey: action.idempotency_key,
          sessionId: shellState.sessionId,
          sessionAccessToken: shellState.sessionAccessToken,
        });

        setShellState((currentState) => applyChatResponse(currentState, response, null));
        setActionNotices((currentNotices) => ({
          ...currentNotices,
          [messageId]: {
            component_id: `msg-action-complete-${action.action_id}`,
            component_type: "message_block",
            body: response.summary,
            tone: response.intent_class === "write_submitted" ? "informational" : "warning",
          },
        }));
      } catch (error) {
        setErrorMessage(error.message);
        setActionNotices((currentNotices) => ({
          ...currentNotices,
          [messageId]: {
            component_id: `msg-action-error-${action.action_id}`,
            component_type: "message_block",
            body: `Confirmation failed: ${error.message}`,
            tone: "error",
          },
        }));
      }
      return;
    }

    setShellState((currentState) => {
      const targetMessage = currentState.messages.find((message) => message.id === messageId);
      if (!targetMessage?.response) {
        return currentState;
      }

      const { nextResponse, actionNotice } = buildActionResult({
        action,
        response: targetMessage.response,
        referenceTime: new Date().toISOString(),
      });

      setActionNotices((currentNotices) => ({
        ...currentNotices,
        [messageId]: actionNotice,
      }));

      return {
        ...currentState,
        messages: currentState.messages.map((message) =>
          message.id === messageId && nextResponse
            ? {
                ...message,
                response: nextResponse,
                id: nextResponse.response_id,
              }
            : message,
        ),
      };
    });
  }

  return (
    <main className="shell" style={shellStyle}>
      <section className="panel chat-panel" style={appLayoutStyle}>
        <header style={{ display: "grid", gap: "14px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "16px", alignItems: "start", flexWrap: "wrap" }}>
            <div>
              <p className="eyebrow">Meridian Logistics</p>
              <h1>Chat session</h1>
              <p className="body" style={{ maxWidth: "760px" }}>
                Ask Meridian
                {" "}
                for shipment context, analytics refreshes, and confirmation-bound actions. Session scope and binding state stay visible in the shell.
              </p>
            </div>
            <button
              type="button"
              className="ghost-button"
              onClick={() => setShellState((currentState) => ({ ...currentState, panelState: cyclePanelState(currentState.panelState) }))}
            >
              Panel: {shellState.panelState}
            </button>
          </div>

          <div style={gridStyle}>
            <article style={{ ...cardStyle, padding: "14px" }}>
              <p className="eyebrow">Session</p>
              <strong>{shellState.sessionId ?? "New chat session"}</strong>
              <p className="body" style={{ margin: "8px 0 0" }}>
                State: {shellState.sessionState}
              </p>
            </article>
            <article style={{ ...cardStyle, padding: "14px", ...badgeToneStyle[bindingBadge.tone] }}>
              <p className="eyebrow">Binding</p>
              <strong>{bindingBadge.label}</strong>
              <p className="body" style={{ margin: "8px 0 0" }}>
                {bindingBadge.detail}
              </p>
            </article>
            <article style={{ ...cardStyle, padding: "14px" }}>
              <p className="eyebrow">Scope</p>
              <strong>{shellState.conversationScope}</strong>
              <p className="body" style={{ margin: "8px 0 0" }}>
                Screen sync: {shellState.screenSyncState}
              </p>
            </article>
            <article style={{ ...cardStyle, padding: "14px" }}>
              <p className="eyebrow">Async</p>
              <strong>{shellState.activeJobId ?? "No active job"}</strong>
              <p className="body" style={{ margin: "8px 0 0" }}>
                {(() => {
                  const jobDisplay = getJobDisplayState(shellState);
                  if (!jobDisplay.hasJob) {
                    return "No background task in flight.";
                  }
                  return `${jobDisplay.status ? `${jobDisplay.status}: ` : ""}${jobDisplay.message}`;
                })()}
              </p>
            </article>
          </div>
        </header>

        <section style={transcriptStyle}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "16px", flexWrap: "wrap" }}>
            <div>
              <p className="eyebrow">Transcript</p>
              <p className="body" style={{ marginBottom: 0 }}>
                Memphis-only trusted context. Backend responses remain the only render source.
              </p>
            </div>
          </div>

          {errorMessage ? (
            <section style={{ ...cardStyle, ...toneStyle.error }}>
              <p className="eyebrow">error</p>
              <p className="body" style={{ marginBottom: 0 }}>
                {errorMessage}
              </p>
            </section>
          ) : null}

          {shellState.messages.length === 0 ? <EmptyTranscript /> : null}
          {shellState.messages.map((message) =>
            message.role === "user" ? (
              <UserMessage key={message.id} message={message} />
            ) : (
              <AssistantMessage
                key={message.id}
                message={message}
                actionNotice={actionNotices[message.id] ?? null}
                onAction={(action) => handleAction(message.id, action)}
              />
            ),
          )}
        </section>

        <form style={composerStyle} onSubmit={handleSubmit}>
          <div style={gridStyle}>
            <label style={{ display: "grid", gap: "8px" }}>
              <span className="eyebrow" style={{ marginBottom: 0 }}>
                Module
              </span>
              <select value={currentModule} onChange={(event) => setCurrentModule(event.target.value)} style={inputStyle}>
                <option value="dispatch_board">Dispatch board</option>
                <option value="track_trace">Track and trace</option>
                <option value="analytics">Analytics</option>
              </select>
            </label>
            <label style={{ display: "grid", gap: "8px" }}>
              <span className="eyebrow" style={{ marginBottom: 0 }}>
                Active shipment
              </span>
              <input
                type="text"
                value={resourceId}
                onChange={(event) => setResourceId(event.target.value)}
                placeholder="88219"
                style={inputStyle}
              />
            </label>
          </div>

          <label style={{ display: "grid", gap: "8px" }}>
            <span className="eyebrow" style={{ marginBottom: 0 }}>
              Ask Meridian
            </span>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={4}
              placeholder="Show shipment 88219 details."
              style={{ ...inputStyle, resize: "vertical", minHeight: "120px" }}
            />
          </label>

          <div style={{ display: "flex", justifyContent: "space-between", gap: "16px", alignItems: "center", flexWrap: "wrap" }}>
            <p className="body" style={{ marginBottom: 0 }}>
              Writes stay confirmation-only. Background reads surface as job-backed pending states.
            </p>
            <button type="submit" className="primary-button" disabled={shellState.sessionState === "loading"}>
              {shellState.sessionState === "loading" ? "Sending..." : "Send prompt"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
