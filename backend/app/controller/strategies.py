from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.app.controller.models import ControllerCheckpoint, ProtectedCore


class Instinct8StrategyProtocol(Protocol):
    def initialize(self, original_goal: str, constraints: list[str]) -> None:
        ...

    def update_goal(self, new_goal: str, rationale: str = "") -> None:
        ...

    def compress(self, context: list[dict[str, Any]], trigger_point: int) -> str:
        ...

    def name(self) -> str:
        ...


@dataclass(frozen=True)
class CompressionEnvelope:
    strategy_name: str
    protected_core: dict[str, object]
    compressed_halo: str
    recent_turns: list[dict[str, Any]]
    trigger_point: int


class CompressionControllerAdapter:
    """
    Bridge instinct8-style strategies into Meridian's controller loop.

    Mapping:
    - protected core bootstrap -> strategy.initialize()
    - goal/constraint drift update -> strategy.update_goal()
    - controller halo compaction -> strategy.compress()
    - controller resume -> protected core + compacted halo + recent turns
    """

    def __init__(self, strategy: Instinct8StrategyProtocol):
        self.strategy = strategy

    def prime(self, protected_core: ProtectedCore) -> None:
        self.strategy.initialize(
            protected_core.task_goal,
            list(protected_core.hard_constraints),
        )

    def update_goal(self, protected_core: ProtectedCore, rationale: str) -> None:
        self.strategy.update_goal(protected_core.task_goal, rationale=rationale)

    def compact(
        self,
        checkpoint: ControllerCheckpoint,
        halo_turns: list[dict[str, Any]],
        recent_turns: list[dict[str, Any]],
        trigger_point: int,
    ) -> CompressionEnvelope:
        compressed_halo = self.strategy.compress(halo_turns, trigger_point)
        return CompressionEnvelope(
            strategy_name=self.strategy.name(),
            protected_core=checkpoint.protected_core.to_dict(),
            compressed_halo=compressed_halo,
            recent_turns=recent_turns,
            trigger_point=trigger_point,
        )
