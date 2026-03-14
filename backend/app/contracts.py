from __future__ import annotations

from pathlib import Path
import json

import yaml

from backend.app.config import load_config


CONTRACT_FILES = {
    "tool_schema": "tool-schema.yaml",
    "permission_context": "permission-context.json",
    "agent_response": "agent-response-schema.json",
    "controller_checkpoint": "controller-checkpoint-schema.json",
    "eval_test_schema": "eval-test-schema.yaml",
}


def contract_path(name: str) -> Path:
    try:
        filename = CONTRACT_FILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown contract name: {name}") from exc
    return load_config().contracts_dir / filename


def load_json_contract(name: str) -> dict:
    with contract_path(name).open() as handle:
        return json.load(handle)


def load_yaml_contract(name: str) -> dict:
    with contract_path(name).open() as handle:
        return yaml.safe_load(handle)
