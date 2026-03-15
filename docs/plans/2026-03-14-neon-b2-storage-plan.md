# Neon B2 Storage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Neon-compatible database config plus Backblaze B2 storage scaffolding, schema hooks, and docs for the Meridian Memphis PoC.

**Architecture:** Keep relational state in Postgres and large generated artifacts in object storage. Implement a small storage adapter seam and metadata tables so later workers can upload and serve artifacts without changing app contracts.

**Tech Stack:** Python, FastAPI, psycopg, Postgres schema files, S3-compatible object storage, pytest

---

### Task 1: Document the chosen storage design

**Files:**
- Create: `docs/plans/2026-03-14-neon-b2-storage-design.md`
- Create: `docs/plans/2026-03-14-neon-b2-storage-plan.md`

**Step 1: Write the design note**

Capture:

- why Postgres fits the source model
- why B2 holds blobs
- data placement rules
- required secrets

**Step 2: Review for repo alignment**

Check the note against:

- `source-brief.md`
- `architecture-overview.md`
- `decisions.md`

**Step 3: Save plan and proceed to tests**

No code yet.

### Task 2: Add failing tests for config and storage seams

**Files:**
- Create: `tests/b1/test_storage_config.py`

**Step 1: Write failing tests**

Cover:

- config loads `MERIDIAN_DIRECT_DATABASE_URL`
- config loads B2 env vars
- storage context exposes provider, bucket, endpoint, manifest path
- storage adapter rejects operations when storage is not configured

**Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/b1/test_storage_config.py -v
```

Expected: failing assertions or import errors for missing config and storage helpers.

**Step 3: Implement minimal code**

Add config fields, storage context, and a storage adapter seam only large enough to satisfy the tests.

**Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/b1/test_storage_config.py -v
```

Expected: PASS

### Task 3: Extend schema and database context for artifact metadata

**Files:**
- Modify: `db/schema.sql`
- Modify: `backend/app/db/context.py`
- Modify: `tests/b1/test_b1_scaffold.py`

**Step 1: Write failing test**

Add expectations for:

- `generation_jobs`
- `documents_manifest`
- optional migrations or seed context references if needed

**Step 2: Run targeted test to verify failure**

Run:

```bash
pytest tests/b1/test_b1_scaffold.py -v
```

Expected: FAIL because new tables are absent.

**Step 3: Write minimal schema/context changes**

Add only the metadata tables and any context fields needed by the app.

**Step 4: Run test to verify pass**

Run:

```bash
pytest tests/b1/test_b1_scaffold.py -v
```

Expected: PASS

### Task 4: Surface storage dependencies through app startup

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/app/storage/__init__.py`
- Create: `backend/app/storage/context.py`
- Create: `backend/app/storage/service.py`

**Step 1: Write failing test**

Extend `tests/b1/test_storage_config.py` to assert:

- app state carries storage service
- unconfigured storage remains explicit, not implicit local-disk fallback

**Step 2: Run test to verify failure**

Run:

```bash
pytest tests/b1/test_storage_config.py -v
```

Expected: FAIL because app state lacks storage service.

**Step 3: Write minimal implementation**

Create a small storage service with:

- provider metadata
- object key builder
- configuration validation
- explicit `is_configured` and `describe()` helpers

**Step 4: Run test to verify pass**

Run:

```bash
pytest tests/b1/test_storage_config.py -v
```

Expected: PASS

### Task 5: Update env and operator docs

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `runbook.md`

**Step 1: Write failing documentation expectation**

Use a simple test only if an existing docs validation hook exists. Otherwise skip code tests and do a manual doc review.

**Step 2: Update env vars**

Document:

- Neon app URL
- Neon direct URL
- B2 bucket config

**Step 3: Update setup docs**

Explain:

- local dev fallback
- which secrets belong only on backend
- where generated artifacts live

**Step 4: Manual review**

Read the edited sections for consistency with the design note.

### Task 6: Verify targeted backend checks

**Files:**
- No new files

**Step 1: Run targeted tests**

```bash
pytest tests/b1/test_b1_scaffold.py tests/b1/test_storage_config.py -v
```

Expected: PASS

**Step 2: Run broader backend checks if clean**

```bash
pytest tests/b1/test_b1_scaffold.py tests/b2b3/test_b2b3_scaffold.py tests/b5/test_b5_scaffold.py tests/controller/test_controller_policy.py tests/controller/test_controller_runtime.py tests/controller/test_controller_scaffold.py contracts/tests -v
```

Expected: PASS, or a bounded report of pre-existing unrelated failures.

**Step 3: Summarize gaps**

Call out any deferred items:

- real upload implementation
- signed URL generation
- background worker plumbing
