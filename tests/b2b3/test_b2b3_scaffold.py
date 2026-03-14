from __future__ import annotations

import inspect
import json
import unittest
from pathlib import Path

from backend.app.gateway import write_gateway
from backend.app.orchestrator import graph
from backend.app.responses import builder
from backend.app.tools import registry as registry_module


ROOT_DIR = Path(__file__).resolve().parents[2]
RESPONSE_CONTRACT = ROOT_DIR / "contracts" / "agent-response-schema.json"


class B2B3ScaffoldTests(unittest.TestCase):
    def test_tool_registry_exposes_typed_tool_access(self) -> None:
        registry = registry_module.load_tool_registry()

        self.assertTrue(hasattr(registry_module, "ToolRegistry"))
        self.assertIsInstance(registry, registry_module.ToolRegistry)
        self.assertTrue(hasattr(registry, "get_tool"))

        shipment_metrics_tool = registry.get_tool("shipment_metrics_lookup")
        self.assertEqual(shipment_metrics_tool["mode"], "read")

    def test_orchestrator_graph_exposes_read_and_write_paths(self) -> None:
        try:
            orchestration_graph = graph.build_orchestrator_graph()
        except NotImplementedError as exc:
            self.fail(f"build_orchestrator_graph not implemented: {exc}")

        self.assertIsInstance(orchestration_graph, dict)
        self.assertIn("read_path", orchestration_graph)
        self.assertIn("write_path", orchestration_graph)
        self.assertEqual(orchestration_graph["read_path"]["tool_families"], ["read_tools"])
        self.assertNotIn("write_tools", orchestration_graph["read_path"]["tool_families"])
        self.assertNotIn(
            "pre_confirmation_tools",
            orchestration_graph["read_path"]["tool_families"],
        )

    def test_write_gateway_requires_permission_context_and_confirmation_boundary(self) -> None:
        parameters = inspect.signature(write_gateway.execute_write_gateway).parameters

        self.assertEqual(
            list(parameters),
            ["request", "permission_context"],
        )

        request = write_gateway.WriteGatewayRequest(
            action_name="booking_create_confirmed",
            confirmation_token="token-123",
            actor_broker_id="broker-123",
            office_id="memphis",
        )
        permission_context = {
            "claims": {
                "broker_id": "broker-123",
                "office_id": "memphis",
                "role": "broker",
            }
        }

        result = write_gateway.execute_write_gateway(request, permission_context)
        self.assertIn("audit", result)
        self.assertEqual(result["audit"]["tool_path"], ["booking_create_confirmed"])

        with self.assertRaisesRegex(ValueError, "unsupported action"):
            write_gateway.execute_write_gateway(
                write_gateway.WriteGatewayRequest(
                    action_name="booking_create_prepare",
                    confirmation_token="token-123",
                    actor_broker_id="broker-123",
                    office_id="memphis",
                ),
                permission_context,
            )

        with self.assertRaisesRegex(ValueError, "broker role"):
            write_gateway.execute_write_gateway(
                request,
                {
                    "claims": {
                        "broker_id": "broker-123",
                        "office_id": "memphis",
                        "role": "office_manager",
                    }
                },
            )

    def test_response_builder_emits_schema_valid_envelopes(self) -> None:
        contract = json.loads(RESPONSE_CONTRACT.read_text())

        self.assertTrue(hasattr(builder, "build_response_envelope"))
        parameters = inspect.signature(builder.build_response_envelope).parameters
        self.assertEqual(list(parameters), ["payload"])

        payload = builder.build_response_envelope(
            {
                "contract_version": contract["contract_version"],
                "response_id": "resp-red",
                "request_id": "req-red",
                "intent_class": "read_result",
                "status": "success",
                "summary": "stub",
                "components": [],
                "policy": {
                    "permission_context_applied": True,
                    "sensitive_fields_redacted": True,
                    "write_confirmation_required": False,
                    "denial_reason_class": "none",
                },
                "audit": {
                    "actor_role": "broker",
                    "office_scope": "memphis",
                    "tool_path": ["shipment_metrics_lookup"],
                    "response_generated_at": "2026-03-13T22:00:00Z",
                },
            }
        )

        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["intent_class"], "read_result")

        with self.assertRaisesRegex(ValueError, "schema validation failed"):
            builder.build_response_envelope(
                {
                    **payload,
                    "intent_class": "read_denied",
                    "status": "denied",
                    "actions": [
                        {
                            "action_id": "details-1",
                            "label": "Open details",
                            "action_type": "open_details",
                        }
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
