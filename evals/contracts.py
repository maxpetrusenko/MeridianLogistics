from __future__ import annotations

import json

import yaml

from backend.app.contracts import contract_path


EVAL_CONTRACT = contract_path("eval_test_schema")
RESPONSE_CONTRACT = contract_path("agent_response")


def load_eval_contract() -> dict:
    with EVAL_CONTRACT.open() as handle:
        return yaml.safe_load(handle)


def load_response_contract() -> dict:
    with RESPONSE_CONTRACT.open() as handle:
        return json.load(handle)
