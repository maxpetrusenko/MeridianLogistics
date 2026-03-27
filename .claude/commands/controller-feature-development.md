---
name: controller-feature-development
description: Workflow command scaffold for controller-feature-development in MeridianLogistics.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /controller-feature-development

Use this workflow when working on **controller-feature-development** in `MeridianLogistics`.

## Goal

Implement new controller features with comprehensive testing and documentation

## Common Files

- `docs/plans/*.md`
- `backend/app/controller/runtime.py`
- `backend/app/controller/models.py`
- `tests/controller/test_*.py`
- `decisions.md`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Create plan document
- Add failing tests (TDD)
- Implement runtime changes
- Update controller models
- Update documentation

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.