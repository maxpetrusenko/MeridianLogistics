-- Meridian Logistics Memphis PoC relational schema.
-- Memphis-only, broker-first, contract-supporting tables.

BEGIN;

CREATE TABLE offices (
    office_id TEXT PRIMARY KEY,
    office_name TEXT NOT NULL,
    deployment_scope TEXT NOT NULL DEFAULT 'memphis_only'
);

CREATE TABLE brokers (
    broker_id TEXT PRIMARY KEY,
    office_id TEXT NOT NULL REFERENCES offices (office_id),
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role = 'broker')
);

CREATE TABLE carriers (
    carrier_id TEXT PRIMARY KEY,
    carrier_name TEXT NOT NULL,
    shipment_mode TEXT NOT NULL,
    on_time_rate NUMERIC(5,2) NOT NULL,
    insurance_expiry_date DATE NOT NULL
);

CREATE TABLE shipment_quotes (
    quote_id TEXT PRIMARY KEY,
    office_id TEXT NOT NULL REFERENCES offices (office_id),
    broker_id TEXT NOT NULL REFERENCES brokers (broker_id),
    carrier_id TEXT NOT NULL REFERENCES carriers (carrier_id),
    origin_region TEXT NOT NULL,
    destination_region TEXT NOT NULL,
    shipment_mode TEXT NOT NULL,
    weight_class TEXT NOT NULL,
    pickup_date DATE NOT NULL,
    quote_status TEXT NOT NULL
);

CREATE TABLE shipments (
    shipment_id TEXT PRIMARY KEY,
    office_id TEXT NOT NULL REFERENCES offices (office_id),
    broker_id TEXT NOT NULL REFERENCES brokers (broker_id),
    carrier_id TEXT NOT NULL REFERENCES carriers (carrier_id),
    quote_id TEXT REFERENCES shipment_quotes (quote_id),
    origin_region TEXT NOT NULL,
    destination_region TEXT NOT NULL,
    shipment_mode TEXT NOT NULL,
    shipment_status TEXT NOT NULL,
    exception_type TEXT,
    transit_hours INTEGER NOT NULL,
    eta_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE shipment_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipments (shipment_id),
    office_id TEXT NOT NULL REFERENCES offices (office_id),
    event_type TEXT NOT NULL,
    event_at TIMESTAMPTZ NOT NULL,
    event_summary TEXT NOT NULL
);

CREATE TABLE booking_confirmations (
    confirmation_token TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL REFERENCES shipment_quotes (quote_id),
    office_id TEXT NOT NULL REFERENCES offices (office_id),
    broker_id TEXT NOT NULL REFERENCES brokers (broker_id),
    carrier_id TEXT NOT NULL REFERENCES carriers (carrier_id),
    pickup_date DATE NOT NULL,
    confirmation_status TEXT NOT NULL DEFAULT 'pending',
    expires_at TIMESTAMPTZ NOT NULL
);

COMMIT;
