from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.app.db.context import load_database_context
from db.seeds import seed_data


ROOT_DIR = Path(__file__).resolve().parents[2]
SCHEMA_FILE = ROOT_DIR / "db" / "schema.sql"
VIEWS_FILE = ROOT_DIR / "db" / "views.sql"


class B1ScaffoldTests(unittest.TestCase):
    def test_database_context_exposes_seed_bundle_target(self) -> None:
        context = load_database_context()

        self.assertTrue(hasattr(context, "seed_bundle_file"))

    def test_schema_defines_memphis_poc_tables(self) -> None:
        schema = SCHEMA_FILE.read_text()

        required_tables = [
            "CREATE TABLE offices",
            "CREATE TABLE brokers",
            "CREATE TABLE carriers",
            "CREATE TABLE shipment_quotes",
            "CREATE TABLE shipments",
            "CREATE TABLE shipment_events",
            "CREATE TABLE booking_confirmations",
        ]

        for table in required_tables:
            self.assertIn(table, schema)

    def test_views_define_agent_safe_semantic_views(self) -> None:
        views = VIEWS_FILE.read_text()

        required_views = [
            "CREATE VIEW v_shipment_metrics",
            "CREATE VIEW v_carrier_rankings",
            "CREATE VIEW v_shipment_exceptions",
            "CREATE VIEW v_booking_confirmation_context",
        ]

        for view in required_views:
            self.assertIn(view, views)

        self.assertNotIn("carrier_rate", views)
        self.assertNotIn("shipper_rate", views)

    def test_seed_data_writes_a_memphis_bundle(self) -> None:
        self.assertTrue(hasattr(seed_data, "build_seed_bundle"))
        self.assertTrue(hasattr(seed_data, "write_seed_bundle"))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = seed_data.write_seed_bundle(Path(temp_dir))
            payload = json.loads(output_path.read_text())

        self.assertEqual(payload["office"]["office_id"], "memphis")
        self.assertGreaterEqual(len(payload["brokers"]), 1)
        self.assertGreaterEqual(len(payload["shipments"]), 1)


if __name__ == "__main__":
    unittest.main()
