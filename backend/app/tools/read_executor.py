from __future__ import annotations

import re

from backend.app.db.read_repository import (
    ReadRepository,
    normalize_date_range_days,
    normalize_limit,
    normalize_metric,
    normalize_ranking_metric,
)


DAY_WINDOW_RE = re.compile(r"\b(last|next)\s+(\d+)\s+days?\b", re.IGNORECASE)
TOP_LIMIT_RE = re.compile(r"\btop\s+(\d+)\b", re.IGNORECASE)
LANE_RE = re.compile(r"\b([A-Za-z]+)\s+to\s+([A-Za-z]+)\b")


def classify_read_tool(prompt: str, *, active_resource: dict[str, object] | None = None) -> str:
    prompt_text = prompt.lower()
    if active_resource is not None:
        return "shipment_exception_lookup"
    if any(token in prompt_text for token in ("top", "carrier", "on-time", "ranking")):
        return "carrier_ranking_lookup"
    if any(token in prompt_text for token in ("insurance", "exception", "in-transit", "delay")):
        return "shipment_exception_lookup"
    return "shipment_metrics_lookup"


def _extract_day_window(prompt: str, *, direction: str, default_days: int) -> int:
    match = DAY_WINDOW_RE.search(prompt)
    if match and match.group(1).lower() == direction:
        return int(match.group(2))
    return default_days


def _extract_lane(prompt: str) -> tuple[str | None, str | None]:
    match = LANE_RE.search(prompt)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _extract_shipment_mode(prompt_text: str) -> str | None:
    if "ftl" in prompt_text:
        return "FTL"
    if "ltl" in prompt_text:
        return "LTL"
    return None


def _extract_weight_class(prompt_text: str) -> str | None:
    if "20,000" in prompt_text or "20000" in prompt_text or "20 000" in prompt_text:
        return "20000_plus"
    return None


def _extract_region(prompt_text: str) -> str | None:
    known_regions = ("southeast", "midwest", "northeast", "southwest", "northwest")
    for region in known_regions:
        if region in prompt_text:
            return region.title()
    return None


def _select_filter_value(
    tool_arguments: dict[str, object] | None,
    key: str,
    fallback: object,
    *,
    aliases: tuple[str, ...] = (),
) -> object:
    if tool_arguments is None:
        return fallback
    for candidate_key in (key, *aliases):
        if candidate_key in tool_arguments:
            return tool_arguments[candidate_key]
    return fallback


def _metrics_filters(prompt: str, *, tool_arguments: dict[str, object] | None = None) -> dict[str, object]:
    prompt_text = prompt.lower()
    origin_region, destination_region = _extract_lane(prompt)
    raw_metric = _select_filter_value(tool_arguments, "metric", "average_transit_time" if "transit" in prompt_text else "shipment_count")
    raw_date_range = _select_filter_value(
        tool_arguments,
        "date_range",
        _extract_day_window(prompt, direction="last", default_days=30),
        aliases=("date_range_days",),
    )
    return {
        "metric": normalize_metric(raw_metric),
        "date_range_days": normalize_date_range_days(raw_date_range),
        "shipment_mode": _select_filter_value(tool_arguments, "shipment_mode", _extract_shipment_mode(prompt_text)),
        "origin_region": _select_filter_value(tool_arguments, "origin_region", origin_region),
        "destination_region": _select_filter_value(tool_arguments, "destination_region", destination_region),
    }


def _ranking_filters(prompt: str, *, tool_arguments: dict[str, object] | None = None) -> dict[str, object]:
    prompt_text = prompt.lower()
    limit_match = TOP_LIMIT_RE.search(prompt)
    raw_ranking_metric = _select_filter_value(
        tool_arguments,
        "ranking_metric",
        "on_time_rate" if "on-time" in prompt_text else "shipment_count",
    )
    raw_date_range = _select_filter_value(
        tool_arguments,
        "date_range",
        _extract_day_window(prompt, direction="last", default_days=30),
        aliases=("date_range_days",),
    )
    raw_limit = _select_filter_value(
        tool_arguments,
        "limit",
        None if limit_match is None else int(limit_match.group(1)),
    )
    return {
        "ranking_metric": normalize_ranking_metric(raw_ranking_metric),
        "date_range_days": normalize_date_range_days(raw_date_range),
        "shipment_mode": _select_filter_value(tool_arguments, "shipment_mode", _extract_shipment_mode(prompt_text)),
        "weight_class": _select_filter_value(tool_arguments, "weight_class", _extract_weight_class(prompt_text)),
        "region": _select_filter_value(tool_arguments, "region", _extract_region(prompt_text)),
        "limit": None if raw_limit is None else normalize_limit(raw_limit),
    }


def _exception_filters(prompt: str) -> dict[str, object]:
    prompt_text = prompt.lower()
    return {
        "exception_type": "insurance_expiring" if "insurance" in prompt_text else "delay",
        "shipment_state": "in_transit" if "in-transit" in prompt_text else None,
        "insurance_expiry_window_days": (
            _extract_day_window(prompt, direction="next", default_days=30) if "insurance" in prompt_text else None
        ),
    }


def execute_allowlisted_read(
    *,
    prompt: str,
    permission_context: dict[str, str],
    active_resource: dict[str, object] | None = None,
    repository: ReadRepository | None = None,
    tool_name: str | None = None,
    tool_arguments: dict[str, object] | None = None,
) -> dict[str, object]:
    repo = repository or ReadRepository()
    office_id = permission_context["office_id"]
    selected_tool_name = tool_name or classify_read_tool(prompt, active_resource=active_resource)

    if selected_tool_name == "shipment_metrics_lookup":
        return _shipment_metrics_response(repo, office_id, prompt=prompt, tool_arguments=tool_arguments)
    if selected_tool_name == "carrier_ranking_lookup":
        return _carrier_ranking_response(repo, office_id, prompt=prompt, tool_arguments=tool_arguments)
    if selected_tool_name == "shipment_exception_lookup":
        return _shipment_exception_response(repo, office_id, prompt=prompt, active_resource=active_resource)
    raise ValueError(f"Unsupported read tool: {selected_tool_name}")


def _shipment_metrics_response(
    repo: ReadRepository,
    office_id: str,
    *,
    prompt: str,
    tool_arguments: dict[str, object] | None = None,
) -> dict[str, object]:
    filters = _metrics_filters(prompt, tool_arguments=tool_arguments)
    shipments = repo.shipments_for_metrics(
        office_id,
        date_range_days=int(filters["date_range_days"]),
        shipment_mode=filters["shipment_mode"],
        origin_region=filters["origin_region"],
        destination_region=filters["destination_region"],
    )
    if not shipments:
        return _empty_read_result("shipment_metrics_lookup", "No Memphis shipment metrics matched the current scope.")

    avg_transit_hours = sum(float(shipment["transit_hours"]) for shipment in shipments) / len(shipments)
    avg_transit_days = round(avg_transit_hours / 24, 2)
    metric = str(filters["metric"])
    if metric == "shipment_count":
        summary = f"{len(shipments)} Memphis shipment(s) matched the current scope."
        component_id = "metric-shipment-count"
        title = "Shipment count"
        metrics = [
            {"label": "Loads", "value": len(shipments), "unit": None},
            {"label": "Average transit time", "value": avg_transit_days, "unit": "days"},
        ]
    else:
        summary = f"Average transit time is {avg_transit_days} days across {len(shipments)} Memphis shipment(s)."
        component_id = "metric-transit-time"
        title = "Transit metrics"
        metrics = [
            {"label": "Average transit time", "value": avg_transit_days, "unit": "days"},
            {"label": "Loads", "value": len(shipments), "unit": None},
        ]

    return {
        "tool_name": "shipment_metrics_lookup",
        "summary": summary,
        "components": [
            {
                "component_id": component_id,
                "component_type": "metric_card",
                "title": title,
                "metrics": metrics,
            }
        ],
    }


def _carrier_ranking_response(
    repo: ReadRepository,
    office_id: str,
    *,
    prompt: str,
    tool_arguments: dict[str, object] | None = None,
) -> dict[str, object]:
    filters = _ranking_filters(prompt, tool_arguments=tool_arguments)
    ranking_rows = repo.carrier_rankings(
        office_id,
        ranking_metric=str(filters["ranking_metric"]),
        date_range_days=int(filters["date_range_days"]),
        shipment_mode=filters["shipment_mode"],
        weight_class=filters["weight_class"],
        region=filters["region"],
        limit=filters["limit"],
    )
    if not ranking_rows:
        return _empty_read_result("carrier_ranking_lookup", "No Memphis carrier rankings matched the current scope.")

    ranking_metric = str(filters["ranking_metric"])
    if ranking_metric == "shipment_count":
        summary = f"Top Memphis carrier is {ranking_rows[0]['carrier_name']} with {ranking_rows[0]['shipment_count']} load(s)."
    else:
        summary = f"Top Memphis carrier is {ranking_rows[0]['carrier_name']} at {ranking_rows[0]['on_time_rate']}% on-time."

    return {
        "tool_name": "carrier_ranking_lookup",
        "summary": summary,
        "components": [
            {
                "component_id": "table-carrier-rankings",
                "component_type": "table",
                "title": "Carrier rankings",
                "columns": [
                    {"key": "carrier_name", "label": "Carrier", "data_type": "string"},
                    {"key": "on_time_rate", "label": "On time %", "data_type": "number"},
                    {"key": "shipment_count", "label": "Loads", "data_type": "number"},
                ],
                "rows": [
                    [row["carrier_name"], row["on_time_rate"], row["shipment_count"]]
                    for row in ranking_rows
                ],
            }
        ],
    }


def _shipment_exception_response(
    repo: ReadRepository,
    office_id: str,
    *,
    prompt: str,
    active_resource: dict[str, object] | None,
) -> dict[str, object]:
    filters = _exception_filters(prompt)
    resource_id = None if active_resource is None else str(active_resource.get("resource_id"))
    shipments = repo.shipments_for_exception_view(
        office_id,
        exception_type=str(filters["exception_type"]),
        shipment_state=filters["shipment_state"],
        insurance_expiry_window_days=filters["insurance_expiry_window_days"],
        resource_id=resource_id,
    )
    if not shipments:
        return _empty_read_result("shipment_exception_lookup", "No Memphis shipment exceptions matched the current scope.")

    primary_shipment = shipments[0]
    events = repo.shipment_events(office_id, shipment_id=str(primary_shipment["shipment_id"]))
    return {
        "tool_name": "shipment_exception_lookup",
        "summary": f"Shipment exceptions found for {len(shipments)} Memphis shipment(s).",
        "components": [
            {
                "component_id": "table-shipment-exceptions",
                "component_type": "table",
                "title": "Shipment exceptions",
                "columns": [
                    {"key": "shipment_id", "label": "Shipment", "data_type": "string"},
                    {"key": "exception_type", "label": "Exception", "data_type": "string"},
                    {"key": "carrier_name", "label": "Carrier", "data_type": "string"},
                    {"key": "eta_at", "label": "ETA", "data_type": "string"},
                ],
                "rows": [
                    [
                        row["shipment_id"],
                        row["exception_type"],
                        row["carrier_name"],
                        row["eta_at"],
                    ]
                    for row in shipments
                ],
            },
            {
                "component_id": "timeline-shipment-events",
                "component_type": "timeline",
                "title": "Shipment timeline",
                "events": [
                    {
                        "label": event["event_type"],
                        "timestamp": event["event_at"],
                        "state": "active",
                    }
                    for event in events
                ],
            },
        ],
    }


def _empty_read_result(tool_name: str, summary: str) -> dict[str, object]:
    return {
        "tool_name": tool_name,
        "summary": summary,
        "components": [
            {
                "component_id": "msg-empty-read",
                "component_type": "message_block",
                "body": summary,
                "tone": "informational",
            }
        ],
    }
