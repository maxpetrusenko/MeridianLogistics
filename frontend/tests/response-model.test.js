import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";

import {
  FIXTURE_RENDER_TIME,
  buildActionResult,
  fixtures,
  getActionInteractivity,
  makeResponse,
} from "../src/response-model.js";

test("confirm action submits when confirmation payload is still valid", () => {
  const validConfirmation = makeResponse({
    id: "confirm-valid",
    intentClass: "write_confirmation_required",
    status: "confirmation_required",
    summary: "Booking is ready for broker confirmation.",
    toolPath: ["booking_create_prepare"],
    writeConfirmationRequired: true,
    components: [
      {
        component_id: "confirm-booking",
        component_type: "confirmation_card",
        title: "Confirm booking",
        action_name: "booking_create_confirmed",
        confirmation_token: "valid-token",
        expires_at: "2026-03-15T23:59:00Z",
        fields: [
          { key: "quote_id", label: "Quote", value: "88219" },
          { key: "carrier", label: "Carrier", value: "Arrow Freight" },
          { key: "pickup", label: "Pickup", value: "Tuesday 09:00" },
        ],
      },
    ],
    actions: [
      {
        action_id: "confirm-booking",
        label: "Confirm booking",
        action_type: "confirm_booking",
        resource_type: "shipment",
        resource_id: "88219",
        surface: "chat",
        requires_confirmation: true,
        enabled: true,
        disabled_reason: null,
        server_endpoint: { method: "POST", path: "/shipments/88219/book" },
        permission_scope: { office_id: "memphis", role: "broker", broker_id: "broker-123" },
        confirmation_token: "valid-token",
        confirmation_expires_at: "2026-03-15T23:59:00Z",
        idempotency_key: "book-88219-arrow-freight-2026-03-15-v1",
        ui_behavior: {
          success_mode: "sync_chat_and_screen",
          failure_mode: "stay_in_confirmation",
          post_success_refresh: ["shipment_detail", "dispatch_board"],
        },
      },
      {
        action_id: "cancel-booking",
        label: "Cancel",
        action_type: "cancel_booking",
        resource_type: "shipment",
        resource_id: "88219",
        surface: "chat",
        requires_confirmation: false,
        enabled: true,
        disabled_reason: null,
      },
    ],
  });

  const result = buildActionResult({
    action: validConfirmation.actions[0],
    response: validConfirmation,
    referenceTime: FIXTURE_RENDER_TIME,
  });

  assert.equal(result.actionNotice, null);
  assert.equal(result.nextResponse.intent_class, "write_submitted");
  assert.equal(result.nextResponse.status, "submitted");
  assert.deepEqual(result.nextResponse.audit.tool_path, ["booking_create_confirmed"]);
});

test("expired confirmation notice derives from the active payload expiry", () => {
  const expiredConfirmation = makeResponse({
    id: "confirm-expired",
    intentClass: "write_confirmation_required",
    status: "confirmation_required",
    summary: "Booking is ready for broker confirmation.",
    toolPath: ["booking_create_prepare"],
    writeConfirmationRequired: true,
    components: [
      {
        component_id: "confirm-booking",
        component_type: "confirmation_card",
        title: "Confirm booking",
        action_name: "booking_create_confirmed",
        confirmation_token: "expired-token",
        expires_at: "2026-03-12T08:30:00Z",
        fields: [
          { key: "quote_id", label: "Quote", value: "88219" },
          { key: "carrier", label: "Carrier", value: "Arrow Freight" },
          { key: "pickup", label: "Pickup", value: "Tuesday 09:00" },
        ],
      },
    ],
    actions: [
      {
        action_id: "confirm-booking",
        label: "Confirm booking",
        action_type: "confirm_booking",
        resource_type: "shipment",
        resource_id: "88219",
        surface: "chat",
        requires_confirmation: true,
        enabled: true,
        disabled_reason: null,
        server_endpoint: { method: "POST", path: "/shipments/88219/book" },
        permission_scope: { office_id: "memphis", role: "broker", broker_id: "broker-123" },
        confirmation_token: "expired-token",
        confirmation_expires_at: "2026-03-12T08:30:00Z",
        idempotency_key: "book-88219-arrow-freight-2026-03-12-v1",
        ui_behavior: {
          success_mode: "sync_chat_and_screen",
          failure_mode: "stay_in_confirmation",
          post_success_refresh: ["shipment_detail", "dispatch_board"],
        },
      },
      {
        action_id: "cancel-booking",
        label: "Cancel",
        action_type: "cancel_booking",
        resource_type: "shipment",
        resource_id: "88219",
        surface: "chat",
        requires_confirmation: false,
        enabled: true,
        disabled_reason: null,
      },
    ],
  });

  const result = buildActionResult({
    action: expiredConfirmation.actions[0],
    response: expiredConfirmation,
    referenceTime: FIXTURE_RENDER_TIME,
  });

  assert.equal(result.nextResponse, expiredConfirmation);
  assert.match(result.actionNotice.body, /2026-03-12T08:30:00Z/);
  assert.doesNotMatch(result.actionNotice.body, /March 13, 2026/);
});

test("shipment exception fixture includes the contract primary table", () => {
  const componentTypes = fixtures.timeline.response.components.map((component) => component.component_type);

  assert.equal(fixtures.timeline.response.audit.tool_path[0], "shipment_exception_lookup");
  assert.equal(componentTypes[0], "table");
  assert.ok(componentTypes.includes("timeline"));
});

test("confirm action requires canonical write metadata", () => {
  const brokenAction = {
    ...fixtures.confirm.response.actions[0],
    idempotency_key: "",
  };

  const result = buildActionResult({
    action: brokenAction,
    response: fixtures.confirm.response,
    referenceTime: FIXTURE_RENDER_TIME,
  });

  assert.equal(result.nextResponse, fixtures.confirm.response);
  assert.match(result.actionNotice.body, /idempotency/i);
});

test("server-disabled actions stay disabled client-side with contract reason", () => {
  const actionState = getActionInteractivity({
    ...fixtures.confirm.response.actions[0],
    enabled: false,
    disabled_reason: "Carrier quote expired on the server.",
  });

  assert.equal(actionState.disabled, true);
  assert.equal(actionState.reason, "Carrier quote expired on the server.");
});

test("disabled confirm action fails closed even if invoked", () => {
  const disabledAction = {
    ...fixtures.confirm.response.actions[0],
    enabled: false,
    disabled_reason: "Carrier quote expired on the server.",
  };

  const result = buildActionResult({
    action: disabledAction,
    response: fixtures.confirm.response,
    referenceTime: FIXTURE_RENDER_TIME,
  });

  assert.equal(result.nextResponse, fixtures.confirm.response);
  assert.match(result.actionNotice.body, /carrier quote expired on the server/i);
});

test("all non-loading fixtures satisfy the accepted response contract", () => {
  const validator = `
import json
import sys
from jsonschema import Draft202012Validator

schema = json.load(open(sys.argv[1]))
payload = json.loads(sys.argv[2])
errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: list(error.path))
if errors:
    for error in errors:
        print(error.message)
    raise SystemExit(1)
`;

  for (const [name, fixture] of Object.entries(fixtures)) {
    if (!fixture?.response) {
      continue;
    }

    const result = spawnSync(
      "python",
      ["-c", validator, new URL("../../contracts/agent-response-schema.json", import.meta.url).pathname, JSON.stringify(fixture.response)],
      { encoding: "utf8" },
    );

    assert.equal(
      result.status,
      0,
      `fixture ${name} no longer matches contracts/agent-response-schema.json\n${result.stdout}${result.stderr}`,
    );
  }
});
