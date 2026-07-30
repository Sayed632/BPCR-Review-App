"""
core/timeseries_checker.py
Real BPCRs often require a repeating log during a hold step - e.g.
"record temperature every 30+-5 minutes." This validates each row's
value against spec range, and flags gaps between consecutive readings
that exceed the allowed interval (a missed/late reading).
"""

from datetime import datetime

TIMESTAMP_FORMATS = [
    "%d-%m-%Y %H:%M",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d %H:%M",
    "%H:%M",
]


def _parse_dt(date_str, time_str):
    combined = f"{date_str or ''} {time_str or ''}".strip()
    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(combined, fmt)
        except ValueError:
            continue
    # fall back to time-only
    for fmt in ["%H:%M"]:
        try:
            return datetime.strptime(time_str.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def _parse_value(raw):
    if raw is None:
        return None
    cleaned = str(raw).strip()
    if cleaned.upper() in ("BLANK", "ILLEGIBLE", ""):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def check_timeseries(rows: list, spec: dict, operation_id: str = None) -> dict:
    """
    rows: extracted log rows [{"date":, "time":, "recorded_by":, "value":}, ...]
    spec: the operation's "time_series_log" spec entry
    Returns: {"out_of_range": [...], "missed_intervals": [...], "unparseable_rows": [...]}
    """
    interval = spec.get("interval_minutes", 30)
    tolerance = spec.get("interval_tolerance_minutes", 5)
    spec_min = spec.get("spec_min")
    spec_max = spec.get("spec_max")

    parsed_rows = []
    unparseable_rows = []
    out_of_range = []

    for row in rows:
        dt = _parse_dt(row.get("date"), row.get("time"))
        value = _parse_value(row.get("value"))

        if dt is None or value is None:
            unparseable_rows.append(
                {**row, "operation_id": operation_id, "table": spec.get("table_name")}
            )
            continue

        parsed_rows.append({**row, "parsed_time": dt, "parsed_value": value})

        if spec_min is not None and spec_max is not None:
            if not (spec_min <= value <= spec_max):
                out_of_range.append(
                    {
                        "operation_id": operation_id,
                        "table": spec.get("table_name"),
                        "time": row.get("time"),
                        "value": value,
                        "spec_range": f"{spec_min}-{spec_max}",
                        "recorded_by": row.get("recorded_by"),
                    }
                )

    parsed_rows.sort(key=lambda r: r["parsed_time"])

    missed_intervals = []
    for prev, curr in zip(parsed_rows, parsed_rows[1:]):
        gap_minutes = (curr["parsed_time"] - prev["parsed_time"]).total_seconds() / 60
        if gap_minutes > interval + tolerance:
            missed_intervals.append(
                {
                    "operation_id": operation_id,
                    "table": spec.get("table_name"),
                    "between": f"{prev['time']} -> {curr['time']}",
                    "gap_minutes": round(gap_minutes, 1),
                    "allowed_max_minutes": interval + tolerance,
                }
            )

    return {
        "out_of_range": out_of_range,
        "missed_intervals": missed_intervals,
        "unparseable_rows": unparseable_rows,
    }
