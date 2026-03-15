import test from "node:test";
import assert from "node:assert/strict";

import {
  getJobPollResultAction,
  getJobPollFailureAction,
  MAX_JOB_POLL_DELAY_MS,
  MAX_JOB_POLL_FAILURES,
  nextRunningJobPollDelay,
} from "../src/job-polling.js";

test("nextRunningJobPollDelay increases gradually and caps", () => {
  assert.equal(nextRunningJobPollDelay(1200), 1600);
  assert.equal(nextRunningJobPollDelay(3800), MAX_JOB_POLL_DELAY_MS);
});

test("getJobPollFailureAction does not retry permanent client failures", () => {
  const error = new Error("unknown job");
  error.status = 404;

  const action = getJobPollFailureAction(error, {
    delayMs: 1200,
    consecutiveFailures: 0,
  });

  assert.equal(action.retry, false);
  assert.equal(action.message, "unknown job");
});

test("getJobPollFailureAction caps transient retries", () => {
  const error = new Error("temporary upstream failure");
  error.status = 503;

  const retryAction = getJobPollFailureAction(error, {
    delayMs: 2400,
    consecutiveFailures: 1,
  });
  assert.equal(retryAction.retry, true);
  assert.equal(retryAction.delayMs, MAX_JOB_POLL_DELAY_MS);

  const stopAction = getJobPollFailureAction(error, {
    delayMs: 2400,
    consecutiveFailures: MAX_JOB_POLL_FAILURES - 1,
  });
  assert.equal(stopAction.retry, false);
});

test("getJobPollResultAction reschedules queued jobs with status context", () => {
  const queuedAction = getJobPollResultAction(
    { status: "queued", result: null, progress_message: "queued" },
    { delayMs: 1200 },
  );
  assert.equal(queuedAction.type, "retry");
  assert.equal(queuedAction.status, "queued");
  assert.equal(queuedAction.message, "queued");
  assert.equal(queuedAction.delayMs, 1600);
});

test("getJobPollResultAction reschedules running jobs with progress message", () => {
  const runningAction = getJobPollResultAction(
    { status: "running", result: null, progress_message: "Refreshing Memphis data..." },
    { delayMs: 1600 },
  );
  assert.equal(runningAction.type, "retry");
  assert.equal(runningAction.status, "running");
  assert.equal(runningAction.message, "Refreshing Memphis data...");
  assert.equal(runningAction.delayMs, 2000);
});

test("getJobPollResultAction defaults progress message for running jobs", () => {
  const runningAction = getJobPollResultAction(
    { status: "running", result: null, progress_message: null },
    { delayMs: 1200 },
  );
  assert.equal(runningAction.message, "Job in progress...");
});

test("getJobPollResultAction completes succeeded jobs with result", () => {
  const completedAction = getJobPollResultAction(
    {
      status: "succeeded",
      result: { response_id: "resp_complete", job_id: "job_1" },
      progress_message: "done",
    },
    { delayMs: 1200 },
  );
  assert.deepEqual(completedAction, {
    type: "complete",
    status: "succeeded",
    result: { response_id: "resp_complete", job_id: "job_1" },
  });
});

test("getJobPollResultAction fails succeeded jobs without result", () => {
  const succeededNoResult = getJobPollResultAction(
    { status: "succeeded", result: null, progress_message: "Job completed" },
    { delayMs: 1200 },
  );
  assert.deepEqual(succeededNoResult, {
    type: "fail",
    status: "succeeded",
    message: "Job completed",
  });
});

test("getJobPollResultAction handles failed jobs with retry context", () => {
  const failedAction = getJobPollResultAction(
    { status: "failed", result: null, progress_message: "backend failed", retry_allowed: true },
    { delayMs: 1200 },
  );
  assert.deepEqual(failedAction, {
    type: "fail",
    status: "failed",
    message: "backend failed",
    retry_allowed: true,
  });
});

test("getJobPollResultAction defaults failed job messages", () => {
  const failedDefault = getJobPollResultAction(
    { status: "failed", result: null, progress_message: null, retry_allowed: false },
    { delayMs: 1200 },
  );
  assert.equal(failedDefault.type, "fail");
  assert.equal(failedDefault.status, "failed");
  assert.equal(failedDefault.message, "Background job failed.");
  assert.equal(failedDefault.retry_allowed, false);
});

test("getJobPollResultAction handles cancelled jobs", () => {
  const cancelledAction = getJobPollResultAction(
    { status: "cancelled", result: null, progress_message: "User cancelled the request" },
    { delayMs: 1200 },
  );
  assert.deepEqual(cancelledAction, {
    type: "fail",
    status: "cancelled",
    message: "User cancelled the request",
  });
});

test("getJobPollResultAction handles expired jobs", () => {
  const expiredAction = getJobPollResultAction(
    { status: "expired", result: null, progress_message: null },
    { delayMs: 1200 },
  );
  assert.deepEqual(expiredAction, {
    type: "fail",
    status: "expired",
    message: "Job expired before completion.",
  });
});

test("getJobPollResultAction handles unknown statuses", () => {
  const unknownAction = getJobPollResultAction(
    { status: "unknown_status", result: null, progress_message: null },
    { delayMs: 1200 },
  );
  assert.equal(unknownAction.type, "fail");
  assert.equal(unknownAction.status, "unknown_status");
  assert.equal(unknownAction.message, "Background job ended with unknown status unknown_status.");
});
