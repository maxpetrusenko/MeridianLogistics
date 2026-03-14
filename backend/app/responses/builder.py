from __future__ import annotations

from copy import deepcopy
from functools import lru_cache

from jsonschema import Draft202012Validator

from backend.app.contracts import load_json_contract


@lru_cache(maxsize=1)
def _response_validator() -> Draft202012Validator:
    return Draft202012Validator(load_json_contract("agent_response"))


def build_response_envelope(payload: dict[str, object]) -> dict[str, object]:
    envelope = deepcopy(payload)
    envelope.setdefault("actions", [])
    envelope.setdefault("follow_up_prompt", None)
    envelope.setdefault("trace_id", None)
    if not envelope.get("components"):
        envelope["components"] = [
            {
                "component_id": "summary-message",
                "component_type": "message_block",
                "body": str(envelope.get("summary", "")),
                "tone": "informational",
            }
        ]
    errors = sorted(_response_validator().iter_errors(envelope), key=str)
    if errors:
        raise ValueError("schema validation failed")
    return envelope
