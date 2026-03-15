from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ResourceType = Literal["shipment", "carrier", "lane", "analytics", "session"]
ConversationScope = Literal["global", "office", "shipment", "lane", "carrier", "analytics"]
ContextBindingState = Literal["bound", "partial", "stale", "missing"]
ScreenSyncState = Literal["not_applicable", "pending", "applied", "blocked"]
JobStatus = Literal["queued", "pending", "running", "succeeded", "failed", "cancelled", "expired"]


class ActiveResourcePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_type: ResourceType
    resource_id: str = Field(min_length=1)
    resource_fingerprint: str | None = Field(default=None, min_length=1)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    session_id: str | None = Field(default=None, pattern=r"^chat_s_[A-Za-z0-9_]+$")
    session_access_token: str | None = Field(default=None, min_length=1)
    broker_id: str | None = Field(default=None, min_length=1)
    office_id: str | None = Field(default=None, min_length=1)
    role: Literal["broker"] | None = None
    current_module: str = Field(min_length=1)
    current_resource: ActiveResourcePayload | None = None


class ActiveResourceEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_type: ResourceType
    resource_id: str
    resource_fingerprint: str


class ChatResponseEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str
    response_id: str
    request_id: str
    trace_id: str | None = None
    session_id: str
    session_access_token: str | None = None
    conversation_scope: ConversationScope
    context_binding_state: ContextBindingState
    screen_sync_state: ScreenSyncState
    active_resource: ActiveResourceEnvelope | None = None
    job_id: str | None = None
    job_poll_token: str | None = None
    intent_class: str
    status: str
    summary: str
    follow_up_prompt: str | None = None
    components: list[dict[str, Any]]
    actions: list[dict[str, Any]] = Field(default_factory=list)
    policy: dict[str, Any]
    audit: dict[str, Any]


class ChatSessionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    broker_id: str
    office_id: str
    role: Literal["broker"]
    current_module: str
    conversation_scope: ConversationScope
    context_binding_state: ContextBindingState
    screen_sync_state: ScreenSyncState
    active_resource: ActiveResourceEnvelope | None = None
    last_response_id: str | None = None
    last_job_id: str | None = None


class AsyncJobEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    session_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    progress_message: str
    retry_allowed: bool
    job_poll_token: str
    completed_response_id: str | None = None
    result: ChatResponseEnvelope | None = None
    error_message: str | None = None
    failed_at: str | None = None


class AsyncJobListEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    session_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    progress_message: str
    retry_allowed: bool
    completed_response_id: str | None = None
    result: ChatResponseEnvelope | None = None
    error_message: str | None = None
    failed_at: str | None = None
