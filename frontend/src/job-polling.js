export const INITIAL_JOB_POLL_DELAY_MS = 1200;
export const MAX_JOB_POLL_DELAY_MS = 4000;
export const MAX_JOB_POLL_FAILURES = 4;

export function nextRunningJobPollDelay(delayMs) {
  return Math.min(delayMs + 400, MAX_JOB_POLL_DELAY_MS);
}

export function getJobPollResultAction(job, { delayMs }) {
  const { status, result, progress_message } = job;

  switch (status) {
    case "queued":
      return {
        type: "retry",
        status: "queued",
        message: progress_message || "Job queued, waiting to start...",
        delayMs: nextRunningJobPollDelay(delayMs),
      };

    case "running":
      return {
        type: "retry",
        status: "running",
        message: progress_message || "Job in progress...",
        delayMs: nextRunningJobPollDelay(delayMs),
      };

    case "succeeded":
      if (result) {
        return {
          type: "complete",
          status: "succeeded",
          result,
        };
      }
      return {
        type: "fail",
        status: "succeeded",
        message: progress_message || "Job completed but no result available.",
      };

    case "failed":
      return {
        type: "fail",
        status: "failed",
        message: progress_message || "Background job failed.",
        retry_allowed: job.retry_allowed ?? false,
      };

    case "cancelled":
      return {
        type: "fail",
        status: "cancelled",
        message: progress_message || "Job was cancelled.",
      };

    case "expired":
      return {
        type: "fail",
        status: "expired",
        message: progress_message || "Job expired before completion.",
      };

    default:
      return {
        type: "fail",
        status: status ?? "unknown",
        message: progress_message || `Background job ended with unknown status ${status}.`,
      };
  }
}

export function getJobPollFailureAction(error, { delayMs, consecutiveFailures }) {
  const message = error instanceof Error ? error.message : "Background polling failed.";
  const status = typeof error?.status === "number" ? error.status : null;
  const nextFailures = consecutiveFailures + 1;

  if (status !== null && status >= 400 && status < 500 && status !== 408 && status !== 429) {
    return {
      retry: false,
      message,
      consecutiveFailures: nextFailures,
    };
  }

  if (nextFailures >= MAX_JOB_POLL_FAILURES) {
    return {
      retry: false,
      message,
      consecutiveFailures: nextFailures,
    };
  }

  return {
    retry: true,
    message,
    consecutiveFailures: nextFailures,
    delayMs: Math.min(delayMs * 2, MAX_JOB_POLL_DELAY_MS),
  };
}
