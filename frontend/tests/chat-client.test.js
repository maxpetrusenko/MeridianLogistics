import test from "node:test";
import assert from "node:assert/strict";

import { getJob, postChat, resolveApiUrl } from "../src/chat-client.js";

test("resolveApiUrl preserves relative paths when no public API base URL is configured", () => {
  assert.equal(resolveApiUrl("/chat", ""), "/chat");
  assert.equal(resolveApiUrl("/jobs/job_1", null), "/jobs/job_1");
});

test("resolveApiUrl joins absolute and path-only public API base URLs safely", () => {
  assert.equal(resolveApiUrl("/chat", "https://api.example.com"), "https://api.example.com/chat");
  assert.equal(resolveApiUrl("/jobs/job_1", "https://api.example.com/v1/"), "https://api.example.com/v1/jobs/job_1");
  assert.equal(resolveApiUrl("/chat", "/api/"), "/api/chat");
});

test("postChat and getJob honor VITE_API_BASE_URL when present", async () => {
  const originalFetch = globalThis.fetch;
  const originalApiBaseUrl = process.env.VITE_API_BASE_URL;
  const calls = [];

  process.env.VITE_API_BASE_URL = "https://api.example.com/meridian";
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    return {
      ok: true,
      async json() {
        return { ok: true };
      },
    };
  };

  try {
    await postChat({ prompt: "Refresh Memphis exceptions." });
    await getJob("job_20260314_0001", { jobPollToken: "jobpoll_token_123456" });
  } finally {
    globalThis.fetch = originalFetch;
    if (originalApiBaseUrl === undefined) {
      delete process.env.VITE_API_BASE_URL;
    } else {
      process.env.VITE_API_BASE_URL = originalApiBaseUrl;
    }
  }

  assert.equal(calls[0].url, "https://api.example.com/meridian/chat");
  assert.equal(calls[1].url, "https://api.example.com/meridian/jobs/job_20260314_0001?job_poll_token=jobpoll_token_123456");
});
