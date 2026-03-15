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

    def __init__(self, config: AppConfig):
        self.config = config
        self.controller = ControllerRuntime(config)

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

        # Check step budget
        if current_metadata.step_index >= current_metadata.step_budget:
            return StepOutcome(
                step_kind=StepKind.FAIL_JOB,
                next_step_kind=None,
                is_terminal=True,
                error_message="Step budget exhausted",
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
        # We just signal completion on the first autonomy step
        step_index = current_metadata.step_index

        if step_index == 0:
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

        Updates checkpoint if needed for resume truth.
        """
        outcome = self.resume_one_step(
            job_id=job_id,
            session_id="",  # Not used in phase 1
            current_metadata=current_metadata,
        )

        # Update metadata for next step
        new_metadata = AutonomyJobMetadata(
            mode=current_metadata.mode,
            task_kind=current_metadata.task_kind,
            checkpoint_id=current_metadata.checkpoint_id,
            step_index=current_metadata.step_index + 1,
            step_budget=current_metadata.step_budget,
            last_controller_action=outcome.step_kind.value,
        )

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
