async function readJson(response) {
  const payload = await response.json();
  if (!response.ok) {
    const detail = payload?.detail ?? "Request failed";
    const error = new Error(typeof detail === "string" ? detail : "Request failed");
    error.status = response.status;
    throw error;
  }
  return payload;
}

function configuredApiBaseUrl() {
  if (typeof import.meta !== "undefined" && typeof import.meta.env?.VITE_API_BASE_URL === "string") {
    return import.meta.env.VITE_API_BASE_URL.trim();
  }
  if (typeof process !== "undefined" && typeof process.env?.VITE_API_BASE_URL === "string") {
    return process.env.VITE_API_BASE_URL.trim();
  }
  return "";
}

export function resolveApiUrl(path, apiBaseUrl = configuredApiBaseUrl()) {
  if (!apiBaseUrl) {
    return path;
  }
  if (/^https?:\/\//.test(apiBaseUrl)) {
    const baseUrl = apiBaseUrl.endsWith("/") ? apiBaseUrl : `${apiBaseUrl}/`;
    return new URL(path.replace(/^\/+/, ""), baseUrl).toString();
  }
  const normalizedBasePath = apiBaseUrl.endsWith("/") ? apiBaseUrl.slice(0, -1) : apiBaseUrl;
  return `${normalizedBasePath}${path}`;
}

export async function postChat(request) {
  const response = await fetch(resolveApiUrl("/chat"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
  return readJson(response);
}

export async function getJob(jobId, { jobPollToken }) {
  const params = new URLSearchParams({
    job_poll_token: jobPollToken,
  });
  const response = await fetch(resolveApiUrl(`/jobs/${jobId}?${params.toString()}`));
  return readJson(response);
}

export async function postConfirmAction({ actionName, confirmationToken, idempotencyKey, sessionId, sessionAccessToken }) {
  const response = await fetch(resolveApiUrl("/actions/confirm"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      action_name: actionName,
      confirmation_token: confirmationToken,
      idempotency_key: idempotencyKey,
      session_id: sessionId,
      session_access_token: sessionAccessToken,
    }),
  });
  return readJson(response);
}
