---
name: enum-state-alignment
description: Workflow command scaffold for enum-state-alignment in MeridianLogistics.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /enum-state-alignment

Use this workflow when working on **enum-state-alignment** in `MeridianLogistics`.

## Goal

Align enumeration states across models, policies, and documentation

## Common Files

- `backend/app/controller/models.py`
- `backend/app/controller/policy.py`
- `docs/plans/*.md`
- `tests/controller/*.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Update enum in models.py
- Update enum in policy.py
- Update documentation references
- Update test files to reflect new naming

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.