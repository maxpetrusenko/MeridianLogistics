from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class TrustedIdentity:
    broker_id: str
    office_id: str
    role: str


def identity_from_request_state(request: Request) -> TrustedIdentity | None:
    trusted_identity = getattr(request.state, "trusted_chat_identity", None)
    if trusted_identity is None:
        return None
    if isinstance(trusted_identity, TrustedIdentity):
        return trusted_identity
    if isinstance(trusted_identity, dict):
        broker_id = trusted_identity.get("broker_id")
        office_id = trusted_identity.get("office_id")
        role = trusted_identity.get("role")
        if broker_id and office_id and role:
            return TrustedIdentity(
                broker_id=str(broker_id),
                office_id=str(office_id),
                role=str(role),
            )
    raise HTTPException(status_code=503, detail="server auth context unavailable")
