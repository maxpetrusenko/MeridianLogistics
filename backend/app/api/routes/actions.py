from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from backend.app.api.identity import TrustedIdentity, identity_from_request_state
from backend.app.api.schemas.chat import (
    ActiveResourceEnvelope,
    ChatResponseEnvelope,
)
from backend.app.gateway.write_gateway import WriteGatewayRequest, execute_write_gateway
from backend.app.responses.builder import build_response_envelope
from backend.app.session.models import ActiveResourceBinding, SessionState


router = APIRouter(tags=["actions"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _response_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _validated_trusted_identity(request: Request, identity: TrustedIdentity) -> TrustedIdentity:
    if identity.role != "broker":
        raise HTTPException(status_code=403, detail="unsupported actor role")
    brokers = request.app.state.read_repository.brokers_for_office(identity.office_id, role=identity.role)
    if not any(str(broker["broker_id"]) == identity.broker_id for broker in brokers):
        raise HTTPException(status_code=403, detail="unknown auth context")
    return identity


def _trusted_action_identity(request: Request) -> TrustedIdentity:
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


def _allow_seeded_dev_identity(app_env: str) -> bool:
    return app_env.strip().lower() in {"development", "dev", "local", "test", "testing"}


def _base_payload(
    *,
    session: SessionState,
    intent_class: str,
    status: str,
    summary: str,
    components: list[dict[str, object]],
    tool_path: list[str],
    denial_reason_class: str = "none",
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
        "job_id": None,
        "job_poll_token": None,
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


@router.post("/actions/confirm", response_model=ChatResponseEnvelope)
def post_confirm_action(request_payload: dict, request: Request) -> ChatResponseEnvelope:
    session_store = request.app.state.session_store
    identity = _trusted_action_identity(request)

    action_name = request_payload.get("action_name")
    confirmation_token = request_payload.get("confirmation_token")
    idempotency_key = request_payload.get("idempotency_key")
    session_id = request_payload.get("session_id")
    session_access_token = request_payload.get("session_access_token")

    if not action_name or action_name != "booking_create_confirmed":
        raise HTTPException(status_code=400, detail="unsupported action")

    if not confirmation_token:
        raise HTTPException(status_code=400, detail="confirmation_token is required")

    if not idempotency_key:
        raise HTTPException(status_code=400, detail="idempotency_key is required")

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    if not session_access_token:
        raise HTTPException(status_code=400, detail="session_access_token is required")

    session = session_store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")

    if session.session_access_token != session_access_token:
        raise HTTPException(status_code=404, detail="unknown session")

    if session.broker_id != identity.broker_id or session.office_id != identity.office_id:
        raise HTTPException(status_code=403, detail="session identity mismatch")

    permission_context: dict = {
        "claims": {
            "role": identity.role,
            "office_id": identity.office_id,
            "broker_id": identity.broker_id,
        },
        "repository": request.app.state.read_repository,
        "idempotency_store": request.app.state.idempotency_store,
    }

    write_request = WriteGatewayRequest(
        action_name=action_name,
        confirmation_token=confirmation_token,
        idempotency_key=idempotency_key,
        actor_broker_id=identity.broker_id,
        office_id=identity.office_id,
    )

    try:
        result = execute_write_gateway(write_request, permission_context)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result_status = result.get("status", "denied")
    denial_reason_class = result.get("denial_reason_class", "none")

    if result_status == "denied":
        intent_class = "write_denied"
        status = "denied"
        summary = "Booking confirmation denied: " + denial_reason_class.replace("_", " ")
        components = [
            {
                "component_id": f"msg-action-denied-{action_name}",
                "component_type": "message_block",
                "title": "Action denied",
                "body": summary,
                "tone": "critical",
            }
        ]
    else:
        intent_class = "write_submitted"
        status = "submitted"
        quote_id = result.get("quote_id", "unknown")
        summary = f"Booking submitted for quote {quote_id}"
        components = [
            {
                "component_id": "msg-booking-submitted",
                "component_type": "message_block",
                "title": "Booking submitted",
                "body": f"Submitted {action_name} for quote {quote_id} with confirmation token {confirmation_token[:8]}...",
                "tone": "informational",
            }
        ]

    payload = _base_payload(
        session=session,
        intent_class=intent_class,
        status=status,
        summary=summary,
        components=components,
        tool_path=[action_name],
        denial_reason_class=denial_reason_class,
    )

    built_payload = build_response_envelope(payload)
    return ChatResponseEnvelope.model_validate(built_payload)
