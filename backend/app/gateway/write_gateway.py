from __future__ import annotations

from dataclasses import dataclass

from backend.app.gateway.booking_actions import execute_confirmed_booking


@dataclass(frozen=True)
class WriteGatewayRequest:
    action_name: str
    confirmation_token: str
    idempotency_key: str
    actor_broker_id: str
    office_id: str


def execute_write_gateway(request: WriteGatewayRequest, permission_context: dict) -> dict[str, object]:
    claims = permission_context.get("claims", {})
    if request.action_name != "booking_create_confirmed":
        raise ValueError("unsupported action")
    if claims.get("role") != "broker":
        raise ValueError("broker role required")
    if claims.get("office_id") != request.office_id:
        raise ValueError("permission context office does not match request")
    if claims.get("broker_id") != request.actor_broker_id:
        raise ValueError("permission context broker does not match request")
    if not request.confirmation_token:
        raise ValueError("confirmation token is required")
    if not request.idempotency_key:
        raise ValueError("idempotency key is required")

    return execute_confirmed_booking(
        action_name=request.action_name,
        confirmation_token=request.confirmation_token,
        idempotency_key=request.idempotency_key,
        actor_broker_id=request.actor_broker_id,
        office_id=request.office_id,
        permission_context=permission_context,
    )
