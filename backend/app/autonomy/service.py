"""Bounded autonomy service adapter for running app.

Translates product runtime work into controller-safe steps.
Uses existing controller runtime APIs. Does not import repo-only semantics.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.app.autonomy.models import (
    ALLOWED_STEP_KINDS,
    AutonomyJobMetadata,
    AutonomyMode,
    StepKind,
    StepOutcome,
    TaskKind,
)
from backend.app.config import AppConfig
from backend.app.controller.models import (
    CompactionState,
    ControllerCheckpoint,
    ControllerDecision,
    FailureSignal,
    ProtectedCore,
    QueueState,
)
from backend.app.controller.runtime import ControllerRuntime


logger = logging.getLogger(__name__)


class BoundedAutonomyService:
    """Adapter for bounded autonomy in the running FastAPI app.

    Responsibilities:
    - Decide if chat request is autonomy-eligible
    - Seed checkpoint + job metadata for new job_id
    - Resume one bounded step for transient autonomy job
    - Materialize success or fail-soft job results

    Phase 1 scope:
    - Internal only, read-only, job-backed, poll-driven
    - Hard-bounded by step count and wall-clock
    - Checkpoint-authoritative (job metadata is derivative cache)
    """

    # Phase 1: simple mapping from resume_point to step_index
    # Future: track step_index in checkpoint compaction state
    _RESUME_POINT_TO_STEP: dict[str, int] = {
        "seed": 0,
        "complete": 1,
        "done": 1,
        "blocked": 1,
        "failed": 1,
    }

    def __init__(self, config: AppConfig):
        self.config = config
        self.controller = ControllerRuntime(config)

    def _step_index_from_checkpoint(self, checkpoint: ControllerCheckpoint) -> int:
        """Derive step_index from checkpoint state (checkpoint-authoritative)."""
        resume_point = checkpoint.protected_core.resume_point
        return self._RESUME_POINT_TO_STEP.get(resume_point, 0)

    def is_enabled(self) -> bool:
        """Check if running-app autonomy is enabled."""
        return (
            self.config.running_autonomy_enabled
            and self.config.controller_checkpoints_enabled
            and self.config.controller_precedence_enabled
        )

    def is_eligible_for_autonomy(
        self,
        *,
        prompt: str,
        is_async_refresh: bool,
    ) -> bool:
        """Decide if chat request is autonomy-eligible.

        Phase 1: only long-running read work already eligible for async jobs.
        """
        if not self.is_enabled():
            return False

        if not is_async_refresh:
            return False

        # Must be read-only work (no writes, no confirmation needed)
        prompt_lower = prompt.lower()
        if any(token in prompt_lower for token in ("book", "confirm", "approve", "reject")):
            return False

        return True

    def seed_autonomy_run(
        self,
        *,
        job_id: str,
        session_id: str,
        prompt: str,
        broker_id: str,
        office_id: str,
    ) -> tuple[AutonomyJobMetadata, ControllerCheckpoint] | None:
        """Seed a new autonomy run for an async job.

        Creates controller checkpoint keyed by job_id and returns
        metadata to persist with the job row.

        Returns None if autonomy is not enabled or not eligible.
        """
        if not self.is_enabled():
            return None

        checkpoint_id = f"{job_id}:seed"

        # Build initial protected core for the task
        protected_core = ProtectedCore(
            task_goal=f"Execute background analytics refresh for exceptions",
            expected_output="Updated exception report with current data",
            current_step="seed_context",
            resume_point="seed",
            hard_constraints=("read_only", "bounded_autonomy"),
            business_invariants=("no_writes", "confirmation_required_for_changes"),
        )

        # Build initial queue state for bounded execution
        queue_state = QueueState(
            wave_name="async_read_refresh",
            status="active",
            run_policy="bounded",
            eligible=True,
            requires_explicit_request=False,
            approval_authority="system",
        )

        # Create failure signal (default)
        failure_signal = FailureSignal(
            kind="none",
            severity="none",
            source="controller",
            details=None,
        )

        # Create initial checkpoint
        checkpoint = ControllerCheckpoint(
            checkpoint_id=checkpoint_id,
            protected_core=protected_core,
            compaction=CompactionState(
                strategy_name="none",
                compaction_sequence=0,
                halo_summary="",
                recent_turn_ids=(),
            ),
            validated_artifacts=(),
            active_failure_signal=failure_signal,
            controller_last_decision=ControllerDecision(
                action="continue",
                reason="seed_autonomy_run",
                source="controller",
            ),
            queue=queue_state,
            terminal_state=None,
        )

        # Persist checkpoint using job_id as key
        self._write_checkpoint(job_id, checkpoint)

        # Create derivative job metadata
        metadata = AutonomyJobMetadata(
            mode=AutonomyMode.POLL_DRIVEN,
            task_kind=TaskKind.ASYNC_READ_REFRESH,
            checkpoint_id=checkpoint_id,
            step_index=0,
            step_budget=self.config.running_autonomy_max_steps,
            last_controller_action="seed",
        )

        logger.info(
            "autonomy_seed %s",
            json.dumps({
                "job_id": job_id,
                "session_id": session_id,
                "step_budget": metadata.step_budget,
            }),
        )

        return metadata, checkpoint

    def resume_one_step(
        self,
        *,
        job_id: str,
        session_id: str,
        current_metadata: AutonomyJobMetadata,
    ) -> StepOutcome:
        """Resume and advance exactly one bounded step.

        Returns:
            StepOutcome with next_step_kind, is_terminal flag, and optional result

        Phase 1 allowed steps:
        - seed_context (initial)
        - execute_allowlisted_read (work)
        - build_response (finalize)
        - complete_job (terminal)
        - fail_job (fail-soft terminal)
        """
        if not self.is_enabled():
            return StepOutcome(
                step_kind=StepKind.FAIL_JOB,
                next_step_kind=None,
                is_terminal=True,
                error_message="Autonomy not enabled",
            )

        # Load checkpoint truth using job_id (not session_id)
        checkpoint = self.load_checkpoint(job_id)

        if checkpoint is None:
            return StepOutcome(
                step_kind=StepKind.FAIL_JOB,
                next_step_kind=None,
                is_terminal=True,
                error_message="Checkpoint missing",
            )

        # Checkpoint-authoritative: derive step_index from checkpoint state
        checkpoint_step_index = self._step_index_from_checkpoint(checkpoint)

        # Check step budget using checkpoint-derived step (not metadata)
        if checkpoint_step_index >= current_metadata.step_budget:
            return StepOutcome(
                step_kind=StepKind.FAIL_JOB,
                next_step_kind=None,
                is_terminal=True,
                error_message="Step budget exhausted",
            )

        # If checkpoint is already terminal, respect it
        if checkpoint.terminal_state is not None:
            return StepOutcome(
                step_kind=StepKind.COMPLETE_JOB,
                next_step_kind=None,
                is_terminal=True,
                error_message=None,
            )

        # Phase 1: After seed, immediately complete on first poll
        # The read work was already prepared by the chat route
        # Checkpoint-authoritative: use checkpoint state, not metadata
        if checkpoint_step_index == 0:
            # First autonomy step - the work is already done, just complete
            return StepOutcome(
                step_kind=StepKind.EXECUTE_ALLOWLISTED_READ,
                next_step_kind=StepKind.COMPLETE_JOB,
                is_terminal=True,
                error_message=None,
            )

        # Any further steps should not happen if we completed
        return StepOutcome(
            step_kind=StepKind.COMPLETE_JOB,
            next_step_kind=None,
            is_terminal=True,
            error_message=None,
        )

    def advance_step(
        self,
        *,
        job_id: str,
        current_metadata: AutonomyJobMetadata,
    ) -> tuple[AutonomyJobMetadata, StepOutcome]:
        """Advance one step and return updated metadata + outcome.

        Checkpoint-authoritative: derives step_index from checkpoint state.
        Updates checkpoint when step completes.
        """
        outcome = self.resume_one_step(
            job_id=job_id,
            session_id="",  # Not used in phase 1
            current_metadata=current_metadata,
        )

        # Load checkpoint to derive next step_index
        checkpoint = self.load_checkpoint(job_id)
        checkpoint_step = self._step_index_from_checkpoint(checkpoint) if checkpoint else 0

        # Checkpoint-authoritative: metadata is derived from checkpoint state
        new_metadata = AutonomyJobMetadata(
            mode=current_metadata.mode,
            task_kind=current_metadata.task_kind,
            checkpoint_id=current_metadata.checkpoint_id,
            # Derive from checkpoint, not metadata (handles stale metadata case)
            step_index=checkpoint_step + 1,
            step_budget=current_metadata.step_budget,
            last_controller_action=outcome.step_kind.value,
        )

        # Update checkpoint to reflect new state for resume truth
        if checkpoint is not None and outcome.is_terminal and not outcome.error_message:
            # Mark checkpoint as terminal on successful completion
            from dataclasses import replace

            terminal_checkpoint = replace(
                checkpoint,
                terminal_state="DONE",
                protected_core=replace(
                    checkpoint.protected_core,
                    resume_point="complete",
                    current_step="complete_job",
                ),
            )
            self._write_checkpoint(job_id, terminal_checkpoint)

        return new_metadata, outcome

    def _write_checkpoint(self, job_id: str, checkpoint: ControllerCheckpoint) -> None:
        """Write checkpoint to disk using job_id as key."""
        self.config.controller_checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = self.config.controller_checkpoint_dir / f"{job_id}.json"
        checkpoint_path.write_text(json.dumps(checkpoint.to_dict(), indent=2))

    def load_checkpoint(self, job_id: str) -> ControllerCheckpoint | None:
        """Load checkpoint by job_id."""
        path = self.config.controller_checkpoint_dir / f"{job_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return ControllerCheckpoint.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
