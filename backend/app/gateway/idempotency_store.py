from __future__ import annotations

from collections.abc import MutableMapping
from copy import deepcopy
from dataclasses import dataclass
from threading import Condition, Lock


IdempotencyMapping = MutableMapping[str, dict[str, object]]

_DEFAULT_STORE: dict[str, dict[str, object]] = {}
_STORE_SYNC_LOCK = Lock()
_STORE_SYNC: dict[int, Condition] = {}
_TARGET_CLAIMS: dict[int, dict[str, str]] = {}


@dataclass(frozen=True)
class IdempotencyClaim:
    outcome: str
    record: dict[str, object] | None = None


def _store_condition(store: IdempotencyMapping) -> Condition:
    store_id = id(store)
    with _STORE_SYNC_LOCK:
        condition = _STORE_SYNC.get(store_id)
        if condition is None:
            condition = Condition()
            _STORE_SYNC[store_id] = condition
        return condition


def _target_claims(store: IdempotencyMapping) -> dict[str, str]:
    store_id = id(store)
    with _STORE_SYNC_LOCK:
        claims = _TARGET_CLAIMS.get(store_id)
        if claims is None:
            claims = {}
            _TARGET_CLAIMS[store_id] = claims
        return claims


def resolve_store(raw_store: IdempotencyMapping | None = None) -> IdempotencyMapping:
    return raw_store if raw_store is not None else _DEFAULT_STORE


def load_record(store: IdempotencyMapping, idempotency_key: str) -> dict[str, object] | None:
    condition = _store_condition(store)
    with condition:
        record = store.get(idempotency_key)
        if record is None or record.get("state") != "completed":
            return None
        return deepcopy(record)


def save_record(
    store: IdempotencyMapping,
    *,
    idempotency_key: str,
    request_fingerprint: str,
    result: dict[str, object],
) -> dict[str, object]:
    return complete_record(
        store,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        result=result,
    )


def claim_record(
    store: IdempotencyMapping,
    *,
    idempotency_key: str,
    request_fingerprint: str,
) -> IdempotencyClaim:
    condition = _store_condition(store)
    with condition:
        while True:
            record = store.get(idempotency_key)
            if record is None:
                store[idempotency_key] = {
                    "state": "in_progress",
                    "request_fingerprint": request_fingerprint,
                }
                return IdempotencyClaim(outcome="execute")
            if record.get("state") == "completed":
                if record["request_fingerprint"] == request_fingerprint:
                    return IdempotencyClaim(outcome="replay", record=deepcopy(record))
                return IdempotencyClaim(outcome="conflict", record=deepcopy(record))
            condition.wait()


def complete_record(
    store: IdempotencyMapping,
    *,
    idempotency_key: str,
    request_fingerprint: str,
    result: dict[str, object],
) -> dict[str, object]:
    condition = _store_condition(store)
    completed_record = {
        "state": "completed",
        "request_fingerprint": request_fingerprint,
        "result": deepcopy(result),
    }
    with condition:
        existing = store.get(idempotency_key)
        if existing is not None and (
            existing.get("state") != "in_progress"
            or existing.get("request_fingerprint") != request_fingerprint
        ):
            raise ValueError("idempotency claim does not match completion request")
        store[idempotency_key] = completed_record
        condition.notify_all()
    return deepcopy(completed_record)


def abandon_record(
    store: IdempotencyMapping,
    *,
    idempotency_key: str,
    request_fingerprint: str,
) -> None:
    condition = _store_condition(store)
    with condition:
        existing = store.get(idempotency_key)
        if existing is not None and (
            existing.get("state") == "in_progress"
            and existing.get("request_fingerprint") == request_fingerprint
        ):
            store.pop(idempotency_key, None)
            condition.notify_all()


def claim_target_execution(
    store: IdempotencyMapping,
    *,
    confirmation_token: str,
    idempotency_key: str,
) -> None:
    condition = _store_condition(store)
    with condition:
        claims = _target_claims(store)
        while True:
            claimed_by = claims.get(confirmation_token)
            if claimed_by is None:
                claims[confirmation_token] = idempotency_key
                return
            if claimed_by == idempotency_key:
                return
            condition.wait()


def release_target_execution(
    store: IdempotencyMapping,
    *,
    confirmation_token: str,
    idempotency_key: str,
) -> None:
    condition = _store_condition(store)
    with condition:
        claims = _target_claims(store)
        if claims.get(confirmation_token) == idempotency_key:
            claims.pop(confirmation_token, None)
            condition.notify_all()
