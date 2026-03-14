-- Meridian Logistics Memphis PoC semantic views.
-- Protected rate fields are excluded by construction.

BEGIN;

CREATE VIEW v_shipment_metrics AS
SELECT
    s.office_id,
    s.shipment_mode,
    s.origin_region,
    s.destination_region,
    COUNT(*) AS shipment_count,
    ROUND(AVG(s.transit_hours)::NUMERIC, 2) AS avg_transit_hours
FROM shipments AS s
GROUP BY
    s.office_id,
    s.shipment_mode,
    s.origin_region,
    s.destination_region;

CREATE VIEW v_carrier_rankings AS
SELECT
    s.office_id,
    s.shipment_mode,
    s.origin_region,
    s.destination_region,
    c.carrier_id,
    c.carrier_name,
    c.on_time_rate,
    COUNT(*) AS shipment_count
FROM shipments AS s
JOIN carriers AS c ON c.carrier_id = s.carrier_id
GROUP BY
    s.office_id,
    s.shipment_mode,
    s.origin_region,
    s.destination_region,
    c.carrier_id,
    c.carrier_name,
    c.on_time_rate;

CREATE VIEW v_shipment_exceptions AS
SELECT
    s.office_id,
    s.shipment_id,
    s.broker_id,
    s.carrier_id,
    c.carrier_name,
    s.shipment_status,
    COALESCE(s.exception_type, 'none') AS exception_type,
    s.eta_at,
    c.insurance_expiry_date
FROM shipments AS s
JOIN carriers AS c ON c.carrier_id = s.carrier_id
WHERE s.exception_type IS NOT NULL
   OR c.insurance_expiry_date <= CURRENT_DATE + INTERVAL '30 days';

CREATE VIEW v_booking_confirmation_context AS
SELECT
    q.office_id,
    q.quote_id,
    q.broker_id,
    b.display_name AS broker_name,
    q.carrier_id,
    c.carrier_name,
    q.origin_region,
    q.destination_region,
    q.shipment_mode,
    q.weight_class,
    q.pickup_date,
    q.quote_status
FROM shipment_quotes AS q
JOIN brokers AS b ON b.broker_id = q.broker_id
JOIN carriers AS c ON c.carrier_id = q.carrier_id;

COMMIT;
