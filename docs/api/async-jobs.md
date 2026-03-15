# Async Jobs API

## Overview

The async jobs API enables long-running operations (analytics refreshes, bulk data processing, report generation) to execute without blocking the chat interface. Jobs are created during chat request processing and polled by the frontend until completion.

## Job Lifecycle

### States

| State | Description |
|-------|-------------|
| `queued` | Job created, waiting to start |
| `running` | Job actively processing |
| `succeeded` | Job completed successfully |
| `failed` | Job failed with error |
| `cancelled` | Job cancelled by user |
| `expired` | Job timed out |

### State Transitions

```
queued -> running -> succeeded
                    -> failed
                    -> expired
        -> cancelled
```

Transitions are enforced by `InMemoryJobStore`:
- `create_job()` initializes jobs as `queued`
- `start_job()` transitions `queued` to `running`
- `complete_job()` transitions `running` to `succeeded`
- Direct `failed`/`cancelled`/`expired` transitions available for error paths

## API Endpoints

### GET /jobs/{job_id}

Retrieve job status and result by job ID and poll token.

**Authentication:** Requires `job_poll_token` query parameter

**Request:**
```
GET /jobs/{job_id}?job_poll_token={token}
```

**Response (200 OK):**
```json
{
  "job_id": "job_20260314_abc123def456",
  "session_id": "chat_s_20260314_0001",
  "status": "succeeded",
  "created_at": "2026-03-14T12:00:00Z",
  "updated_at": "2026-03-14T12:02:30Z",
  "progress_message": "Background refresh completed for Memphis exceptions.",
  "retry_allowed": true,
  "completed_response_id": "resp_abc123",
  "result": {
    "contract_version": "0.1.0",
    "response_id": "resp_abc123",
    "status": "success",
    "summary": "Background refresh completed...",
    "components": [...],
    "actions": [],
    "policy": {...},
    "audit": {...}
  }
}
```

**Error Responses:**
- `404 Not Found`: Unknown job ID or invalid poll token

## Frontend Polling Behavior

### Poll Configuration (frontend/src/job-polling.js)

| Constant | Value | Purpose |
|----------|-------|---------|
| `INITIAL_JOB_POLL_DELAY_MS` | 1200 | Initial delay before first poll |
| `MAX_JOB_POLL_DELAY_MS` | 4000 | Maximum backoff delay |
| `MAX_JOB_POLL_FAILURES` | 4 | Max consecutive failures before giving up |

### Poll Logic

1. **Initial Request**: Chat response with `job_id` + `job_poll_token` triggers polling
2. **Exponential Backoff**: Delay increases by 400ms per poll, capped at 4s
3. **Result Handling**:
   - If `result` present: dispatch `complete` action with result
   - If status `queued` or `running`: schedule retry with backoff
   - Otherwise: dispatch `fail` action with error message

### Failure Handling

Poll failures are categorized by HTTP status:
- **4xx (except 408, 429)**: Fatal, no retry
- **408, 429, 5xx**: Retry with exponential backoff
- **Network errors**: Retry with exponential backoff
- **Max failures exceeded**: Abort polling

## Session Integration

### Job-Session Binding

Jobs are bound to sessions during creation:
- `session_id` links job to conversation
- `pending_response_id` tracks the response that created the job
- `last_job_id` in session state tracks most recent job

### Completion Promotion

When a job completes, the system attempts to promote its result to the session:
```python
session_store.promote_job_completion(
    session_id=job.session_id,
    expected_last_response_id=job.pending_response_id,
    completed_response_id=job.completed_response_id,
    job_id=job.job_id,
)
```

Promotion succeeds only if the session's `last_response_id` still matches the `pending_response_id` when the job was created. This prevents stale completions from overwriting newer conversation state.

## Security Model

### Job Poll Tokens

Each job receives a cryptographically random `job_poll_token` (24 bytes, URL-safe base64 encoded):
- Generated at job creation via `secrets.token_urlsafe(24)`
- Required for all job status queries
- NOT exposed in chat responses (only `job_id` is visible)
- Prevents unauthorized job status access

### Legacy Backfill

Jobs created before poll token introduction are automatically backfilled:
- `InMemoryJobStore._backfill_job_poll_tokens()` runs on initialization
- Assigns tokens to any job with `NULL` or empty `job_poll_token`

## Error Handling & Retry

### Client-Side Retry

Frontend implements exponential backoff for transient failures:
- Network errors: retry
- 5xx errors: retry
- 408 (Request Timeout): retry
- 429 (Too Many Requests): retry
- Other 4xx: fatal, no retry

### Server-Side Retry

Jobs can be marked `retry_allowed: true` during creation:
- Indicates client may retry the operation that spawned this job
- Does NOT trigger automatic server-side retry
- Serves as advisory flag for UI behavior

### Completion Refresh Mechanism

Running jobs use a "completion refresh" pattern to avoid race conditions:
1. Background worker prepares result via `prepare_result()`
2. Client polls via `/jobs/{job_id}`
3. `refresh_job()` decrements `completion_refreshes_remaining`
4. After N polls, job materializes the prepared result via `complete_job()`

This ensures the session is ready to receive the completion before the job transitions to `succeeded`.

## Database Schema

```sql
CREATE TABLE generation_jobs (
    job_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    office_id TEXT NOT NULL,
    broker_id TEXT NOT NULL,
    job_kind TEXT NOT NULL,
    job_status TEXT NOT NULL,
    progress_message TEXT NOT NULL,
    retry_allowed INTEGER NOT NULL,
    pending_response_id TEXT,
    completed_response_id TEXT,
    prepared_result_payload TEXT,
    result_payload TEXT,
    job_poll_token TEXT,
    completion_refreshes_remaining INTEGER,
    completion_ready_at REAL,
    artifact_key TEXT,
    artifact_mime_type TEXT,
    artifact_size_bytes INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);
```

## Idempotency

Job ID generation is deterministic and thread-safe:
- Format: `job_{YYYYMMDD}_{12-char-hex}`
- Uses UUIDv4 for uniqueness
- `InMemoryJobStore` uses threading locks for concurrent access
- Database-backed state survives restarts

## Testing

See `tests/b2b3/test_async_job_lifecycle.py` for comprehensive coverage of:
- Session ID uniqueness under concurrent load
- Job state transitions (queued -> running -> succeeded)
- Poll token backfill for legacy rows
- Completion promotion conditional logic
- Job persistence across app restarts

## Bounded Autonomy (Phase 1)

### Overview

When `MERIDIAN_RUNNING_AUTONOMY_ENABLED=true` (together with controller checkpoint flags), async read jobs execute autonomously in bounded steps. The frontend's polling behavior drives execution forward without changing the public API contract.

### Execution Model

**Poll-Driven Bounded Steps:**
- Each `GET /jobs/{job_id}` poll advances exactly one autonomy step
- No background workers or queues required
- One poll = one step, max steps configured via `MERIDIAN_RUNNING_AUTONOMY_MAX_STEPS`
- Read-only phase 1: no autonomous writes, confirmation-gated writes unchanged

### Feature Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `MERIDIAN_RUNNING_AUTONOMY_ENABLED` | `false` | Master switch for running-app autonomy |
| `MERIDIAN_CONTROLLER_CHECKPOINTS_ENABLED` | `false` | Required for checkpoint persistence |
| `MERIDIAN_CONTROLLER_PRECEDENCE_ENABLED` | `false` | Required for checkpoint truth |
| `MERIDIAN_RUNNING_AUTONOMY_MAX_STEPS` | `3` | Maximum steps per autonomy run |
| `MERIDIAN_RUNNING_AUTONOMY_POLL_STEP_TIMEOUT_SECONDS` | `5` | Per-step wall-clock timeout |

### Allowed Steps (Phase 1)

1. `seed_context` - Initialize controller checkpoint
2. `execute_allowlisted_read` - Run read-only analytics
3. `build_response` - Assemble response envelope
4. `complete_job` - Mark job as succeeded
5. `fail_job` - Fail-soft termination on budget exhaustion

### Checkpoint Architecture

- **Authoritative truth**: Controller checkpoint stored under `job_id`
- **Derivative cache**: Job metadata (`autonomy_metadata` JSON column)
- Checkpoint truth wins on resume if job metadata is stale
- Checkpoint path: `.controller-checkpoints/{job_id}.json`

### Audit Fields

When autonomy runs, response audit section includes:
```json
{
  "audit": {
    "actor_role": "broker",
    "office_scope": "memphis",
    "tool_path": ["shipment_exception_lookup"],
    "response_generated_at": "2026-03-15T20:00:00Z",
    "autonomy_mode": "poll_driven",
    "autonomy_task_kind": "async_read_refresh",
    "autonomy_run_id": "job_20260315_abc123",
    "checkpoint_id": "job_20260315_abc123:seed"
  }
}
```

### Termination Conditions

Autonomy jobs terminate on:
1. **Successful completion** - All steps executed, result materialized
2. **Step budget exhausted** - `MERIDIAN_RUNNING_AUTONOMY_MAX_STEPS` reached
3. **Checkpoint terminal state** - Controller marked run as blocked/done
4. **Poll validation failure** - Invalid token or session mismatch

### Non-Goals (Phase 1)

- Autonomous booking writes (require confirmation)
- Background worker processes (poll-driven only)
- Multi-job fan-out or nested autonomy
- Frontend contract changes (audit fields are additive)
