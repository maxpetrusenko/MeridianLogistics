from __future__ import annotations

from datetime import UTC, datetime
from sqlite3 import Connection, Row

from backend.app.db.read_repository import ReadRepository
from backend.app.gateway.idempotency_store import (
    abandon_record,
    claim_record,
    claim_target_execution,
    complete_record,
    release_target_execution,
    resolve_store,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_timestamp(raw_value: str) -> datetime:
    return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))


def _request_fingerprint(
    *,
    action_name: str,
    confirmation_token: str,
    actor_broker_id: str,
    office_id: str,
) -> str:
    return "|".join(
        [
            action_name,
            confirmation_token,
            actor_broker_id,
            office_id,
        ]
    )


def _result_audit(
    *,
    idempotency_key: str,
    outcome: str,
    actor_broker_id: str,
    office_id: str,
    outcome_recorded_at: str | None = None,
) -> dict[str, object]:
    return {
        "tool_path": ["booking_create_confirmed"],
        "idempotency_key": idempotency_key,
        "outcome": outcome,
        "actor_broker_id": actor_broker_id,
        "office_id": office_id,
        "outcome_recorded_at": outcome_recorded_at or _now().isoformat().replace("+00:00", "Z"),
    }


def _submitted_result(
    *,
    action_name: str,
    confirmation_token: str,
    idempotency_key: str,
    office_id: str,
    actor_broker_id: str,
    quote_id: str,
    carrier_id: str,
    pickup_date: str,
) -> dict[str, object]:
    return {
        "action_name": action_name,
        "status": "submitted",
        "confirmation_token": confirmation_token,
        "quote_id": quote_id,
        "carrier_id": carrier_id,
        "pickup_date": pickup_date,
        "office_id": office_id,
        "actor_broker_id": actor_broker_id,
        "idempotency_key": idempotency_key,
        "audit": _result_audit(
            idempotency_key=idempotency_key,
            outcome="submitted",
            actor_broker_id=actor_broker_id,
            office_id=office_id,
        ),
    }


def _denied_result(
    *,
    action_name: str,
    confirmation_token: str,
    idempotency_key: str,
    office_id: str,
    actor_broker_id: str,
    denial_reason_class: str,
    outcome_recorded_at: str | None = None,
    quote_id: str | None = None,
    carrier_id: str | None = None,
    pickup_date: str | None = None,
) -> dict[str, object]:
    return {
        "action_name": action_name,
        "status": "denied",
        "confirmation_token": confirmation_token,
        "quote_id": quote_id,
        "carrier_id": carrier_id,
        "pickup_date": pickup_date,
        "office_id": office_id,
        "actor_broker_id": actor_broker_id,
        "idempotency_key": idempotency_key,
        "denial_reason_class": denial_reason_class,
        "audit": _result_audit(
            idempotency_key=idempotency_key,
            outcome=denial_reason_class,
            actor_broker_id=actor_broker_id,
            office_id=office_id,
            outcome_recorded_at=outcome_recorded_at,
        ),
    }


def _confirmation_row(connection: Connection, confirmation_token: str) -> Row | None:
    return connection.execute(
        """
        SELECT confirmation_token, quote_id, office_id, broker_id, carrier_id, pickup_date,
               confirmation_status, expires_at
        FROM booking_confirmations
        WHERE confirmation_token = ?
        """,
        (confirmation_token,),
    ).fetchone()


def _quote_row(connection: Connection, quote_id: str) -> Row | None:
    return connection.execute(
        """
        SELECT quote_id, office_id, broker_id, carrier_id, pickup_date, quote_status
        FROM shipment_quotes
        WHERE quote_id = ?
        """,
        (quote_id,),
    ).fetchone()


def execute_confirmed_booking(
    *,
    action_name: str,
    confirmation_token: str,
    idempotency_key: str,
    actor_broker_id: str,
    office_id: str,
    permission_context: dict,
) -> dict[str, object]:
    repository = permission_context.get("repository") or ReadRepository()
    connection = repository.connection
    store = resolve_store(permission_context.get("idempotency_store"))
    request_fingerprint = _request_fingerprint(
        action_name=action_name,
        confirmation_token=confirmation_token,
        actor_broker_id=actor_broker_id,
        office_id=office_id,
    )

    claim = claim_record(
        store,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )
    if claim.outcome == "replay":
        return dict(claim.record["result"])
    if claim.outcome == "conflict":
        existing_result = dict(claim.record["result"])
        return _denied_result(
            action_name=action_name,
            confirmation_token=confirmation_token,
            idempotency_key=idempotency_key,
            office_id=office_id,
            actor_broker_id=actor_broker_id,
            denial_reason_class="idempotency_conflict",
            outcome_recorded_at=existing_result.get("audit", {}).get("outcome_recorded_at"),
            quote_id=existing_result.get("quote_id"),
            carrier_id=existing_result.get("carrier_id"),
            pickup_date=existing_result.get("pickup_date"),
        )

    target_claimed = False
    try:
        claim_target_execution(
            store,
            confirmation_token=confirmation_token,
            idempotency_key=idempotency_key,
        )
        target_claimed = True
        confirmation = _confirmation_row(connection, confirmation_token)
        if confirmation is None:
            result = _denied_result(
                action_name=action_name,
                confirmation_token=confirmation_token,
                idempotency_key=idempotency_key,
                office_id=office_id,
                actor_broker_id=actor_broker_id,
                denial_reason_class="unsupported_or_missing_confirmation",
            )
            complete_record(
                store,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                result=result,
            )
            return result

        quote = _quote_row(connection, confirmation["quote_id"])
        stale_result = _stale_result_if_needed(
            action_name=action_name,
            idempotency_key=idempotency_key,
            office_id=office_id,
            actor_broker_id=actor_broker_id,
            confirmation=confirmation,
            quote=quote,
        )
        if stale_result is not None:
            complete_record(
                store,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                result=stale_result,
            )
            return stale_result

        before_submit_hook = permission_context.get("before_submit_hook")
        if callable(before_submit_hook):
            before_submit_hook()

        connection.execute(
            "UPDATE shipment_quotes SET quote_status = ? WHERE quote_id = ?",
            ("booked", confirmation["quote_id"]),
        )
        connection.execute(
            "UPDATE booking_confirmations SET confirmation_status = ? WHERE confirmation_token = ?",
            ("consumed", confirmation_token),
        )
        connection.commit()

        result = _submitted_result(
            action_name=action_name,
            confirmation_token=confirmation_token,
            idempotency_key=idempotency_key,
            office_id=office_id,
            actor_broker_id=actor_broker_id,
            quote_id=str(confirmation["quote_id"]),
            carrier_id=str(confirmation["carrier_id"]),
            pickup_date=str(confirmation["pickup_date"]),
        )
        complete_record(
            store,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            result=result,
        )
        return result
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        abandon_record(
            store,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )
        raise
    finally:
        if target_claimed:
            release_target_execution(
                store,
                confirmation_token=confirmation_token,
                idempotency_key=idempotency_key,
            )


def _stale_result_if_needed(
    *,
    action_name: str,
    idempotency_key: str,
    office_id: str,
    actor_broker_id: str,
    confirmation: Row,
    quote: Row | None,
) -> dict[str, object] | None:
    if confirmation["office_id"] != office_id or confirmation["broker_id"] != actor_broker_id:
        return _denied_result(
            action_name=action_name,
            confirmation_token=str(confirmation["confirmation_token"]),
            idempotency_key=idempotency_key,
            office_id=office_id,
            actor_broker_id=actor_broker_id,
            denial_reason_class="stale_state",
            quote_id=str(confirmation["quote_id"]),
            carrier_id=str(confirmation["carrier_id"]),
            pickup_date=str(confirmation["pickup_date"]),
        )
    if confirmation["confirmation_status"] != "pending":
        return _denied_result(
            action_name=action_name,
            confirmation_token=str(confirmation["confirmation_token"]),
            idempotency_key=idempotency_key,
            office_id=office_id,
            actor_broker_id=actor_broker_id,
            denial_reason_class="stale_state",
            quote_id=str(confirmation["quote_id"]),
            carrier_id=str(confirmation["carrier_id"]),
            pickup_date=str(confirmation["pickup_date"]),
        )
    if _parse_timestamp(str(confirmation["expires_at"])) <= _now():
        return _denied_result(
            action_name=action_name,
            confirmation_token=str(confirmation["confirmation_token"]),
            idempotency_key=idempotency_key,
            office_id=office_id,
            actor_broker_id=actor_broker_id,
            denial_reason_class="stale_state",
            quote_id=str(confirmation["quote_id"]),
            carrier_id=str(confirmation["carrier_id"]),
            pickup_date=str(confirmation["pickup_date"]),
        )
    if quote is None:
        return _denied_result(
            action_name=action_name,
            confirmation_token=str(confirmation["confirmation_token"]),
            idempotency_key=idempotency_key,
            office_id=office_id,
            actor_broker_id=actor_broker_id,
            denial_reason_class="stale_state",
            quote_id=str(confirmation["quote_id"]),
            carrier_id=str(confirmation["carrier_id"]),
            pickup_date=str(confirmation["pickup_date"]),
        )
    if quote["office_id"] != office_id or quote["broker_id"] != actor_broker_id:
        return _denied_result(
            action_name=action_name,
            confirmation_token=str(confirmation["confirmation_token"]),
            idempotency_key=idempotency_key,
            office_id=office_id,
            actor_broker_id=actor_broker_id,
            denial_reason_class="stale_state",
            quote_id=str(confirmation["quote_id"]),
            carrier_id=str(confirmation["carrier_id"]),
            pickup_date=str(confirmation["pickup_date"]),
        )
    if quote["quote_status"] != "eligible_for_booking":
        return _denied_result(
            action_name=action_name,
            confirmation_token=str(confirmation["confirmation_token"]),
            idempotency_key=idempotency_key,
            office_id=office_id,
            actor_broker_id=actor_broker_id,
            denial_reason_class="stale_state",
            quote_id=str(confirmation["quote_id"]),
            carrier_id=str(confirmation["carrier_id"]),
            pickup_date=str(confirmation["pickup_date"]),
        )
    if quote["carrier_id"] != confirmation["carrier_id"] or quote["pickup_date"] != confirmation["pickup_date"]:
        return _denied_result(
            action_name=action_name,
            confirmation_token=str(confirmation["confirmation_token"]),
            idempotency_key=idempotency_key,
            office_id=office_id,
            actor_broker_id=actor_broker_id,
            denial_reason_class="stale_state",
            quote_id=str(confirmation["quote_id"]),
            carrier_id=str(confirmation["carrier_id"]),
            pickup_date=str(confirmation["pickup_date"]),
        )
    return None
