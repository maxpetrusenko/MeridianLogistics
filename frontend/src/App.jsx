import { useState } from "react";

import {
  buildActionResult,
  fixtures,
  getConfirmationCard,
  getResponseMode,
  getStaleConfirmationNotice,
  isExpired,
  sampleKeys,
} from "./response-model.js";

const shellStyle = {
  width: "min(1100px, 100%)",
};

const layoutStyle = {
  display: "grid",
  gap: "24px",
};

const tabRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: "10px",
  marginBottom: "20px",
};

const tabStyle = (active) => ({
  border: `1px solid ${active ? "#ffb375" : "rgba(255,255,255,0.12)"}`,
  background: active ? "rgba(255,179,117,0.14)" : "rgba(255,255,255,0.04)",
  color: "#f7f4ef",
  borderRadius: "999px",
  padding: "10px 14px",
  font: "inherit",
  cursor: "pointer",
});

const sectionStyle = {
  display: "grid",
  gap: "16px",
};

const cardStyle = {
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: "18px",
  padding: "18px",
  background: "rgba(255,255,255,0.03)",
};

const gridStyle = {
  display: "grid",
  gap: "12px",
  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
};

const actionRowStyle = {
  display: "flex",
  flexWrap: "wrap",
  gap: "10px",
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

const toneStyle = {
  informational: { borderColor: "rgba(113, 196, 255, 0.35)" },
  warning: { borderColor: "rgba(255, 179, 117, 0.5)" },
  error: { borderColor: "rgba(255, 112, 112, 0.55)" },
};

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

function ConfirmationCard({ component, actions, onAction, disabled }) {
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
        {confirmationActions.map((action) => (
          <button
            key={action.action_id}
            type="button"
            style={actionStyle(action.action_type, disabled)}
            disabled={disabled}
            onClick={() => onAction(action)}
          >
            {action.label}
          </button>
        ))}
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
        {visibleActions.map((action) => (
          <button
            key={action.action_id}
            type="button"
            style={actionStyle(action.action_type)}
            onClick={() => onAction(action)}
          >
            {action.label}
          </button>
        ))}
      </div>
    </section>
  );
}

function LoadingState() {
  return (
    <section style={cardStyle}>
      <p className="eyebrow">Loading</p>
      <p className="body" style={{ marginBottom: 0 }}>
        Request in progress. Prior confirmed state stays stable until the next payload arrives.
      </p>
    </section>
  );
}

function ResponseRenderer({ response, previousResponse, actionNotice, onAction }) {
  if (!response) {
    return (
      <div style={sectionStyle}>
        <LoadingState />
        {previousResponse ? (
          <ResponseRenderer
            response={previousResponse}
            previousResponse={null}
            actionNotice={actionNotice}
            onAction={onAction}
          />
        ) : null}
      </div>
    );
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
      {confirmationExpired ? (
        <MessageBlock component={getStaleConfirmationNotice(confirmationCard?.expires_at)} />
      ) : null}
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
                disabled={confirmationExpired}
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

export default function App() {
  const [activeKey, setActiveKey] = useState("metrics");
  const [activeResponse, setActiveResponse] = useState(fixtures.metrics.response);
  const [lastResolvedResponse, setLastResolvedResponse] = useState(fixtures.metrics.response);
  const [actionNotice, setActionNotice] = useState(null);

  function handleSelect(key) {
    const nextResponse = fixtures[key]?.response ?? null;

    setActiveKey(key);
    setActiveResponse(nextResponse);
    setActionNotice(null);
    if (nextResponse) {
      setLastResolvedResponse(nextResponse);
    }
  }

  function handleAction(action) {
    const { nextResponse, actionNotice: nextActionNotice } = buildActionResult({
      action,
      response: activeResponse,
      referenceTime: new Date().toISOString(),
    });

    setActionNotice(nextActionNotice);

    if (nextResponse !== activeResponse) {
      setActiveResponse(nextResponse);
    }

    if (nextResponse) {
      setLastResolvedResponse(nextResponse);
    }
  }

  return (
    <main className="shell" style={shellStyle}>
      <section className="panel" style={layoutStyle}>
        <div>
          <p className="eyebrow">Meridian Logistics</p>
          <h1>Structured response renderer</h1>
          <p className="body">
            Contract-anchored frontend slice. Memphis-only PoC states: loading, empty, read,
            denial, error, and booking confirmation.
          </p>
        </div>

        <section>
          <div style={tabRowStyle}>
            {sampleKeys.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => handleSelect(key)}
                style={tabStyle(activeKey === key)}
              >
                {fixtures[key]?.label ?? "Loading"}
              </button>
            ))}
          </div>
          <ResponseRenderer
            response={activeResponse}
            previousResponse={lastResolvedResponse}
            actionNotice={actionNotice}
            onAction={handleAction}
          />
        </section>
      </section>
    </main>
  );
}
