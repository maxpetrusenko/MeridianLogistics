from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


ResourceType = Literal["shipment", "carrier", "lane", "analytics", "session"]
ConversationScope = Literal["global", "office", "shipment", "lane", "carrier", "analytics"]
ContextBindingState = Literal["bound", "partial", "stale", "missing"]
ScreenSyncState = Literal["not_applicable", "pending", "applied", "blocked"]


@dataclass(frozen=True)
class ActiveResourceBinding:
    resource_type: ResourceType
    resource_id: str
    resource_fingerprint: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class SessionState:
    session_id: str
    session_access_token: str
    broker_id: str
    office_id: str
    role: str
    current_module: str
    conversation_scope: ConversationScope
    context_binding_state: ContextBindingState
    screen_sync_state: ScreenSyncState
    active_resource: ActiveResourceBinding | None
    last_response_id: str | None = None
    last_job_id: str | None = None

    def to_summary(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "broker_id": self.broker_id,
            "office_id": self.office_id,
            "role": self.role,
            "current_module": self.current_module,
            "conversation_scope": self.conversation_scope,
            "context_binding_state": self.context_binding_state,
            "screen_sync_state": self.screen_sync_state,
            "active_resource": self.active_resource.to_dict() if self.active_resource else None,
            "last_response_id": self.last_response_id,
            "last_job_id": self.last_job_id,
        }
