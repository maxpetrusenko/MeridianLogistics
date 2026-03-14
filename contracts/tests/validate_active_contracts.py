#!/usr/bin/env python3

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = ROOT / "contracts"


def load_validator(path: Path) -> Draft202012Validator:
    with path.open() as handle:
        schema = json.load(handle)
    return Draft202012Validator(schema)


def load_yaml(path: Path) -> dict:
    with path.open() as handle:
        return yaml.safe_load(handle)


def error_messages(validator: Draft202012Validator, instance: dict) -> list[str]:
    return [error.message for error in validator.iter_errors(instance)]


def assert_valid(name: str, validator: Draft202012Validator, instance: dict) -> None:
    errors = error_messages(validator, instance)
    if errors:
        raise AssertionError(f"{name}: expected valid, got {errors}")


def assert_invalid(name: str, validator: Draft202012Validator, instance: dict) -> None:
    errors = error_messages(validator, instance)
    if not errors:
        raise AssertionError(f"{name}: expected invalid, but instance validated")


permission_validator = load_validator(CONTRACTS_DIR / "permission-context.json")
response_validator = load_validator(CONTRACTS_DIR / "agent-response-schema.json")
tool_contract = load_yaml(CONTRACTS_DIR / "tool-schema.yaml")
eval_contract = load_yaml(CONTRACTS_DIR / "eval-test-schema.yaml")


valid_permission_context = {
    "claims": {
        "broker_id": "broker-123",
        "office_id": "memphis",
        "role": "broker",
        "token_id": "jwt-1",
        "issued_at": "2026-03-13T12:00:00Z",
        "expires_at": "2026-03-13T13:00:00Z",
    },
    "role_shape": {
        "role": "broker",
        "runtime_access": "day_one_enabled",
        "office_scope_mode": "single_office",
        "record_scope_mode": "assigned_or_office",
        "cross_office_access": False,
    },
    "subject_scope": {
        "deployment_scope": "memphis_only",
        "allowed_office_ids": ["memphis"],
        "resource_owner_broker_id": "broker-123",
        "sensitive_field_policy": "never_expose",
    },
    "safety_context": {
        "read_path_policy": "allowlisted_tools_only",
        "write_path_policy": "allowlisted_single_step_booking_only",
        "read_confirmation_required": False,
        "pre_confirmation_required": False,
        "write_execution_confirmation_required": True,
        "audit_required": True,
        "deny_on_missing_context": True,
        "deny_on_scope_mismatch": True,
        "deny_on_sensitive_field_request": True,
    },
}

assert_valid("permission valid broker", permission_validator, valid_permission_context)

assert_invalid(
    "permission mismatched role",
    permission_validator,
    {
        **valid_permission_context,
        "role_shape": {
            **valid_permission_context["role_shape"],
            "role": "vp",
        },
    },
)

assert_invalid(
    "permission cross office runtime",
    permission_validator,
    {
        **valid_permission_context,
        "role_shape": {
            **valid_permission_context["role_shape"],
            "cross_office_access": True,
        },
    },
)

assert_invalid(
    "permission runtime mismatch",
    permission_validator,
    {
        **valid_permission_context,
        "claims": {
            **valid_permission_context["claims"],
            "role": "office_manager",
        },
        "role_shape": {
            "role": "office_manager",
            "runtime_access": "day_one_enabled",
            "office_scope_mode": "single_office",
            "record_scope_mode": "office_only",
            "cross_office_access": False,
        },
    },
)

assert_invalid(
    "permission non broker runtime denied",
    permission_validator,
    {
        **valid_permission_context,
        "claims": {
            **valid_permission_context["claims"],
            "role": "vp",
        },
        "role_shape": {
            "role": "vp",
            "runtime_access": "boundary_review_only",
            "office_scope_mode": "role_bound_review_only",
            "record_scope_mode": "role_bound_review_only",
            "cross_office_access": False,
        },
    },
)

assert_invalid(
    "permission missing fail closed flag",
    permission_validator,
    {
        **valid_permission_context,
        "safety_context": {
            key: value
            for key, value in valid_permission_context["safety_context"].items()
            if key != "deny_on_sensitive_field_request"
        },
    },
)


valid_read_response = {
    "contract_version": "0.1.0",
    "response_id": "resp-1",
    "request_id": "req-1",
    "trace_id": "trace-1",
    "intent_class": "read_result",
    "status": "success",
    "summary": "Found matching shipments.",
    "follow_up_prompt": None,
    "components": [
        {
            "component_id": "tbl-1",
            "component_type": "table",
            "title": "Shipments",
            "columns": [
                {"key": "shipment_id", "label": "Shipment", "data_type": "string"},
                {"key": "status", "label": "Status", "data_type": "status"},
            ],
            "rows": [["S-100", "in_transit"]],
        }
    ],
    "actions": [
        {
            "action_id": "details-1",
            "label": "Open details",
            "action_type": "open_details",
        }
    ],
    "policy": {
        "permission_context_applied": True,
        "sensitive_fields_redacted": True,
        "write_confirmation_required": False,
        "denial_reason_class": "none",
    },
    "audit": {
        "actor_role": "broker",
        "office_scope": "memphis",
        "tool_path": ["shipments.search"],
        "response_generated_at": "2026-03-13T12:01:00Z",
    },
}

assert_valid("response valid read", response_validator, valid_read_response)

valid_confirmation_response = {
    **valid_read_response,
    "response_id": "resp-2",
    "intent_class": "write_confirmation_required",
    "status": "confirmation_required",
    "summary": "Confirm the booking details.",
    "components": [
        {
            "component_id": "confirm-1",
            "component_type": "confirmation_card",
            "title": "Confirm booking",
            "action_name": "booking_create_confirmed",
            "confirmation_token": "token-123",
            "expires_at": "2026-03-13T12:05:00Z",
            "fields": [
                {"key": "load_id", "label": "Load", "value": "L-1"},
                {"key": "carrier", "label": "Carrier", "value": "Acme"},
                {"key": "pickup_date", "label": "Pickup", "value": "2026-03-14"},
            ],
        }
    ],
    "actions": [
        {
            "action_id": "confirm-1",
            "label": "Confirm booking",
            "action_type": "confirm_booking",
        },
        {
            "action_id": "cancel-1",
            "label": "Cancel",
            "action_type": "cancel_booking",
        },
    ],
    "policy": {
        "permission_context_applied": True,
        "sensitive_fields_redacted": True,
        "write_confirmation_required": True,
        "denial_reason_class": "none",
    },
}

assert_valid("response valid confirmation", response_validator, valid_confirmation_response)

assert_invalid(
    "response confirmation missing card",
    response_validator,
    {
        **valid_confirmation_response,
        "components": [
            {
                "component_id": "msg-1",
                "component_type": "message_block",
                "body": "Please confirm.",
            }
        ],
    },
)

assert_invalid(
    "response read exposes confirm action",
    response_validator,
    {
        **valid_read_response,
        "actions": [
            {
                "action_id": "confirm-1",
                "label": "Confirm booking",
                "action_type": "confirm_booking",
            }
        ],
    },
)

assert_invalid(
    "response read cannot require confirmation",
    response_validator,
    {
        **valid_read_response,
        "status": "confirmation_required",
    },
)

assert_invalid(
    "response denied cannot expose open details",
    response_validator,
    {
        **valid_read_response,
        "intent_class": "read_denied",
        "status": "denied",
        "summary": "Denied by policy.",
        "components": [
            {
                "component_id": "msg-2",
                "component_type": "message_block",
                "body": "Cross-office comparison is out of scope.",
                "tone": "warning",
            }
        ],
        "actions": [
            {
                "action_id": "details-1",
                "label": "Open details",
                "action_type": "open_details",
            }
        ],
        "policy": {
            "permission_context_applied": True,
            "sensitive_fields_redacted": True,
            "write_confirmation_required": False,
            "denial_reason_class": "permission",
        },
    },
)

assert_invalid(
    "response table row object keys",
    response_validator,
    {
        **valid_read_response,
        "components": [
            {
                "component_id": "tbl-2",
                "component_type": "table",
                "title": "Shipments",
                "columns": [
                    {"key": "shipment_id", "label": "Shipment", "data_type": "string"},
                    {"key": "status", "label": "Status", "data_type": "status"},
                ],
                "rows": [
                    {
                        "shipment_id": "S-200",
                        "status": "booked",
                        "sensitive_rate": "$1000",
                    }
                ],
            }
        ],
    },
)

valid_denied_before_tool_response = {
    **valid_read_response,
    "response_id": "resp-3",
    "intent_class": "read_denied",
    "status": "denied",
    "summary": "Cross-office comparison is out of scope.",
    "components": [
        {
            "component_id": "msg-3",
            "component_type": "message_block",
            "body": "Cross-office comparison is out of scope.",
            "tone": "warning",
        }
    ],
    "actions": [],
    "policy": {
        "permission_context_applied": True,
        "sensitive_fields_redacted": True,
        "write_confirmation_required": False,
        "denial_reason_class": "permission",
    },
    "audit": {
        **valid_read_response["audit"],
        "tool_path": [],
    },
}

assert_valid(
    "response deny before tool execution allows empty audit path",
    response_validator,
    valid_denied_before_tool_response,
)

assert_invalid(
    "response success requires executed tool path",
    response_validator,
    {
        **valid_read_response,
        "audit": {
            **valid_read_response["audit"],
            "tool_path": [],
        },
    },
)

read_tools = tool_contract["tool_families"]["read_tools"]["tools"]
pre_confirmation_tools = tool_contract["tool_families"].get("pre_confirmation_tools", {}).get("tools", [])
write_tools = tool_contract["tool_families"]["write_tools"]["tools"]
scenarios = {
    scenario["scenario_id"]: scenario for scenario in eval_contract["scenario_catalog"]
}

if tool_contract["execution_model"]["read_tools"]["confirmation_required"] is not False:
    raise AssertionError("tool contract: read tools must never require confirmation")

if tool_contract["execution_model"]["pre_confirmation_tools"]["confirmation_required"] is not False:
    raise AssertionError("tool contract: pre-confirmation tools must never require confirmation")

if tool_contract["execution_model"]["write_tools"]["confirmation_required"] is not True:
    raise AssertionError("tool contract: write execution must require confirmation")

if any(tool["confirmation_required"] for tool in read_tools):
    raise AssertionError("tool contract: every read tool must keep confirmation_required false")

if any(tool["confirmation_required"] for tool in pre_confirmation_tools):
    raise AssertionError("tool contract: every pre-confirmation tool must keep confirmation_required false")

if any(not tool["confirmation_required"] for tool in write_tools):
    raise AssertionError("tool contract: every write execution tool must keep confirmation_required true")

if {tool["name"] for tool in pre_confirmation_tools} != {"booking_create_prepare"}:
    raise AssertionError("tool contract: pre-confirmation booking tool split missing")

if {
    tool["name"] for tool in write_tools
} != {"booking_create_confirmed"}:
    raise AssertionError("tool contract: write tool set drifted from confirmed execution only")

write_tool = write_tools[0]
if write_tool["result_shape"]["primary"] != "message_block":
    raise AssertionError("tool contract: confirmed booking execution must return execution result, not confirmation UI")

if set(scenario["actor_role"] for scenario in eval_contract["scenario_catalog"]) != {"broker"}:
    raise AssertionError("eval contract: broker must be the only actor role in Memphis PoC scenarios")

if "boundary_review_vp" in scenarios:
    raise AssertionError("eval contract: cross-office boundary review scenario must stay out of Memphis PoC")

if scenarios["deny_cross_office_broker"]["expected_gate"] != "deny":
    raise AssertionError("eval contract: cross-office comparison must deny")

if scenarios["deny_cross_office_broker"]["expected_tool_path"] != []:
    raise AssertionError("eval contract: deny-before-tool-execution must keep an empty tool path")

if scenarios["booking_confirmation_happy_path"]["expected_tool_path"] != ["booking_create_prepare"]:
    raise AssertionError("eval contract: confirmation scenario must bind to pre-confirmation tool")

if scenarios["booking_submit_after_confirmation"]["expected_tool_path"] != ["booking_create_confirmed"]:
    raise AssertionError("eval contract: execution scenario must bind to confirmed write tool")

print("active contract validation tests passed")
