from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import lru_cache
import json
from pathlib import Path
import sqlite3

from backend.app.db.context import DatabaseContext, load_database_context


SQLITE_SCHEMA = """
CREATE TABLE offices (
    office_id TEXT PRIMARY KEY,
    office_name TEXT NOT NULL,
    deployment_scope TEXT NOT NULL
);

CREATE TABLE brokers (
    broker_id TEXT PRIMARY KEY,
    office_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL
);

CREATE TABLE carriers (
    carrier_id TEXT PRIMARY KEY,
    carrier_name TEXT NOT NULL,
    shipment_mode TEXT NOT NULL,
    on_time_rate REAL NOT NULL,
    insurance_expiry_date TEXT NOT NULL
);

CREATE TABLE shipment_quotes (
    quote_id TEXT PRIMARY KEY,
    office_id TEXT NOT NULL,
    broker_id TEXT NOT NULL,
    carrier_id TEXT NOT NULL,
    origin_region TEXT NOT NULL,
    destination_region TEXT NOT NULL,
    shipment_mode TEXT NOT NULL,
    weight_class TEXT NOT NULL,
    pickup_date TEXT NOT NULL,
    quote_status TEXT NOT NULL
);

CREATE TABLE shipments (
    shipment_id TEXT PRIMARY KEY,
    office_id TEXT NOT NULL,
    broker_id TEXT NOT NULL,
    carrier_id TEXT NOT NULL,
    quote_id TEXT,
    origin_region TEXT NOT NULL,
    destination_region TEXT NOT NULL,
    shipment_mode TEXT NOT NULL,
    shipment_status TEXT NOT NULL,
    exception_type TEXT,
    transit_hours INTEGER NOT NULL,
    eta_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE shipment_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id TEXT NOT NULL,
    office_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_at TEXT NOT NULL,
    event_summary TEXT NOT NULL
);

CREATE TABLE booking_confirmations (
    confirmation_token TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL,
    office_id TEXT NOT NULL,
    broker_id TEXT NOT NULL,
    carrier_id TEXT NOT NULL,
    pickup_date TEXT NOT NULL,
    confirmation_status TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""

MAX_READ_DATE_RANGE_DAYS = 90
MAX_READ_LIMIT = 5
ALLOWED_SHIPMENT_METRICS = frozenset({"average_transit_time", "shipment_count"})
ALLOWED_RANKING_METRICS = frozenset({"on_time_rate", "shipment_count"})


def _load_seed_bundle(seed_bundle_file: str) -> dict[str, object]:
    with open(seed_bundle_file) as handle:
        return json.load(handle)


def _connect_sqlite() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def _insert_rows(
    connection: sqlite3.Connection,
    table_name: str,
    rows: list[dict[str, object]],
) -> None:
    if not rows:
        return

    columns = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    connection.executemany(
        f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders})",
        [tuple(row.get(column) for column in columns) for row in rows],
    )


def build_seeded_read_connection(bundle: dict[str, object]) -> sqlite3.Connection:
    connection = _connect_sqlite()
    connection.executescript(SQLITE_SCHEMA)

    office = bundle.get("office")
    if office:
        _insert_rows(connection, "offices", [office])

    for table_name in (
        "brokers",
        "carriers",
        "shipment_quotes",
        "shipments",
        "shipment_events",
        "booking_confirmations",
    ):
        _insert_rows(connection, table_name, list(bundle.get(table_name, [])))

    return connection


@lru_cache(maxsize=1)
def _seed_connection(seed_bundle_file: str) -> sqlite3.Connection:
    return build_seeded_read_connection(_load_seed_bundle(seed_bundle_file))


def _parse_timestamp(raw_value: str | None) -> datetime:
    if not raw_value:
        return datetime.now(UTC)
    return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))


def _coerce_bounded_int(raw_value: object, *, field_name: str, maximum: int) -> int:
    if isinstance(raw_value, bool):
        raise ValueError(f"{field_name} must be a positive integer")

    candidate = raw_value
    if isinstance(raw_value, dict):
        candidate = raw_value.get("days") or raw_value.get("value")

    try:
        value = int(candidate)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a positive integer") from exc

    if value < 1:
        raise ValueError(f"{field_name} must be a positive integer")
    return min(value, maximum)


def normalize_date_range_days(raw_value: object) -> int:
    return _coerce_bounded_int(raw_value, field_name="date_range", maximum=MAX_READ_DATE_RANGE_DAYS)


def normalize_limit(raw_value: object) -> int:
    return _coerce_bounded_int(raw_value, field_name="limit", maximum=MAX_READ_LIMIT)


def normalize_metric(raw_value: object) -> str:
    if raw_value not in ALLOWED_SHIPMENT_METRICS:
        raise ValueError(f"metric must be one of {sorted(ALLOWED_SHIPMENT_METRICS)}")
    return str(raw_value)


def normalize_ranking_metric(raw_value: object) -> str:
    if raw_value not in ALLOWED_RANKING_METRICS:
        raise ValueError(f"ranking_metric must be one of {sorted(ALLOWED_RANKING_METRICS)}")
    return str(raw_value)


class ReadRepository:
    def __init__(
        self,
        context: DatabaseContext | None = None,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        self.context = context or load_database_context()
        self.connection = connection or _seed_connection(str(self.context.seed_bundle_file))

    def reference_timestamp(self, office_id: str) -> datetime:
        row = self.connection.execute(
            """
            SELECT MAX(created_at) AS latest_created_at
            FROM shipments
            WHERE office_id = ?
            """,
            (office_id,),
        ).fetchone()
        return _parse_timestamp(None if row is None else row["latest_created_at"])

    def brokers_for_office(
        self,
        office_id: str,
        *,
        role: str | None = None,
    ) -> list[dict[str, object]]:
        query = """
            SELECT broker_id, office_id, display_name, role
            FROM brokers
            WHERE office_id = ?
        """
        parameters: list[object] = [office_id]
        if role is not None:
            query += " AND lower(role) = lower(?)"
            parameters.append(role)
        query += " ORDER BY broker_id ASC"
        return [dict(row) for row in self.connection.execute(query, parameters).fetchall()]

    def shipment_events(self, office_id: str, shipment_id: str | None = None) -> list[dict[str, object]]:
        query = """
            SELECT shipment_id, office_id, event_type, event_at, event_summary
            FROM shipment_events
            WHERE office_id = ?
        """
        parameters: list[object] = [office_id]
        if shipment_id is not None:
            query += " AND shipment_id = ?"
            parameters.append(shipment_id)
        query += " ORDER BY datetime(event_at) ASC"
        return [dict(row) for row in self.connection.execute(query, parameters).fetchall()]

    def shipments_for_metrics(
        self,
        office_id: str,
        *,
        date_range_days: int,
        shipment_mode: str | None = None,
        origin_region: str | None = None,
        destination_region: str | None = None,
    ) -> list[dict[str, object]]:
        bounded_date_range_days = normalize_date_range_days(date_range_days)
        reference_timestamp = self.reference_timestamp(office_id)
        cutoff = (reference_timestamp - timedelta(days=bounded_date_range_days)).isoformat().replace("+00:00", "Z")
        query = """
            SELECT shipment_id, transit_hours, shipment_mode, origin_region, destination_region, created_at
            FROM shipments
            WHERE office_id = ?
              AND datetime(created_at) >= datetime(?)
        """
        parameters: list[object] = [office_id, cutoff]

        if shipment_mode is not None:
            query += " AND lower(shipment_mode) = lower(?)"
            parameters.append(shipment_mode)
        if origin_region is not None:
            query += " AND lower(origin_region) = lower(?)"
            parameters.append(origin_region)
        if destination_region is not None:
            query += " AND lower(destination_region) = lower(?)"
            parameters.append(destination_region)

        query += " ORDER BY datetime(created_at) DESC"
        return [dict(row) for row in self.connection.execute(query, parameters).fetchall()]

    def carrier_rankings(
        self,
        office_id: str,
        *,
        ranking_metric: str,
        date_range_days: int,
        shipment_mode: str | None = None,
        weight_class: str | None = None,
        region: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        normalized_ranking_metric = normalize_ranking_metric(ranking_metric)
        bounded_date_range_days = normalize_date_range_days(date_range_days)
        bounded_limit = None if limit is None else normalize_limit(limit)
        reference_timestamp = self.reference_timestamp(office_id)
        cutoff = (reference_timestamp - timedelta(days=bounded_date_range_days)).isoformat().replace("+00:00", "Z")
        query = """
            SELECT
                carriers.carrier_name AS carrier_name,
                carriers.on_time_rate AS on_time_rate,
                COUNT(*) AS shipment_count
            FROM shipments
            JOIN carriers ON carriers.carrier_id = shipments.carrier_id
            LEFT JOIN shipment_quotes ON shipment_quotes.quote_id = shipments.quote_id
            WHERE shipments.office_id = ?
              AND datetime(shipments.created_at) >= datetime(?)
        """
        parameters: list[object] = [office_id, cutoff]

        if shipment_mode is not None:
            query += " AND lower(shipments.shipment_mode) = lower(?)"
            parameters.append(shipment_mode)
        if weight_class is not None:
            query += " AND lower(shipment_quotes.weight_class) = lower(?)"
            parameters.append(weight_class)
        if region is not None:
            query += """
              AND (
                    lower(shipment_quotes.origin_region) = lower(?)
                 OR lower(shipment_quotes.destination_region) = lower(?)
              )
            """
            parameters.extend([region, region])

        query += """
            GROUP BY carriers.carrier_id, carriers.carrier_name, carriers.on_time_rate
        """
        if normalized_ranking_metric == "shipment_count":
            query += " ORDER BY shipment_count DESC, carriers.on_time_rate DESC, carriers.carrier_name ASC"
        else:
            query += " ORDER BY carriers.on_time_rate DESC, shipment_count DESC, carriers.carrier_name ASC"
        if bounded_limit is not None:
            query += " LIMIT ?"
            parameters.append(bounded_limit)

        return [dict(row) for row in self.connection.execute(query, parameters).fetchall()]

    def shipments_for_exception_view(
        self,
        office_id: str,
        *,
        exception_type: str,
        shipment_state: str | None = None,
        insurance_expiry_window_days: int | None = None,
        limit: int | None = None,
        resource_id: str | None = None,
    ) -> list[dict[str, object]]:
        reference_timestamp = self.reference_timestamp(office_id)
        reference_date = reference_timestamp.date().isoformat()
        query = """
            SELECT
                shipments.shipment_id,
                shipments.quote_id,
                shipments.exception_type,
                shipments.shipment_status,
                shipments.eta_at,
                shipments.created_at,
                carriers.carrier_name,
                carriers.insurance_expiry_date
            FROM shipments
            JOIN carriers ON carriers.carrier_id = shipments.carrier_id
            WHERE shipments.office_id = ?
        """
        parameters: list[object] = [office_id]

        if shipment_state is not None:
            query += " AND lower(shipments.shipment_status) = lower(?)"
            parameters.append(shipment_state)

        if exception_type == "insurance_expiring":
            if insurance_expiry_window_days is None:
                query += " AND shipments.exception_type = ?"
                parameters.append(exception_type)
            else:
                window_end = (reference_timestamp.date() + timedelta(days=insurance_expiry_window_days)).isoformat()
                query += """
                  AND date(carriers.insurance_expiry_date) BETWEEN date(?) AND date(?)
                """
                parameters.extend([reference_date, window_end])
        else:
            query += " AND shipments.exception_type = ?"
            parameters.append(exception_type)

        if resource_id is not None:
            normalized_resource_id = resource_id.replace("quote-", "").replace("ship-", "")
            query += """
              AND (
                    shipments.shipment_id = ?
                 OR shipments.quote_id = ?
                 OR replace(shipments.shipment_id, 'ship-', '') = ?
                 OR replace(coalesce(shipments.quote_id, ''), 'quote-', '') = ?
              )
            """
            parameters.extend([resource_id, resource_id, normalized_resource_id, normalized_resource_id])

        query += " ORDER BY datetime(shipments.created_at) DESC"
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(normalize_limit(limit))

        return [dict(row) for row in self.connection.execute(query, parameters).fetchall()]


SeedBackedReadRepository = ReadRepository
