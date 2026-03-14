from __future__ import annotations

import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT_DIR / "db" / "seeds" / "memphis_seed_bundle.json"


def build_seed_bundle() -> dict[str, object]:
    return {
        "office": {
            "office_id": "memphis",
            "office_name": "Memphis Brokerage",
            "deployment_scope": "memphis_only",
        },
        "brokers": [
            {
                "broker_id": "broker-mem-001",
                "office_id": "memphis",
                "display_name": "Maya Brooks",
                "role": "broker",
            }
        ],
        "carriers": [
            {
                "carrier_id": "carrier-4412",
                "carrier_name": "Acme Freight",
                "shipment_mode": "FTL",
                "on_time_rate": 97.2,
                "insurance_expiry_date": "2026-04-15",
            }
        ],
        "shipment_quotes": [
            {
                "quote_id": "quote-88219",
                "office_id": "memphis",
                "broker_id": "broker-mem-001",
                "carrier_id": "carrier-4412",
                "origin_region": "Dallas",
                "destination_region": "Chicago",
                "shipment_mode": "FTL",
                "weight_class": "20000_plus",
                "pickup_date": "2026-03-17",
                "quote_status": "eligible_for_booking",
            }
        ],
        "shipments": [
            {
                "shipment_id": "ship-100",
                "office_id": "memphis",
                "broker_id": "broker-mem-001",
                "carrier_id": "carrier-4412",
                "quote_id": "quote-88219",
                "origin_region": "Dallas",
                "destination_region": "Chicago",
                "shipment_mode": "FTL",
                "shipment_status": "in_transit",
                "exception_type": "insurance_expiring",
                "transit_hours": 36,
                "eta_at": "2026-03-18T17:00:00Z",
                "created_at": "2026-03-13T12:00:00Z",
            }
        ],
        "shipment_events": [
            {
                "shipment_id": "ship-100",
                "office_id": "memphis",
                "event_type": "departed_origin",
                "event_at": "2026-03-14T08:00:00Z",
                "event_summary": "Departed Dallas terminal",
            }
        ],
        "booking_confirmations": [
            {
                "confirmation_token": "confirm-quote-88219",
                "quote_id": "quote-88219",
                "office_id": "memphis",
                "broker_id": "broker-mem-001",
                "carrier_id": "carrier-4412",
                "pickup_date": "2026-03-17",
                "confirmation_status": "pending",
                "expires_at": "2026-03-16T12:00:00Z",
            }
        ],
    }


def write_seed_bundle(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "memphis_seed_bundle.json"
    output_path.write_text(json.dumps(build_seed_bundle(), indent=2))
    return output_path


def main() -> None:
    output_path = write_seed_bundle(DEFAULT_OUTPUT.parent)
    print(f"Seed bundle written to {output_path}")


if __name__ == "__main__":
    main()
