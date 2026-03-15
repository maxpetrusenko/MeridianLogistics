from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from backend.app.api.identity import TrustedIdentity, identity_from_request_state
from backend.app.api.schemas.chat import (
    ChatRequest,
    ChatResponseEnvelope,
)
from backend.app.orchestrator.graph import execute_read_path
from backend.app.responses.builder import build_response_envelope
from backend.app.session.models import ActiveResourceBinding, SessionState
from backend.app.autonomy.models import AutonomyJobMetadata


router = APIRouter(tags=["chat"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _response_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _scope_for_resource(resource: ActiveResourceBinding | None, prompt: str) -> str:
    if resource is not None:
        return resource.resource_type
    prompt_text = prompt.lower()
    if any(token in prompt_text for token in ("analytics", "ranking", "metric", "refresh", "background", "async")):
        return "analytics"
    return "office"


def _normalize_resource(payload: ChatRequest) -> ActiveResourceBinding | None:
    resource = payload.current_resource
    if resource is None:
        return None
    fingerprint = resource.resource_fingerprint or f"{resource.resource_type}:{resource.resource_id}:v1"
    return ActiveResourceBinding(
        resource_type=resource.resource_type,
        resource_id=resource.resource_id,
        resource_fingerprint=fingerprint,
    )


def _is_async_refresh_request(prompt: str) -> bool:
    prompt_text = prompt.lower()
    return (
        "background" in prompt_text
        and "refresh" in prompt_text
        and "analytics" in prompt_text
        and any(token in prompt_text for token in ("exception", "exceptions"))
    )


def _allow_seeded_dev_identity(app_env: str) -> bool:
    return app_env.strip().lower() in {"development", "dev", "local", "test", "testing"}


def _validated_trusted_identity(request: Request, identity: TrustedIdentity) -> TrustedIdentity:
    if identity.role != "broker":
        raise HTTPException(status_code=403, detail="unsupported actor role")
    brokers = request.app.state.read_repository.brokers_for_office(identity.office_id, role=identity.role)
    if not any(str(broker["broker_id"]) == identity.broker_id for broker in brokers):
        raise HTTPException(status_code=403, detail="unknown auth context")
    return identity


def _trusted_chat_identity(request: Request) -> TrustedIdentity:
    header_broker_id = request.headers.get("x-meridian-broker-id")
    header_office_id = request.headers.get("x-meridian-office-id")
    header_role = request.headers.get("x-meridian-role")
    trusted_identity = identity_from_request_state(request)
    if trusted_identity is not None:
        return _validated_trusted_identity(request, trusted_identity)
    if any(value is not None for value in (header_broker_id, header_office_id, header_role)):
        raise HTTPException(status_code=403, detail="untrusted auth context")
    if not _allow_seeded_dev_identity(request.app.state.config.app_env):
        raise HTTPException(status_code=503, detail="server auth context unavailable")

    default_office_id = request.app.state.config.memphis_office_id
    brokers = request.app.state.read_repository.brokers_for_office(default_office_id, role="broker")
    if len(brokers) != 1:
        raise HTTPException(status_code=503, detail="server auth context unavailable")
    broker = brokers[0]
    return _validated_trusted_identity(
        request,
        TrustedIdentity(
            broker_id=str(broker["broker_id"]),
            office_id=str(broker["office_id"]),
            role=str(broker["role"]),
        ),
    )


def _session_state_for_request(
    request_payload: ChatRequest,
    request: Request,
    identity: TrustedIdentity,
) -> tuple[SessionState, bool]:
    store = request.app.state.session_store
    incoming_resource = _normalize_resource(request_payload)
    existing = None
    if request_payload.session_id is not None:
        existing = store.get_session(request_payload.session_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="unknown session")
        if request_payload.session_access_token != existing.session_access_token:
            raise HTTPException(status_code=404, detail="unknown session")
        if (
            existing.broker_id != identity.broker_id
            or existing.office_id != identity.office_id
            or existing.role != identity.role
        ):
            raise HTTPException(status_code=404, detail="unknown session")

    context_binding_state = "missing"
    active_resource = incoming_resource
    if existing is not None and incoming_resource is None:
        active_resource = existing.active_resource
        context_binding_state = "bound" if active_resource is not None else "missing"
    elif incoming_resource is not None:
        if existing is None or existing.active_resource is None:
            context_binding_state = "bound"
        elif existing.active_resource == incoming_resource:
            context_binding_state = "bound"
        else:
            context_binding_state = "stale"

    session = SessionState(
        session_id=(
            existing.session_id
            if existing
            else request_payload.session_id or request.app.state.session_store.next_session_id()
        ),
        broker_id=existing.broker_id if existing else identity.broker_id,
        office_id=existing.office_id if existing else identity.office_id,
        role=existing.role if existing else identity.role,
        session_access_token=(
            existing.session_access_token
            if existing
            else request.app.state.session_store.next_session_access_token()
        ),
        current_module=request_payload.current_module,
        conversation_scope=_scope_for_resource(active_resource, request_payload.prompt),
        context_binding_state=context_binding_state,
        screen_sync_state="not_applicable",
        active_resource=active_resource,
        last_response_id=existing.last_response_id if existing else None,
        last_job_id=existing.last_job_id if existing else None,
    )
    return session, context_binding_state == "stale"


def _base_payload(
    *,
    session: SessionState,
    intent_class: str,
    status: str,
    summary: str,
    components: list[dict[str, object]],
    tool_path: list[str],
    denial_reason_class: str = "none",
    job_id: str | None = None,
    job_poll_token: str | None = None,
) -> dict[str, object]:
    return {
        "contract_version": "0.1.0",
        "response_id": _response_id("resp"),
        "request_id": _response_id("req"),
        "trace_id": _response_id("trace"),
        "session_id": session.session_id,
        "session_access_token": session.session_access_token,
        "conversation_scope": session.conversation_scope,
        "context_binding_state": session.context_binding_state,
        "screen_sync_state": session.screen_sync_state,
        "active_resource": session.active_resource.to_dict() if session.active_resource else None,
        "job_id": job_id,
        "job_poll_token": job_poll_token,
        "intent_class": intent_class,
        "status": status,
        "summary": summary,
        "follow_up_prompt": None,
        "components": components,
        "actions": [],
        "policy": {
            "permission_context_applied": True,
            "sensitive_fields_redacted": True,
            "write_confirmation_required": False,
            "denial_reason_class": denial_reason_class,
        },
        "audit": {
            "actor_role": session.role,
            "office_scope": session.office_id,
            "tool_path": tool_path,
            "response_generated_at": _now_iso(),
        },
    }


def _read_result_for_request(
    request_payload: ChatRequest,
    session: SessionState,
    *,
    stale_binding: bool,
    identity: TrustedIdentity,
) -> dict[str, object]:
    if stale_binding:
        return {
            "tool_name": "shipment_exception_lookup",
            "summary": "Shipment context changed. Refresh before taking further action.",
            "components": [
                {
                    "component_id": "msg-chat-read",
                    "component_type": "message_block",
                    "body": "Shipment context changed. Refresh before taking further action.",
                    "tone": "warning",
                }
            ],
            "denial_reason_class": "stale_state",
        }
    return execute_read_path(
        prompt=request_payload.prompt,
        broker_id=identity.broker_id,
        office_id=identity.office_id,
        role=identity.role,
        active_resource=session.active_resource.to_dict() if session.active_resource else None,
    )


def _build_read_result_payload(
    request_payload: ChatRequest,
    session: SessionState,
    *,
    stale_binding: bool,
    identity: TrustedIdentity,
    job_id: str | None = None,
) -> dict[str, object]:
    read_result = _read_result_for_request(
        request_payload,
        session,
        stale_binding=stale_binding,
        identity=identity,
    )
    return _base_payload(
        session=session,
        intent_class="read_result",
        status="success",
        summary=str(read_result["summary"]),
        components=list(read_result["components"]),
        tool_path=[str(read_result["tool_name"])],
        denial_reason_class=str(read_result.get("denial_reason_class", "none")),
        job_id=job_id,
    )


@router.post("/chat", response_model=ChatResponseEnvelope)
def post_chat(request_payload: ChatRequest, request: Request) -> ChatResponseEnvelope:
    session_store = request.app.state.session_store
    job_store = request.app.state.job_store
    autonomy_service = request.app.state.autonomy_service
    identity = _trusted_chat_identity(request)
    session, stale_binding = _session_state_for_request(request_payload, request, identity)

    if _is_async_refresh_request(request_payload.prompt):
        pending_session = session_store.save_session(session)
        is_async_eligible = True
        job = job_store.create_job(
            session_id=pending_session.session_id,
            broker_id=pending_session.broker_id,
            office_id=pending_session.office_id,
            progress_message="Background refresh queued for Memphis exceptions.",
            retry_allowed=True,
        )

        # Seed autonomy if enabled and eligible
        autonomy_seeded = False
        if autonomy_service.is_eligible_for_autonomy(
            prompt=request_payload.prompt,
            is_async_refresh=is_async_eligible,
        ):
            seed_result = autonomy_service.seed_autonomy_run(
                job_id=job.job_id,
                session_id=pending_session.session_id,
                prompt=request_payload.prompt,
                broker_id=pending_session.broker_id,
                office_id=pending_session.office_id,
            )
            if seed_result is not None:
                metadata, _checkpoint = seed_result
                job_store.update_autonomy_metadata(job.job_id, metadata.to_dict())
                autonomy_seeded = True

        job_store.prepare_result(
            job.job_id,
            build_response_envelope(
                _build_read_result_payload(
                    request_payload,
                    pending_session,
                    stale_binding=stale_binding,
                    identity=identity,
                    job_id=job.job_id,
                )
            ),
        )
        pending_session = replace(pending_session, last_job_id=job.job_id)
        session_store.save_session(pending_session)
        payload = _base_payload(
            session=pending_session,
            intent_class="read_pending",
            status="pending",
            summary="Background refresh started for the Memphis exception view.",
            components=[
                {
                    "component_id": "msg-job-pending",
                    "component_type": "message_block",
                    "body": "Background refresh started for the Memphis exception view.",
                    "tone": "informational",
                }
            ],
            tool_path=[],
            job_id=job.job_id,
            job_poll_token=job.job_poll_token,
        )
    else:
        saved_session = session_store.save_session(session)
        payload = _build_read_result_payload(
            request_payload,
            saved_session,
            stale_binding=stale_binding,
            identity=identity,
        )

    built_payload = build_response_envelope(payload)
    if built_payload.get("job_id"):
        job_store.bind_pending_response(
            str(built_payload["job_id"]),
            str(built_payload["response_id"]),
        )
        job_store.start_job(
            str(built_payload["job_id"]),
            progress_message="Background refresh running for Memphis exceptions.",
        )
    finalized_session = replace(
        session_store.get_session(session.session_id) or session,
        last_response_id=str(built_payload["response_id"]),
        last_job_id=(
            str(built_payload.get("job_id"))
            if built_payload.get("job_id")
            else (session_store.get_session(session.session_id) or session).last_job_id
        ),
    )
    session_store.save_session(finalized_session)
    return ChatResponseEnvelope.model_validate(built_payload)
