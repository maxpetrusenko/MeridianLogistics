import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";

import {
  FIXTURE_RENDER_TIME,
  buildActionResult,
  fixtures,
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
      { action_id: "confirm-booking", label: "Confirm booking", action_type: "confirm_booking" },
      { action_id: "cancel-booking", label: "Cancel", action_type: "cancel_booking" },
    ],
  });

  const result = buildActionResult({
    action: { action_type: "confirm_booking" },
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
      { action_id: "confirm-booking", label: "Confirm booking", action_type: "confirm_booking" },
      { action_id: "cancel-booking", label: "Cancel", action_type: "cancel_booking" },
    ],
  });

  const result = buildActionResult({
    action: { action_type: "confirm_booking" },
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
