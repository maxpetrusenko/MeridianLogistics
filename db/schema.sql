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

CREATE TABLE chat_sessions (
    session_id TEXT PRIMARY KEY,
    session_access_token TEXT,
    office_id TEXT NOT NULL REFERENCES offices (office_id),
    broker_id TEXT NOT NULL REFERENCES brokers (broker_id),
    role TEXT NOT NULL,
    current_module TEXT NOT NULL,
    conversation_scope TEXT NOT NULL,
    context_binding_state TEXT NOT NULL,
    screen_sync_state TEXT NOT NULL,
    active_resource_type TEXT,
    active_resource_id TEXT,
    active_resource_fingerprint TEXT,
    last_response_id TEXT,
    last_job_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE generation_jobs (
    job_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions (session_id),
    office_id TEXT NOT NULL REFERENCES offices (office_id),
    broker_id TEXT NOT NULL REFERENCES brokers (broker_id),
    job_kind TEXT NOT NULL,
    job_status TEXT NOT NULL,
    progress_message TEXT NOT NULL,
    retry_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    pending_response_id TEXT,
    completed_response_id TEXT,
    prepared_result_payload JSONB,
    result_payload JSONB,
    job_poll_token TEXT,
    completion_refreshes_remaining INTEGER,
    completion_ready_at DOUBLE PRECISION,
    artifact_key TEXT,
    artifact_mime_type TEXT,
    artifact_size_bytes BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE documents_manifest (
    document_id TEXT PRIMARY KEY,
    job_id TEXT REFERENCES generation_jobs (job_id),
    office_id TEXT NOT NULL REFERENCES offices (office_id),
    broker_id TEXT REFERENCES brokers (broker_id),
    document_kind TEXT NOT NULL,
    object_key TEXT NOT NULL,
    storage_provider TEXT NOT NULL DEFAULT 'backblaze_b2',
    mime_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    checksum_sha256 TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMIT;
